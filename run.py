"""
Cross-platform server starter.

    python run.py

Platform is read from config.json:
  "platform": "windows"  →  ProactorEventLoop, Chrome opens a real window
  "platform": "linux"    →  Xvfb virtual display started first, then Chrome
                             runs non-headless against it (bypasses Cloudflare)
"""
import sys
import json
import asyncio
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"
config      = json.loads(CONFIG_PATH.read_text())
PLATFORM    = config.get("platform", "windows")

# ── Windows: ProactorEventLoop so Playwright can spawn subprocesses ───────────
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ── Linux: start Xvfb virtual display so Chrome can run non-headless ─────────
if PLATFORM == "linux":
    import os
    import subprocess
    import time

    display = ":99"
    subprocess.Popen(
        ["Xvfb", display, "-screen", "0", "1280x900x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)                    # give Xvfb time to initialise
    os.environ["DISPLAY"] = display
    print(f"[startup] Xvfb started on display {display}")

import uvicorn

if __name__ == "__main__":
    config = uvicorn.Config("main:app", host="0.0.0.0", port=8000, loop="asyncio")
    server = uvicorn.Server(config)
    asyncio.run(server.serve())
