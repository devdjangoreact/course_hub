from pydantic import BaseModel, Field


class LavaWebhookIn(BaseModel):
    event_type: str = Field(alias="eventType")
    contract_id: str = Field(alias="contractId")

    model_config = {"populate_by_name": True}
