import asyncio
from .base import BaseBot


class CopilotBot(BaseBot):
    """
    Playwright automation for Microsoft Copilot (copilot.microsoft.com).

    Supported modes (pass as model arg):
      - "balanced"   (default)
      - "creative"
      - "precise"

    First run: headless=False so you can log in with your Microsoft account.
    Session is saved in browser_profile/copilot/ for future headless runs.
    """

    CHAT_URL = "https://copilot.microsoft.com/"

    TONE_MAP = {
        "balanced":  "Balanced",
        "creative":  "Creative",
        "precise":   "Precise",
    }
    DEFAULT_MODEL = "balanced"

    def __init__(self, model: str = "balanced", headless: bool = True,
                 user_data_dir: str = "./browser_profile/copilot"):
        # Use Edge for Copilot — Microsoft's Cloudflare is less aggressive towards Edge
        super().__init__(headless=headless, user_data_dir=user_data_dir, channel="msedge")
        self.model = model if model in self.TONE_MAP else self.DEFAULT_MODEL

    async def navigate_to_chat(self):
        await self._page.goto(self.CHAT_URL, wait_until="domcontentloaded")
        # Wait for the chat input (long timeout to allow CAPTCHA / login challenges)
        try:
            await self._page.wait_for_selector(
                "textarea[placeholder], div[contenteditable='true']",
                timeout=120000
            )
        except Exception:
            raise RuntimeError(
                "Copilot chat input not found. "
                "Run once with headless=False to sign in, then re-run headless."
            )
        await self._select_tone()

    async def _select_tone(self):
        """Click the correct conversation style button if visible."""
        tone_label = self.TONE_MAP[self.model]
        try:
            btn = self._page.get_by_role("button", name=tone_label)
            if await btn.is_visible():
                await btn.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass  # tone selector may not be present in all Copilot layouts

    async def upload_files(self, file_paths: list[str]) -> bool:
        """
        Copilot supports image/document uploads via a file input.
        We look for the attach / image upload button.
        """
        # Try various selectors Copilot has used over time
        selectors = [
            "button[aria-label*='ttach']",
            "button[aria-label*='pload']",
            "label[aria-label*='ttach']",
        ]
        attach_el = None
        for sel in selectors:
            el = self._page.locator(sel).first
            if await el.is_visible():
                attach_el = el
                break

        if attach_el:
            await attach_el.click()
            await asyncio.sleep(0.5)

        file_input = self._page.locator("input[type='file']").first
        await file_input.set_input_files(file_paths)
        await asyncio.sleep(2)
        return True

    async def send_prompt(self, prompt: str) -> str:
        # Copilot uses either a textarea or a contenteditable div
        input_el = self._page.locator(
            "textarea#searchbox, textarea[placeholder], div[contenteditable='true']"
        ).first
        await input_el.click()
        await input_el.fill(prompt)

        # Submit with Enter or the send button
        try:
            send_btn = self._page.locator(
                "button[aria-label*='end'], button[type='submit']"
            ).first
            await send_btn.click()
        except Exception:
            await input_el.press("Enter")

        return await self._wait_for_response()

    async def _wait_for_response(self) -> str:
        """
        Wait until Copilot finishes generating.
        We detect the 'Stop responding' button appearing then disappearing.
        """
        # Wait for generation to start
        try:
            await self._page.wait_for_selector(
                "button[aria-label*='Stop'], button[aria-label*='stop']",
                timeout=20000
            )
            # Wait for it to finish
            await self._page.wait_for_selector(
                "button[aria-label*='Stop'], button[aria-label*='stop']",
                state="hidden",
                timeout=300000
            )
        except Exception:
            # Fallback: just wait a bit if stop button wasn't detected
            await asyncio.sleep(8)

        await asyncio.sleep(0.5)

        # Grab the last bot response
        candidates = [
            "div[data-testid='messageBlock']",
            "div.ac-textBlock",
            "cib-message-group[source='bot'] cib-message",
        ]
        for sel in candidates:
            els = await self._page.locator(sel).all()
            if els:
                return (await els[-1].inner_text()).strip()

        return ""
