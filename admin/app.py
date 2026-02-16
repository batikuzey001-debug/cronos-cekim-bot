"""
Cronos Cekim Bot - Web Panel
=============================
Bekleyen cekimleri gormek icin web arayuzu.
Bot tarafinda taranan veriler burada gosterilir.

Kullanim:
    uvicorn admin.app:app --host 0.0.0.0 --port 8000
"""
import logging
import json
import os
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

# Bot'un son tarama sonuclari burada tutulur (in-memory)
bot_state = {
    "last_scan": None,
    "pending_count": 0,
    "pending_total": 0,
    "pending_items": [],
    "beklemede_count": 0,
    "beklemede_total": 0,
    "beklemede_items": [],
    "reserve_count": 0,
    "reserve_total": 0,
    "reserve_items": [],
    "islemde_count": 0,
    "islemde_total": 0,
    "islemde_items": [],
    "bot_status": "baslatilamadi",
    "login_user": None,
    "scan_count": 0,
    "errors": [],
}

DATA_FILE = Path("bot_data.json")


def load_bot_data():
    """Disk'ten bot verisini yukle."""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                bot_state.update(data)
        except Exception:
            pass


def save_bot_data():
    """Bot verisini disk'e kaydet."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(bot_state, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Veritabani opsiyonel - yoksa sessizce atla
    try:
        from database.db import init_db
        init_db()
    except Exception as e:
        logger.info("Veritabani atlanıyor (opsiyonel): %s", e)
    load_bot_data()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    """Railway / load balancer health check."""
    return {"status": "ok"}


@app.get("/api/status")
def api_status():
    """Bot durumu ve ozet bilgi (3 durum dahil)."""
    return {
        "status": bot_state["bot_status"],
        "last_scan": bot_state["last_scan"],
        "login_user": bot_state["login_user"],
        "scan_count": bot_state["scan_count"],
        "beklemede": {
            "count": bot_state.get("beklemede_count", 0),
            "total": bot_state.get("beklemede_total", 0),
        },
        "reserve": {
            "count": bot_state.get("reserve_count", 0),
            "total": bot_state.get("reserve_total", 0),
        },
        "islemde": {
            "count": bot_state.get("islemde_count", 0),
            "total": bot_state.get("islemde_total", 0),
        },
    }


@app.get("/api/withdrawals")
def api_withdrawals():
    """Tum durumlardaki cekim listeleri."""
    return {
        "beklemede": {
            "count": bot_state.get("beklemede_count", 0),
            "total": bot_state.get("beklemede_total", 0),
            "items": bot_state.get("beklemede_items", []),
        },
        "reserve": {
            "count": bot_state.get("reserve_count", 0),
            "total": bot_state.get("reserve_total", 0),
            "items": bot_state.get("reserve_items", []),
        },
        "islemde": {
            "count": bot_state.get("islemde_count", 0),
            "total": bot_state.get("islemde_total", 0),
            "items": bot_state.get("islemde_items", []),
        },
        "last_scan": bot_state["last_scan"],
    }


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Ana panel sayfasi."""
    return HTML_TEMPLATE


