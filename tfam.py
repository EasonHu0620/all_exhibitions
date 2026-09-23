import re
from urllib.parse import urljoin

from http_client import make_session
from bs4 import BeautifulSoup as bs

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

session = make_session()


def get_driver(headless=True):
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    if headless:
        opts.add_argument("--headless")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=zh-TW")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    try:
        return webdriver.Chrome(options=opts)
    except Exception as e:
        print("⚠️ 無法啟動 Selenium driver，略過北美館：", repr(e))
        return None


def parse_tfam_date(raw: str):
    """
    處理臺北市立美術館的展覽日期格式，例如：
    2025/11/01 - 2026/03/29
    2025/09/19 - 2026/08/31
    2025/01/18 - 2025/12/21
    2025/09/27 - 2026/02/22

    通常會混在 ex_time 字串裡（日期 + 時段），所以這裡用 regex 抓出日期部分。

    規則：
    - 有 'YYYY/MM/DD - YYYY/MM/DD'：
        -> start_date、end_date 皆有，is_permanent = 0
    - 只有一個 'YYYY/MM/DD'：
        -> start_date 有值、end_date = None、is_permanent = 1
    """
    if not raw:
        return None, None, 0

    s = raw.strip()
    if not s:
        return None, None, 0

    def norm_date(d: str):
        # 'YYYY/MM/DD' -> 'YYYY-MM-DD'
        d = d.strip()
        parts = d.split("/")
        if len(parts) != 3:
            return None
        y, mm, dd = parts
        try:
            y = int(y)
            mm = int(mm)
            dd = int(dd)
        except ValueError:
            return None
        return f"{y:04d}-{mm:02d}-{dd:02d}"

    # 1) 嘗試抓「起訖日期區間」
    m = re.search(r"(\d{4}/\d{1,2}/\d{1,2})\s*-\s*(\d{4}/\d{1,2}/\d{1,2})", s)
    if m:
        start_raw, end_raw = m.groups()
        start = norm_date(start_raw)
        end = norm_date(end_raw)
        if start and end:
            return start, end, 0
        if start and not end:
            return start, None, 1
        if start:
            return start, None, 0
        return None, None, 0

    # 2) 沒有範圍，就抓單一日期
    m2 = re.search(r"(\d{4}/\d{1,2}/\d{1,2})", s)
    if m2:
        start = norm_date(m2.group(1))
        if start:
            return start, None, 1

    # 3) 完全抓不到
    return None, None, 0


def fetch_tfam_exhibitions():
    BASE = "https://www.tfam.museum/"
    HOME = "https://www.tfam.museum/index.aspx?ddlLang=zh-tw"
    EXH = "https://www.tfam.museum/Exhibition/Exhibition.aspx?ddlLang=zh-tw"
    CONTAINER_XPATH = '/html/body/form/div[3]/div[3]/div/div[2]'

    # 抓館名（保留你原本的寫法）
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

            # 解析日期區間
            start_date, end_date, is_permanent = parse_tfam_date(ex_time)

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
                # 取 id 結尾的完整數字（不要只取 3 位，id 到 1000 以上會錯）
                m = re.search(r"(\d+)$", link.get_attribute("id") or "")
                if m:
                    ex_link = f"{BASE}Exhibition/Exhibition_Special.aspx?ddlLang=zh-tw&id={m.group(1)}"
            except Exception:
                pass

            if any([title, ex_time, ex_place, img_src, ex_link]):
                results.append({
                    "museum": museum_name,
                    "title": title,
                    "date": ex_time,          # 原始：日期 + 時間
                    "start_date": start_date, # 解析後開始日期
                    "end_date": end_date,     # 解析後結束日期
                    "is_permanent": is_permanent,  # 北美館幾乎都是 0
                    "topic": "",
                    "url": ex_link,
                    "image_url": img_src,
                    "location": ex_place,
                    "time": ex_time,          # 你要的話之後可以只留下時段
                    "category": "",
                    "extra": "",
                })
    finally:
        driver.quit()

    return results
