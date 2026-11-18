"""
Browser automation for mrclip.gr (Playwright).

!!! The CSS selectors / URLs in SELECTORS below are GUESSES. !!!
They must be filled in from screenshots (or the page HTML) of the real
mrclip.gr admin pages. Everything else in the bot is already wired up.
"""
import asyncio
import logging
import os
from dataclasses import dataclass

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from . import config

log = logging.getLogger(__name__)

SELECTORS = {
    # --- login page ---
    "login_path": "/login",
    "login_user": "input[name='username'], input[name='email'], input[type='email']",
    "login_pass": "input[type='password']",
    "login_submit": "button[type='submit'], input[type='submit']",
    # something that only exists when you ARE logged in
    "logged_in_marker": "a[href*='logout']",

    # --- pending clips list (clips waiting for accept/reject) ---
    "pending_path": "/admin/clips?status=pending",
    "clip_row": ".clip-row",               # one element per clip
    "clip_id_attr": "data-id",             # attribute on clip_row holding its id
    "clip_title": ".clip-title",
    "clip_link": "a",
    "approve_btn": "button.approve",
    "reject_btn": "button.reject",

    # --- approved clips list (where the "refresh views" button lives) ---
    "approved_path": "/admin/clips?status=approved",
    "refresh_btn": "button.refresh-views",
    "next_page": "a[rel='next']",          # pagination; empty string if none
}

STATE_FILE = os.path.join(config.DATA_DIR, "browser_state.json")


@dataclass
class Clip:
    id: str
    title: str
    url: str


class MrClip:
    def __init__(self) -> None:
        self._pw = None
        self.browser: Browser | None = None
        self.ctx: BrowserContext | None = None
        self.lock = asyncio.Lock()  # one browser action at a time

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(headless=config.HEADLESS)
        kw = {"storage_state": STATE_FILE} if os.path.exists(STATE_FILE) else {}
        self.ctx = await self.browser.new_context(**kw)

    async def stop(self) -> None:
        if self.ctx:
            await self.ctx.storage_state(path=STATE_FILE)
        if self.browser:
            await self.browser.close()
        if self._pw:
            await self._pw.stop()

    # ---------- helpers ----------
    def _url(self, key: str) -> str:
        return config.SITE_URL + SELECTORS[key]

    async def _page(self, key: str) -> Page:
        page = await self.ctx.new_page()
        await page.goto(self._url(key), wait_until="domcontentloaded")
        if not await page.locator(SELECTORS["logged_in_marker"]).count():
            await self._login(page)
            await page.goto(self._url(key), wait_until="domcontentloaded")
        return page

    async def _login(self, page: Page) -> None:
        log.info("Logging in to mrclip")
        await page.goto(self._url("login_path"), wait_until="domcontentloaded")
        await page.fill(SELECTORS["login_user"], config.SITE_USER)
        await page.fill(SELECTORS["login_pass"], config.SITE_PASS)
        await page.click(SELECTORS["login_submit"])
        await page.wait_for_load_state("networkidle")
        if not await page.locator(SELECTORS["logged_in_marker"]).count():
            raise RuntimeError("Login failed - check username/password or the login selectors")
        await self.ctx.storage_state(path=STATE_FILE)

    async def _row(self, page: Page, clip_id: str):
        sel = f"{SELECTORS['clip_row']}[{SELECTORS['clip_id_attr']}='{clip_id}']"
        return page.locator(sel).first

    # ---------- public actions ----------
    async def pending_clips(self) -> list[Clip]:
        async with self.lock:
            page = await self._page("pending_path")
            try:
                clips = []
                for row in await page.locator(SELECTORS["clip_row"]).all():
                    cid = await row.get_attribute(SELECTORS["clip_id_attr"]) or ""
                    title_loc = row.locator(SELECTORS["clip_title"])
                    title = (await title_loc.first.inner_text()).strip() if await title_loc.count() else cid
                    link_loc = row.locator(SELECTORS["clip_link"])
                    href = await link_loc.first.get_attribute("href") if await link_loc.count() else ""
                    if href and href.startswith("/"):
                        href = config.SITE_URL + href
                    if cid:
                        clips.append(Clip(cid, title, href or ""))
                return clips
            finally:
                await page.close()

    async def decide(self, clip_id: str, approve: bool) -> bool:
        async with self.lock:
            page = await self._page("pending_path")
            try:
                row = await self._row(page, clip_id)
                if not await row.count():
                    return False
                btn = row.locator(SELECTORS["approve_btn" if approve else "reject_btn"])
                page.once("dialog", lambda d: asyncio.ensure_future(d.accept()))  # "are you sure?"
                await btn.first.click()
                await page.wait_for_load_state("networkidle")
                return True
            finally:
                await page.close()

    async def refresh_all_views(self, progress=None) -> int:
        """Click 'refresh views' on every approved clip, page by page, slowly."""
        clicked = 0
        async with self.lock:
            page = await self._page("approved_path")
            try:
                while True:
                    buttons = await page.locator(SELECTORS["refresh_btn"]).all()
                    for b in buttons:
                        try:
                            await b.click()
                            clicked += 1
                        except Exception as e:  # keep going on single failures
                            log.warning("refresh click failed: %s", e)
                        await asyncio.sleep(config.CLICK_DELAY_SEC)
                        if progress and clicked % 100 == 0:
                            await progress(clicked)
                    nxt = SELECTORS["next_page"]
                    if not nxt or not await page.locator(nxt).count():
                        break
                    await page.locator(nxt).first.click()
                    await page.wait_for_load_state("domcontentloaded")
            finally:
                await page.close()
        return clicked
