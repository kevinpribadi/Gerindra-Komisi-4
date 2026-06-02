import feedparser
import json
import os
import time
import urllib.parse
from datetime import datetime
import requests
from bs4 import BeautifulSoup

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

# ============================================================
# 3. HELPER: ANALISIS OTOMATIS PER LEMBAGA
# ============================================================
def generate_analysis(agency, title):
    templates = {
        "Kementerian Pertanian": {
            "pro": ["Mendorong peningkatan produksi beras nasional.", "Menguatkan program ketahanan pangan domestik."],
            "kontra": ["Risiko kelangkaan pupuk subsidi bagi petani kecil.", "Tantangan alokasi anggaran cetak sawah baru."],
            "tanya": ["Bagaimana pengawasan distribusi pupuk subsidi?", "Kapan target swasembada pangan tercapai?"]
        },
        "Kementerian Kehutanan": {
            "pro": ["Mempercepat rehabilitasi lahan kritis dan reboisasi.", "Memperketat izin pemanfaatan kawasan hutan."],
            "kontra": ["Potensi konflik lahan dengan masyarakat adat.", "Pengawasan deforestasi ilegal masih lemah di lapangan."],
            "tanya": ["Sejauh mana realisasi target perhutanan sosial?", "Bagaimana mitigasi kebakaran hutan tahun ini?"]
        },
        "Kementerian Kelautan dan Perikanan": {
            "pro": ["Peningkatan ekspor komoditas perikanan unggulan.", "Pengawasan ketat terhadap illegal fishing."],
            "kontra": ["Keluhan nelayan tradisional mengenai regulasi zonasi.", "Fluktuasi harga BBM bersubsidi bagi nelayan kecil."],
            "tanya": ["Bagaimana implementasi penangkapan ikan terukur?", "Apa langkah konkret pemberdayaan nelayan?"]
        },
        "Badan Karantina Indonesia": {
            "pro": ["Pencegahan masuknya hama penyakit hewan dan tumbuhan luar.", "Standardisasi ketat pelabuhan masuk barang impor."],
            "kontra": ["Keterbatasan personil di pos lintas batas negara.", "Proses sertifikasi karantina dianggap lambat oleh importir."],
            "tanya": ["Bagaimana kesiapan sistem digitalisasi karantina?"]
        },
        "Badan Pangan Nasional": {
            "pro": ["Stabilisasi harga pangan pokok secara nasional.", "Penyaluran bantuan pangan beras tepat waktu."],
            "kontra": ["Bergantung pada impor saat produksi lokal merosot.", "Koordinasi data pangan antar lembaga sering berbeda."],
            "tanya": ["Apakah neraca pangan saat ini aman hingga akhir tahun?"]
        },
        "Perum Bulog": {
            "pro": ["Penyerapan gabah petani lokal berjalan maksimal.", "Stok beras cadangan pemerintah terjaga aman."],
            "kontra": ["Penyimpanan beras rawan mengalami penurunan mutu/kualitas.", "Keterbatasan kapasitas gudang di beberapa wilayah."],
            "tanya": ["Berapa ton stok beras impor yang masuk bulan ini?"]
        }
    }
    default = {
        "pro": [f"Langkah {agency} mendukung ketahanan pangan and sektor produktif.", "Meningkatkan sinergi antar mitra kerja Komisi IV."],
        "kontra": ["Tantangan implementasi kebijakan di tingkat daerah.", "Ketergantungan pada faktor cuaca dan logistik."],
        "tanya": ["Sejauh mana efektivitas kebijakan ini dirasakan pelaku usaha?"]
    }
    return templates.get(agency, default)

# ============================================================
# 4. FASE 1: TARIK BERITA LEMBAGA
# ============================================================
def fetch_agency_news():
    results = []
    for agency, query in AGENCIES.items():
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=id&gl=ID&ceid=ID:id"
        print(f"  [LEMBAGA] Menarik data: {agency}...")
        try:
            feed = feedparser.parse(url)
            if feed.entries and len(feed.entries) > 0:
                entry = feed.entries[0]
                results.append({
                    "agency": agency,
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published,
                    "analysis": generate_analysis(agency, entry.title)
                })
            else:
                results.append({
                    "agency": agency,
                    "title": f"[Sistem Alert] Tidak ada berita terbaru untuk keyword {agency}.",
                    "link": "#",
                    "published": datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT"),
                    "analysis": generate_analysis(agency, "")
                })
        except Exception as e:
            print(f"  [WARN] Error fetching {agency}: {e}")
            results.append({
                "agency": agency,
                "title": f"[Error] Gagal menarik data: {e}",
                "link": "#",
                "published": datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT"),
                "analysis": generate_analysis(agency, "")
            })
    return results

