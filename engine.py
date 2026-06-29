import feedparser
import json
import os
import re
import time
import copy
import hashlib
import urllib.parse
from datetime import datetime, date
import requests

# ============================================================
# 1. DATA SUMBER: LEMBAGA & KEYWORD (KOMISI IV DPR RI PARTNERS)
# ============================================================
AGENCIES = {
    "Kementerian Pertanian": "Kementerian Pertanian OR Kementan",
    "Kementerian Kehutanan": "Kementerian Kehutanan OR Kemenhut",
    "Kementerian Kelautan dan Perikanan": "Kementerian Kelautan dan Perikanan OR KKP",
    "Badan Karantina Indonesia": "Badan Karantina Indonesia OR Barantin",
    "Badan Pangan Nasional": "Badan Pangan Nasional OR Bapanas",
    "Perum Bulog": "Perum Bulog OR Bulog"
}

# ============================================================
# 2. DATA ANGGOTA KOMISI IV DPR RI (2024-2029)
# ============================================================
KOMISI4_MEMBERS = {
    "PDI-P": ["Alex Indra Lukman", "Sonny T. Danaparamita", "Mayjen TNI (Purn) Sturman Panjaitan", "Rokhmin Dahuri", "I Nyoman Adi Wiryatama", "Paolus Hadi", "Agus Ambo Djiwa", "I Ketut Suwendra", "Edoardus Kaize"],
    "Golkar": ["Panggah Susanto", "Robert Joppy Kardinal", "Adrianus Asia Sidot", "Eko Wahyudi", "Firman Subagyo", "Alien Mus", "Dadang M Naser", "Ilham Pangestu"],
    "Gerindra": ["Siti Hediati Soeharto", "Darori Wonodipuro", "Dwita Ria Gunadi", "Endang Setyawati Thohari", "TA Khalid", "Sumail Abdullah", "Melati"],
    "NasDem": ["Sulaeman L Hamzah", "Ananda Tohpati", "Cindy Monica Salsabila Setiawan", "Rajiv", "Arief Rahman", "Muhammad Habibur Rochman"],
    "PKB": ["Jaelani", "Daniel Johan", "Hindun Anisah", "Usman Husin", "Rina Sa'adah"],
    "PKS": ["Abdul Kharis", "Slamet", "Johan Rosihan", "Riyono", "Rahmat Saleh"],
    "PAN": ["Ahmad Yohan", "Herry Dermawan", "Irham Jafar Lan Putra", "Ajbar"],
    "Demokrat": ["Bambang Purwanto", "Ellen Esther Pelealu", "Hasan Saleh", "Muhammad Zulfikar Suhardi"]
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

# ============================================================
# HELPERS
# ============================================================
def _stat(value, source, source_url, confidence, fetched_at):
    return {
        "value": value,
        "source": source,
        "source_url": source_url,
        "confidence": confidence,   # AUDITED | KLAIM_MANAJEMEN | UNAUDITED | FALLBACK
        "fetched_at": fetched_at,
    }

def fetch_json(url, params=None, timeout=15):
    r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

# ============================================================
# 3. FASE 1: BERITA LEMBAGA (Google News RSS)
# ============================================================
def fetch_agency_news():
    results = []
    errors = []
    for agency, query in AGENCIES.items():
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=id&gl=ID&ceid=ID:id"
        print(f"  [LEMBAGA] Menarik data: {agency}...")
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                entry = feed.entries[0]
                results.append({
                    "agency": agency,
                    "title": entry.title,
                    "link": entry.link,
                    "link_resolved": None,
                    "published": entry.get("published", "N/A"),
                })
            else:
                results.append({
                    "agency": agency,
                    "title": f"[Sistem Alert] Tidak ada berita terbaru untuk keyword {agency}.",
                    "link": "#",
                    "link_resolved": None,
                    "published": datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT"),
                })
        except Exception as e:
            msg = f"Gagal fetch {agency}: {e}"
            print(f"  [WARN] {msg}")
            errors.append(msg)
            results.append({
                "agency": agency,
                "title": f"[Error] Gagal menarik data: {e}",
                "link": "#",
                "link_resolved": None,
                "published": datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT"),
            })
    return results, errors

# ============================================================
# 4. FASE 2: BERITA ANGGOTA (Google News RSS)
# ============================================================
def fetch_member_news():
    results = {}
    errors = []
    all_members = [m for members in KOMISI4_MEMBERS.values() for m in members]
    print(f"  Memproses {len(all_members)} anggota Komisi IV...")
    for member in all_members:
        try:
            query = urllib.parse.quote(f'"{member}" DPR OR Komisi')
            url = f"https://news.google.com/rss/search?q={query}&hl=id&gl=ID&ceid=ID:id"
            feed = feedparser.parse(url)
            if feed.entries:
                entry = feed.entries[0]
                results[member] = {
                    "title": entry.title,
                    "link": entry.link,
                    "link_resolved": None,
                    "published": entry.get("published", "N/A"),
                    "fetched_at": datetime.now().isoformat()
                }
                try:
                    print(f"  [OK] {member}: {entry.title[:60]}...")
                except UnicodeEncodeError:
                    print(f"  [OK] {member}: (judul mengandung karakter non-ASCII)")
            else:
                print(f"  [INFO] Tidak ada berita untuk: {member}")
        except Exception as e:
            msg = f"Gagal fetch anggota {member}: {e}"
            print(f"  [WARN] {msg}")
            errors.append(msg)
        time.sleep(0.5)
    return results, errors

# ============================================================
# 5. FASE 3: DATA MAKRO (API resmi + FALLBACK jujur)
# ============================================================
#
# Prinsip: hanya angka yang punya sumber API beneran yang jadi live.
# Sisanya FALLBACK berlabel, BUKAN scrape regex yang menebak.
#
# Confidence:
#   AUDITED         -> rilis resmi BPS (WebAPI)
#   UNAUDITED       -> data operasional harian (Panel Harga Bapanas)
#   FALLBACK        -> nilai statis manual, belum/ tidak ada API
#
# ------------------------------------------------------------
# 5a. PANEL HARGA BAPANAS (harga beras) — API harian, tanpa auth
# ------------------------------------------------------------
# >>> KONFIRMASI ENDPOINT (2 menit, wajib sebelum deploy):
#     1. Buka https://panelharga.badanpangan.go.id  -> menu Harga Eceran.
#     2. DevTools (F12) > tab Network > filter "Fetch/XHR".
#     3. Ganti tanggal/komoditas; lihat request yang muncul (biasanya ke
#        host api-panelhargav2.badanpangan.go.id). Salin URL + parameternya.
#     4. Tempel URL itu ke PANELHARGA_URL, sesuaikan PANELHARGA_PARAMS, dan
#        sesuaikan _parse_panelharga_beras() dengan bentuk JSON response asli.
#   Sampai dikonfirmasi, fungsi ini aman gagal -> harga_beras tetap FALLBACK.
# >>> SAKLAR: integrasi API yang belum dikonfirmasi dimatikan dulu (mode statis jujur).
#     Flip ke True setelah endpoint/credential dikonfirmasi (lihat report untuk atasan).
ENABLE_PANELHARGA_API = False
PANELHARGA_URL = "https://api-panelhargav2.badanpangan.go.id/api/front/harga-pangan-table"

def _parse_panelharga_beras(data):
    """Best-effort: telusuri JSON cari komoditas 'Beras' -> harga rata-rata nasional.
    SESUAIKAN dengan struktur response asli setelah cek DevTools."""
    candidates = []
    if isinstance(data, dict):
        candidates = data.get("data") or data.get("result") or data.get("list") or []
    elif isinstance(data, list):
        candidates = data
    for item in candidates:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("nama") or item.get("komoditas") or "").lower()
        if "beras" in name:
            for k in ("today", "harga", "price", "value", "gridharga", "harga_today"):
                v = item.get(k)
                if isinstance(v, (int, float)) and v > 0:
                    return int(v)
                if isinstance(v, str):
                    digits = re.sub(r"[^\d]", "", v)
                    if digits:
                        return int(digits)
    return None

