from pydantic import BaseModel


class RegisterRequest(BaseModel):
    ticketswap_url: str


class RegisterResponse(BaseModel):
    ics_url: str
    webcal_url: str
    user_id: str
