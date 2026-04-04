"""
AI Browser Automation API
=========================
A FastAPI service that drives real AI chat UIs (ChatGPT, Copilot, …) via
Playwright, accepts file uploads and a prompt, and returns the AI's response.

Endpoints
---------
POST /chat          — main endpoint (multipart form)
GET  /bots          — list available bots and their supported models
GET  /health        — liveness check

Quick start
-----------
    python run.py
"""

import os
import sys
import json
import shutil
import tempfile
import asyncio
import traceback
from contextlib import asynccontextmanager
from typing import Annotated
from pathlib import Path

# ── Windows fix ──────────────────────────────────────────────────────────────
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from bots import BOT_REGISTRY


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR    = Path(__file__).parent.resolve()
PROFILE_DIR = BASE_DIR / "browser_profile"
UPLOADS_DIR = BASE_DIR / "uploads"
CONFIG_PATH = BASE_DIR / "config.json"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"config.json not found at {CONFIG_PATH}")
    with open(CONFIG_PATH) as f:
        return json.load(f)

CONFIG = load_config()
PLATFORM: str = CONFIG.get("platform", "windows")   # "windows" | "linux"
USERS: dict   = CONFIG.get("users", {})


# ---------------------------------------------------------------------------
# Per-user semaphore — prevents the same user from running two browsers at once
# ---------------------------------------------------------------------------
_user_semaphores: dict[str, asyncio.Semaphore] = {}

def _get_semaphore(username: str) -> asyncio.Semaphore:
    if username not in _user_semaphores:
        _user_semaphores[username] = asyncio.Semaphore(1)
    return _user_semaphores[username]


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[startup] platform         → {PLATFORM}")
    print(f"[startup] browser profiles → {PROFILE_DIR}")
    print(f"[startup] uploads          → {UPLOADS_DIR}")
    print(f"[startup] users configured → {list(USERS.keys())}")
    yield


app = FastAPI(
    title="AI Browser Automation API",
    description="Control ChatGPT, Copilot, and more via Playwright — upload files and get AI responses.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
BOT_MODELS = {
    "chatgpt": ["gpt-4o", "gpt-4o-mini", "gpt-4", "o1", "o3-mini"],
    "copilot":  ["balanced", "creative", "precise"],
}


def _authenticate(username: str, password: str):
    """Raise 401 if credentials are not in config."""
    if USERS.get(username) != password:
        raise HTTPException(status_code=401, detail="Invalid username or password.")


async def run_bot(
    bot_name: str,
    model: str,
    prompt: str,
    file_paths: list[str],
    username: str,
) -> str:
    bot_class = BOT_REGISTRY.get(bot_name)
    if not bot_class:
        raise ValueError(f"Unknown bot '{bot_name}'. Available: {list(BOT_REGISTRY.keys())}")

    # Each user gets their own browser profile — enables true concurrency
    profile_path = str(PROFILE_DIR / bot_name / username)
    print(f"[bot] user={username} profile → {profile_path}")

    # ChatGPT sits behind Cloudflare which blocks headless Chrome.
    # On Linux we rely on Xvfb (started by run.py) to provide a virtual display.
    # On Windows Chrome opens a real window.
    headless = False if bot_name == "chatgpt" else (PLATFORM == "linux")

    bot = bot_class(
        model=model,
        headless=headless,
        user_data_dir=profile_path,
    )

    async with _get_semaphore(username):
        await bot.start()
        try:
            response = await bot.run(
                prompt=prompt,
                file_paths=file_paths if file_paths else None,
            )
        finally:
            await bot.stop()

    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Meta"])
async def health():
    return {"status": "ok", "platform": PLATFORM}


@app.get("/bots", tags=["Meta"])
async def list_bots():
    """Return all available bots and their supported models/modes."""
    return {
        "bots": [
            {"name": name, "models": models}
            for name, models in BOT_MODELS.items()
        ]
    }


@app.post("/chat", tags=["Chat"])
async def chat(
    prompt:   Annotated[str, Form(description="The prompt / question to send to the AI.")],
    username: Annotated[str, Form(description="Your username from config.json.")],
    password: Annotated[str, Form(description="Your password from config.json.")],
    bot:      Annotated[str, Form(description="Which AI to use: 'chatgpt' or 'copilot'.")] = "chatgpt",
    model:    Annotated[str, Form(description="Model or mode (e.g. 'gpt-4o', 'balanced').")] = "gpt-4o",
    files:    Annotated[list[UploadFile], File(description="Optional files to upload into the chat.")] = None,
):
    """
    Send a prompt (and optional files) to the selected AI and return its response.

    - **username / password**: credentials from config.json
    - **bot**: `chatgpt` | `copilot`
    - **model**: see `/bots` for valid values per bot
    - **files**: any files the AI platform supports (images, PDFs, .txt, etc.)
    """
    _authenticate(username, password)

    if bot not in BOT_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown bot '{bot}'. Available: {list(BOT_REGISTRY.keys())}"
        )

    tmp_dir = tempfile.mkdtemp(dir=str(UPLOADS_DIR))
    saved_paths = []
    try:
        if files:
            for upload in files:
                if upload.filename:
                    dest = os.path.join(tmp_dir, upload.filename)
                    with open(dest, "wb") as f:
                        shutil.copyfileobj(upload.file, f)
                    saved_paths.append(dest)

        try:
            response_text = await run_bot(
                bot_name=bot,
                model=model,
                prompt=prompt,
                file_paths=saved_paths,
                username=username,
            )
        except Exception as e:
            err_detail = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            print(f"[error]\n{err_detail}")
            status = 503 if isinstance(e, RuntimeError) and not isinstance(e, NotImplementedError) else 500
            raise HTTPException(status_code=status, detail=err_detail)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return JSONResponse({
        "bot": bot,
        "model": model,
        "prompt": prompt,
        "files_uploaded": [os.path.basename(p) for p in saved_paths],
        "response": response_text,
    })