def fetch_food_prices(now):
    errors = []
    harga_beras = _stat(15500, "BAPANAS, nilai fallback statis",
                        "https://panelharga.badanpangan.go.id/", "FALLBACK", now)
    if not ENABLE_PANELHARGA_API:
        return harga_beras, []   # mode statis disengaja, bukan kegagalan
    today = date.today().strftime("%d/%m/%Y")
    params = {"level_harga_id": 3, "period_date": f"{today} - {today}", "province_id": ""}
    print("  [STATS] Panel Harga Bapanas (harga beras)...")
    try:
        data = fetch_json(PANELHARGA_URL, params=params)
        val = _parse_panelharga_beras(data)
        if val:
            harga_beras = _stat(val, "BAPANAS Panel Harga (API)",
                                "https://panelharga.badanpangan.go.id/", "UNAUDITED", now)
            print(f"  [STATS] Harga beras (API): Rp {val}")
        else:
            errors.append("panelharga: komoditas 'beras' tidak ditemukan / parser belum disesuaikan")
    except Exception as e:
        errors.append(f"panelharga gagal: {e}")
        print(f"  [WARN] panelharga gagal: {e}")
    return harga_beras, errors

# ------------------------------------------------------------
# 5b. BPS WebAPI (NTP) — data resmi, BUTUH API KEY GRATIS
# ------------------------------------------------------------
# >>> SETUP (sekali):
#     1. Daftar di https://webapi.bps.go.id, buat aplikasi -> dapat API key.
#     2. Simpan key sebagai GitHub Secret bernama BPS_API_KEY
#        (Settings > Secrets and variables > Actions).
#     3. Cari variable ID untuk "Nilai Tukar Petani" di katalog WebAPI,
#        isi NTP_VAR_ID di bawah.
#   Tanpa key/var_id, NTP aman jatuh ke FALLBACK.
ENABLE_BPS_API = False
BPS_KEY = os.environ.get("BPS_API_KEY", "").strip()
NTP_VAR_ID = ""  # << isi var id NTP dari katalog BPS WebAPI

