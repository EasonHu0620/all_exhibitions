import re
from http_client import make_session
from bs4 import BeautifulSoup as bs

session = make_session()


BASE_URL = "https://www.artmuse.ntnu.edu.tw/index.php/current_exhibit/"


def parse_ntnu_date(raw: str):
    """
    處理師大美術館展覽日期格式，例如：
    2025/09/23 Tue.－
    2024/7/1（二）起
    （預留）2025/09/23 - 2025/12/31

    規則：
    - 抓字串中的所有 'YYYY/M/D' 或 'YYYY/MM/DD'
    - 若有兩個日期：視為起訖區間 -> is_permanent = 0
    - 若只有一個日期：視為長期/常設展 -> is_permanent = 1
    """

    if not raw:
        return None, None, 0

    s = raw.strip()
    if not s:
        return None, None, 0

    # 預防將來出現「常設展」文字
    if "常設展" in s:
        return None, None, 1

    def norm_date(d: str):
        # 'YYYY/M/D' -> 'YYYY-MM-DD'
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

    # 擷取所有 yyyy/m/d 或 yyyy/mm/dd
    dates = re.findall(r"\d{4}/\d{1,2}/\d{1,2}", s)

    if len(dates) >= 2:
        start = norm_date(dates[0])
        end = norm_date(dates[1])
        if start and end:
            return start, end, 0
        if start and not end:
            return start, None, 1
        if start:
            return start, None, 0
        return None, None, 0

    if len(dates) == 1:
        start = norm_date(dates[0])
        if start:
            # 只有開始日期 -> 長期/常設
            return start, None, 1

    # 抓不到就當解析失敗
    return None, None, 0


def museum_info(base_url: str):
    r = session.get(base_url, timeout=15)
    r.raise_for_status()
    html = bs(r.text, "html.parser")

    # 館名
    NTNU = html.find("h4", class_="widget-title")
    ntnu_text = NTNU.text.strip() if NTNU else "師大美術館 NTNU Art Museum"

    # 地址
    address = html.find_all("div", style="line-height: 1.5;")
    address_text = ""
    if len(address) > 1:
        address_text = address[1].get_text().strip().split("：", 1)[-1]

    # 開放 / 休館時間
    time_blocks = html.find_all("p", style="margin-bottom: 4px;")
    open_time_text, off_time_text = None, None
    if time_blocks:
        offtime_tag = time_blocks.pop()
        if offtime_tag:
            off_time_text = offtime_tag.get_text().split("：", 1)[-1]

        open_list = []
        for i in time_blocks:
            opentime_text = i.get_text().strip()
            open_list.append(opentime_text)
        if len(open_list) >= 2:
            open_time_text = f"{open_list[0].split('：', 1)[-1]}, {open_list[1]}"
        elif open_list:
            open_time_text = open_list[0]

    return ntnu_text, address_text, open_time_text, off_time_text


def get_exhibitions(base_url: str):
    r = session.get(base_url, timeout=15)
    r.raise_for_status()
    html = bs(r.text, "html.parser")
    figures = html.find_all("figure", class_="wp-caption")

    exhibitions = []
    for f in figures:
        a = f.find("a")
        img = f.find("img")
        cap = f.find("figcaption")

        link = a["href"] if a and a.has_attr("href") else None
        image = img["src"] if img and img.has_attr("src") else None
        title = cap.get_text(strip=True) if cap else None

        exhibitions.append({"title": title, "url": link, "image_url": image})
    return exhibitions


def get_time_and_place(exh_url: str):
    r = session.get(exh_url, timeout=20)
    r.raise_for_status()
    soup = bs(r.text, "html.parser")
    entry = soup.find("div", class_="entry clr")
    if not entry:
        return None, None

    text = entry.get_text("\n", strip=True)
    time_text = None
    place_text = None

    m_time = re.search(r"(展覽時間|時間)[:：]\s*([^\n。]+)", text)
    if m_time:
        time_text = m_time.group(2).strip()

    m_place = re.search(r"(展覽地點|地點)[:：]\s*([^\n。]+)", text)
    if m_place:
        place_text = m_place.group(2).strip()

    return time_text, place_text


def fetch_ntnu_exhibitions():
    museum_name, address_text, open_time, off_time = museum_info(BASE_URL)

    exhibitions = get_exhibitions(BASE_URL)
    results = []

    for ex in exhibitions:
        time_text, place_text = None, None
        if ex.get("url"):
            time_text, place_text = get_time_and_place(ex["url"])

        # ⭐ 解析日期為 start_date / end_date / is_permanent
        start_date, end_date, is_permanent = parse_ntnu_date(time_text or "")

        results.append({
            "museum": "國立臺灣師範大學-師大美術館",
            "title": ex.get("title", ""),
            "date": time_text or "",          # 原始日期字串（例如 2025/09/23 Tue.－）
            "start_date": start_date,         # YYYY-MM-DD 或 None
            "end_date": end_date,             # YYYY-MM-DD 或 None
            "is_permanent": is_permanent,     # 1 = 長期/常設, 0 = 一般展期
            "topic": "",
            "url": ex.get("url", ""),
            "image_url": ex.get("image_url", ""),
            "location": place_text or "",
            "time": time_text or "",
            "category": "",
            "extra": "",
        })

    return results
