import requests
import pandas as pd
import pymysql

from config import get_db_config, require_env
from csv_utils import csv_safe

# ==========================
#  Google Places API 設定
# ==========================

# 金鑰從環境變數 / .env 讀取，見 config.py 與 .env.example
API_KEY = require_env("GOOGLE_API_KEY")

BASE_URL = "https://places.googleapis.com/v1/places:searchText"

# 要回傳的欄位（注意：要有 places.types 才能判斷是不是博物館）
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.types",
    "places.websiteUri",
    "places.internationalPhoneNumber",
    "places.rating",
    "places.regularOpeningHours.weekdayDescriptions"
])

HEADERS = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": API_KEY,
    "X-Goog-FieldMask": FIELD_MASK,
}

# 雙北博物館 / 美術館關鍵字
KEYWORDS = [
    # 台北市
    "台北市 博物館",
    "台北市 美術館",
    "museum in Taipei City",
    "art museum Taipei",

    # 新北市
    "新北市 博物館",
    "新北市 美術館",
    "museum in New Taipei City",
    "art museum New Taipei",
]

# 額外一定要查詢的文化園區關鍵字
EXTRA_QUERIES = [
    "華山1914文化創意產業園區",
    "松山文創園區",
]

# 只保留這兩個主園區的 place_id
KEEP_PARK_IDS = {
    "ChIJbSTgI2WpQjQRcVwWB2cnyfE",   # 華山
    "ChIJO0vOI7-rQjQR3Pl9_4cPK8g",   # 松菸
}

# 視為博物館 / 美術館的 types
MUSEUM_TYPES = {"museum", "art_gallery"}


# ==========================
#  MySQL 設定
# ==========================

DB_CONFIG = get_db_config()


# ==========================
#  API 呼叫與工具函式
# ==========================

def search_text_all_pages(text_query: str):
    """用 Places API (New) 搜尋關鍵字，支援翻頁"""
    all_places = []
    page_token = None

    while True:
        body = {
            "textQuery": text_query,
            "languageCode": "zh-TW",  # 繁體中文
            "pageSize": 20,
        }
        if page_token:
            body["pageToken"] = page_token

        resp = requests.post(BASE_URL, headers=HEADERS, json=body, timeout=30)
        print(f"[searchText] {text_query} -> {resp.status_code}")
        data = resp.json()

        if "error" in data:
            print("❌ API 錯誤：", data["error"].get("message"))
            break

        places = data.get("places", [])
        all_places.extend(places)

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return all_places


def is_museum_like(place: dict) -> bool:
    """判斷此地點是否為博物館 / 美術館"""
    types = set(place.get("types", []) or [])
    return bool(types & MUSEUM_TYPES)


def extract_row(place: dict) -> dict:
    """整理輸出欄位（不輸出類型 types）"""
    pid = place.get("id")
    name = place.get("displayName", {}).get("text")
    addr = place.get("formattedAddress")
    loc = place.get("location", {}) or {}
    lat = loc.get("latitude")
    lng = loc.get("longitude")
    website = place.get("websiteUri")
    phone = place.get("internationalPhoneNumber")
    rating = place.get("rating")
    opening_list = place.get("regularOpeningHours", {}).get("weekdayDescriptions", [])

    opening_str = "|".join(opening_list) if opening_list else None

    return {
        "place_id": pid,
        "館名": name,
        "地址": addr,
        "緯度": lat,
        "經度": lng,
        "網站": website,
        "電話": phone,
        "評分": rating,
        "營業時間": opening_str,
    }


# ==========================
#  MySQL 相關函式
# ==========================

def get_db_connection():
    conn = pymysql.connect(**DB_CONFIG)
    return conn


def init_table():
    """建立資料表（若不存在），name 為 PRIMARY KEY（展覽表以館名做外鍵）"""
    create_sql = """
    CREATE TABLE IF NOT EXISTS taipei_museums_info (
        place_id VARCHAR(100) ,
        name VARCHAR(255) PRIMARY KEY,
        address TEXT,
        lat DOUBLE,
        lng DOUBLE,
        website TEXT,
        phone VARCHAR(100),
        rating DECIMAL(3,2),
        opening_hours TEXT
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(create_sql)
        conn.commit()
    finally:
        conn.close()


def upsert_museum_row(row: dict):
    """
    將一筆 row 寫入 MySQL
    name 為 PRIMARY KEY，同名的館已存在則更新其餘欄位（ON DUPLICATE KEY UPDATE）
    """
    sql = """
    INSERT INTO taipei_museums_info
    (place_id, name, address, lat, lng, website, phone, rating, opening_hours)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
      name = VALUES(name),
      address = VALUES(address),
      lat = VALUES(lat),
      lng = VALUES(lng),
      website = VALUES(website),
      phone = VALUES(phone),
      rating = VALUES(rating),
      opening_hours = VALUES(opening_hours);
    """

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, (
                row.get("place_id"),
                row.get("館名"),
                row.get("地址"),
                row.get("緯度"),
                row.get("經度"),
                row.get("網站"),
                row.get("電話"),
                row.get("評分"),
                row.get("營業時間"),
            ))
        conn.commit()
    finally:
        conn.close()


# ==========================
#  主流程
# ==========================

def main():
    # 建表（若尚未建立）
    init_table()

    all_places_by_id = {}

    # 1) 抓雙北博物館、美術館
    for kw in KEYWORDS:
        places = search_text_all_pages(kw)
        for p in places:
            pid = p.get("id")
            if pid:
                all_places_by_id[pid] = p

    # 2) 抓華山 & 松菸（避免 types 不符時被漏掉）
    for q in EXTRA_QUERIES:
        places = search_text_all_pages(q)
        for p in places:
            pid = p.get("id")
            if pid:
                all_places_by_id[pid] = p

    print("🔢 抓到（去重後） place 數量：", len(all_places_by_id))

    # 3) 保留博物館、美術館 + 華山、松菸主園區
    selected_places = []
    for p in all_places_by_id.values():
        pid = p.get("id")
        if is_museum_like(p) or pid in KEEP_PARK_IDS:
            selected_places.append(p)

    print("✅ 最終保留的 place 數量：", len(selected_places))

    # 4) 整理成 rows
    #    館名是資料表主鍵：沒有館名的略過；不同地點同名時只保留第一筆，避免互相覆蓋
    rows = []
    seen_names = {}
    for p in selected_places:
        row = extract_row(p)
        name = row["館名"]
        if not name:
            print(f"⚠️ 地點沒有館名，略過：{row['place_id']}")
            continue
        if name in seen_names:
            print(f"⚠️ 館名重複，只保留第一筆：{name}"
                  f"（保留 {seen_names[name]}，略過 {row['place_id']}）")
            continue
        seen_names[name] = row["place_id"]
        rows.append(row)

    # 5) 存成 CSV
    df = pd.DataFrame(rows).map(csv_safe)  # 避免 Excel 公式注入
    df.to_csv("taipei_museums_info.csv", encoding="utf-8-sig", index=False)
    print("📁 已輸出 CSV：taipei_museums_info.csv")

    # 6) 同步寫入 MySQL（name 為 PRIMARY KEY）
    for row in rows:
        upsert_museum_row(row)
    print("🗄️ 已同步寫入 MySQL：資料表 taipei_museums_info")


if __name__ == "__main__":
    main()
