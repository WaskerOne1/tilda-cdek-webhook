from pydantic import BaseModel


class Order(BaseModel):

    order_number: str

    customer_name: str

    customer_phone: str

    customer_email: str | None = None

    city: str

    address: str

    comment: str | None = None