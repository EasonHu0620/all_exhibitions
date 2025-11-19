# songshan.py
import requests as req
from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
session = req.Session()
session.verify = False


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

        # 展覽日期
        ex_date = ""
        date_tag = ex_html.find("p", class_="date montsrt")
        if date_tag:
            ex_date = date_tag.get_text(strip=True)

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
            "date": ex_date,
            "topic": "",
            "url": link,
            "image_url": img,
            "location": place,
            "time": "",
            "category": "",
            "extra": "",
        })

    return results
