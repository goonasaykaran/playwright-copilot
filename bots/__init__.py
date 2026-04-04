from .chatgpt import ChatGPTBot
from .copilot import CopilotBot

# Registry — add new bots here to make them auto-discoverable by the API
BOT_REGISTRY = {
    "chatgpt": ChatGPTBot,
    "copilot": CopilotBot,
}

__all__ = ["ChatGPTBot", "CopilotBot", "BOT_REGISTRY"]
