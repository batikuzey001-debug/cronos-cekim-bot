"""
Scraper testi: auth_session ile finansal işlemler sayfasına gidip
bekleyen çekimleri okur ve yazdırır.
"""
import asyncio
from bot.browser import get_browser_context, close_browser, BASE_URL
from bot.scraper import get_pending_withdrawals


async def main():
    # Browser context oluştur (auth_session.json ile)
    await get_browser_context()
    from bot.browser import _page
    page = _page
    if page is None:
        print("Sayfa alınamadı.")
        return
    try:
        # Finansal işlemler sayfasına git
        url = f"{BASE_URL}/financial/financial-transactions"
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        # Pending çekimleri oku
        pending = await get_pending_withdrawals(page)
        # Yazdır
        print(f"Bekleyen çekim sayısı: {len(pending)}")
        for i, row in enumerate(pending[:3]):
            print(f"  {i + 1}. id={row['id']!r} oyuncu={row['oyuncu']!r} tutar={row['tutar']} tarih={row['tarih']!r}")
        if len(pending) > 3:
            print(f"  ... ve {len(pending) - 3} tane daha")
    finally:
        await close_browser()


if __name__ == "__main__":
    asyncio.run(main())
