import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, filters)

from . import config, storage
from .site import MrClip

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
log = logging.getLogger("mrclipbot")

site = MrClip()
ADMIN = filters.User(user_id=config.ADMIN_ID)


async def send(app: Application, text: str, **kw) -> None:
    await app.bot.send_message(config.ADMIN_ID, text, disable_web_page_preview=True, **kw)


# ---------------- background jobs ----------------
async def check_new(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    app = ctx.application
    try:
        clips = await site.pending_clips()
    except Exception as e:
        log.exception("check failed")
        await send(app, f"⚠️ Couldn't read pending clips: {e}")
        return
    new = [c for c in clips if not storage.is_seen(c.id)]
    for c in new:
        storage.mark_seen(c.id)
        if config.AUTO_APPROVE:
            ok = await site.decide(c.id, approve=True)
            storage.mark_decided(c.id, "approved-auto")
            await send(app, f"{'✅ Auto-approved' if ok else '⚠️ Could not approve'}: {c.title}\n{c.url}")
        else:
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Approve", callback_data=f"ok:{c.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"no:{c.id}"),
            ]])
            await send(app, f"🎬 New clip: {c.title}\n{c.url}", reply_markup=kb)
    if new:
        log.info("notified %d new clips", len(new))


async def refresh_views(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    app = ctx.application
    await send(app, "🔄 Starting views refresh on all clips… (this takes a while)")

    async def progress(n: int) -> None:
        await send(app, f"…refreshed {n} clips so far")

    try:
        n = await site.refresh_all_views(progress)
        await send(app, f"✅ Views refresh done — {n} clips refreshed.")
    except Exception as e:
        log.exception("refresh failed")
        await send(app, f"⚠️ Views refresh stopped: {e}")


# ---------------- commands ----------------
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 MrClip bot is running.\n"
        "/check – look for new clips now\n"
        "/refresh – refresh views on all clips now\n"
        "/status – settings"
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"Checking every {config.CHECK_INTERVAL_MIN} min\n"
        f"Refreshing views every {config.REFRESH_INTERVAL_MIN} min\n"
        f"Auto-approve: {'ON' if config.AUTO_APPROVE else 'OFF'}"
    )


async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔍 Checking…")
    ctx.job_queue.run_once(check_new, 0)


async def cmd_refresh(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.job_queue.run_once(refresh_views, 0)


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if q.from_user.id != config.ADMIN_ID:
        await q.answer("Not allowed", show_alert=True)
        return
    action, clip_id = q.data.split(":", 1)
    approve = action == "ok"
    await q.answer("Working…")
    try:
        ok = await site.decide(clip_id, approve)
    except Exception as e:
        await q.edit_message_text(f"{q.message.text}\n\n⚠️ Error: {e}")
        return
    storage.mark_decided(clip_id, "approved" if approve else "rejected")
    status = ("✅ Approved" if approve else "❌ Rejected") if ok else "⚠️ Clip not found (already handled?)"
    await q.edit_message_text(f"{q.message.text}\n\n{status}", disable_web_page_preview=True)


# ---------------- lifecycle ----------------
async def post_init(app: Application) -> None:
    await site.start()
    jq = app.job_queue
    jq.run_repeating(check_new, interval=config.CHECK_INTERVAL_MIN * 60, first=5)
    jq.run_repeating(refresh_views, interval=config.REFRESH_INTERVAL_MIN * 60,
                     first=config.REFRESH_INTERVAL_MIN * 60)
    await send(app, "🤖 MrClip bot started.")


async def post_shutdown(app: Application) -> None:
    await site.stop()


def main() -> None:
    app = (Application.builder().token(config.TOKEN)
           .post_init(post_init).post_shutdown(post_shutdown).build())
    app.add_handler(CommandHandler("start", cmd_start, filters=ADMIN))
    app.add_handler(CommandHandler("status", cmd_status, filters=ADMIN))
    app.add_handler(CommandHandler("check", cmd_check, filters=ADMIN))
    app.add_handler(CommandHandler("refresh", cmd_refresh, filters=ADMIN))
    app.add_handler(CallbackQueryHandler(on_button))
    app.run_polling()


if __name__ == "__main__":
    main()
