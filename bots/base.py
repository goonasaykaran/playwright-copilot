from abc import ABC, abstractmethod
from rebrowser_playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import Stealth
from pathlib import Path
import asyncio


class BaseBot(ABC):
    """
    Abstract base class for all AI browser bots.
    Extend this to add support for any new AI platform (Gemini, Claude Web, etc.)
    """

    def __init__(self, headless: bool = True, user_data_dir: str = "./browser_profile",
                 channel: str = "chrome"):
        self.headless = headless
        self.user_data_dir = user_data_dir  # Persistent profile so login is remembered
        self.channel = channel
        self._playwright = None
        self._browser: Browser = None
        self._context: BrowserContext = None
        self._page: Page = None

    async def start(self):
        """Launch the browser and open a new page."""
        self._playwright = await async_playwright().start()
        # Use a persistent context so cookies/login session are saved
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            channel=self.channel,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=False,
            viewport={"width": 1280, "height": 900},
        )
        # launch_persistent_context already opens one page — reuse it instead of
        # calling new_page() which can trigger TargetClosedError on some systems.
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()
        await Stealth().apply_stealth_async(self._page)

    async def stop(self):
        """Close browser and playwright."""
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

    @abstractmethod
    async def navigate_to_chat(self):
        """Open the AI platform's chat page."""
        pass

    @abstractmethod
    async def upload_files(self, file_paths: list[str]) -> bool:
        """Upload one or more files into the chat interface."""
        pass

    @abstractmethod
    async def send_prompt(self, prompt: str) -> str:
        """Type and submit the prompt, then return the AI's full response."""
        pass

    async def run(self, prompt: str, file_paths: list[str] = None) -> str:
        """
        High-level entry point:
        1. Navigate to chat
        2. Upload files (if any)
        3. Send prompt
        4. Return response
        """
        await self.navigate_to_chat()
        if file_paths:
            await self.upload_files(file_paths)
        response = await self.send_prompt(prompt)
        return response
