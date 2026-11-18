import json
import logging
import os
import time

from playwright.async_api import async_playwright
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from . import config
from .site import MrClip, NotLoggedIn

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("mrclipbot")

site: MrClip | None = None
_pw = None


def _load_notified() -> set[str]:
    if os.path.exists(config.NOTIFIED_FILE):
        with open(config.NOTIFIED_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def _save_notified(ids: set[str]) -> None:
    with open(config.NOTIFIED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f)


async def send(app: Application, text: str):
    return await app.bot.send_message(config.ADMIN_ID, text, disable_web_page_preview=True)


async def send_long(app: Application, lines: list[str]) -> None:
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) > 3800:
            await send(app, chunk)
            chunk = ""
        chunk += line + "\n"
    if chunk:
        await send(app, chunk)


async def run_cycle(app: Application, do_refresh: bool = True) -> None:
    if site.lock.locked():
        await send(app, "⏳ Already working, please wait.")
        return
    async with site.lock:
        page = None
        status = None
        try:
            page = await site.open_submissions()
            if do_refresh:
                status = await send(app, "🔄 Clicked REFRESH STATS… waiting for views to update.")
                t0 = time.time()
                last_edit = 0.0

                async def progress(done: int, total: int) -> None:
                    nonlocal last_edit
                    if time.time() - last_edit > 60:
                        last_edit = time.time()
                        pct = done * 100 // max(total, 1)
                        try:
                            await status.edit_text(f"🔄 Refreshing views… {done}/{total} ({pct}%)")
                        except Exception:
                            pass

                await site.refresh_stats(page, progress)
                mins = int((time.time() - t0) / 60)
                await status.edit_text(f"✅ Views refreshed ({mins} min). Checking all pending pages…")

            clips, pages = await site.scan_pending(page)
            await report(app, clips, pages)
        except NotLoggedIn as e:
            await send(app, f"🔒 {e}\nOn your PC run:  python -m bot.login  and log in again.")
            await screenshot(app, page)
        except Exception as e:
            log.exception("cycle failed")
            await send(app, f"⚠️ Something went wrong: {e}")
            await screenshot(app, page)
        finally:
            if page:
                await page.close()


async def screenshot(app: Application, page) -> None:
    if not page:
        return
    try:
        path = os.path.join(config.DATA_DIR, "error.png")
        await page.screenshot(path=path)
        with open(path, "rb") as f:
            await app.bot.send_photo(config.ADMIN_ID, f, caption="What the bot saw")
    except Exception:
        pass


async def report(app: Application, clips, pages: int) -> None:
    ready = sorted((c for c in clips if c.views >= config.MIN_VIEWS), key=lambda c: -c.views)
    notified = _load_notified()
    new = [c for c in ready if c.id not in notified]
    if not clips:
        await send(app, f"🤷 Found no pending clips ({pages} page(s) read).")
        return
    if not ready:
        top = max(c.views for c in clips)
        await send(app, f"⏳ No clips at {config.MIN_VIEWS}+ views yet.\n"
                        f"{len(clips)} pending · highest has {top:,} views.")
        return
    lines = [f"🔥 {len(ready)} clip(s) ready to ACCEPT ({config.MIN_VIEWS:,}+ views)"
             f" — {len(new)} new\n({len(clips)} pending checked, {pages} pages)\n"]
    for c in ready:
        tag = "🆕 " if c.id not in notified else ""
        lines.append(f"{tag}👁 {c.views:,} · {c.user}\n   {c.campaign}\n   {c.url}\n")
    await send_long(app, lines)
    _save_notified(notified | {c.id for c in ready})


# ---------------- jobs & commands ----------------
async def job_cycle(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await run_cycle(ctx.application, do_refresh=True)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 MrClip bot\n"
        f"Every {config.REFRESH_EVERY_HOURS:g}h I click REFRESH STATS, check every pending page and "
        f"tell you which clips have {config.MIN_VIEWS:,}+ views.\n\n"
        "/check – refresh views + check now\n"
        "/scan – check now without refreshing (fast)\n"
        "/status – is it working right now?")


async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.application.create_task(run_cycle(ctx.application, do_refresh=True))


async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔍 Checking pending pages…")
    ctx.application.create_task(run_cycle(ctx.application, do_refresh=False))


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    jobs = ctx.job_queue.jobs()
    nxt = jobs[0].next_t.strftime("%H:%M") if jobs and jobs[0].next_t else "?"
    busy = "working right now" if site.lock.locked() else "idle"
    await update.message.reply_text(f"🤖 Bot is {busy}. Next automatic run at {nxt}.")


async def post_init(app: Application) -> None:
    global site, _pw
    _pw = await async_playwright().start()
    site = MrClip(_pw)
    await site.start()
    app.job_queue.run_repeating(job_cycle, interval=config.REFRESH_EVERY_HOURS * 3600, first=10)
    await send(app, f"🤖 MrClip bot started. First check in a few seconds, then every "
                    f"{config.REFRESH_EVERY_HOURS:g} hours.")


async def post_shutdown(app: Application) -> None:
    if site:
        await site.stop()
    if _pw:
        await _pw.stop()


def main() -> None:
    if not config.TOKEN or not config.ADMIN_ID:
        raise SystemExit("Fill in TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_ID in .env first")
    app = (Application.builder().token(config.TOKEN)
           .post_init(post_init).post_shutdown(post_shutdown).build())
    me = filters.User(user_id=config.ADMIN_ID)
    app.add_handler(CommandHandler("start", cmd_start, filters=me))
    app.add_handler(CommandHandler("check", cmd_check, filters=me))
    app.add_handler(CommandHandler("scan", cmd_scan, filters=me))
    app.add_handler(CommandHandler("status", cmd_status, filters=me))
    app.run_polling()


if __name__ == "__main__":
    main()
