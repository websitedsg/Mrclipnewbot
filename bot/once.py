"""One full run (refresh + scan + Telegram message), then exit.
Used by the GitHub Actions schedule, so no PC has to stay on.

Login comes from data/session.json (kept between runs, encrypted) or from the
MRCLIP_SESSION secret when you paste a new one."""
import asyncio
import hashlib
import os
import sys

from playwright.async_api import async_playwright
from telegram import Bot

from . import config, main, session
from .site import MrClip

SESSION_FILE = os.path.join(config.DATA_DIR, "session.json")
SEED_FILE = os.path.join(config.DATA_DIR, "seed.sha")


def _pick_session() -> str | None:
    seed = os.getenv("MRCLIP_SESSION", "").strip()
    seed_hash = hashlib.sha256(seed.encode()).hexdigest() if seed else ""
    old_hash = open(SEED_FILE).read().strip() if os.path.exists(SEED_FILE) else ""
    if seed and seed_hash != old_hash:  # you pasted a new login -> use it
        with open(SEED_FILE, "w") as f:
            f.write(seed_hash)
        return seed
    if os.path.exists(SESSION_FILE):
        return open(SESSION_FILE, encoding="utf-8").read()
    return seed or None


class _App:  # main.run_cycle only needs .bot
    def __init__(self, bot: Bot) -> None:
        self.bot = bot


async def run(refresh: bool) -> None:
    async with Bot(config.TOKEN) as bot, async_playwright() as pw:
        app = _App(bot)
        raw = _pick_session()
        if not raw:
            await bot.send_message(config.ADMIN_ID, "🔒 No mrclip login saved. Add the MRCLIP_SESSION secret (see README).")
            sys.exit(1)
        site = MrClip(pw)
        await site.start()
        try:
            await session.apply(site.ctx, raw)
            main.site = site
            await main.run_cycle(app, do_refresh=refresh)
        finally:
            try:  # save the (possibly renewed) login for next time
                with open(SESSION_FILE, "w", encoding="utf-8") as f:
                    f.write(await session.export(site.ctx))
            except Exception as e:
                print("could not save session:", e)
            await site.stop()


if __name__ == "__main__":
    asyncio.run(run(refresh=os.getenv("DO_REFRESH", "true").lower() != "false"))
