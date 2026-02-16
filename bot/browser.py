"""
CronosBrowser - Pydoll ile Cloudflare bypass + element tiklama.
================================================================
Pydoll (WebDriver-free, CDP tabanli) ile Chrome acar,
Cloudflare Turnstile'i otomatik cozer,
kullanici 1 kere login yapar,
sonra cekim sayfasinda INSAN GIBI:
  - dropdown'lara tiklar
  - secenekleri secer
  - ARAMA butonuna tiklar
  - tablodan verileri okur

API KULLANMAZ - panelde ne goruyorsaniz aynen onu ceker.
"""
import asyncio
import json
import os
from pathlib import Path

from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.commands.runtime_commands import RuntimeCommands

from config.settings import CRONOS_BASE_URL

WITHDRAWALS_URL = f"{CRONOS_BASE_URL}/financial/financial-transactions"
CHROME_PROFILE_DIR = str(Path.home() / ".cronos_bot_chrome_profile")
CHROME_BIN = os.environ.get("CHROME_BIN", "")
SESSION_FILE = Path(__file__).parent.parent / "session_data.json"


def _extract_cdp_value(response):
    """Pydoll execute_script CDP response'undan gercek degeri cikar."""
    if isinstance(response, dict):
        inner = response.get("result", {})
        if isinstance(inner, dict):
            inner2 = inner.get("result", {})
            if isinstance(inner2, dict):
                return inner2.get("value")
        return inner
    return response