def _parse_bps_latest(data):
    """Ambil nilai periode terbaru dari response 'dynamic data' BPS.
    Struktur BPS rumit (datacontent ber-key gabungan id); VERIFIKASI dengan
    response asli. Heuristik: ambil value pada key dengan tahun/periode terbesar."""
    dc = data.get("datacontent") if isinstance(data, dict) else None
    if not isinstance(dc, dict) or not dc:
        return None
    try:
        latest_key = sorted(dc.keys())[-1]   # heuristik kasar: key terbesar = periode terbaru
        return float(dc[latest_key])
    except Exception:
        return None

def fetch_bps_ntp(now):
    errors = []
    ntp = _stat(110.5, "BPS, nilai fallback statis", "https://www.bps.go.id/", "FALLBACK", now)
    if not ENABLE_BPS_API or not BPS_KEY or not NTP_VAR_ID:
        return ntp, errors   # mode statis disengaja, bukan kegagalan
    url = (f"https://webapi.bps.go.id/v1/api/list/model/data/lang/ind/"
           f"domain/0000/var/{NTP_VAR_ID}/key/{BPS_KEY}/")
    print("  [STATS] BPS WebAPI (NTP)...")
    try:
        data = fetch_json(url)
        val = _parse_bps_latest(data)
        if val is not None:
            ntp = _stat(round(val, 2), "BPS WebAPI", "https://www.bps.go.id/", "AUDITED", now)
            print(f"  [STATS] NTP (BPS API): {val}")
        else:
            errors.append("BPS: datacontent kosong / format tak terduga")
    except Exception as e:
        errors.append(f"BPS NTP gagal: {e}")
        print(f"  [WARN] BPS NTP gagal: {e}")
    return ntp, errors

# ------------------------------------------------------------
# 5c. STAT FALLBACK JUJUR (belum ada API publik bersih)
#     Update manual berkala. Label tetap FALLBACK -> UI menandai abu-abu.
# ------------------------------------------------------------
def build_macro_stats(now, ntp_stat):
    return {
        "ntp":               ntp_stat,
        "luas_panen_padi":   _stat("10.2 Juta Ha",        "BPS, fallback statis",     "https://www.bps.go.id/",        "FALLBACK", now),
        "produksi_beras":    _stat("31.5 Juta Ton",       "BPS, fallback statis",     "https://www.bps.go.id/",        "FALLBACK", now),
        "luas_panen_jagung": _stat("4.1 Juta Ha",         "BPS, fallback statis",     "https://www.bps.go.id/",        "FALLBACK", now),
        "produksi_jagung":   _stat("14.4 Juta Ton",       "BPS, fallback statis",     "https://www.bps.go.id/",        "FALLBACK", now),
        "kampung_nelayan":   _stat("12 Lokasi Selesai",   "KKP, fallback statis",     "https://kkp.go.id/",            "FALLBACK", now),
        "harga_pangan_avg":  _stat("Stabil (Inflasi 0.2%)","BAPANAS, fallback statis","https://badanpangan.go.id/",    "FALLBACK", now),
        "bantuan_pangan":    _stat("85% Tersalurkan",     "BAPANAS, fallback statis", "https://badanpangan.go.id/",    "FALLBACK", now),
        "realisasi_sphp":    _stat("750.000 Ton",         "Bulog, fallback statis",   "https://www.bulog.co.id/",      "FALLBACK", now),
    }

