"""Browser automation for mrclip.gr (Playwright, persistent logged-in profile)."""
import asyncio
import logging
import re
import time
from dataclasses import dataclass

from playwright.async_api import BrowserContext, Page, Playwright

from . import config

log = logging.getLogger(__name__)


class NotLoggedIn(Exception):
    pass


@dataclass
class Clip:
    id: str
    user: str
    campaign: str
    url: str
    views: int


async def launch(pw: Playwright, headless: bool) -> BrowserContext:
    """Open Chrome with the saved profile so the Google login is remembered."""
    kw = dict(
        user_data_dir=config.PROFILE_DIR,
        headless=headless,
        viewport={"width": 1400, "height": 1000},
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    if config.BROWSER_CHANNEL:
        try:
            return await pw.chromium.launch_persistent_context(channel=config.BROWSER_CHANNEL, **kw)
        except Exception as e:
            log.warning("Could not start %s (%s) - using bundled Chromium", config.BROWSER_CHANNEL, e)
    return await pw.chromium.launch_persistent_context(**kw)


def parse_views(text: str) -> int | None:
    t = text.strip().upper().replace(" ", "")
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)([KM])", t)
    if m:
        return int(float(m.group(1).replace(",", ".")) * (1000 if m.group(2) == "K" else 1_000_000))
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", t):
        return int(re.sub(r"[.,]", "", t))
    if re.fullmatch(r"\d+", t):
        return int(t)
    return None


# Runs inside the page: finds every row that has an APPROVE button.
_SCAN_JS = r"""
() => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const headers = [...document.querySelectorAll('th')].map(h => norm(h.innerText).toUpperCase());
  const rows = [];
  const btns = [...document.querySelectorAll('button, a, [role=button]')]
      .filter(b => norm(b.innerText).toUpperCase() === 'APPROVE');
  for (const b of btns) {
    let row = b.closest('tr'), cells;
    if (row) {
      cells = [...row.children].map(c => norm(c.innerText));
    } else {
      row = b.parentElement;
      while (row && row !== document.body && !/tiktok\.com/i.test(row.innerText) && !row.querySelector('a[href*="tiktok"]'))
        row = row.parentElement;
      if (!row || row === document.body) continue;
      cells = row.innerText.split('\n').map(norm).filter(Boolean);
    }
    const a = row.querySelector('a[href*="tiktok"]');
    rows.push({cells, url: a ? a.href : ''});
  }
  return {headers, rows};
}
"""


def _row_to_clip(headers: list[str], cells: list[str], href: str) -> Clip | None:
    url = href or next((c for c in cells if "tiktok.com" in c), "")
    views = None
    if "VIEWS" in headers and len(cells) == len(headers):
        views = parse_views(cells[headers.index("VIEWS")])
    if views is None:  # fallback: first number after the PENDING status
        start = next((i for i, c in enumerate(cells) if c.upper() == "PENDING"), -1)
        views = next((v for c in cells[start + 1:] if (v := parse_views(c)) is not None), None)
    if views is None:
        return None

    def col(name: str, default: int) -> str:
        if name in headers and len(cells) == len(headers):
            return cells[headers.index(name)]
        return cells[default] if len(cells) > default else ""

    return Clip(id=url or "|".join(cells[:3]), user=col("USER", 0), campaign=col("CAMPAIGN", 1),
                url=url, views=views)


