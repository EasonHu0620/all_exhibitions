# moca.py
import requests as req
from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin
from requests.utils import requote_uri
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
session = req.Session()
session.verify = False


def fetch_moca_exhibitions():
    base_url = "https://www.moca.taipei/tw"
    exhs_url = "https://www.moca.taipei/tw/ExhibitionAndEvent"
    museum_name = "當代藝術館"

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

        # 展覽日期
        ex_date = ""
        dates = [d.get_text(strip=True) for d in exh.find_all("p", class_="day")]
        if dates:
            ex_date = " - ".join(dates[:2])

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
            "date": ex_date,
            "topic": "",
            "url": link,
            "image_url": ex_img,
            "location": ex_place,
            "time": "",
            "category": "",
            "extra": "",
        })

    return results
