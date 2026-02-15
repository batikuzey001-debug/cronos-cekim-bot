"""
Chrome profilindeki mevcut oturumu (cookies) kopyalar.

Alternatif yollar (extension / manuel):
- EditThisCookie, Cookie-Editor gibi extension ile cookies export
- Manuel: Chrome DevTools (F12) > Application > Cookies > cronos.redlanegaming.com

Daha kolay yol (bu script):
- launch_persistent_context() ile Chrome'un profil klasörü kullanılır
- Windows: C:/Users/{username}/AppData/Local/Google/Chrome/User Data
- Playwright aynı cookies ile açar, auth_session.json'a kaydeder

Kullanım: Chrome'u KAPATIN, sonra: python copy_chrome_session.py
"""
import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright

SESSION_PATH = "auth_session.json"
SITE_URL = "https://cronos.redlanegaming.com"


def get_chrome_user_data_dir() -> str:
    """
    Windows'ta Chrome'un varsayılan profil klasörünü döner.
    CHROME_USER_DATA_DIR env ile override edilebilir.
    """
    path = os.environ.get("CHROME_USER_DATA_DIR")
    if path and os.path.isdir(path):
        return path
    username = os.environ.get("USERNAME", os.environ.get("USER", ""))
    if not username:
        username = Path.home().name
    default = os.path.expandvars(
        rf"C:\Users\{username}\AppData\Local\Google\Chrome\User Data"
    )
    if os.path.isdir(default):
        return default
    # Yedek: sadece User Data (Chrome farklı kurulumda olabilir)
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        alt = os.path.join(local_app, "Google", "Chrome", "User Data")
        if os.path.isdir(alt):
            return alt
    raise FileNotFoundError(
        "Chrome User Data bulunamadı. CHROME_USER_DATA_DIR ile yol verebilirsiniz."
    )


async def get_browser_with_chrome_profile():
    """
    Chrome'un mevcut profilini (User Data) kullanarak tarayıcı başlatır.
    Böylece Chrome'da giriş yapılmış hesaplar / cookies aynen kullanılır.

    Önce Chrome'u kapatmanız gerekir (profil kilidi için).

    Returns:
        (context, page): BrowserContext ve ilk sayfa. context.storage_state(path=...) ile session kaydedilebilir.
    """
    playwright = await async_playwright().start()
    user_data_dir = get_chrome_user_data_dir()
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir,
        channel="chrome",
        headless=False,
        accept_downloads=True,
        viewport={"width": 1920, "height": 1080},
        locale="tr-TR",
        ignore_default_args=["--enable-automation"],
    )
    # Mevcut sekme yoksa yeni aç
    if context.pages:
        page = context.pages[0]
    else:
        page = await context.new_page()
    return context, page


async def main():
    print("Chrome profil klasörü kullanılıyor. (Chrome kapalı olmalı.)")
    try:
        context, page = await get_browser_with_chrome_profile()
    except FileNotFoundError as e:
        print(e)
        return
    try:
        await page.goto(SITE_URL, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        await context.storage_state(path=SESSION_PATH)
        print(f"Session kaydedildi: {SESSION_PATH}")
    finally:
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