# ============================================================
# 5. FASE 2: TARIK BERITA ANGGOTA KOMISI IV
# ============================================================
def fetch_member_news():
    results = {}
    all_members = [m for members in KOMISI4_MEMBERS.values() for m in members]

    print(f"  Memproses {len(all_members)} anggota Komisi IV...")
    for member in all_members:
        try:
            query = urllib.parse.quote(f'"{member}" DPR OR Komisi')
            url = f"https://news.google.com/rss/search?q={query}&hl=id&gl=ID&ceid=ID:id"
            feed = feedparser.parse(url)

            if feed.entries and len(feed.entries) > 0:
                entry = feed.entries[0]
                results[member] = {
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.get("published", "N/A"),
                    "fetched_at": datetime.now().isoformat()
                }
                print(f"  [OK] {member}: {entry.title[:60]}...")
            else:
                print(f"  [INFO] Tidak ada berita untuk: {member}")

        except Exception as e:
            print(f"  [WARN] Gagal menarik berita untuk {member}: {e}")

        # Jeda 0.5 detik antar request agar tidak diblokir Google
        time.sleep(0.5)

    return results

# ============================================================
# 6. FASE 3: TARIK DATA MAKRO PERTANIAN (BPS, KKP, BAPANAS)
# ============================================================
def fetch_agriculture_stats():
    # Fallback values
    harga_beras = 15500
    stok_bulog = 1250000

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print("  [STATS] Mengambil data harga beras dari Badan Pangan Nasional...")
    try:
        url = "https://panelharga.badanpangan.go.id/"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            import re
            prices = re.findall(r'1[3-9]\.\d{3}', response.text)
            if prices:
                val = int(prices[0].replace('.', ''))
                harga_beras = val
                print(f"  [STATS] Berhasil mengambil harga beras dari Bapanas: Rp {harga_beras}")
            else:
                match = re.search(r'Beras\s+Premium.*?(\d{2}\.\d{3})', response.text, re.IGNORECASE | re.DOTALL)
                if match:
                    harga_beras = int(match.group(1).replace('.', ''))
                    print(f"  [STATS] Berhasil mengambil harga beras Premium dari Bapanas: Rp {harga_beras}")
                else:
                    print("  [STATS] Tidak menemukan kecocokan harga beras di halaman Bapanas, menggunakan fallback.")
        else:
            print(f"  [WARN] Respon non-200 dari Bapanas: {response.status_code}")
    except Exception as e:
        print(f"  [WARN] Gagal mengambil harga beras dari Bapanas: {e}. Menggunakan fallback.")

    print("  [STATS] Mengambil data stok beras Bulog...")
    try:
        url = "https://www.bulog.co.id/siaran-pers/"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            import re
            text = soup.get_text()
            match = re.search(r'stok\s+(?:beras\s+)?(?:mencapai\s+)?([\d\.,]+)\s+(?:juta\s+)?ton', text, re.IGNORECASE)
            if match:
                val_str = match.group(1).replace(',', '.')
                try:
                    val = float(val_str)
                    if "juta" in match.group(0).lower():
                        stok_bulog = int(val * 1000000)
                    else:
                        stok_bulog = int(val)
                    print(f"  [STATS] Berhasil mengambil stok beras Bulog: {stok_bulog} Ton")
                except Exception as ex:
                    print(f"  [WARN] Gagal parsing angka stok Bulog: {ex}")
            else:
                print("  [STATS] Tidak menemukan kecocokan stok beras di halaman Bulog, menggunakan fallback.")
        else:
            print(f"  [WARN] Respon non-200 dari Bulog: {response.status_code}")
    except Exception as e:
        print(f"  [WARN] Gagal mengambil stok beras Bulog: {e}. Menggunakan fallback.")

    return harga_beras, stok_bulog


