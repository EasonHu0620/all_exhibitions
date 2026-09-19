from http_client import make_session
from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin

session = make_session()


def parse_npm_date(raw: str):
    """
    專門處理故宮展覽日期格式。

    目前看到的樣子：
    2025-10-10~2026-01-07
    2024-05-17~2026-05-17
    2023-12-01~
    2020-05-01~
    常設展

    規則：
    - '常設展'：
        start_date = None, end_date = None, is_permanent = 1
    - 'YYYY-MM-DD~YYYY-MM-DD'：
        start_date, end_date 皆有值, is_permanent = 0
    - 'YYYY-MM-DD~'（只有開頭）：
        start_date 有值, end_date = None, is_permanent = 1
    """
    if not raw:
        return None, None, 0

    s = raw.strip()
    if not s:
        return None, None, 0

    # 1) 明寫常設展
    if "常設展" in s:
        return None, None, 1

    # 2) 含有 "~" 的格式
    if "~" in s:
        left, right = s.split("~", 1)
        start = left.strip() or None
        end = right.strip() or None

        # 有開始、沒有結束 -> 視為常設/長期展
        if start and not end:
            return start, None, 1
        # 有開始、有結束 -> 一般期間展
        if start and end:
            return start, end, 0

        # 其它怪情況
        if start:
            return start, None, 0
        return None, None, 0

    # 3) 其它形式（基本上故宮不太會用，但保險留一下）
    return None, None, 0


def fetch_npm_exhibitions():
    base_url = "https://www.npm.gov.tw"
    exhs_url = "https://www.npm.gov.tw/Exhibition-Current.aspx?sno=03000060&l=1"
    museum_name = "國立故宮博物院"

    resp = session.get(exhs_url, timeout=20)
    resp.raise_for_status()
    html = bs(resp.text, "html.parser")
    exhs = html.find_all("li", class_="mb-8")

    results = []

    for exh in exhs:
        # 展覽名稱
        title = ""
        h3 = exh.find("h3", class_="font-medium") or exh.find("h3", class_="card-title h5")
        if h3:
            title = h3.get_text(strip=True)

        # 展覽日期（原始字串）
        ex_date = ""
        d1 = exh.find("div", class_="exhibition-list-date")
        if d1:
            ex_date = d1.get_text(strip=True)
        else:
            content_top = exh.find("div", class_="card-content-top")
            if content_top:
                date_div = content_top.find("div", class_=False, recursive=False)
                if date_div:
                    ex_date = date_div.get_text(strip=True)

        # 解析日期 -> start_date, end_date, is_permanent
        start_date, end_date, is_permanent = parse_npm_date(ex_date)

        # 展覽標籤/類別
        ex_tag = ""
        tag_div = exh.find("div", class_="mt-2") or exh.find("div", class_="card-tags")
        if tag_div:
            ex_tag = tag_div.get_text(strip=True)

        # 展覽地點
        ex_place = ""
        place_div = exh.find("div", class_="card-content-bottom")
        if place_div:
            ex_place = place_div.get_text(strip=True)

        # 展覽連結
        ex_link = ""
        a = exh.find("a")
        if a and a.has_attr("href"):
            ex_link = urljoin(base_url, a["href"])

        # 展覽圖片
        ex_img = ""
        img_tag = exh.find("img")
        if img_tag:
            src = img_tag.get("data-src") or img_tag.get("src")
            if src and "loader.gif" not in src:
                ex_img = urljoin(base_url, src).split("&")[0]

        results.append({
            "museum": museum_name,
            "title": title,
            "date": ex_date,            # 原始日期字串
            "start_date": start_date,   # 解析後開始日期
            "end_date": end_date,       # 解析後結束日期
            "is_permanent": is_permanent,  # 1=常設/長期展, 0=一般展期
            "topic": ex_tag,
            "url": ex_link,
            "image_url": ex_img,
            "location": ex_place,
            "time": "",
            "category": ex_tag,
            "extra": "",
        })

    return results
