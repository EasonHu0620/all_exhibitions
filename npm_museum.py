# npm_museum.py
import requests as req
from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
session = req.Session()
session.verify = False


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

        # 展覽日期
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
            "date": ex_date,
            "topic": ex_tag,
            "url": ex_link,
            "image_url": ex_img,
            "location": ex_place,
            "time": "",
            "category": ex_tag,
            "extra": "",
        })

    return results
