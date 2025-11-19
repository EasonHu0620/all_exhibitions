# huashan.py
import re
from urllib.parse import urljoin

import requests as req
from bs4 import BeautifulSoup as bs
from requests.utils import requote_uri
import urllib3

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
session = req.Session()
session.verify = False


def get_driver(headless=True):
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    if headless:
        # 某些環境對 --headless=new 會不穩，可以改用傳統寫法
        opts.add_argument("--headless")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=zh-TW")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    try:
        return webdriver.Chrome(options=opts)
    except Exception as e:
        print("⚠️ 無法啟動 Selenium driver，略過華山：", repr(e))
        return None


def fetch_huashan_exhibitions():
    base_url = "https://www.huashan1914.com"
    exh = "https://www.huashan1914.com/w/huashan1914"
    museum_name = "華山1914文創園區"

    driver = get_driver(headless=True)
    if driver is None:
        return []

    results = []
    try:
        driver.get(exh)
        wait = WebDriverWait(driver, 20)
        container = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".swiper-slide.swiper-slide-active")
            )
        )
        items = container.find_elements(By.XPATH, "./div")

        for it in items:
            # 展覽連結
            ex_link = ""
            try:
                img = it.find_element(By.XPATH, "./img")
                onclick = img.get_attribute("onclick") or ""
                m = re.search(r"'(/[^']+)'", onclick)
                if m:
                    url_part = m.group(1)
                    ex_link = urljoin(base_url, url_part)
            except Exception:
                pass

            if not ex_link.startswith(("http://", "https://")):
                continue

            resp = session.get(ex_link, timeout=20)
            resp.raise_for_status()
            html = bs(resp.text, "html.parser")

            # 展覽名稱
            title = ""
            ex_title = html.find("div", class_="article-title page")
            if ex_title:
                title = ex_title.get_text(strip=True)

            # 展覽日期
            ex_date = ""
            dates = [d.get_text(strip=True) for d in html.find_all("div", class_="card-date")]
            if dates:
                ex_date = " - ".join(dates[:2])

            # 展覽時間
            ex_time = ""
            node = html.find("div", class_="card-time")
            if node:
                raw = node.get_text(" ", strip=True)
                if re.match(r"^\d", raw):
                    ex_time = raw

            # 展覽圖片
            ex_img = ""
            first_img = html.select_one("span[rel] img")
            if first_img and first_img.get("src"):
                ex_img = requote_uri(urljoin(base_url, first_img["src"]))

            # 展覽地點
            ex_place = ""
            place = html.find("a", class_="openMap")
            if place:
                ex_place = place.get_text(strip=True)

            results.append({
                "museum": museum_name,
                "title": title,
                "date": ex_date,
                "topic": "",
                "url": ex_link,
                "image_url": ex_img,
                "location": ex_place,
                "time": ex_time,
                "category": "",
                "extra": "",
            })
    finally:
        driver.quit()

    return results
