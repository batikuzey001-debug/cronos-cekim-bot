"""
Manuel giriş ile session oluşturur.
Chrome remote debugging ile açılır; giriş sonrası cookies auth_session.json'a kaydedilir.
"""
import asyncio
import os
import subprocess
import tempfile
import time

from playwright.async_api import async_playwright

CDP_PORT = 9222
CDP_URL = f"http://localhost:{CDP_PORT}"
SESSION_PATH = "auth_session.json"
SITE_URL = "https://cronos.redlanegaming.com"


def get_chrome_path():
    """Sistemdeki Chrome veya Edge yolunu döner."""
    path = os.environ.get("CHROME_PATH")
    if path and os.path.isfile(path):
        return path
    # Windows: Chrome
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    # Edge yedek
    edge = os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe")
    if os.path.isfile(edge):
        return edge
    raise FileNotFoundError("Chrome veya Edge bulunamadı. CHROME_PATH ile yol verebilirsiniz.")


def is_port_open(host: str, port: int, timeout: float = 15.0) -> bool:
    import socket
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect((host, port))
                return True
        except OSError:
            time.sleep(0.3)
    return False


async def main():
    chrome_path = get_chrome_path()
    user_data_dir = tempfile.mkdtemp(prefix="chrome_session_")
    process = None
    try:
        process = subprocess.Popen(
            [
                chrome_path,
                f"--remote-debugging-port={CDP_PORT}",
                f"--user-data-dir={user_data_dir}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not is_port_open("127.0.0.1", CDP_PORT):
            print("Chrome başlatıldı ancak CDP portu açılmadı.")
            return

        print("Chrome'da cronos.redlanegaming.com'a giriş yap, giriş yaptıktan sonra Enter'a bas")
        input()

        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(CDP_URL)
        try:
            if not browser.contexts:
                print("Tarayıcı bağlamı bulunamadı.")
                return
            context = browser.contexts[0]
            await context.storage_state(path=SESSION_PATH)
            print(f"Session kaydedildi: {SESSION_PATH}")
        finally:
            await browser.close()
        await playwright.stop()
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        try:
            import shutil
            shutil.rmtree(user_data_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
