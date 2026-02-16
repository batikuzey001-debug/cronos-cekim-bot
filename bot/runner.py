"""
Cronos Cekim Bot - Ana calisma dongusu.
========================================
Pydoll ile Chrome acip Cloudflare'i otomatik asar,
kullanici 1 kere login yapar, sonra cekim sayfasini
DOM scraping ile okuyarak surekli tarar.
Web panel (FastAPI) ile ayni anda calisir.

API KULLANMAZ - panelde ne goruyorsaniz aynen onu ceker.

Kullanim:
    python -m bot.runner
"""
import asyncio
import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

# Windows konsolunda Turkce karakter destegi
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config.settings import BOT_SCAN_INTERVAL

DATA_FILE = Path("bot_data.json")


def _calc_total(items):
    """Cekim listesinin toplam tutarini hesapla."""
    total = 0
    for r in items:
        try:
            amt = r.get("amount", "0")
            clean = str(amt).replace("TRY", "").replace("TL", "").replace("\u20ba", "").strip()
            clean = clean.replace(".", "").replace(",", ".")
            total += float(clean) if clean else 0
        except (ValueError, TypeError):
            pass
    return total


def update_panel(pending=None, status_data=None, status="calisiyor", error=None, login_user=None):
    """Web panel icin verileri guncelle (disk'e yaz)."""
    try:
        data = {}
        if DATA_FILE.exists():
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

        data["bot_status"] = status
        data["last_scan"] = datetime.now().isoformat()
        data["scan_count"] = data.get("scan_count", 0) + 1

        if login_user:
            data["login_user"] = login_user

        # Durum bazli veri (scan_all_statuses sonucu)
        if status_data is not None:
            for key in ("beklemede", "reserve", "islemde"):
                items = status_data.get(key, [])
                # Gercek toplam: sayfalamadan gelen sayi (50+ olabilir)
                real_count = status_data.get(f"{key}_total_count", len(items))
                data[f"{key}_count"] = real_count
                data[f"{key}_total"] = _calc_total(items)
                data[f"{key}_items"] = items

            # Geriye uyumluluk: beklemede = pending
            bek = status_data.get("beklemede", [])
            data["pending_count"] = status_data.get("beklemede_total_count", len(bek))
            data["pending_total"] = _calc_total(bek)
            data["pending_items"] = bek

        # Eski tek-durum uyumlulugu
        if pending is not None and status_data is None:
            data["pending_count"] = len(pending)
            data["pending_total"] = _calc_total(pending)
            data["pending_items"] = pending

        if error:
            errors = data.get("errors", [])
            errors.insert(0, {"time": datetime.now().isoformat(), "msg": str(error)})
            data["errors"] = errors[:20]

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        try:
            from admin.app import bot_state
            bot_state.update(data)
        except Exception:
            pass
    except Exception as e:
        print(f"[!] Panel guncelleme hatasi: {e}", flush=True)


def start_web_panel():
    """Web paneli ayri thread'de baslat."""
    try:
        import uvicorn
        port = int(os.environ.get("PORT", "8001"))
        print(f"[Web] Panel baslatiliyor: http://localhost:{port}", flush=True)
        uvicorn.run(
            "admin.app:app",
            host="0.0.0.0",
            port=port,
            log_level="warning",
        )
    except Exception as e:
        print(f"[!] Web panel hatasi: {e}", flush=True)


async def run_cycle(browser):
    """Tek tarama dongusu - 3 durumu sirayla tarayip panele gonder."""
    # Session hala gecerli mi?
    logged_in = await browser.is_logged_in()
    if not logged_in:
        print("[!] Session gecersiz!", flush=True)
        update_panel(status="session_dusmus")
        return False

    # 3 durumu sirayla tara
    print("[*] Durum bazli tarama yapiliyor...", flush=True)
    result = await browser.scan_all_statuses()

    if result is None:
        print("[!] Tarama basarisiz!", flush=True)
        return False

    # Ozet log
    for key, label in [("beklemede", "Beklemede"), ("reserve", "Reserve"), ("islemde", "Islemde")]:
        items = result.get(key, [])
        real_count = result.get(f"{key}_total_count", len(items))
        total = browser._calc_total(items)
        print(f"[Bot] {label}: {real_count} cekim, {total:,.0f} TRY", flush=True)

    # Panel'e durum bazli veri gonder
    update_panel(status_data=result, status="calisiyor")

    # Session'i periyodik kaydet
    await browser.save_session()
    return True


