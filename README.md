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

## ⭐ Easiest: run it free on GitHub (no PC or phone needs to stay on)

GitHub runs the bot by itself every 5 hours (file `.github/workflows/mrclip.yml`).
You need a laptop **once, ~3 minutes**, to copy your mrclip login.

**1. Copy your mrclip login (on the laptop, in Chrome)**
1. Open **mrclip.gr** and log in with Google (relvismazi@gmail.com) until you see your dashboard.
2. Press **F12** → click the **Console** tab.
3. Type `allow pasting` and press Enter (Chrome asks for this once).
4. Paste this and press Enter — it copies your login to the clipboard:
   ```js
   copy(JSON.stringify({ls:Object.fromEntries(Object.keys(localStorage).filter(k=>k.startsWith('sb-')).map(k=>[k,localStorage.getItem(k)])),ck:document.cookie}))
   ```
5. Close the tab. ⚠️ **Don't press "Log out" on mrclip** (on any device) — that would log the bot out too.

**2. Add 3 secrets on GitHub** — repo → **Settings → Secrets and variables → Actions → New repository secret**:
| Name | Value |
|---|---|
| `MRCLIP_SESSION` | paste (Ctrl+V) what you copied in step 1 |
| `TELEGRAM_BOT_TOKEN` | your **new** token from @BotFather |
| `TELEGRAM_ADMIN_ID` | `8399379960` |

**3. Start it** — repo → **Actions** tab → **MrClip check** → **Run workflow** → green button.
Within a few minutes you get Telegram messages. After that it runs by itself every 5 hours.
You can press **Run workflow** any time from the GitHub phone app for an extra check.

If the bot says the login expired, repeat steps 1–2 (just update `MRCLIP_SESSION`).

Notes:
- Your login is kept between runs **encrypted** (with your bot token as the key).
- Private repos get 2,000 free GitHub minutes/month. If one run takes longer than ~12 minutes,
  either make the repo public (the code contains no passwords) or change `*/5` to `*/8` in the workflow file.
- GitHub may pause schedules on repos with no activity for 60 days — it emails you; one click turns it back on.

---

## Alternative: run on your own PC (must stay on)

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
