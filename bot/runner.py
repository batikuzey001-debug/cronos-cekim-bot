"""
Bot worker: sürekli çalışır, finansal işlemler sayfasını tarar.
Railway'de worker process olarak çalıştırılır (Procfile: worker).
"""
import asyncio
import json
import os
import sys

# Session dosyası proje kökünde (cwd)
SESSION_FILENAME = "auth_session.json"


def _ensure_session_file():
    """AUTH_SESSION_JSON env varsa auth_session.json dosyasına yazar (Railway için)."""
    raw = os.environ.get("AUTH_SESSION_JSON")
    if not raw:
        return False
    path = os.path.join(os.getcwd(), SESSION_FILENAME)
    try:
        data = json.loads(raw)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"AUTH_SESSION_JSON yazılamadı: {e}", file=sys.stderr)
        return False


async def run_cycle():
    from bot.browser import get_browser_context, close_browser, BASE_URL
    from bot.scraper import get_pending_withdrawals

    await get_browser_context()
    from bot.browser import _page
    page = _page
    if not page:
        return
    try:
        url = f"{BASE_URL}/financial/financial-transactions"
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        pending = await get_pending_withdrawals(page)
        print(f"[Bot] Bekleyen çekim: {len(pending)}", flush=True)
        for row in pending[:5]:
            print(f"  - {row.get('id')} | {row.get('oyuncu')} | {row.get('tutar')}", flush=True)
    finally:
        await close_browser()


async def main():
    if not os.path.isfile(os.path.join(os.getcwd(), SESSION_FILENAME)):
        if not _ensure_session_file():
            print("auth_session.json yok ve AUTH_SESSION_JSON env tanımlı değil. Çıkılıyor.", file=sys.stderr)
            sys.exit(1)
    # Railway/headless için
    os.environ.setdefault("HEADLESS", "1")
    interval = int(os.environ.get("BOT_SCAN_INTERVAL", "300"))  # saniye
    print(f"[Bot] Başlatıldı. Tarama aralığı: {interval}s", flush=True)
    while True:
        try:
            await run_cycle()
        except Exception as e:
            print(f"[Bot] Hata: {e}", file=sys.stderr, flush=True)
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())
