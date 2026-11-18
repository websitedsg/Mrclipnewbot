"""Run once on your PC:  python -m bot.login
A Chrome window opens -> log in to mrclip.gr with Google -> come back here and press Enter.
The login is saved in data/browser-profile so the bot stays logged in."""
import asyncio

from playwright.async_api import async_playwright

from . import config
from .site import launch


async def main() -> None:
    async with async_playwright() as pw:
        ctx = await launch(pw, headless=False)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(config.SITE_URL)
        print("\n>>> Log in to mrclip.gr with Google in the browser window.")
        print(">>> When you can see your Submissions page, come back here and press Enter.\n")
        await asyncio.get_running_loop().run_in_executor(None, input)
        await ctx.close()
        print("Saved. Now start the bot:  python -m bot.main")


if __name__ == "__main__":
    asyncio.run(main())
