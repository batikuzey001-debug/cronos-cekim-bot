"""
Login ve 2FA akışını test eder.
Cloudflare manuel geçildikten sonra giriş yapılır, session kaydedilir.
"""
import asyncio
from bot.browser import get_browser_context, login, close_browser
from config.settings import CRONOS_USERNAME, CRONOS_PASSWORD

LOGIN_SELECTOR = 'input[type="password"], input[name="password"], [name="password"]'
SESSION_PATH = "auth_session.json"


async def main():
    try:
        # 1. Tarayıcıyı aç (login sayfasını beklemeden)
        await get_browser_context(wait_for_login=False)
        from bot.browser import _page
        page = _page
        if page is None:
            print("Sayfa bulunamadı.")
            return

        # 2. Cloudflare sayfası için 60 saniye bekle (sayfa yüklensin)
        try:
            await page.wait_for_load_state("networkidle", timeout=60000)
        except Exception:
            pass

        # 3–4. Kullanıcıdan Cloudflare'i manuel geçmesini iste
        print("Cloudflare kontrolünü manuel geç, Enter'a bas")
        input()

        # 5. Login sayfası yüklendiyse devam et (60 saniye bekle)
        try:
            await page.wait_for_selector(LOGIN_SELECTOR, state="visible", timeout=60000)
        except Exception as e:
            print("Login sayfası yüklenemedi (60 sn aşıldı):", e)
            return

        # 6. Giriş yap
        await login(CRONOS_USERNAME, CRONOS_PASSWORD)

        # 2FA varsa
        await asyncio.sleep(3)
        two_fa_input = page.locator(
            'input[name="code"], input[name="totp"], input[placeholder*="code"], '
            'input[placeholder*="2FA"], input[type="tel"][maxlength="6"], '
            'input[inputmode="numeric"]'
        ).first
        try:
            await two_fa_input.wait_for(state="visible", timeout=5000)
            code = input("2FA kodunu girin: ").strip()
            if code:
                await two_fa_input.fill(code)
                submit = page.locator('button[type="submit"], input[type="submit"]').first
                await submit.click()
                await asyncio.sleep(3)
        except Exception:
            pass

        await asyncio.sleep(2)
        current_url = page.url
        if "login" not in current_url.lower():
            print("Giriş başarılı!")
            # Session kaydet
            await page.context.storage_state(path=SESSION_PATH)
            print(f"Session kaydedildi: {SESSION_PATH}")
        else:
            err = page.locator(".error, .alert-danger, [role=alert]").first
            if await err.count() > 0:
                print("Giriş başarısız:", await err.text_content())
            else:
                print("Giriş başarılı!")
                await page.context.storage_state(path=SESSION_PATH)
                print(f"Session kaydedildi: {SESSION_PATH}")
    finally:
        await close_browser()


if __name__ == "__main__":
    asyncio.run(main())
