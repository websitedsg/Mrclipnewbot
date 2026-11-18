"""Move the mrclip.gr login (Supabase session) in/out of the browser as JSON.

The JSON is what the console snippet in README produces:
  {"ls": {"sb-...-auth-token": "..."}, "ck": "sb-...=...; sb-...=..."}
"""
import json
import logging

from playwright.async_api import BrowserContext

from . import config

log = logging.getLogger(__name__)


def _parse_cookie_string(s: str) -> dict:
    out = {}
    for part in (s or "").split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            out[k] = v
    return out


async def apply(ctx: BrowserContext, raw: str) -> None:
    data = json.loads(raw)
    ls = data.get("ls") or {}
    ck = data.get("ck") or {}
    if isinstance(ck, str):
        ck = _parse_cookie_string(ck)
    if ck:
        await ctx.add_cookies([{"name": k, "value": v, "url": config.SITE_URL} for k, v in ck.items()])
    page = await ctx.new_page()
    try:
        await page.goto(config.SITE_URL, wait_until="domcontentloaded")
        await page.evaluate("ls => { for (const [k, v] of Object.entries(ls)) localStorage.setItem(k, v) }", ls)
    finally:
        await page.close()
    log.info("session applied (%d localStorage keys, %d cookies)", len(ls), len(ck))


async def export(ctx: BrowserContext) -> str:
    page = await ctx.new_page()
    try:
        await page.goto(config.SITE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)  # let the site refresh its token if needed
        ls = await page.evaluate(
            "() => Object.fromEntries(Object.keys(localStorage).filter(k => k.startsWith('sb-'))"
            ".map(k => [k, localStorage.getItem(k)]))")
    finally:
        await page.close()
    ck = {c["name"]: c["value"] for c in await ctx.cookies(config.SITE_URL) if c["name"].startswith("sb-")}
    return json.dumps({"ls": ls, "ck": ck})