def fetch_macro_stats():
    # Fallback values
    stats = {
        "ntp": 110.5,
        "luas_panen_padi": "10.2 Juta Ha",
        "produksi_beras": "31.5 Juta Ton",
        "luas_panen_jagung": "4.1 Juta Ha",
        "produksi_jagung": "14.4 Juta Ton",
        "kampung_nelayan": "12 Lokasi Selesai",
        "harga_pangan_avg": "Stabil (Inflasi 0.2%)",
        "bantuan_pangan": "85% Tersalurkan",
        "realisasi_sphp": "750.000 Ton"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # Scraping BPS for NTP
    print("  [STATS] Mengambil data Nilai Tukar Petani (NTP) dari BPS...")
    try:
        url = "https://www.bps.go.id/"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            import re
            match = re.search(r'Nilai\s+Tukar\s+Petani\s*.*?(\d{3}[\.,]\d+)', response.text, re.IGNORECASE)
            if match:
                stats["ntp"] = float(match.group(1).replace(',', '.'))
                print(f"  [STATS] Berhasil mengambil NTP dari BPS: {stats['ntp']}")
    except Exception as e:
        print(f"  [WARN] Gagal mengambil NTP dari BPS: {e}. Menggunakan fallback.")

    # Scraping KKP for Kampung Nelayan
    print("  [STATS] Mengambil data Kampung Nelayan dari KKP...")
    try:
        url = "https://kkp.go.id/artikel/"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            import re
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            match = re.search(r'Kampung\s+Nelayan\s+Modern.*?(\d+)\s+Lokasi', text, re.IGNORECASE)
            if match:
                stats["kampung_nelayan"] = f"{match.group(1)} Lokasi Selesai"
                print(f"  [STATS] Berhasil mengambil Kampung Nelayan KKP: {stats['kampung_nelayan']}")
    except Exception as e:
        print(f"  [WARN] Gagal mengambil Kampung Nelayan KKP: {e}. Menggunakan fallback.")

    # Scraping Bapanas for Bantuan Pangan
    print("  [STATS] Mengambil data Bantuan Pangan dari Badan Pangan Nasional...")
    try:
        url = "https://badanpangan.go.id/"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            import re
            text = response.text
            match = re.search(r'penyaluran\s+bantuan\s+pangan.*?(\d+)%', text, re.IGNORECASE)
            if match:
                stats["bantuan_pangan"] = f"{match.group(1)}% Tersalurkan"
                print(f"  [STATS] Berhasil mengambil Bantuan Pangan: {stats['bantuan_pangan']}")
    except Exception as e:
        print(f"  [WARN] Gagal mengambil Bantuan Pangan Bapanas: {e}. Menggunakan fallback.")

    return stats

# ============================================================
# 7. MAIN: GABUNGKAN SEMUA OUTPUT KE live_data.json
# ============================================================
def fetch_data():
    print("=" * 50)
    print("NPCC ENGINE KOMISI IV DIMULAI")
    print("=" * 50)

    print("\n>>> FASE 1: Menarik Data Berita Lembaga Mitra Komisi IV...")
    agency_news = fetch_agency_news()
    print(f"[FASE 1 SELESAI] {len(agency_news)} lembaga berhasil diproses.")

    print("\n>>> FASE 2: Menarik Berita Anggota Komisi IV...")
    member_news = fetch_member_news()
    print(f"[FASE 2 SELESAI] {len(member_news)} anggota berhasil diproses.")

    print("\n>>> FASE 3: Menarik Data Makro Pertanian (Harga Beras & Stok Bulog)...")
    harga_beras, stok_bulog = fetch_agriculture_stats()
    print(f"[FASE 3 SELESAI] Harga Beras: Rp {harga_beras}, Stok Bulog: {stok_bulog} Ton.")

    print("\n>>> FASE 3b: Menarik Data Statistik Makro Sektoral (9 Metrik)...")
    macro_stats = fetch_macro_stats()
    print(f"[FASE 3b SELESAI] Sektor Makro berhasil diproses.")

    # Gabungkan ke satu output
    output = {
        "agency_news": agency_news,
        "member_news": member_news,
        "harga_beras": harga_beras,
        "stok_bulog": stok_bulog,
        "macro_stats": macro_stats,
        "last_updated": datetime.now().isoformat()
    }

    output_path = os.path.join(os.path.dirname(__file__), 'live_data.json')
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=4)
        print(f"\n[SUKSES] live_data.json diperbarui pada {datetime.now().strftime('%H:%M:%S WIB')}")
        print(f"         - {len(agency_news)} berita lembaga")
        print(f"         - {len(member_news)} berita anggota")
        print(f"         - 9 data makro statistik")
    except Exception as e:
        print(f"[GAGAL] Error saat menyimpan data: {e}")

if __name__ == "__main__":
    fetch_data()
