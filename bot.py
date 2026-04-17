from playwright.sync_api import sync_playwright
import time
import json
import os
import re
import requests

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
URL = "https://www.hepsiburada.com/cep-telefonlari-c-371965?filtreler=satici:Hepsiburada"
CHECK_INTERVAL = 600
DATA_FILE = "prices.json"


def telegram_mesaj_gonder(mesaj):
    api_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": mesaj
    }
    requests.post(api_url, data=data, timeout=20)


def kayitlari_yukle():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def kayitlari_kaydet(veri):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)


def fiyat_parse_et(text):
    if not text:
        return None

    eslesme = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', text)
    if not eslesme:
        return None

    fiyat_yazi = eslesme.group(1)
    try:
        return float(fiyat_yazi.replace(".", "").replace(",", "."))
    except:
        return None


def urunleri_cek():
    urunler = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, timeout=60000)
        page.wait_for_timeout(5000)

        html = page.content()
        browser.close()

    # basit ürün linklerini bul
    linkler = re.findall(r'href="([^"]*-p-[^"]+)"', html)

    temiz_linkler = []
    for link in linkler:
        if link.startswith("/"):
            tam_link = "https://www.hepsiburada.com" + link
        elif link.startswith("http"):
            tam_link = link
        else:
            continue

        if tam_link not in temiz_linkler:
            temiz_linkler.append(tam_link)

    for link in temiz_linkler[:20]:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(link, timeout=60000)
                page.wait_for_timeout(3000)

                sayfa = page.content()
                browser.close()

            isim_eslesme = re.search(r'<title>(.*?)</title>', sayfa, re.IGNORECASE | re.DOTALL)
            isim = isim_eslesme.group(1).strip() if isim_eslesme else link

            fiyat = None
            fiyat_eslesmeleri = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*TL', sayfa)
            if fiyat_eslesmeleri:
                fiyat = float(fiyat_eslesmeleri[0].replace(".", "").replace(",", "."))

            if fiyat:
                urunler[link] = {
                    "name": isim[:120],
                    "price": fiyat,
                    "url": link
                }

        except Exception as e:
            print("Ürün okunamadı:", link, e)

    return urunler


def kontrol_et():
    eski_kayitlar = kayitlari_yukle()
    yeni_urunler = urunleri_cek()
    guncel_kayitlar = dict(eski_kayitlar)

    for link, bilgi in yeni_urunler.items():
        isim = bilgi["name"]
        yeni_fiyat = bilgi["price"]

        if link not in eski_kayitlar:
            guncel_kayitlar[link] = bilgi
            print("İlk kayıt:", isim, "-", yeni_fiyat, "TL")
            continue

        eski_fiyat = eski_kayitlar[link]["price"]

        if yeni_fiyat < eski_fiyat:
            mesaj = (
                f"🔥 İndirim var kanka!\n\n"
                f"Ürün: {isim}\n"
                f"Eski fiyat: {eski_fiyat} TL\n"
                f"Yeni fiyat: {yeni_fiyat} TL\n\n"
                f"Link: {link}"
            )
            telegram_mesaj_gonder(mesaj)
            print("İndirim bulundu:", isim)

        guncel_kayitlar[link] = bilgi

    kayitlari_kaydet(guncel_kayitlar)


def main():
    print("Bot başladı...")
    while True:
        try:
            print("Kontrol ediliyor...")
            kontrol_et()
            print("Kontrol tamam. 10 dakika bekleniyor...")
        except Exception as e:
            print("Hata:", e)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
