import asyncio
from pathlib import Path
from .base import BaseBot


class ChatGPTBot(BaseBot):
    """
    Playwright automation for ChatGPT (chat.openai.com).

    Supported models (pass as constructor arg):
      - "gpt-4o"         (default)
      - "gpt-4o-mini"
      - "gpt-4"
      - "o1"
      - "o3-mini"

    First run: headless=False so you can log in manually.
    After login your session is saved in browser_profile/ — future runs can be headless.
    """

    MODEL_URLS = {
        "gpt-4o":      "https://chatgpt.com/?model=gpt-4o",
        "gpt-4o-mini": "https://chatgpt.com/?model=gpt-4o-mini",
        "gpt-4":       "https://chatgpt.com/?model=gpt-4",
        "o1":          "https://chatgpt.com/?model=o1",
        "o3-mini":     "https://chatgpt.com/?model=o3-mini",
    }
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, model: str = "gpt-4o", headless: bool = False,
                 user_data_dir: str = None):
        if user_data_dir is None:
            user_data_dir = str(Path(__file__).parent.parent / "browser_profile" / "chatgpt")
        super().__init__(headless=headless, user_data_dir=user_data_dir)

        self.model = model if model in self.MODEL_URLS else self.DEFAULT_MODEL

    async def navigate_to_chat(self):
        url = self.MODEL_URLS[self.model]
        await self._page.goto(url, wait_until="domcontentloaded")
        # Wait for the prompt textarea to appear (confirms we're logged in & loaded)
        try:
            await self._page.wait_for_selector("#prompt-textarea", timeout=20000)
        except Exception:
            screenshot_path = str(Path(__file__).parent.parent / "debug_headless.png")
            await self._page.screenshot(path=screenshot_path, full_page=True)
            page_title = await self._page.title()
            page_url = self._page.url
            raise RuntimeError(
                f"ChatGPT prompt box not found (title='{page_title}', url={page_url}). "
                f"Screenshot saved to {screenshot_path}"
            )

    async def upload_files(self, file_paths: list[str]) -> bool:
        """
        ChatGPT uses a hidden <input type='file'> triggered by the paperclip button.
        We set the files directly on the input element.
        """
        # Try known attach button selectors (ChatGPT UI changes frequently)
        attach_selectors = [
            "button[aria-label='Attach files']",
            "button[aria-label='Add attachments']",
            "button[aria-label='Upload files']",
            "button[aria-label='Attach']",
        ]
        attach_btn = None
        for sel in attach_selectors:
            btn = self._page.locator(sel)
            try:
                await btn.wait_for(timeout=3000)
                attach_btn = btn
                break
            except Exception:
                continue

        if attach_btn is None:
            # Fall back: set files directly on the hidden general-purpose file input
            file_input = self._page.locator("#upload-files")
            await file_input.set_input_files(file_paths)
        else:
            await attach_btn.click()
            await asyncio.sleep(0.5)
            file_input = self._page.locator("#upload-files")
            await file_input.set_input_files(file_paths)
        # Wait for upload indicators to appear (thumbnail or filename chip)
        await asyncio.sleep(2)
        return True

    async def send_prompt(self, prompt: str) -> str:
        textarea = self._page.locator("#prompt-textarea")
        await textarea.click()
        await textarea.fill(prompt)

        # Submit
        send_btn = self._page.locator("button[data-testid='send-button']")
        await send_btn.click()

        # Wait for the response to finish streaming
        return await self._wait_for_response()

    async def _wait_for_response(self) -> str:
        """
        Poll until ChatGPT stops generating.
        The stop-button disappears and a copy/regenerate button appears when done.
        """
        # Wait for generation to start (stop button appears)
        await self._page.wait_for_selector(
            "button[data-testid='stop-button']", timeout=30000
        )
        # Wait for generation to finish (stop button disappears)
        await self._page.wait_for_selector(
            "button[data-testid='stop-button']",
            state="hidden",
            timeout=300000  # allow up to 5 min for long responses
        )
        await asyncio.sleep(0.5)  # small settle delay

        # Grab the last assistant message
        messages = await self._page.locator(
            "div[data-message-author-role='assistant']"
        ).all()
        if not messages:
            return ""
        last = messages[-1]
        return (await last.inner_text()).strip()