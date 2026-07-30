from pydantic import BaseModel, Field


class AtlosWebhookIn(BaseModel):
    order_id: str = Field(alias="OrderId")
    status: int = Field(alias="Status")

    model_config = {"populate_by_name": True}
