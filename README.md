# MrClip Telegram bot

Watches **mrclip.gr** for you and talks to you on Telegram:

* 🎬 Sends you a message for every new clip waiting for review, with **✅ Approve / ❌ Reject** buttons
  (or approves automatically if `AUTO_APPROVE=true`).
* 🔄 Every few hours clicks **"refresh views"** on all clips by itself — slowly, so ~900 clips is fine —
  and messages you when it's finished.
* Only answers **you** (your Telegram ID); everyone else is ignored.

Commands: `/start`, `/check`, `/refresh`, `/status`.

## Setup (on your PC or a server that stays on)

1. Install Python 3.10+.
2. In this folder:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Copy `.env.example` to `.env` and fill it in (bot token from @BotFather, your mrclip login).
   **Never share or commit `.env`.**
4. Run:
   ```bash
   python -m bot.main
   ```
   You should get "🤖 MrClip bot started." on Telegram.

Tip: set `HEADLESS=false` the first time to watch the browser do the clicking.

## ⚠️ Not finished yet
`bot/site.py` → `SELECTORS` holds placeholder page addresses/buttons. They must be updated to match
the real mrclip.gr admin pages (login page, pending clips list, approve/reject buttons, refresh-views button).
