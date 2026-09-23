import re

from http_client import is_same_host, make_session
from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin

session = make_session()


def parse_songshan_date(raw: str):
    """
    專門處理松山文創園區的展覽日期格式。

    目前觀察到的格式：
    2025-11-01 - 2025-11-30
    2025-12-11 - 2025-12-14
    2026-09-22            （單日活動）

    規則：
    - 有「開始 - 結束」：start_date、end_date 都給值，is_permanent = 0
    - 只有一個日期：視為單日活動，start_date = end_date = 該日，is_permanent = 0
    - 空字串或找不到日期：全部回 None, None, 0
    """
    if not raw:
        return None, None, 0

    dates = re.findall(r"\d{4}-\d{2}-\d{2}", raw)
    if len(dates) >= 2:
        return dates[0], dates[1], 0
    if len(dates) == 1:
        return dates[0], dates[0], 0
    return None, None, 0


def fetch_songshan_exhibitions():
    base_url = "https://www.songshanculturalpark.org/"
    exhs_url = "https://www.songshanculturalpark.org/exhibition"
    museum_name = "松山文創園區"

    resp = session.get(exhs_url, timeout=20)
    resp.raise_for_status()
    html = bs(resp.text, "html.parser")
    exhs = html.find_all("div", class_="rows")

    results = []

    for exh in exhs:
        # 展覽連結
        link = ""
        a = exh.find("a")
        if a and a.has_attr("href"):
            link = urljoin(base_url, a["href"])

        # 只跟隨松山官網網域的連結
        if not is_same_host(link, base_url):
            continue

        try:
            ex_resp = session.get(link, timeout=20)
            ex_resp.raise_for_status()
        except Exception as e:
            # 單一展覽頁失敗不應讓整個流程中斷，略過該筆
            print(f"⚠️ 松山展覽頁讀取失敗，略過：{link} ({type(e).__name__})")
            continue
        ex_html = bs(ex_resp.text, "html.parser")

        # 展覽名稱
        title = ""
        ex_title = ex_html.find("p", class_="inner_title")
        if ex_title:
            title = ex_title.get_text(strip=True)

        # 展覽日期（原始字串）
        ex_date = ""
        date_tag = ex_html.find("p", class_="date montsrt")
        if date_tag:
            ex_date = date_tag.get_text(strip=True)

        # 解析成 start_date / end_date / is_permanent
        start_date, end_date, is_permanent = parse_songshan_date(ex_date)

        # 展覽地點
        place = ""
        place_tag = ex_html.find("p", class_="place")
        if place_tag:
            place = place_tag.get_text(strip=True)

        # 展覽圖片
        img = ""
        img_tag = ex_html.find("img", class_="big_img")
        if img_tag and img_tag.has_attr("src"):
            img = urljoin(base_url, img_tag["src"])

        results.append({
            "museum": museum_name,
            "title": title,
            "date": ex_date,           # 原始日期字串
            "start_date": start_date,  # 解析後開始日期
            "end_date": end_date,      # 解析後結束日期
            "is_permanent": is_permanent,  # 松山皆為 0（單日活動 start = end）
            "topic": "",
            "url": link,
            "image_url": img,
            "location": place,
            "time": "",
            "category": "",
            "extra": "",
        })

    return results
