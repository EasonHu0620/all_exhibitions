# fubon.py
import requests as req
from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin
from requests.utils import requote_uri
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
session = req.Session()
session.verify = False


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

        # 展覽圖片
        img = ""
        img_tag = exh.find("img")
        if img_tag and img_tag.has_attr("src"):
            img = requote_uri(img_tag["src"])

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

print(fetch_fubon_exhibitions())