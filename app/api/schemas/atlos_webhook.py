from pydantic import BaseModel

class AtlosWebhookIn(BaseModel):
    id: str
    status: str
