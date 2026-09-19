from http_client import make_session
from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin
from requests.utils import requote_uri
import re  # ⭐ 新增：用來解析日期

session = make_session()


def parse_fubon_date(raw: str):
    """
    處理富邦美術館的展覽日期格式，例如：
    2025.10.23 - 2026.4.20
    2025.7.26 - 2025.11.30
    2025.12.24 - 2026.4.20

    規則：
    - 'YYYY.M.D - YYYY.M.D'：
        -> start_date / end_date 都有，is_permanent = 0
    - 'YYYY.M.D~YYYY.M.D' 或 'YYYY.M.D~'（預留未來可能）
    - 只有單一日期 'YYYY.M.D'：
        -> start_date 有值、end_date = None，is_permanent = 1

    回傳：(start_date, end_date, is_permanent)
    日期格式一律為 'YYYY-MM-DD' 或 None
    """

    if not raw:
        return None, None, 0

    s = raw.strip()
    if not s:
        return None, None, 0

    def parse_dot_date(token: str):
        """把 'YYYY.M.D' 或 'YYYY.MM.DD' 轉成 'YYYY-MM-DD'"""
        cleaned = re.sub(r"[^0-9\.]", "", token)  # 只留數字和點
        m = re.match(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})$", cleaned)
        if not m:
            return None
        y, mm, dd = m.groups()
        return f"{y}-{int(mm):02d}-{int(dd):02d}"

    # 1) 含 '~' 的情況（預防性支援）
    if "~" in s:
        left, right = s.split("~", 1)
        start = parse_dot_date(left.strip())
        end = parse_dot_date(right.strip())
        if start and not end:
            # 只有開始 → 視為長期/常設
            return start, None, 1
        if start and end:
            return start, end, 0
        if start:
            return start, None, 0
        return None, None, 0

    # 2) 典型範圍：'YYYY.M.D - YYYY.M.D'
    if "-" in s:
        left, right = s.split("-", 1)
        start = parse_dot_date(left.strip())
        end = parse_dot_date(right.strip())
        if start and end:
            return start, end, 0
        if start and not end:
            return start, None, 1
        if start:
            return start, None, 0
        return None, None, 0

    # 3) 單一日期：'YYYY.M.D'
    start = parse_dot_date(s)
    if start:
        return start, None, 1

    # 4) 無法解析
    return None, None, 0


def fetch_fubon_exhibitions():
    base_url = "https://www.fubonartmuseum.org"
    exhs_url = "https://www.fubonartmuseum.org/Exhibitions"
    museum_name = "富邦美術館"

    resp = session.get(exhs_url, timeout=20)
    resp.raise_for_status()
    html = bs(resp.text, "html.parser")
    exhs = html.find_all("a", class_="fb-exhibitions-card")

    results = []

    for exh in exhs:
        # 展覽連結
        ex_link = exh.get("href", "")
        link = urljoin(base_url, ex_link)

        info_group = exh.find_all("div", class_="info_group")

        # 展覽名稱
        title = ""
        if info_group:
            try:
                ex_title = info_group[0].find("h2", class_="font-h2 font-bold")
                if ex_title:
                    title = ex_title.get_text(strip=True)
            except Exception:
                pass

        # 展覽日期 & 地點
        ex_date = ""
        place = ""
        if len(info_group) >= 3:
            try:
                date_place_group = info_group[2].find_all("p")
                if len(date_place_group) >= 1:
                    ex_date = date_place_group[0].get_text(strip=True)
                if len(date_place_group) >= 2:
                    place = date_place_group[1].get_text(strip=True)
            except Exception:
                pass

        # ⭐ 解析富邦日期格式
        start_date, end_date, is_permanent = parse_fubon_date(ex_date)

        # 展覽圖片
        img = ""
        img_tag = exh.find("img")
        if img_tag and img_tag.has_attr("src"):
            img = requote_uri(img_tag["src"])

        results.append({
            "museum": museum_name,
            "title": title,
            "date": ex_date,           # 原始字串
            "start_date": start_date,  # YYYY-MM-DD
            "end_date": end_date,      # YYYY-MM-DD or None
            "is_permanent": is_permanent,  # 0: 一般展期, 1: 長期/常設
            "topic": "",
            "url": link,
            "image_url": img,
            "location": place,
            "time": "",
            "category": "",
            "extra": "",
        })

    return results


if __name__ == "__main__":
    print(fetch_fubon_exhibitions())

