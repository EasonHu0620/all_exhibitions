import re
from urllib.parse import urljoin, urlparse

from http_client import make_session
from bs4 import BeautifulSoup as bs
from requests.utils import requote_uri

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

session = make_session()


def get_driver(headless=True):
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    if headless:
        # 某些環境對 --headless=new 會不穩，可以改用傳統寫法
        opts.add_argument("--headless")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=zh-TW")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    try:
        return webdriver.Chrome(options=opts)
    except Exception as e:
        print("⚠️ 無法啟動 Selenium driver，略過華山：", repr(e))
        return None


def parse_huashan_date(raw: str):
    """
    處理華山展覽日期格式，例如：
    202510.03(五) - 202511.30(日)
    202511.07(五) - 202511.09(日)
    202510.01(三) - 202601.05(一)
    202505.08(四) - 202512.31(三)
    202511.21(五) - 202511.23(日)

    型態為：YYYYMM.DD(週) - YYYYMM.DD(週)

    規則：
    - 有開始、有結束：一般展期 → is_permanent = 0
    - 只有單一日期：視為單日活動 → start_date = end_date = 該日, is_permanent = 0

    回傳：start_date, end_date, is_permanent
    日期格式為 'YYYY-MM-DD' 或 None
    """
    if not raw:
        return None, None, 0

    s = raw.strip()
    if not s:
        return None, None, 0

    def parse_token(token: str):
        # 只保留數字和小數點
        cleaned = re.sub(r"[^0-9\.]", "", token)
        # 例如 202510.03 -> YYYY=2025, MM=10, DD=03
        m = re.match(r"^(\d{4})(\d{2})\.(\d{1,2})$", cleaned)
        if not m:
            return None
        y, mm, dd = m.groups()
        return f"{y}-{int(mm):02d}-{int(dd):02d}"

    # 標準情況：有 "-"，兩邊各一個日期
    norm = s.replace("－", "-")  # 有時候會用全形 dash
    parts = re.split(r"\s*-\s*", norm, maxsplit=1)

    if len(parts) == 2:
        left, right = parts
        start = parse_token(left)
        end = parse_token(right)

        if start and end:
            return start, end, 0   # 一般展期
        if start:
            return start, start, 0  # 只有一個日期 -> 單日
        return None, None, 0

    # 若只出現一段
    start = parse_token(norm)
    if start:
        return start, start, 0

    return None, None, 0


def fetch_huashan_exhibitions():
    base_url = "https://www.huashan1914.com"
    exh = "https://www.huashan1914.com/w/huashan1914"
    museum_name = "華山1914文化創意產業園區"

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

            # 只跟隨華山官網網域，避免 //other-host/ 之類的連結導向外部或內網
            if urlparse(ex_link).hostname != urlparse(base_url).hostname:
                continue

            try:
                resp = session.get(ex_link, timeout=40)
                resp.raise_for_status()
            except Exception as e:
                # 單一展覽頁失敗不應讓整個流程中斷，略過該筆
                print(f"⚠️ 華山展覽頁讀取失敗，略過：{ex_link} ({type(e).__name__})")
                continue
            html = bs(resp.text, "html.parser")

            # 展覽名稱
            title = ""
            ex_title = html.find("div", class_="article-title page")
            if ex_title:
                title = ex_title.get_text(strip=True)

            # 展覽日期（原始字串）
            ex_date = ""
            dates = [d.get_text(strip=True) for d in html.find_all("div", class_="card-date")]
            if dates:
                ex_date = " - ".join(dates[:2])

            # 解析日期
            start_date, end_date, is_permanent = parse_huashan_date(ex_date)

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
                "date": ex_date,           # 原始日期字串
                "start_date": start_date,  # 解析後開始日期
                "end_date": end_date,      # 解析後結束日期
                "is_permanent": is_permanent,  # 皆為 0（單日活動 start = end）
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


