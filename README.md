# MrClip Telegram bot

Every **5 hours** the bot:
1. opens your mrclip.gr **Submissions** page (logged in as you),
2. clicks **REFRESH STATS** and waits until all views are fetched (it updates one Telegram message with the %),
3. goes through **every PENDING page** (NEXT → NEXT → …),
4. sends you a Telegram message listing every clip with **1,000+ views** (ready to accept), with 🆕 on new ones.
   Clips under 1,000 are skipped.

If something goes wrong (for example you got logged out) it messages you, with a screenshot of what it saw.

Telegram commands (only your Telegram ID can use them):
`/check` refresh + check now · `/scan` check now without refreshing · `/status`

## Setup (Windows/Mac/Linux PC that stays on)

1. Install **Python 3.10+** (python.org; on Windows tick "Add Python to PATH") and **Google Chrome**.
2. Download this repo (green **Code** button → Download ZIP), unzip, open a terminal in the folder:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Copy `.env.example` to `.env` and put in your **new** bot token from @BotFather.
4. Log in once (a Chrome window opens, log in with Google, then press Enter in the terminal):
   ```bash
   python -m bot.login
   ```
5. Start the bot and leave it running:
   ```bash
   python -m bot.main
   ```
   You'll get "🤖 MrClip bot started." on Telegram.

## Settings (`.env`)
| Setting | Default | Meaning |
|---|---|---|
| `MIN_VIEWS` | 1000 | views needed to count as "ready" |
| `REFRESH_EVERY_HOURS` | 5 | how often to run |
| `REFRESH_TIMEOUT_MIN` | 180 | max wait for REFRESH STATS |
| `HEADLESS` | true | `false` = show the browser window while it works |
| `SUBMISSIONS_URL` | (auto) | address of the Submissions page, if auto-finding fails |

If Google says "this browser may not be secure" during login, make sure Chrome is installed and
`BROWSER_CHANNEL=chrome` is in `.env`.
