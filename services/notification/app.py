from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(title="NexusEnroll Notification Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

messages = []


class Event(BaseModel):
    name: str
    payload: dict


@app.get("/health")
def health():
    return {"status": "ok", "service": "notification"}


@app.post("/events", status_code=202)
def receive_event(event: Event):
    messages.append(
        {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "event": event.name,
            "payload": event.payload,
        }
    )
    return {"accepted": True}


@app.get("/notifications")
def list_notifications():
    return messages