class CronosBrowser:
    def __init__(self):
        self._browser = None
        self._tab = None
        self._filters_set = False

    # ── JS Helper (sadece basit string/bool donduren sorgular icin) ──

    async def _js(self, script):
        """Basit JS calistir (string/bool/number donduren sorgular icin)."""
        try:
            raw = await self._tab.execute_script(script, return_by_value=True)
            return _extract_cdp_value(raw)
        except Exception as e:
            print(f"[!] JS hata: {e}", flush=True)
            return None

    async def _js_json(self, script):
        """
        JS calistir, JSON string dondur, Python dict'e cevir.
        Script icinde 'return VALUE' olmali (IIFE icinde).

        Pydoll'un execute_script'i 'return' gorunce scripti
        tekrar (function(){...})() ile sarmalamaya calisiyor ve
        brace counting hatasi yuzunden SyntaxError veriyor.
        Bu yuzden dogrudan CDP Runtime.evaluate kullaniyoruz.
        """
        expression = "JSON.stringify((function() { " + script + " })())"
        try:
            command = RuntimeCommands.evaluate(
                expression=expression,
                return_by_value=True,
            )
            raw = await self._tab._execute_command(command)
            val = _extract_cdp_value(raw)

            if val is None or not val or val == "null" or val == "undefined":
                return None

            return json.loads(val)
        except json.JSONDecodeError as e:
            print(f"[!] JSON parse: {e}", flush=True)
            return None
        except Exception as e:
            print(f"[!] _js_json: {type(e).__name__}: {e}", flush=True)
            return None

    # ── Browser Lifecycle ────────────────────────────────────────

    async def start(self, headless=False):
        """Chrome'u Pydoll ile baslat (sabit profil klasoru ile)."""
        options = ChromiumOptions()

        if headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.add_argument("--start-maximized")
        options.add_argument("--lang=tr-TR")
        options.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")

        # Railway'de Chromium binary path
        if CHROME_BIN:
            options.binary_location = CHROME_BIN

        self._browser = Chrome(options=options)
        await self._browser.__aenter__()
        self._tab = await self._browser.start()

        print(f"[+] Chrome baslatildi (profil: {CHROME_PROFILE_DIR})", flush=True)
        return self

    async def bypass_cloudflare(self, timeout=60):
        """Cloudflare Turnstile challenge'i otomatik coz."""
        print("[*] Cloudflare bypass deneniyor...", flush=True)

        try:
            async with self._tab.expect_and_bypass_cloudflare_captcha(
                time_to_wait_captcha=timeout
            ):
                await self._tab.go_to(CRONOS_BASE_URL)

            print("[+] Cloudflare gecildi!", flush=True)
            return True
        except Exception as e:
            print(f"[!] Cloudflare bypass hatasi: {e}", flush=True)
            try:
                await self._tab.go_to(CRONOS_BASE_URL)
                await asyncio.sleep(3)
            except Exception:
                pass
            return False

    async def close(self):
        """Temiz kapatma - session'i kaydet, browser'i kapat."""
        try:
            await self.save_session()
        except Exception:
            pass
        try:
            if self._browser:
                await self._browser.__aexit__(None, None, None)
                print("[+] Browser kapatildi", flush=True)
        except Exception as e:
            print(f"[!] Kapatma hatasi: {e}", flush=True)

    @property
    def tab(self):
        return self._tab

    # ── Session Persistence ───────────────────────────────────────

    async def save_session(self):
        """localStorage verisini dosyaya kaydet (yedek)."""
        try:
            data = await self._js_json(
                "return {localStorage: Object.assign({}, localStorage)}"
            )
            if data and data.get("localStorage"):
                SESSION_FILE.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print("[+] Session kaydedildi", flush=True)
        except Exception as e:
            print(f"[!] Session kaydetme hatasi: {e}", flush=True)

    async def restore_session(self):
        """Kaydedilmis localStorage verisini Chrome'a yukle."""
        if not SESSION_FILE.exists():
            return False
        try:
            raw = SESSION_FILE.read_text(encoding="utf-8")
            data = json.loads(raw)
            ls = data.get("localStorage", {})
            if not ls or not ls.get("access_token"):
                return False

            # localStorage'a yaz
            for key, value in ls.items():
                safe_key = key.replace("'", "\\'")
                safe_val = str(value).replace("'", "\\'").replace("\n", "\\n")
                await self._js(
                    "localStorage.setItem('" + safe_key + "', '" + safe_val + "')"
                )

            print("[+] Session restore edildi (localStorage)", flush=True)
            return True
        except Exception as e:
            print(f"[!] Session restore hatasi: {e}", flush=True)
            return False

    async def check_and_restore_session(self):
        """
        Session gecerli mi kontrol et.
        Chrome profili sayesinde genelde login korunur.
        Korunmadiysa localStorage backup'tan restore dene.
        Hala login gerekiyorsa kullanicidan iste.
        """
        print("[*] Session kontrol ediliyor...", flush=True)

        # Chrome profili Cloudflare cookie'lerini sakliyor,
        # bu yuzden bypass denemeden direkt sayfaya git
        await self._tab.go_to(CRONOS_BASE_URL)
        await asyncio.sleep(5)

        # Cloudflare challenge'a takildi mi?
        title = await self._js("return document.title") or ""
        t = title.lower()
        if "checking" in t or "just a moment" in t or "dakika" in t:
            print("[*] Cloudflare challenge, bypass deneniyor...", flush=True)
            await self.bypass_cloudflare()
            await asyncio.sleep(3)

        # Vue.js SPA yukleniyor - sayfa yonlendirme yapabilir
        # Birden fazla kontrol yap cunku SPA ilk basta Dashboard
        # gosteriyor sonra token gecersizse login'e yonlendiriyor
        for i in range(5):
            await asyncio.sleep(2)
            title = await self._js("return document.title") or ""
            url = await self._js("return window.location.href") or ""
            print(f"[*] Session kontrol ({i+1}/5): title={title}, url={url}", flush=True)

            if self._is_login_page(title, url):
                print("[*] Login sayfasina yonlendirildi.", flush=True)
                break

            # Dashboard veya baska panel sayfasindaysa
            if "dashboard" in title.lower() or "cronos" in title.lower():
                if not self._is_login_page(title, url):
                    # Gercekten paneldeyiz, session gecerli
                    print("[+] Session gecerli! Login atlaniyor.", flush=True)
                    await self.save_session()
                    return True
        else:
            # 5 kontrol sonunda hala login degilse, gecerli say
            if not self._is_login_page(title, url):
                print("[+] Session gecerli! Login atlaniyor.", flush=True)
                await self.save_session()
                return True

        # Chrome profili yetmedi, localStorage backup dene
        print("[*] Session gecersiz, localStorage backup deneniyor...", flush=True)
        restored = await self.restore_session()
        if restored:
            await self._tab.go_to(CRONOS_BASE_URL)
            await asyncio.sleep(8)
            title = await self._js("return document.title") or ""
            url = await self._js("return window.location.href") or ""
            if not self._is_login_page(title, url):
                print("[+] localStorage ile session kurtarildi!", flush=True)
                return True

        # Hicbiri ise yaramadi, kullanicidan login iste
        print("[*] Otomatik session kurtarilamadi.", flush=True)
        return False

    # ── Login & Session ──────────────────────────────────────────

    def _is_login_page(self, title="", url=""):
        """Title veya URL login sayfasina mi isaret ediyor?"""
        t = (title or "").lower()
        u = (url or "").lower()
        # Turkce: "Giriş Yap", Ingilizce: "Login"
        if "login" in t or "giriş" in t or "giris" in t:
            return True
        if "/login" in u:
            return True
        return False

    async def wait_for_login(self, max_wait=600):
        """Manuel login bekleme."""
        print("[*] Login bekleniyor...", flush=True)
        print("[*] Bot'un actigi Chrome penceresinden giris yapin!", flush=True)

        elapsed = 0
        while elapsed < max_wait:
            await asyncio.sleep(3)
            elapsed += 3

            try:
                title = await self._js("return document.title")
                url = await self._js("return window.location.href")
            except Exception as exc:
                if elapsed % 15 == 0:
                    print(f"[*] Sayfa okunamiyor ({elapsed}s): {exc}", flush=True)
                continue

            t = (title or "").lower()

            if elapsed % 15 == 0:
                print(f"[*] ({elapsed}s) Title: {title}", flush=True)

            if "dakika" in t or "checking" in t or "just a moment" in t:
                continue
            if self._is_login_page(title, url):
                continue

            print(f"[+] Panel acildi! Title: {title}", flush=True)
            await asyncio.sleep(2)
            await self.save_session()
            return True

        print("[!] Login zaman asimi!", flush=True)
        return False

    async def is_logged_in(self):
        """Session hala gecerli mi kontrol et."""
        try:
            title = await self._js("return document.title")
            url = await self._js("return window.location.href")
            t = (title or "").lower()
            if self._is_login_page(title, url):
                return False
            if "dakika" in t or "checking" in t or "just a moment" in t:
                return False
            return True
        except Exception:
            return False

    # ── Element Helpers (insan gibi tikla) ───────────────────────

    async def _click_element(self, css_selector, timeout=10):
        """CSS selector ile element bul ve tikla."""
        try:
            el = await self._tab.query(css_selector, timeout=timeout)
            if el:
                await el.click()
                return True
        except Exception as e:
            print(f"[!] Tiklanamadi ({css_selector}): {e}", flush=True)
        return False

    async def _select_option_by_index(self, select_index, option_value, label=""):
        """
        Sayfadaki N'inci select'te option sec (JS ile).
        select_index: 0-based index (document.querySelectorAll('select')[index])
        option_value: secilecek option'un value'su
        label: log icin etiket
        """
        js = (
            "var s = document.querySelectorAll('select')[" + str(select_index) + "]; "
            "if(s) { "
            "  s.value = '" + str(option_value) + "'; "
            "  s.dispatchEvent(new Event('change', {bubbles:true})); "
            "  s.dispatchEvent(new Event('input', {bubbles:true})); "
            "  return s.value; "
            "} return null;"
        )
        result = await self._js("return (function() { " + js + " })()")
        if result is not None:
            print(f"  [OK] {label} (value={result})", flush=True)
            return True
        else:
            print(f"  [!] {label} - select bulunamadi", flush=True)
            return False

    async def _get_element_text(self, css_selector, timeout=5):
        """Element'in text'ini oku."""
        try:
            el = await self._tab.query(css_selector, timeout=timeout, raise_exc=False)
            if el:
                return await el.text
        except Exception:
            pass
        return ""

    # ── Filtreleme (tikla + sec) ─────────────────────────────────

    async def set_withdrawal_filters(self):
        """
        Cekim sayfasindaki filtreleri TIKLAYARAK ayarla:
        - Tur = Para Cekme (value=2)
        - Durum = Beklemede (value=0)
        - Bonus = Hayir (value=2) - genelde varsayilan
        Sonra ARAMA butonuna tikla.

        Sayfadaki select siralari (DOM'dan dogrulanmis):
          select:nth-of-type(1) -> Tur
          select:nth-of-type(2) -> Bonus
          select:nth-of-type(3) -> Para Birimi
          select:nth-of-type(4) -> Durum
        """
        print("[*] Filtreler ayarlaniyor...", flush=True)

        # Select siralari (Chrome DOM'dan dogrulanmis):
        #   [0] Tur: Tumu, Para Yatirma=1, Para Cekme=2
        #   [1] Bonus: Tumu, Evet=1, Hayir=2
        #   [2] Para Birimi: TRY=1, ...
        #   [3] Durum: Tumu, Beklemede=0, Onaylandi=1, ...

        # 1) Tur = Para Cekme (2)
        tur_ok = await self._select_option_by_index(0, "2", "Tur=Para Cekme")
        await asyncio.sleep(0.5)

        # 2) Bonus = Hayir (2)
        bonus_ok = await self._select_option_by_index(1, "2", "Bonus=Hayir")
        await asyncio.sleep(0.5)

        # 3) Durum = Beklemede (0)
        durum_ok = await self._select_option_by_index(3, "0", "Durum=Beklemede")

        await asyncio.sleep(0.5)

        print(f"[*] Filtre sonuclari: Tur={tur_ok}, Bonus={bonus_ok}, Durum={durum_ok}", flush=True)

        # ARAMA butonuna tikla
        print("[*] ARAMA butonuna tiklaniyor...", flush=True)
        arama_clicked = False

        # Yontem 1: "Arama" text'li link bul
        try:
            links = await self._tab.query("a", find_all=True, timeout=5)
            if links:
                for link in links:
                    try:
                        text = await link.text
                        if text and text.strip() in ("Arama", "ARAMA", "Ara"):
                            await link.click()
                            arama_clicked = True
                            print("[+] ARAMA tiklandi!", flush=True)
                            break
                    except Exception:
                        continue
        except Exception as e:
            print(f"[!] Link arama hatasi: {e}", flush=True)

        if not arama_clicked:
            print("[!] ARAMA butonu bulunamadi, JS ile deneniyor...", flush=True)
            # Yedek: JS ile tikla
            await self._js("""
                var els = document.querySelectorAll('a, button');
                for (var i = 0; i < els.length; i++) {
                    var t = els[i].textContent.trim();
                    if (t === 'Arama' || t === 'ARAMA') { els[i].click(); break; }
                }
            """)
            arama_clicked = True

        # Tablonun yuklenmesini bekle
        await asyncio.sleep(3)

        for _ in range(15):
            try:
                td_el = await self._tab.query(
                    "table tbody tr td", timeout=1, raise_exc=False
                )
                if td_el:
                    self._filters_set = True
                    print("[+] Filtreler uygulandi, tablo yuklendi!", flush=True)
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)

        # Bos sonuc olabilir
        self._filters_set = True
        print("[*] Filtreler uygulandi (sonuc bos olabilir).", flush=True)
        return True

    # ── Navigasyon ───────────────────────────────────────────────

    async def navigate_to_withdrawals(self):
        """Cekim sayfasina git, filtrele, tablonun yuklenmesini bekle."""
        current_url = await self._js("return window.location.href") or ""

        if "/financial/financial-transactions" in current_url and self._filters_set:
            # Zaten sayfadayiz, ARAMA'ya tekrar tiklayarak yenile
            print("[*] Cekim sayfasi yenileniyor...", flush=True)

            try:
                links = await self._tab.query("a", find_all=True, timeout=5)
                if links:
                    for link in links:
                        try:
                            text = await link.text
                            if text and text.strip() in ("Arama", "ARAMA", "Ara"):
                                await link.click()
                                break
                        except Exception:
                            continue
            except Exception:
                # JS fallback
                await self._js("""
                    var els = document.querySelectorAll('a');
                    for (var i = 0; i < els.length; i++) {
                        if (els[i].textContent.trim() === 'Arama') { els[i].click(); break; }
                    }
                """)

            await asyncio.sleep(3)
            print("[+] Cekim sayfasi yenilendi!", flush=True)
            return True
        else:
            # Cekim sayfasina git
            print("[*] Cekim sayfasina gidiliyor...", flush=True)
            await self._tab.go_to(WITHDRAWALS_URL)

            # Sayfanin yuklenmesini bekle
            for _ in range(20):
                await asyncio.sleep(1)
                try:
                    tr = await self._tab.query(
                        "table tbody tr", timeout=1, raise_exc=False
                    )
                    if tr:
                        await asyncio.sleep(2)
                        print("[+] Cekim sayfasi yuklendi!", flush=True)
                        break
                except Exception:
                    pass
            else:
                print("[!] Cekim sayfasi yuklenemedi!", flush=True)
                return False

            # Filtreleri ayarla
            self._filters_set = False
            return await self.set_withdrawal_filters()

    # ── Veri Okuma ───────────────────────────────────────────────

    async def _read_pagination_total(self):
        """v-data-footer'dan toplam kayit sayisini oku. '1-50 of 62' -> 62"""
        total = await self._js_json("""
            var footer = document.querySelector('.v-data-footer');
            if (!footer) return null;
            var text = footer.innerText;
            var m = text.match(/(\\d+)\\s*[-]\\s*(\\d+)\\s*(?:of|\\/)\\s*(\\d+)/);
            if (m) return {from: parseInt(m[1]), to: parseInt(m[2]), total: parseInt(m[3])};
            return null;
        """)
        return total

    async def _read_table(self):
        """Sayfadaki tabloyu oku, satirlari dict listesi olarak dondur."""
        items = await self._js_json("""
            var rows = document.querySelectorAll('table tbody tr');
            var items = [];

            for (var i = 0; i < rows.length; i++) {
                var row = rows[i];
                var tds = row.querySelectorAll('td');
                if (tds.length < 10) continue;

                var cells = [];
                for (var j = 0; j < tds.length; j++) {
                    cells.push(tds[j].textContent.trim());
                }

                var userLink = row.querySelector('a[href*="customer-detail"]');
                var playerHref = userLink ? userLink.getAttribute('href') : '';
                var playerIdMatch = playerHref.match(/customer-detail\\/(\\d+)/);
                var playerId = playerIdMatch ? playerIdMatch[1] : cells[2];

                var statusSpan = row.querySelector('td:nth-child(10) span');
                var status = statusSpan ? statusSpan.textContent.trim() : cells[9];

                var hasAccept = row.innerHTML.indexOf('Kabul et') !== -1;
                var hasReject = row.innerHTML.indexOf('Reddet') !== -1;

                items.push({
                    id: cells[0] || '',
                    type: cells[1] || '',
                    player_id: playerId || '',
                    username: cells[3] || '',
                    full_name: cells[4] || '',
                    amount: cells[5] || '',
                    extra: cells[6] || '',
                    payment_method: (cells[7] || '').replace('edit', '').trim(),
                    note: cells[8] || '',
                    status: status || '',
                    manager_note: cells[10] || '',
                    created_at: cells[11] || '',
                    updated_at: cells[12] || '',
                    manager: cells[13] || '',
                    has_accept_btn: hasAccept,
                    has_reject_btn: hasReject
                });
            }

            return items;
        """)
        return items or []

    def _calc_total(self, items):
        """Cekim listesinin toplam tutarini hesapla."""
        total = 0
        for item in items:
            try:
                amt_str = item.get("amount", "0")
                amt_clean = amt_str.replace("TRY", "").replace("TL", "").strip()
                amt_clean = amt_clean.replace(".", "").replace(",", ".")
                total += float(amt_clean)
            except (ValueError, AttributeError):
                pass
        return total

    async def _ensure_vue_component(self):
        """
        Vue financial component'ini bul ve window._finComp'a ata.
        Sayfa yuklendiginde bir kez cagrilir, sonra her filtrede kullanilir.
        """
        comp = await self._js_json("""
            if (window._finComp && window._finComp.$data && 'financial_list' in window._finComp.$data) {
                return {status: window._finComp.$data.status, total: window._finComp.$data.total};
            }
            var app = document.getElementById('app');
            if (!app || !app.__vue__) return null;
            var root = app.__vue__;
            try {
                var vApp = root.$children[0].$children[0];
                var children = vApp.$children || [];
                for (var i = 0; i < children.length; i++) {
                    var c = children[i];
                    if (c.$data && 'financial_list' in c.$data) {
                        window._finComp = c;
                        return {status: c.$data.status, total: c.$data.total};
                    }
                }
            } catch(e) {}
            return null;
        """)
        return comp is not None

    async def _set_status_filter(self, status_value, label):
        """
        Vue component data'sini dogrudan set edip getData() cagir.
        DOM select manipulasyonu yerine Vue reactivity kullanir.
        getData() API cagrisi yapar, total degismesini bekleriz.
        """
        # Onceki total'i oku
        prev_state = await self._js_json("""
            var c = window._finComp;
            if (!c) return null;
            return {total: c.$data.total, loading: c.$data.loading};
        """)
        prev_total = prev_state["total"] if prev_state else None

        # Vue component data'sini dogrudan set et
        result = await self._js_json("""
            var c = window._finComp;
            if (!c) return null;

            c.$set(c.$data, 'type', '2');
            c.$set(c.$data, 'bonus', '2');
            c.$set(c.$data, 'status', '""" + str(status_value) + """');

            var selects = document.querySelectorAll('select');
            if (selects[0]) selects[0].value = '2';
            if (selects[1]) selects[1].value = '2';
            if (selects[3]) selects[3].value = '""" + str(status_value) + """';

            return {status: c.$data.status, type: c.$data.type, bonus: c.$data.bonus};
        """)

        if not result:
            print(f"  [!] Vue component bulunamadi, {label} filtrelemesi basarisiz!", flush=True)
            return False

        print(f"  [OK] Tur=Para Cekme, Bonus=Hayir, Durum={label} (value={status_value})", flush=True)

        # getData() cagir (Vue component'in kendi API metodu)
        await self._js("window._finComp.getData()")

        # 1) Once loading=True olmasini bekle (API istegi baslasin)
        for _ in range(10):
            await asyncio.sleep(0.2)
            loading = await self._js_json("""
                var c = window._finComp;
                return c ? {loading: c.$data.loading} : null;
            """)
            if loading and loading.get("loading"):
                break

        # 2) Sonra loading=False olmasini bekle (API yaniti gelsin)
        for _ in range(30):
            await asyncio.sleep(0.3)
            state = await self._js_json("""
                var c = window._finComp;
                if (!c) return null;
                return {total: c.$data.total, loading: c.$data.loading};
            """)
            if state and not state.get("loading"):
                break

        return True

    async def get_pending_withdrawals(self):
        """
        Cekim tablosundaki verileri oku (sadece aktif filtre).
        Tablo satirlarini element element okur (insan gibi).
        """
        ok = await self.navigate_to_withdrawals()
        if not ok:
            return []

        await asyncio.sleep(1)
        items = await self._read_table()

        count = len(items)
        total = self._calc_total(items)
        print(f"[+] {count} cekim bulundu, toplam: {total:,.0f} TRY", flush=True)

        for i, item in enumerate(items[:3]):
            print(
                f"  [{i+1}] #{item['id']} - {item['username']} - "
                f"{item['amount']} - {item['status']}",
                flush=True,
            )
        if count > 3:
            print(f"  ... ve {count - 3} cekim daha", flush=True)

        return items

    async def scan_all_statuses(self):
        """
        3 durum icin sirayla filtrele ve tabloyu oku.
        Vue component'inin data'sini dogrudan set ederek filtreler.
        getData() ile API cagrisi yapar, total degismesini bekler.
        Sonuc: { "beklemede": [...], "reserve": [...], "islemde": [...] }
        """
        # Durum select option degerleri (DOM'dan dogrulanmis):
        #   0=Beklemede, 1=Onaylandi, 2=Reddedildi, 3=Islemde, 4=Reserve Edildi
        statuses = [
            (0, "beklemede", "Beklemede"),
            (4, "reserve", "Reserve Edildi"),
            (3, "islemde", "Islemde"),
        ]

        # Cekim sayfasina git (ilk seferde veya farkli sayfadaysak)
        current_url = await self._js("return window.location.href") or ""
        if "/financial/financial-transactions" not in current_url:
            print("[*] Cekim sayfasina gidiliyor...", flush=True)
            await self._tab.go_to(WITHDRAWALS_URL)
            for _ in range(20):
                await asyncio.sleep(1)
                try:
                    tr = await self._tab.query(
                        "table tbody tr", timeout=1, raise_exc=False
                    )
                    if tr:
                        await asyncio.sleep(2)
                        print("[+] Cekim sayfasi yuklendi!", flush=True)
                        break
                except Exception:
                    pass
            else:
                print("[!] Cekim sayfasi yuklenemedi!", flush=True)
                return None

        # Vue component'ini bul (sayfa yuklendikten sonra)
        vue_ok = await self._ensure_vue_component()
        if not vue_ok:
            print("[!] Vue component bulunamadi!", flush=True)
            return None

        result = {}

        for filter_val, key, label in statuses:
            # Vue uzerinden filtrele ve getData() cagir
            ok = await self._set_status_filter(filter_val, label)
            if not ok:
                print(f"  [!] {label} filtrelemesi basarisiz!", flush=True)
                result[key] = []
                result[f"{key}_total_count"] = 0
                continue

            # Tabloyu oku
            items = await self._read_table()
            total = self._calc_total(items)

            # Total'i Vue component'tan oku (en guvenilir)
            vue_total = await self._js_json("""
                var c = window._finComp;
                return c ? {total: c.$data.total} : null;
            """)
            real_count = vue_total["total"] if vue_total else len(items)

            result[key] = items
            result[f"{key}_total_count"] = real_count
            print(f"  [{label}] {real_count} cekim ({len(items)} gorunen), {total:,.0f} TRY", flush=True)

        return result

    async def refresh_withdrawals_page(self):
        """Cekim sayfasini yenile."""
        try:
            return await self.navigate_to_withdrawals()
        except Exception as e:
            print(f"[!] Sayfa yenileme hatasi: {e}", flush=True)
            return False
