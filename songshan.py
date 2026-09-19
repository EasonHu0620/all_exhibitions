from http_client import make_session
from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin

session = make_session()


def parse_songshan_date(raw: str):
    """
    專門處理松山文創園區的展覽日期格式。

    目前觀察到的格式：
    2025-11-01 - 2025-11-30
    2025-12-11 - 2025-12-14

    規則：
    - 有「開始 - 結束」：start_date、end_date 都給值，is_permanent = 0
    - 只有一個日期：start_date 有值，end_date = None，is_permanent = 1
    - 空字串或看起來怪怪的：全部回 None, None, 0
    """
    if not raw:
        return None, None, 0

    s = raw.strip()
    if not s:
        return None, None, 0

    # 如果有明顯範圍 " - "
    if " - " in s:
        left, right = s.split(" - ", 1)
        start = left.strip() or None
        end = right.strip() or None

        # 松菸目前這批資料幾乎都是 YYYY-MM-DD，直接用原字串即可
        if start and not end:
            # 只有開始日期 -> 視為常設/長期
            return start, None, 1
        if start and end:
            return start, end, 0
        if start:
            return start, None, 0
        return None, None, 0

    # 沒有 "-"，但有單一日期
    start = s
    if start:
        # 只有開始日期 -> 視為常設/長期
        return start, None, 1

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

        if not link:
            continue

        ex_resp = session.get(link, timeout=20)
        ex_resp.raise_for_status()
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
            "is_permanent": is_permanent,  # 0: 一般展期, 1: 常設/長期展
            "topic": "",
            "url": link,
            "image_url": img,
            "location": place,
            "time": "",
            "category": "",
            "extra": "",
        })

    return results