# ============================================================
# 6. COMMIT-ON-DIFF: skip tulis kalau konten (tanpa timestamp) sama
# ============================================================
def _strip_volatile(obj):
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items()
                if k not in ("fetched_at", "last_updated")}
    if isinstance(obj, list):
        return [_strip_volatile(x) for x in obj]
    return obj

def _fingerprint(output):
    norm = _strip_volatile(output)
    blob = json.dumps(norm, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()

# ============================================================
# 7. MAIN
# ============================================================
def fetch_data():
    print("=" * 50)
    print("ENGINE KOMISI IV DIMULAI")
    print("=" * 50)
    now = datetime.now().isoformat()
    all_errors = []

    print("\n>>> FASE 1: Berita Lembaga Mitra...")
    agency_news, e1 = fetch_agency_news()
    all_errors += e1
    real_agency = sum(1 for a in agency_news
                      if not a["title"].startswith(("[Sistem Alert]", "[Error]")) and a["link"] != "#")
    phase1 = "failed" if real_agency == 0 else ("partial" if real_agency < len(AGENCIES) else "ok")
    print(f"[FASE 1] {real_agency}/{len(AGENCIES)} lembaga dapat berita real.")

    print("\n>>> FASE 2: Berita Anggota...")
    member_news, e2 = fetch_member_news()
    all_errors += e2
    total_members = sum(len(v) for v in KOMISI4_MEMBERS.values())
    phase2 = "failed" if len(member_news) == 0 else (
        "partial" if (e2 or len(member_news) < total_members * 0.5) else "ok")
    print(f"[FASE 2] {len(member_news)}/{total_members} anggota dapat berita.")

    print("\n>>> FASE 3: Data Makro (API + fallback)...")
    harga_beras, e3a = fetch_food_prices(now)
    ntp_stat, e3b = fetch_bps_ntp(now)
    all_errors += e3a + e3b
    macro_stats = build_macro_stats(now, ntp_stat)
    stok_bulog = _stat(1250000, "Bulog, nilai fallback statis", "https://www.bulog.co.id/", "FALLBACK", now)

    # status fase 3 = berapa target API aktif yang benar-benar live.
    # Kalau semua API dimatikan (mode statis disengaja), itu bukan kegagalan -> "ok".
    live_targets = []
    if ENABLE_PANELHARGA_API:
        live_targets.append(harga_beras)
    if ENABLE_BPS_API and BPS_KEY and NTP_VAR_ID:
        live_targets.append(ntp_stat)
    if not live_targets:
        phase3 = "ok"
        print("[FASE 3] Mode statis (FALLBACK), tidak ada target API aktif.")
    else:
        live_ok = sum(1 for s in live_targets if s["confidence"] in ("UNAUDITED", "AUDITED"))
        phase3 = "failed" if live_ok == 0 else ("partial" if live_ok < len(live_targets) else "ok")
        print(f"[FASE 3] {live_ok}/{len(live_targets)} target API live.")

    output = {
        "agency_news": agency_news,
        "member_news": member_news,
        "harga_beras": harga_beras,
        "stok_bulog":  stok_bulog,
        "macro_stats": macro_stats,
        "scrape_status": {
            "phase_1_agency":  phase1,
            "phase_2_members": phase2,
            "phase_3_macro":   phase3,
            "errors": all_errors[-20:],
        },
        "last_updated": now,
    }

    output_path = os.path.join(os.path.dirname(__file__), "live_data.json")

    # commit-on-diff: bandingkan fingerprint tanpa timestamp
    new_fp = _fingerprint(output)
    old_fp = None
    if os.path.exists(output_path):
        try:
            with open(output_path, encoding="utf-8") as f:
                old_fp = _fingerprint(json.load(f))
        except Exception:
            old_fp = None
    if new_fp == old_fp:
        print("\n[SKIP] Konten tidak berubah, live_data.json tidak ditulis ulang "
              "(mencegah commit kosong tiap jam).")
        return

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=4)
        print(f"\n[SUKSES] live_data.json diperbarui {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"[GAGAL] Simpan data: {e}")

if __name__ == "__main__":
    fetch_data()
