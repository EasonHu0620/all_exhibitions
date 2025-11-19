# ntnu.py
import re
import requests as req
from bs4 import BeautifulSoup as bs
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
session = req.Session()
session.verify = False


BASE_URL = "https://www.artmuse.ntnu.edu.tw/index.php/current_exhibit/"


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

        results.append({
            "museum": museum_name,
            "title": ex.get("title", ""),
            "date": time_text or "",
            "topic": "",
            "url": ex.get("url", ""),
            "image_url": ex.get("image_url", ""),
            "location": place_text or "",
            "time": time_text or "",
            "category": "",
            "extra": "",
        })

    return results
