import asyncio
import os
from playwright.async_api import async_playwright, Page

BASE_URL = "https://cronos.redlanegaming.com"
SESSION_PATH = "auth_session.json"
_browser = None
_page: Page | None = None

# Stealth / gerçek Chrome gibi görünüm
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-browser-side-navigation",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-web-security",
    "--window-size=1920,1080",
]

# Cloudflare / bot tespitini azaltmak için sayfa yüklenmeden çalışacak script
STEALTH_INIT_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR', 'tr', 'en-US', 'en'] });
    window.chrome = { runtime: {} };
"""


async def run_browser():
    """Chromium'u başlatır, siteye gider ve login sayfasının yüklenmesini bekler."""
    return await get_browser_context()


async def get_browser_context(wait_for_login: bool = True):
    """
    Session varsa onunla açar ve Cronos'a gider (giriş atlanır).
    Session yoksa hata verir; copy_chrome_session.py çalıştırılması önerilir.
    wait_for_login: Session yokken True ise login sayfası (şifre alanı) beklenir.
    (browser, page) döner.
    """
    global _browser, _page
    if not os.path.isfile(SESSION_PATH):
        raise FileNotFoundError(
            f"Session dosyası bulunamadı: {SESSION_PATH}\n"
            "Önce session oluşturun: python copy_chrome_session.py\n"
            "(Chrome'u kapatıp Chrome profilinden cookies kopyalanır)"
        )
    headless = os.environ.get("HEADLESS", "").strip() in ("1", "true", "yes")
    use_channel = not headless and not os.environ.get("RAILWAY_ENVIRONMENT")
    playwright = await async_playwright().start()
    launch_options = dict(headless=headless, args=STEALTH_ARGS)
    if use_channel:
        launch_options["channel"] = "chrome"
    try:
        _browser = await playwright.chromium.launch(**launch_options)
    except Exception:
        if use_channel:
            launch_options["channel"] = "msedge"
            _browser = await playwright.chromium.launch(**launch_options)
        else:
            raise
    context_options = dict(
        user_agent=CHROME_USER_AGENT,
        viewport={"width": 1920, "height": 1080},
        locale="tr-TR",
        timezone_id="Europe/Istanbul",
        permissions=[],
        extra_http_headers={
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        },
        ignore_https_errors=False,
        java_script_enabled=True,
        storage_state=SESSION_PATH,
    )
    context = await _browser.new_context(**context_options)
    await context.add_init_script(STEALTH_INIT_SCRIPT)
    _page = await context.new_page()
    await _page.goto(BASE_URL, wait_until="domcontentloaded")
    # Session ile açıldığı için giriş sayfası beklenmez; zaten giriş yapılmış olur
    return _browser, _page


async def login(username: str, password: str) -> None:
    """
    Login sayfasında kullanıcı adı ve şifre girip giriş yapar.
    Önce run_browser() çağrılmış olmalıdır.
    """
    if _page is None:
        raise RuntimeError("Önce run_browser() çağrılmalı.")
    # Kullanıcı adı alanı (placeholder/label/name ile dene)
    username_input = _page.get_by_placeholder("Username").or_(
        _page.get_by_placeholder("Kullanıcı adı")
    ).or_(_page.locator('input[name="username"], input[type="text"]').first)
    await username_input.fill(username)
    # Şifre alanı
    password_input = _page.get_by_placeholder("Password").or_(
        _page.get_by_placeholder("Şifre")
    ).or_(_page.locator('input[name="password"], input[type="password"]').first)
    await password_input.fill(password)
    # Giriş butonu
    submit_btn = _page.get_by_role("button", name="Login").or_(
        _page.get_by_role("button", name="Giriş")
    ).or_(_page.get_by_text("Login", exact=True)).or_(
        _page.locator('button[type="submit"], input[type="submit"]').first
    )
    await submit_btn.click()


async def close_browser():
    """Tarayıcıyı kapatır."""
    global _browser, _page
    if _browser:
        await _browser.close()
        _browser = None
        _page = None


if __name__ == "__main__":
    async def main():
        await run_browser()
        from config.settings import CRONOS_USERNAME, CRONOS_PASSWORD
        await login(CRONOS_USERNAME, CRONOS_PASSWORD)
        await asyncio.sleep(5)
        await close_browser()

    asyncio.run(main())
