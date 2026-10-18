"""Web front end for the setup chatbot. Run: uvicorn app:app --app-dir assistant

Sign-in is handled in front of the app by Container Apps authentication (Entra ID), which only
lets members of the admin group through. The app itself keeps no state.
"""

from __future__ import annotations

import base64
import hmac
import html
import json
import logging
import secrets
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

import agent
import github_setup
from pipeline import Pipeline, PipelineError

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
    # The GitHub setup page posts its form to github.com; everything else stays on this site.
    form_action = "'self' https://github.com" if request.url.path == "/setup/github" else "'self'"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        f"connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action {form_action}"
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
    except agent.NotConnected as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:  # surface a readable error; details go to the log only
        log.exception("chat turn failed")
        name = type(exc).__name__
        raise HTTPException(502, f"The model call failed ({name}). Check the app's logs, then try again.") from exc


# --- One-click GitHub App for the deploy pipeline (github_setup.py) ---------------------------

def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _setup_error(exc: Exception) -> HTMLResponse:
    log.warning("GitHub setup: %s", type(exc).__name__)
    return HTMLResponse(github_setup.page("GitHub setup didn't finish", f"<p>{exc}</p>"), status_code=400)


@app.get("/setup/github")
def setup_github(request: Request, replace: bool = False):
    pipeline = Pipeline()
    if not pipeline.configured:
        raise HTTPException(404, "This chat isn't connected to the deploy pipeline (./nerdio assistant --pipeline).")
    try:
        existing = pipeline.app_key()
        if existing and existing.get("slug") and not replace:
            slug = html.escape(existing["slug"], quote=True)
            return HTMLResponse(github_setup.page("GitHub is connected", (
                f"<p>This chat uses the GitHub App <b>{slug}</b>. If you haven't installed it on the repository yet, "
                f'<a href="https://github.com/apps/{slug}/installations/new">install it</a>.</p>'
                '<p><a href="/">Back to the chat</a>. To replace the app, open <a href="/setup/github?replace=true">'
                "this page with replace</a>, then delete the old app in GitHub.</p>")))
        state = secrets.token_urlsafe(24)
        response = HTMLResponse(github_setup.form_page(pipeline, _base_url(request), state))
    except PipelineError as exc:
        return _setup_error(exc)
    response.set_cookie(github_setup.STATE_COOKIE, state, max_age=3600, httponly=True, secure=True,
                        samesite="lax", path="/setup/github")
    return response


@app.get("/setup/github/callback")
def setup_github_callback(request: Request, code: str = "", state: str = ""):
    expected = request.cookies.get(github_setup.STATE_COOKIE, "")
    if not expected or not hmac.compare_digest(expected, state):
        return _setup_error(PipelineError("This link didn't come from this browser's setup page. Start again from /setup/github."))
    try:
        result = github_setup.convert_and_import(Pipeline(), code)
    except PipelineError as exc:
        return _setup_error(exc)
    response = RedirectResponse(result["install_url"], status_code=303)
    response.delete_cookie(github_setup.STATE_COOKIE, path="/setup/github")
    return response


@app.get("/setup/github/installed")
def setup_github_installed():
    return HTMLResponse(github_setup.page("GitHub is connected", (
        "<p>The chat can now start the deploy workflow. Applies still wait for your approval in GitHub.</p>"
        '<p><a href="/">Back to the chat</a></p>')))
