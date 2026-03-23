"""
TicketSwap Calendar → ICS Feed converter
"""

from fastapi import FastAPI

from routes import router

app = FastAPI(title="TicketSwap → ICS", version="0.1.0")
app.include_router(router)
