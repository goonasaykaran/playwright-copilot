# AI Browser Automation API

A FastAPI service that automates **ChatGPT**, **Microsoft Copilot**, and more via **Playwright**.  
Upload files, send a prompt, get back the AI's response — all through a clean REST API.

---

## Project Structure

```
ai_browser_api/
├── main.py                  # FastAPI app & endpoints
├── requirements.txt
├── bots/
│   ├── __init__.py          # BOT_REGISTRY (add new bots here)
│   ├── base.py              # Abstract BaseBot class
│   ├── chatgpt.py           # ChatGPT implementation
│   └── copilot.py           # Microsoft Copilot implementation
└── browser_profile/         # Auto-created; stores login sessions
    ├── chatgpt/
    └── copilot/
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. First-time login (important!)

The browser saves your login session so you only do this once per AI platform.

**ChatGPT:**
```bash
python -c "
import asyncio
from bots import ChatGPTBot
async def login():
    bot = ChatGPTBot(headless=False)
    await bot.start()
    await bot.navigate_to_chat()
    input('Log in to ChatGPT in the browser, then press Enter here...')
    await bot.stop()
asyncio.run(login())
"
```

**Copilot:**
```bash
python -c "
import asyncio
from bots import CopilotBot
async def login():
    bot = CopilotBot(headless=False)
    await bot.start()
    await bot.navigate_to_chat()
    input('Log in to Copilot in the browser, then press Enter here...')
    await bot.stop()
asyncio.run(login())
"
```

### 3. Start the API

```bash
uvicorn main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

---

## API Usage

### `GET /bots` — list available bots

```bash
curl http://localhost:8000/bots
```

### `POST /chat` — send a prompt

**ChatGPT, no files:**
```bash
curl -X POST http://localhost:8000/chat \
  -F "bot=chatgpt" \
  -F "model=gpt-4o" \
  -F "prompt=Summarise quantum entanglement in 3 bullet points."
```

**ChatGPT, with file upload:**
```bash
curl -X POST http://localhost:8000/chat \
  -F "bot=chatgpt" \
  -F "model=gpt-4o" \
  -F "prompt=Summarise this document." \
  -F "files=@/path/to/document.pdf"
```

**Switch to Copilot:**
```bash
curl -X POST http://localhost:8000/chat \
  -F "bot=copilot" \
  -F "model=balanced" \
  -F "prompt=Write a haiku about the ocean."
```

### Response format

```json
{
  "bot": "chatgpt",
  "model": "gpt-4o",
  "prompt": "Summarise this document.",
  "files_uploaded": ["document.pdf"],
  "response": "Here is a summary of the document..."
}
```

---

## Supported Bots & Models

| Bot       | `model` values                                    |
|-----------|---------------------------------------------------|
| `chatgpt` | `gpt-4o` (default), `gpt-4o-mini`, `gpt-4`, `o1`, `o3-mini` |
| `copilot` | `balanced` (default), `creative`, `precise`       |

---

## Adding a New Bot (e.g. Gemini)

1. Create `bots/gemini.py` extending `BaseBot`
2. Implement `navigate_to_chat`, `upload_files`, `send_prompt`
3. Register it in `bots/__init__.py`:
   ```python
   from .gemini import GeminiBot
   BOT_REGISTRY["gemini"] = GeminiBot
   ```
That's it — the API picks it up automatically.

---

## Notes & Tips

- **Headless mode**: set `headless=false` in the form body when debugging to watch the browser.
- **Session persistence**: login sessions are stored in `./browser_profile/<bot>/`. Delete this folder to force a fresh login.
- **Selectors may drift**: AI UIs change their HTML frequently. If a bot stops working, inspect the page and update the selectors in the relevant `bots/*.py` file.
- **Rate limits**: these are real browser sessions — don't hammer the endpoints. Add delays between requests if needed.
