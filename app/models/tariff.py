from pydantic import BaseModel


class TariffRequest(BaseModel):
    tariff_code: int

    from_code: int

    to_code: int

    weight: int

    length: int

    width: int

    height: int