# ---- HTML Template ----

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cronos Cekim Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-bottom: 1px solid #334155;
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 20px; color: #f8fafc; }
        .header h1 span { color: #f59e0b; }
        .header-right { display: flex; align-items: center; gap: 12px; }
        .status-badge {
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
        }
        .status-ok { background: #065f46; color: #6ee7b7; }
        .status-err { background: #7f1d1d; color: #fca5a5; }
        .status-wait { background: #78350f; color: #fcd34d; }

        .container { max-width: 1400px; margin: 0 auto; padding: 24px; }

        /* Durum kartlari - 3 sutun */
        .status-cards {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-bottom: 16px;
        }
        .status-card {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            border-left: 4px solid;
            cursor: pointer;
            transition: transform 0.15s, box-shadow 0.15s;
        }
        .status-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .status-card.active { box-shadow: 0 0 0 2px rgba(255,255,255,0.2); }
        .status-card.beklemede { border-color: #eab308; }
        .status-card.reserve { border-color: #a855f7; }
        .status-card.islemde { border-color: #3b82f6; }

        .sc-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .sc-label { font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        .sc-label.beklemede { color: #eab308; }
        .sc-label.reserve { color: #a855f7; }
        .sc-label.islemde { color: #3b82f6; }
        .sc-dot {
            width: 8px; height: 8px; border-radius: 50%;
            animation: pulse 2s infinite;
        }
        .sc-dot.beklemede { background: #eab308; }
        .sc-dot.reserve { background: #a855f7; }
        .sc-dot.islemde { background: #3b82f6; }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        .sc-row { display: flex; justify-content: space-between; align-items: baseline; }
        .sc-count { font-size: 36px; font-weight: 800; color: #f8fafc; }
        .sc-total { font-size: 18px; font-weight: 700; color: #f59e0b; }
        .sc-unit { font-size: 13px; color: #94a3b8; margin-left: 4px; }

        /* Info kartlari */
        .info-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }
        .info-card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 10px;
            padding: 14px 16px;
        }
        .info-label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
        .info-value { font-size: 16px; font-weight: 600; margin-top: 4px; color: #cbd5e1; }

        /* Tablo */
        .table-wrapper {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            overflow: hidden;
        }
        .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            border-bottom: 1px solid #334155;
        }
        .table-header h2 { font-size: 16px; color: #f8fafc; }
        .tab-buttons { display: flex; gap: 6px; }
        .tab-btn {
            padding: 6px 14px;
            border-radius: 6px;
            border: 1px solid #475569;
            background: transparent;
            color: #94a3b8;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.15s;
        }
        .tab-btn:hover { background: #334155; color: #e2e8f0; }
        .tab-btn.active-tab { color: #f8fafc; }
        .tab-btn.active-tab.beklemede { background: #854d0e; border-color: #eab308; color: #fef08a; }
        .tab-btn.active-tab.reserve { background: #581c87; border-color: #a855f7; color: #e9d5ff; }
        .tab-btn.active-tab.islemde { background: #1e3a5f; border-color: #3b82f6; color: #bfdbfe; }

        .search-box {
            padding: 12px 20px;
            border-bottom: 1px solid #334155;
        }
        .search-box input {
            width: 100%;
            padding: 10px 14px;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            color: #e2e8f0;
            font-size: 14px;
            outline: none;
        }
        .search-box input:focus { border-color: #f59e0b; }

        table { width: 100%; border-collapse: collapse; }
        thead th {
            text-align: left;
            padding: 12px 16px;
            font-size: 12px;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #334155;
            background: #1e293b;
            position: sticky;
            top: 0;
        }
        tbody tr { border-bottom: 1px solid #1e293b; }
        tbody tr:hover { background: #1e293b80; }
        tbody td {
            padding: 12px 16px;
            font-size: 14px;
            white-space: nowrap;
        }
        .amount-cell { font-weight: 700; color: #f59e0b; }
        .username-cell { color: #38bdf8; }
        .date-cell { color: #94a3b8; font-size: 13px; }
        .method-cell {
            font-size: 12px;
            padding: 4px 8px;
            background: #334155;
            border-radius: 4px;
            display: inline-block;
        }
        .status-cell {
            font-size: 12px;
            padding: 3px 10px;
            border-radius: 12px;
            font-weight: 600;
            display: inline-block;
        }
        .status-cell.beklemede { background: #854d0e; color: #fef08a; }
        .status-cell.reserve { background: #581c87; color: #e9d5ff; }
        .status-cell.islemde { background: #1e3a5f; color: #bfdbfe; }

        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #64748b;
        }
        .empty-state .icon { font-size: 48px; margin-bottom: 12px; }

        .last-update {
            text-align: center;
            padding: 12px;
            color: #64748b;
            font-size: 12px;
        }
        .scroll-table {
            max-height: 600px;
            overflow-y: auto;
        }

        @media (max-width: 768px) {
            .status-cards { grid-template-columns: 1fr; }
            .info-cards { grid-template-columns: repeat(2, 1fr); }
            .container { padding: 12px; }
            .sc-count { font-size: 28px; }
            tbody td, thead th { padding: 8px 10px; font-size: 12px; }
            .tab-buttons { flex-wrap: wrap; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1><span>CRONOS</span> Cekim Bot</h1>
        <div class="header-right">
            <span id="statusBadge" class="status-badge status-wait">Yukleniyor...</span>
        </div>
    </div>

    <div class="container">
        <!-- Durum Kartlari -->
        <div class="status-cards">
            <div class="status-card beklemede active" onclick="switchTab('beklemede')">
                <div class="sc-header">
                    <span class="sc-label beklemede">Beklemede</span>
                    <span class="sc-dot beklemede"></span>
                </div>
                <div class="sc-row">
                    <div><span class="sc-count" id="bekCount">0</span><span class="sc-unit">cekim</span></div>
                    <div class="sc-total" id="bekTotal">0 TL</div>
                </div>
            </div>
            <div class="status-card reserve" onclick="switchTab('reserve')">
                <div class="sc-header">
                    <span class="sc-label reserve">Reserve Edildi</span>
                    <span class="sc-dot reserve"></span>
                </div>
                <div class="sc-row">
                    <div><span class="sc-count" id="resCount">0</span><span class="sc-unit">cekim</span></div>
                    <div class="sc-total" id="resTotal">0 TL</div>
                </div>
            </div>
            <div class="status-card islemde" onclick="switchTab('islemde')">
                <div class="sc-header">
                    <span class="sc-label islemde">Islemde</span>
                    <span class="sc-dot islemde"></span>
                </div>
                <div class="sc-row">
                    <div><span class="sc-count" id="islCount">0</span><span class="sc-unit">cekim</span></div>
                    <div class="sc-total" id="islTotal">0 TL</div>
                </div>
            </div>
        </div>

        <!-- Bilgi Kartlari -->
        <div class="info-cards">
            <div class="info-card">
                <div class="info-label">Son Tarama</div>
                <div class="info-value" id="lastScan">-</div>
            </div>
            <div class="info-card">
                <div class="info-label">Tarama Sayisi</div>
                <div class="info-value" id="scanCount">-</div>
            </div>
        </div>

        <!-- Tablo -->
        <div class="table-wrapper">
            <div class="table-header">
                <h2 id="tableTitle">Beklemede</h2>
                <div class="tab-buttons">
                    <button class="tab-btn active-tab beklemede" onclick="switchTab('beklemede')">Beklemede</button>
                    <button class="tab-btn" onclick="switchTab('reserve')">Reserve</button>
                    <button class="tab-btn" onclick="switchTab('islemde')">Islemde</button>
                    <button class="tab-btn" onclick="loadData()" style="margin-left:8px;border-color:#334155">Yenile</button>
                </div>
            </div>
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="Ara... (kullanici adi, isim, tutar)" oninput="filterTable()">
            </div>
            <div class="scroll-table">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Kullanici</th>
                            <th>Ad Soyad</th>
                            <th>Tutar</th>
                            <th>Odeme Yontemi</th>
                            <th>Durum</th>
                            <th>Tarih</th>
                            <th>Not</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody">
                        <tr><td colspan="8" class="empty-state"><div class="icon">&#128270;</div>Veri yukleniyor...</td></tr>
                    </tbody>
                </table>
            </div>
            <div class="last-update" id="lastUpdate"></div>
        </div>
    </div>

    <script>
        let allData = { beklemede: [], reserve: [], islemde: [] };
        let currentTab = 'beklemede';
        const tabTitles = { beklemede: 'Beklemede', reserve: 'Reserve Edildi', islemde: 'Islemde' };

        function formatMoney(val) {
            if (typeof val === 'number') {
                return val.toLocaleString('tr-TR', {minimumFractionDigits: 0, maximumFractionDigits: 0}) + ' TL';
            }
            let s = String(val).replace(/TRY|TL|\u20ba/gi, '').trim();
            s = s.replace(/\./g, '').replace(',', '.');
            const n = parseFloat(s) || 0;
            return n.toLocaleString('tr-TR', {minimumFractionDigits: 0, maximumFractionDigits: 0}) + ' TL';
        }

        function formatTime(dateStr) {
            if (!dateStr) return '-';
            const d = new Date(dateStr);
            const hh = String(d.getHours()).padStart(2, '0');
            const mm = String(d.getMinutes()).padStart(2, '0');
            const ss = String(d.getSeconds()).padStart(2, '0');
            return hh + ':' + mm + ':' + ss;
        }

        function statusClass(item) {
            const s = (item.status || '').toLowerCase();
            if (s.includes('bekle')) return 'beklemede';
            if (s.includes('reserve') || s.includes('rezerve')) return 'reserve';
            if (s.includes('isle') || s.includes('process')) return 'islemde';
            return 'beklemede';
        }

        function renderTable(items) {
            const tbody = document.getElementById('tableBody');
            if (!items || items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="empty-state"><div class="icon">&#9989;</div>Bu durumda cekim yok</td></tr>';
                return;
            }
            tbody.innerHTML = items.map(item => `
                <tr>
                    <td>#${item.id}</td>
                    <td class="username-cell">${item.username || '-'}</td>
                    <td>${item.full_name || '-'}</td>
                    <td class="amount-cell">${formatMoney(item.amount)}</td>
                    <td><span class="method-cell">${(item.payment_method || '-').replace('Withdraw - ', '')}</span></td>
                    <td><span class="status-cell ${statusClass(item)}">${item.status || '-'}</span></td>
                    <td class="date-cell">${item.created_at || '-'}</td>
                    <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${item.manager_note || '-'}</td>
                </tr>
            `).join('');
        }

        function switchTab(tab) {
            currentTab = tab;
            document.getElementById('tableTitle').textContent = tabTitles[tab];

            // Tab butonlari
            document.querySelectorAll('.tab-btn').forEach(b => {
                b.classList.remove('active-tab', 'beklemede', 'reserve', 'islemde');
            });
            const btns = document.querySelectorAll('.tab-btn');
            btns.forEach(b => {
                if (b.textContent.trim().toLowerCase().startsWith(tab.substring(0, 3))) {
                    b.classList.add('active-tab', tab);
                }
            });

            // Kart vurgulama
            document.querySelectorAll('.status-card').forEach(c => c.classList.remove('active'));
            document.querySelector('.status-card.' + tab).classList.add('active');

            // Tablo
            document.getElementById('searchInput').value = '';
            renderTable(allData[tab] || []);
        }

        function filterTable() {
            const q = document.getElementById('searchInput').value.toLowerCase();
            const items = allData[currentTab] || [];
            if (!q) { renderTable(items); return; }
            const filtered = items.filter(i =>
                (i.username || '').toLowerCase().includes(q) ||
                (i.full_name || '').toLowerCase().includes(q) ||
                String(i.amount).includes(q) ||
                String(i.id).includes(q) ||
                (i.payment_method || '').toLowerCase().includes(q)
            );
            renderTable(filtered);
        }

        async function loadData() {
            try {
                const sr = await fetch('/api/status');
                const status = await sr.json();

                const badge = document.getElementById('statusBadge');
                if (status.status === 'calisiyor') {
                    badge.textContent = 'Calisiyor';
                    badge.className = 'status-badge status-ok';
                } else if (status.status === 'hata') {
                    badge.textContent = 'Hata';
                    badge.className = 'status-badge status-err';
                } else {
                    badge.textContent = status.status || 'Bilinmiyor';
                    badge.className = 'status-badge status-wait';
                }

                document.getElementById('scanCount').textContent = status.scan_count || 0;
                document.getElementById('lastScan').textContent = status.last_scan ? formatTime(status.last_scan) : 'Henuz taranmadi';

                // Durum kartlarini guncelle
                const bek = status.beklemede || {};
                const res = status.reserve || {};
                const isl = status.islemde || {};

                document.getElementById('bekCount').textContent = bek.count || 0;
                document.getElementById('bekTotal').textContent = formatMoney(bek.total || 0);
                document.getElementById('resCount').textContent = res.count || 0;
                document.getElementById('resTotal').textContent = formatMoney(res.total || 0);
                document.getElementById('islCount').textContent = isl.count || 0;
                document.getElementById('islTotal').textContent = formatMoney(isl.total || 0);

                // Cekim listelerini al
                const wr = await fetch('/api/withdrawals');
                const data = await wr.json();

                allData.beklemede = (data.beklemede || {}).items || [];
                allData.reserve = (data.reserve || {}).items || [];
                allData.islemde = (data.islemde || {}).items || [];

                // Aktif tab'i renderla
                renderTable(allData[currentTab] || []);

                document.getElementById('lastUpdate').textContent =
                    'Son guncelleme: ' + new Date().toLocaleTimeString('tr-TR');
            } catch(e) {
                document.getElementById('statusBadge').textContent = 'Baglanti Hatasi';
                document.getElementById('statusBadge').className = 'status-badge status-err';
            }
        }

        loadData();
        setInterval(loadData, 10000);
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("admin.app:app", host="127.0.0.1", port=8001, reload=True)
