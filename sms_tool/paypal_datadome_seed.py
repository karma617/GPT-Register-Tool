"""Isolated PayPal DataDome browser seed helper.

This script runs browser automation in a child process so Playwright/Camoufox
driver crashes cannot terminate the main payment flow.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any, Optional


PP_ORIGIN = "https://www.paypal.com"


def _build_onboard_url(*, ba_token: str, locale_country: str, locale_lang: str) -> str:
    params = [
        ("ul", "1"),
        ("country.x", locale_country),
        ("locale.x", f"{locale_lang}_{locale_country}"),
        ("modxo_redirect_reason", "guest_user"),
        ("ulOnboardRedirect", "true"),
        ("ba_token", ba_token),
    ]
    return f"{PP_ORIGIN}/agreements/approve?{urllib.parse.urlencode(params)}"


def _build_signup_url(*, ba_token: str, ec_token: str, locale_country: str, locale_lang: str) -> str:
    params = [
        ("ul", "1"),
        ("country.x", locale_country),
        ("locale.x", f"{locale_lang}_{locale_country}"),
        ("modxo_redirect_reason", "guest_user"),
        ("ba_token", ba_token),
        ("token", ec_token),
        ("rcache", "1"),
        ("cookieBannerVariant", "hidden"),
    ]
    return f"{PP_ORIGIN}/checkoutweb/signup?{urllib.parse.urlencode(params)}"


def _extract_ec_token(text: str) -> str:
    match = re.search(r"(EC-[A-Z0-9]{17,})", text or "")
    return match.group(1) if match else ""


def _looks_like_paypal_datadome(text: str) -> bool:
    head = (text or "")[:5000].lower()
    return any(
        marker in head
        for marker in (
            "datadome",
            "geo.ddc.paypal.com",
            "ct.ddc.paypal.com",
            "ddcaptcha",
            "ddchallenge",
            "captcha-delivery.com",
        )
    )


def _browser_proxy(proxy: str) -> Optional[dict[str, str]]:
    if not proxy:
        return None
    parsed = urllib.parse.urlparse(proxy.replace("socks5h://", "socks5://"))
    if not parsed.scheme or not parsed.hostname or not parsed.port:
        return None
    out = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        out["username"] = urllib.parse.unquote(parsed.username)
    if parsed.password:
        out["password"] = urllib.parse.unquote(parsed.password)
    return out


def _cookie_map(cookies: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in cookies:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        value = str(item.get("value") or "")
        domain = str(item.get("domain") or "paypal.com")
        if name and value and "paypal.com" in domain:
            out[name] = value
    return out


def _write_result(path: str, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_with_chromium(args: argparse.Namespace, approve_url: str) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    proxy = _browser_proxy(args.proxy)
    profile_dir = tempfile.mkdtemp(prefix="paypal_datadome_chromium_")
    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=bool(args.headless),
                proxy=proxy,
                locale=f"{args.locale_lang}-{args.locale_country}",
                viewport={"width": 1280, "height": 900},
                extra_http_headers={
                    "Accept-Language": f"{args.locale_lang}-{args.locale_country},{args.locale_lang};q=0.9,en;q=0.8"
                },
            )
            return _poll_context(ctx, approve_url, args)
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)


def _seed_with_camoufox(args: argparse.Namespace, approve_url: str) -> dict[str, Any]:
    from browserforge.fingerprints import Screen
    from camoufox.sync_api import Camoufox

    profile_dir = tempfile.mkdtemp(prefix="paypal_datadome_camoufox_")
    try:
        options = {
            "headless": bool(args.headless),
            "humanize": True,
            "persistent_context": True,
            "user_data_dir": profile_dir,
            "screen": Screen(max_width=1280, max_height=900),
            "proxy": _browser_proxy(args.proxy),
            "geoip": True,
            "locale": f"{args.locale_lang}-{args.locale_country}",
            "extra_http_headers": {
                "Accept-Language": f"{args.locale_lang}-{args.locale_country},{args.locale_lang};q=0.9,en;q=0.8"
            },
        }
        with Camoufox(**options) as ctx:
            return _poll_context(ctx, approve_url, args)
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)


def _poll_context(ctx: Any, approve_url: str, args: argparse.Namespace) -> dict[str, Any]:
    page = ctx.pages[0] if getattr(ctx, "pages", None) else ctx.new_page()
    page.goto(approve_url, wait_until="domcontentloaded", timeout=60000)
    deadline = time.time() + max(30, int(args.timeout or 300))
    last_url = ""
    html = ""
    ec_token = ""
    signup_url = ""
    print("[datadome-seed] Browser opened. Complete PayPal/DataDome verification in the visible window.", flush=True)
    while time.time() < deadline:
        page.wait_for_timeout(1000)
        last_url = page.url or ""
        html = page.content() or ""
        ec_token = _extract_ec_token(last_url) or _extract_ec_token(html)
        if ec_token and "/checkoutweb/signup" in last_url:
            signup_url = last_url
            break
        if ec_token and not _looks_like_paypal_datadome(html):
            signup_url = _build_signup_url(
                ba_token=args.ba_token,
                ec_token=ec_token,
                locale_country=args.locale_country,
                locale_lang=args.locale_lang,
            )
            break
    cookies = ctx.cookies([PP_ORIGIN])
    try:
        ctx.close()
    except Exception:
        pass
    if not ec_token:
        raise RuntimeError(f"timeout waiting for EC token; last_url={last_url[:160]}")
    return {
        "ok": True,
        "engine": args.engine,
        "ec_token": ec_token,
        "signup_url": signup_url or _build_signup_url(
            ba_token=args.ba_token,
            ec_token=ec_token,
            locale_country=args.locale_country,
            locale_lang=args.locale_lang,
        ),
        "cookies": _cookie_map(cookies),
        "last_url": last_url,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ba-token", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--proxy", default="")
    parser.add_argument("--locale-country", default="US")
    parser.add_argument("--locale-lang", default="en")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--engine", choices=["chromium", "camoufox"], default="chromium")
    args = parser.parse_args(argv)

    approve_url = _build_onboard_url(
        ba_token=args.ba_token,
        locale_country=args.locale_country,
        locale_lang=args.locale_lang,
    )
    try:
        if args.engine == "camoufox":
            result = _seed_with_camoufox(args, approve_url)
        else:
            result = _seed_with_chromium(args, approve_url)
        _write_result(args.out, result)
        return 0
    except Exception as exc:
        _write_result(args.out, {"ok": False, "engine": args.engine, "error": str(exc) or type(exc).__name__})
        print(f"[datadome-seed] failed: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
