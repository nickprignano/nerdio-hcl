"""Web front end for the setup chatbot. Run: uvicorn app:app --app-dir assistant

Sign-in is handled in front of the app by Container Apps authentication (Entra ID), which only
lets members of the admin group through. The app itself keeps no state.
"""

from __future__ import annotations

import base64
import json
import logging
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

import agent
from pipeline import Pipeline

STATIC = Path(__file__).resolve().parent / "static"
MAX_BODY = 4 * 1024 * 1024
log = logging.getLogger("nerdio-assistant")

app = FastAPI(title="Nerdio setup assistant", docs_url=None, redoc_url=None, openapi_url=None)


class Turn(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    messages: list = Field(default_factory=list, max_length=600)
    answers: dict = Field(default_factory=dict)


@lru_cache(maxsize=1)
def client():
    return agent.make_client()


@app.middleware("http")
async def headers(request: Request, call_next):
    if int(request.headers.get("content-length") or 0) > MAX_BODY:
        return JSONResponse({"detail": "conversation too large; start a new one"}, status_code=413)
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


OBJECT_ID_CLAIMS = ("http://schemas.microsoft.com/identity/claims/objectidentifier", "oid")


def _claim(request: Request, types: tuple[str, ...]) -> str:
    raw = request.headers.get("x-ms-client-principal")
    if not raw:
        return ""
    try:
        claims = json.loads(base64.b64decode(raw)).get("claims", [])
    except (ValueError, TypeError):
        return ""
    return next((c.get("val", "") for c in claims if c.get("typ") in types), "")


def signed_in_name(request: Request) -> str:
    """The display name Container Apps authentication passes in. Empty when running locally."""
    if not request.headers.get("x-ms-client-principal"):
        return request.headers.get("x-ms-client-principal-name", "")
    return _claim(request, ("name",))


def signed_in_object_id(request: Request) -> str:
    """The signed-in user's Entra object ID, set by Container Apps authentication (the browser can't forge it)."""
    return _claim(request, OBJECT_ID_CLAIMS)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/static/{name}")
def static(name: str):
    path = (STATIC / name).resolve()
    if path.parent != STATIC or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


@app.get("/api/me")
def me(request: Request):
    return {"name": signed_in_name(request)}


@app.post("/api/chat")
def chat(turn: Turn, request: Request):
    try:
        return agent.chat_turn(client(), turn.messages, turn.answers, turn.text,
                               signed_in_object_id(request), Pipeline())
    except Exception as exc:  # surface a readable error; details go to the log only
        log.exception("chat turn failed")
        name = type(exc).__name__
        raise HTTPException(502, f"The model call failed ({name}). Check the app's logs, then try again.") from exc