class MrClip:
    def __init__(self, pw: Playwright) -> None:
        self.pw = pw
        self.ctx: BrowserContext | None = None
        self.lock = asyncio.Lock()
        self._subs_url = config.SUBMISSIONS_URL

    async def start(self) -> None:
        self.ctx = await launch(self.pw, config.HEADLESS)

    async def stop(self) -> None:
        if self.ctx:
            await self.ctx.close()

    # ---------- navigation ----------
    @staticmethod
    async def _goto(page: Page, url: str) -> None:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        except Exception as e:  # slow page - we check what loaded right after
            log.warning("goto %s: %s", url, e)

    async def _find_submissions_url(self, page: Page) -> str:
        await self._goto(page, config.SITE_URL)
        await page.wait_for_timeout(3000)
        for sel in ('a:has-text("Submissions")', 'a[href*="submission" i]'):
            loc = page.locator(sel)
            if await loc.count():
                href = await loc.first.get_attribute("href")
                if href:
                    return href if href.startswith("http") else config.SITE_URL + "/" + href.lstrip("/")
        raise NotLoggedIn("Couldn't find the Submissions link - are you logged in?")

    async def open_submissions(self) -> Page:
        page = await self.ctx.new_page()
        try:
            if not self._subs_url:
                self._subs_url = await self._find_submissions_url(page)
                log.info("Submissions page: %s", self._subs_url)
            await self._goto(page, self._subs_url)
            try:
                await page.locator("text=/REFRESH STATS|RUNNING/i").first.wait_for(timeout=45_000)
            except Exception:
                raise NotLoggedIn("Submissions page didn't load (logged out?)")
            return page
        except Exception:
            await page.close()
            raise

    async def _pending_tab(self, page: Page) -> None:
        tab = page.get_by_role("button", name=re.compile(r"^\s*PENDING\s*$", re.I))
        if not await tab.count():
            tab = page.locator('a, [role=tab]').filter(has_text=re.compile(r"^\s*PENDING\s*$", re.I))
        if await tab.count():
            await tab.first.click()
            await page.wait_for_timeout(2500)

    # ---------- actions ----------
    async def _running(self, page: Page) -> bool:
        loc = page.locator("text=/RUNNING|REFRESHING STATS/i")
        for i in range(await loc.count()):
            if await loc.nth(i).is_visible():
                return True
        return False

    async def refresh_stats(self, page: Page, progress=None) -> None:
        if not await self._running(page):
            btn = page.locator('button:has-text("REFRESH STATS"), a:has-text("REFRESH STATS")').first
            await btn.click()
            await page.wait_for_timeout(5000)
        deadline = time.time() + config.REFRESH_TIMEOUT_MIN * 60
        last = None
        while await self._running(page):
            if time.time() > deadline:
                raise TimeoutError("REFRESH STATS didn't finish in time")
            body = await page.locator("body").inner_text()
            m = re.search(r"(\d+)\s*/\s*(\d+)\s*fetched", body, re.I)
            if m and progress and m.group(0) != last:
                last = m.group(0)
                await progress(int(m.group(1)), int(m.group(2)))
            await asyncio.sleep(20)
        await page.wait_for_timeout(3000)

    async def scan_pending(self, page: Page) -> tuple[list[Clip], int]:
        """Go through every PENDING page. Returns (all clips, pages read)."""
        await page.reload(wait_until="domcontentloaded")
        await page.locator("text=/REFRESH STATS|RUNNING/i").first.wait_for(timeout=45_000)
        await self._pending_tab(page)
        clips: dict[str, Clip] = {}
        pages = 0
        prev_sig = None
        while pages < 500:
            await page.wait_for_timeout(1500)
            data = await page.evaluate(_SCAN_JS)
            sig = tuple(tuple(r["cells"]) for r in data["rows"])
            if sig == prev_sig:
                break
            prev_sig = sig
            pages += 1
            for r in data["rows"]:
                c = _row_to_clip(data["headers"], r["cells"], r["url"])
                if c:
                    clips.setdefault(c.id, c)
            nxt = page.locator('button:has-text("NEXT"), a:has-text("NEXT")').first
            if not await nxt.count() or await nxt.is_disabled() \
                    or (await nxt.get_attribute("aria-disabled")) == "true":
                break
            await nxt.click()
            # wait for the rows to change
            for _ in range(30):
                await page.wait_for_timeout(500)
                d2 = await page.evaluate(_SCAN_JS)
                if tuple(tuple(r["cells"]) for r in d2["rows"]) != sig:
                    break
        return list(clips.values()), pages
