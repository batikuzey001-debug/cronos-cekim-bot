"""
Finansal işlemler sayfasından bekleyen para çekme taleplerini okur.
"""
from decimal import Decimal
import re
from playwright.async_api import Page


async def get_pending_withdrawals(page: Page) -> list:
    """
    Beklemede çekimleri bulur: "Kabul et" ve "Reddet" butonları olan satırlar.
    Sadece "Para Çekme" ve bu butonların göründüğü satırları alır.

    Her satırdan:
    - İşlem ID: 1. sütun (td:nth-child(1) > a)
    - Oyuncu adı: 4. sütun (td:nth-child(4) > a)
    - Tutar: 6. sütun (td:nth-child(6))
    - Tarih: 12. sütun (td:nth-child(12))

    Returns:
        [{"id": str, "oyuncu": str, "tutar": Decimal|str, "tarih": str}, ...]
    """
    result = []
    # Kabul et (.button.i-green) ve Reddet (.button.i-red) olan satırlar = beklemede
    rows = page.locator("tr:has(.button.i-green):has(.button.i-red)")
    n = await rows.count()
    for i in range(n):
        row = rows.nth(i)
        row_text = (await row.text_content()) or ""
        if "Para Çekme" not in row_text:
            continue
        try:
            id_el = row.locator("td:nth-child(1) > a")
            oyuncu_el = row.locator("td:nth-child(4) > a")
            tutar_el = row.locator("td:nth-child(6)")
            tarih_el = row.locator("td:nth-child(12)")
            cekim_id = (await id_el.text_content() or "").strip() if await id_el.count() else ""
            oyuncu = (await oyuncu_el.text_content() or "").strip() if await oyuncu_el.count() else ""
            tutar_raw = (await tutar_el.text_content() or "").strip() if await tutar_el.count() else ""
            tarih = (await tarih_el.text_content() or "").strip() if await tarih_el.count() else ""
        except Exception:
            continue
        tutar_val: str | Decimal = tutar_raw
        if tutar_raw:
            num_str = re.sub(r"[^\d,.\-]", "", tutar_raw).replace(",", ".")
            if num_str:
                try:
                    tutar_val = Decimal(num_str)
                except Exception:
                    pass
        result.append({
            "id": cekim_id,
            "oyuncu": oyuncu,
            "tutar": tutar_val,
            "tarih": tarih,
        })
    return result
