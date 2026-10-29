import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional


class IdempotencyStore:
    """Persistent request deduplication for Tilda order IDs."""

    def __init__(self, database_path: str):
        if database_path == ":memory:":
            raise ValueError("Idempotency requires a persistent SQLite database path")
        self.database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tilda_orders (
                    order_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    cdek_uuid TEXT,
                    result_json TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def reserve(self, order_id: str) -> tuple[str, Optional[dict[str, Any]]]:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state, result_json FROM tilda_orders WHERE order_id = ?",
                (order_id,),
            ).fetchone()
            if row is not None:
                connection.commit()
                result = json.loads(row["result_json"]) if row["result_json"] else None
                return row["state"], result

            connection.execute(
                "INSERT INTO tilda_orders (order_id, state) VALUES (?, 'processing')",
                (order_id,),
            )
            connection.commit()
            return "claimed", None

    def complete(self, order_id: str, result: dict[str, Any]) -> None:
        entity = result.get("entity") if isinstance(result, dict) else None
        cdek_uuid = entity.get("uuid") if isinstance(entity, dict) else None
        result_json = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE tilda_orders
                SET state = 'succeeded', cdek_uuid = ?, result_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ? AND state = 'processing'
                """,
                (cdek_uuid, result_json, order_id),
            )

    def mark_uncertain(self, order_id: str) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE tilda_orders
                SET state = 'uncertain', updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ? AND state = 'processing'
                """,
                (order_id,),
            )

    def release(self, order_id: str) -> None:
        """Release reservations only when no order-creation attempt was made."""

        with self._connection() as connection:
            connection.execute(
                "DELETE FROM tilda_orders WHERE order_id = ? AND state = 'processing'",
                (order_id,),
            )
