from pydantic import BaseModel, HttpUrl


class RegisterRequest(BaseModel):
    ticketswap_url: HttpUrl


class RegisterResponse(BaseModel):
    ics_url: str
    webcal_url: str
    user_id: str
