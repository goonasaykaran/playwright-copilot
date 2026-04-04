# save as debug.py and run: python debug.py
import asyncio
import traceback
from bots import ChatGPTBot


async def debug():
    bot = ChatGPTBot(headless=False, model="gpt-4o")  # headless=False so you can see what's happening

    print("Step 1: Starting browser...")
    await bot.start()
    print("✓ Browser started")

    try:
        print("Step 2: Navigating to ChatGPT...")
        await bot.navigate_to_chat()
        print("✓ Navigation successful")

        print("Step 3: Sending prompt...")
        response = await bot.send_prompt("Say hello in one sentence.")
        print(f"✓ Response received:\n{response}")

    except Exception as e:
        print(f"\n✗ FAILED at step above")
        print(f"Error: {e}")
        traceback.print_exc()
        input("Browser is still open — look at what's on screen, then press Enter to close...")

    finally:
        await bot.stop()


asyncio.run(debug())