async def try_recover_session(browser):
    """Session dusunce sayfayi yenileyerek kurtarmayi dene."""
    print("[*] Session kurtarma deneniyor...", flush=True)
    try:
        await browser.bypass_cloudflare()
        await asyncio.sleep(5)

        is_ok = await browser.is_logged_in()
        if is_ok:
            print("[+] Session kurtarildi!", flush=True)
            return True

        print("[!] Session kurtarilamadi.", flush=True)
        return False
    except Exception as e:
        print(f"[!] Session kurtarma hatasi: {e}", flush=True)
        return False


async def main():
    from bot.browser import CronosBrowser

    interval = BOT_SCAN_INTERVAL

    # Railway'de headless, lokalde headed
    is_railway = os.environ.get("RAILWAY_ENVIRONMENT") is not None
    headless = is_railway or os.environ.get("HEADLESS", "").lower() in ("1", "true")

    print("=" * 60, flush=True)
    print("  Cronos Cekim Bot - DOM Scraping Edition", flush=True)
    print(f"  Mod: {'Headless' if headless else 'Headed'}", flush=True)
    print(f"  Tarama araligi: {interval}s", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)

    # Web paneli arka planda baslat
    web_thread = threading.Thread(target=start_web_panel, daemon=True)
    web_thread.start()

    update_panel(status="baslatiliyor")

    # Chrome'u baslat (sabit profil klasoru ile - session korunur)
    browser = CronosBrowser()
    await browser.start(headless=headless)

    # Session kontrol - onceki login hala gecerli mi?
    update_panel(status="session_kontrol")
    session_ok = await browser.check_and_restore_session()

    if session_ok:
        print(flush=True)
        print("[+] Onceki session gecerli! Login atlanıyor.", flush=True)
    else:
        # Manuel login gerekiyor
        print("[*] Tarayicida giris yapin (Login + 2FA)", flush=True)
        print("[*] Panel acilinca bot otomatik devam edecek...", flush=True)
        print(flush=True)
        update_panel(status="login_bekliyor")

        logged_in = await browser.wait_for_login(max_wait=600)

        if not logged_in:
            print("[!] Login basarisiz!", flush=True)
            update_panel(status="login_basarisiz")
            await browser.close()
            sys.exit(1)

    update_panel(status="calisiyor", login_user="logged_in")
    print(flush=True)
    print("[+] Bot surekli tarama moduna gecti.", flush=True)
    print("[*] Tarayiciyi kapatmayin!", flush=True)

    # Ilk tarama
    print(flush=True)
    print("[Bot] Ilk tarama yapiliyor...", flush=True)
    try:
        await run_cycle(browser)
    except Exception as e:
        print(f"[Bot] Ilk tarama hatasi: {e}", flush=True)
        update_panel(status="hata", error=str(e))

    # Sonsuz dongude tara
    print(f"\n[Bot] Surekli tarama basliyor ({interval}s aralikla)...", flush=True)
    consecutive_failures = 0
    max_failures = 5

    while True:
        await asyncio.sleep(interval)
        try:
            success = await run_cycle(browser)
            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                print(f"[!] Session dusmus ({consecutive_failures}/{max_failures})", flush=True)

                recovered = await try_recover_session(browser)
                if recovered:
                    consecutive_failures = 0
                    update_panel(status="calisiyor")
                elif consecutive_failures >= max_failures:
                    print(f"[!] {max_failures} basarisiz deneme. Manuel login gerekiyor.", flush=True)
                    update_panel(status="login_bekliyor")

                    ok = await browser.wait_for_login(max_wait=600)
                    if ok:
                        consecutive_failures = 0
                        print("[+] Yeniden login basarili!", flush=True)
                        update_panel(status="calisiyor")
                    else:
                        print("[!] Login zaman asimi. Bot durduruluyor.", flush=True)
                        update_panel(status="durdu")
                        break
                else:
                    wait_time = min(30 * consecutive_failures, 300)
                    print(f"[*] {wait_time}s sonra tekrar...", flush=True)
                    update_panel(status="session_dusmus")
                    await asyncio.sleep(wait_time)
        except Exception as e:
            print(f"[Bot] Hata: {e}", file=sys.stderr, flush=True)
            update_panel(status="hata", error=str(e))
            await asyncio.sleep(30)

    await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
