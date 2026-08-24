from pydantic import BaseModel
from typing import Optional


class TariffRequest(BaseModel):
    tariff_code: int

    from_code: int

    to_code: Optional[int] = None

    from_address: Optional[str] = None

    delivery_point: Optional[str] = None

    weight: float

    length: float

    width: float

    height: float