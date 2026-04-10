import asyncio
from bots import CopilotBot

# Use your real Edge profile so Microsoft recognises the session (no Cloudflare block).
# IMPORTANT: close ALL Edge windows before running this script.
EDGE_PROFILE = r"C:\Users\65811\AppData\Local\Microsoft\Edge\User Data"

async def test():
    bot = CopilotBot(headless=False, model='balanced', user_data_dir=EDGE_PROFILE)
    await bot.start()
    await bot.navigate_to_chat()
    response = await bot.send_prompt('Say hello in one sentence.')
    print('Response:', response)
    await bot.stop()

asyncio.run(test())
