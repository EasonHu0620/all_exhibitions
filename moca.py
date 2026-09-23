from http_client import make_session
from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin
from requests.utils import requote_uri
import re
from datetime import date, datetime

session = make_session()


def parse_moca_date(raw: str):
    """
    處理台北當代藝術館的展覽日期格式，例如：
    10 / 04Sat. - 01 / 11Sun.
    11 / 15Sat. - 03 / 29Sun.

    規則：
    - 網站沒有年份，從「去年、今年、明年」三種開始年份中，
      選展期最接近今天的一個（今天落在展期內的優先）。
      例如 1 月抓到「11/15 - 03/29」→ 去年 11/15 到今年 3/29；
      12 月抓到「01/10 - 03/01」→ 明年。
    - 若 end_month < start_month，視為跨年展：end_year = start_year + 1
    - 都有開始和結束日期 -> is_permanent = 0
    如果解析失敗，就回 (None, None, 0)
    """
    if not raw:
        return None, None, 0

    s = raw.strip()
    if not s:
        return None, None, 0

    # 拆成左右兩段
    if "-" not in s:
        return None, None, 0

    left, right = s.split("-", 1)
    left = left.strip()
    right = right.strip()

    def parse_mmdd(token: str):
        # 只留數字和斜線
        cleaned = re.sub(r"[^0-9/]", "", token)
        m = re.match(r"^\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$", cleaned)
        if not m:
            return None, None
        mm, dd = m.groups()
        return int(mm), int(dd)

    start_mm, start_dd = parse_mmdd(left)
    end_mm, end_dd = parse_mmdd(right)

    if not (start_mm and start_dd and end_mm and end_dd):
        # 如果有缺就先當作無法解析
        return None, None, 0

    today = datetime.today().date()

    def distance(rng):
        # 今天在展期內 = 0，否則為距離展期最近一端的天數
        start, end = rng
        if start <= today <= end:
            return 0
        return (start - today).days if today < start else (today - end).days

    candidates = []
    for start_year in (today.year - 1, today.year, today.year + 1):
        # 若結束月份比開始月份小，視為跨年
        end_year = start_year + 1 if end_mm < start_mm else start_year
        try:
            candidates.append((date(start_year, start_mm, start_dd),
                               date(end_year, end_mm, end_dd)))
        except ValueError:
            # 不存在的日期（如 02/30，或非閏年的 02/29）
            continue

    if not candidates:
        return None, None, 0

    start, end = min(candidates, key=distance)
    start_date = start.isoformat()
    end_date = end.isoformat()

    # MOCA 這一批都有完整起訖，視為一般展期
    is_permanent = 0

    return start_date, end_date, is_permanent


def fetch_moca_exhibitions():
    base_url = "https://www.moca.taipei/tw"
    exhs_url = "https://www.moca.taipei/tw/ExhibitionAndEvent"
    museum_name = "臺北當代藝術館"

    resp = session.get(exhs_url, timeout=20)
    resp.raise_for_status()
    html = bs(resp.text, "html.parser")
    exhs = html.find_all("div", class_="list show")

    results = []

    for exh in exhs:
        # 展覽連結
        link = ""
        a = exh.find("a", class_="link")
        if a and a.has_attr("href"):
            link = requote_uri(a["href"])

        # 展覽名稱
        title = ""
        h3 = exh.find("h3", class_="imgTitle")
        if h3:
            title = h3.get_text(strip=True)

        # 展覽日期（原始字串）
        ex_date = ""
        dates = [d.get_text(strip=True) for d in exh.find_all("p", class_="day")]
        if dates:
            # 通常是兩個 <p class="day">，起訖分開
            ex_date = " - ".join(dates[:2])

        # 解析日期 -> start_date / end_date / is_permanent
        start_date, end_date, is_permanent = parse_moca_date(ex_date)

        # 展覽圖片
        ex_img = ""
        img = exh.find("img", class_="img")
        if img:
            img_src = img.get("data-src")
            if img_src:
                ex_img = urljoin(base_url, img_src)

        # 展覽地點
        ex_place = ""
        place = exh.find("h4", class_="imgSubTitle")
        if place:
            ex_place = place.get_text(strip=True)

        results.append({
            "museum": museum_name,
            "title": title,
            "date": ex_date,            # 原始日期
            "start_date": start_date,   # YYYY-MM-DD
            "end_date": end_date,       # YYYY-MM-DD（跨年會 +1 年）
            "is_permanent": is_permanent,  # MOCA 多半是 0
            "topic": "",
            "url": link,
            "image_url": ex_img,
            "location": ex_place,
            "time": "",
            "category": "",
            "extra": "",
        })

    return results
