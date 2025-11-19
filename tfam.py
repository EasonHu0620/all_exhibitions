# tfam.py
import re
from urllib.parse import urljoin

import requests as req
from bs4 import BeautifulSoup as bs
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
        opts.add_argument("--headless")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=zh-TW")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    try:
        return webdriver.Chrome(options=opts)
    except Exception as e:
        print("⚠️ 無法啟動 Selenium driver，略過北美館：", repr(e))
        return None


def fetch_tfam_exhibitions():
    BASE = "https://www.tfam.museum/"
    HOME = "https://www.tfam.museum/index.aspx?ddlLang=zh-tw"
    EXH = "https://www.tfam.museum/Exhibition/Exhibition.aspx?ddlLang=zh-tw"
    CONTAINER_XPATH = '/html/body/form/div[3]/div[3]/div/div[2]'

    # 抓館名
    museum_name = "臺北市立美術館"
    r = session.get(HOME, timeout=20)
    r.raise_for_status()
    html = bs(r.text, "html.parser")
    tfam = html.find("div", class_="footer-info-container")
    if tfam:
        tfam_text = tfam.get_text(" ", strip=True)
        m = re.search(r"臺北市立美術館", tfam_text)
        if m:
            museum_name = m.group()

    driver = get_driver(headless=True)
    if driver is None:
        return []

    results = []
    try:
        driver.get(EXH)
        wait = WebDriverWait(driver, 20)
        container = wait.until(EC.presence_of_element_located((By.XPATH, CONTAINER_XPATH)))
        items = container.find_elements(By.XPATH, "./div")

        for it in items:
            # 圖片
            img_src = ""
            try:
                img = it.find_element(By.XPATH, "./div[1]/img")
                img_src = img.get_attribute("src") or ""
                img_src = urljoin(BASE, img_src)
            except Exception:
                pass

            # 展覽標題
            title = ""
            try:
                a = it.find_element(By.XPATH, "./div[2]/h3/a")
                title = (a.text or "").strip()
            except Exception:
                pass

            # 展覽時間（官網常把日期 + 時段寫一起）
            ex_time = ""
            try:
                ex_time = it.find_element(By.XPATH, "./div[2]/p[1]").text.strip()
            except Exception:
                pass

            # 展覽地點
            ex_place = ""
            try:
                ex_place = it.find_element(By.XPATH, "./div[2]/p[2]").text.strip()
            except Exception:
                pass

            # 展覽連結
            ex_link = ""
            try:
                link = it.find_element(By.XPATH, "./div[2]/div")
                link_num = link.get_attribute("id")[-3:] or ""
                ex_link = f"{BASE}Exhibition/Exhibition_Special.aspx?ddlLang=zh-tw&id={link_num}"
            except Exception:
                pass

            if any([title, ex_time, ex_place, img_src, ex_link]):
                results.append({
                    "museum": museum_name,
                    "title": title,
                    "date": ex_time,      # 這裡日期+時間混在一起，暫時放 date
                    "topic": "",
                    "url": ex_link,
                    "image_url": img_src,
                    "location": ex_place,
                    "time": ex_time,
                    "category": "",
                    "extra": "",
                })
    finally:
        driver.quit()

    return results
