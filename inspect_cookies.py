"""
CDP ile çalışan Chrome'a bağlanıp cronos.redlanegaming.com tab'ındaki
cookies/session'ı auth_session.json formatında kaydeder.

Kullanım:
1. Chrome'u şu komutla başlatın (Chrome kapalıyken):
   chrome.exe --remote-debugging-port=9222
   (Windows'ta tam yol: "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222)

2. Chrome'da cronos.redlanegaming.com sayfasını açıp giriş yapın.

3. Bu script'i çalıştırın: python inspect_cookies.py
"""
import asyncio
from playwright.async_api import async_playwright

CDP_URL = "http://localhost:9222"
SESSION_PATH = "auth_session.json"
CRONOS_HOST = "cronos.redlanegaming.com"


async def capture_cookies_from_running_chrome() -> bool:
    """
    CDP ile çalışan Chrome'a bağlanır, cronos.redlanegaming.com tab'ını bulur,
    o context'in cookies/storage'ını auth_session.json formatında kaydeder.

    Returns:
        True kayıt başarılıysa, False cronos tabı bulunamazsa.
    """
    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(CDP_URL)
    except Exception as e:
        print(f"Chrome'a bağlanılamadı: {e}")
        print("Chrome'u şu komutla başlattığınızdan emin olun: chrome.exe --remote-debugging-port=9222")
        await playwright.stop()
        return False

    try:
        target_page = None
        for context in browser.contexts:
            for page in context.pages:
                try:
                    url = page.url
                except Exception:
                    url = ""
                if CRONOS_HOST in url:
                    target_page = page
                    break
            if target_page is not None:
                break

        if target_page is None:
            print(f"cronos.redlanegaming.com içeren açık tab bulunamadı.")
            print("Chrome'da bu siteyi açıp tekrar deneyin.")
            return False

        await target_page.context.storage_state(path=SESSION_PATH)
        print(f"Session kaydedildi: {SESSION_PATH}")
        return True
    finally:
        await browser.close()
        await playwright.stop()


if __name__ == "__main__":
    print("Chrome'u şu komutla başlatın: chrome.exe --remote-debugging-port=9222")
    print("cronos.redlanegaming.com sayfasını açıp giriş yaptıktan sonra Enter'a basın.")
    input()
    success = asyncio.run(capture_cookies_from_running_chrome())
    if not success:
        exit(1)
