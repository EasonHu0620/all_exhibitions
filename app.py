import csv
from datetime import datetime
import traceback
import os

import pymysql

from config import get_db_config
from csv_utils import csv_safe
from songshan import fetch_songshan_exhibitions
from npm_museum import fetch_npm_exhibitions
from moca import fetch_moca_exhibitions
from huashan import fetch_huashan_exhibitions
from fubon import fetch_fubon_exhibitions
from tfam import fetch_tfam_exhibitions
from ntnu import fetch_ntnu_exhibitions

# ===================== MySQL 設定 =====================

# 帳密從環境變數 / .env 讀取，見 config.py 與 .env.example
DB_CONFIG = get_db_config()

TABLE_NAME = "taipei_exhibitions"

# 館名改過的舊寫法 → 新寫法，建表時會把舊資料的館名換成新的
MUSEUM_ALIASES = {
    "台北當代藝術館": "臺北當代藝術館",
}

# ==================== 輸出 CSV 欄位 ====================

FIELDNAMES = [
    "館別",
    "展覽名稱",
    "展覽日期",
    "開始日期",
    "結束日期",
    "是否常設展",
    "展覽主題",
    "展覽連結",
    "展覽圖片",
    "展覽地點",
    "展覽時間",
    "展覽類別",
    "備註",
]


def clean_date(value):
    """統一成 YYYY-MM-DD 字串；沒有或格式不對就回 None。"""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def normalize(ex):
    """統一欄位名稱，方便寫入 CSV"""
    row = {
        "館別": ex.get("museum", ""),
        "展覽名稱": ex.get("title", ""),
        "展覽日期": ex.get("date", ""),
        "開始日期": clean_date(ex.get("start_date")) or "",
        "結束日期": clean_date(ex.get("end_date")) or "",
        "是否常設展": 1 if ex.get("is_permanent") else 0,
        "展覽主題": ex.get("topic", ""),
        "展覽連結": ex.get("url", ""),
        "展覽圖片": ex.get("image_url", ""),
        "展覽地點": ex.get("location", ""),
        "展覽時間": ex.get("time", ""),
        "展覽類別": ex.get("category", ""),
        "備註": ex.get("extra", ""),
    }
    return {k: csv_safe(v) for k, v in row.items()}


# ===================== MySQL 工具 ======================

def get_connection():
    return pymysql.connect(**DB_CONFIG)

def init_table():
    """建立展覽資料表（包含與 taipei_museums_info 的外鍵連結）。"""
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        title        VARCHAR(255) NOT NULL,
        museum_name  VARCHAR(255) NOT NULL,
        date         VARCHAR(255),
        start_date   DATE NULL,
        end_date     DATE NULL,
        is_permanent TINYINT(1) NOT NULL DEFAULT 0,
        topic        VARCHAR(255),
        url          TEXT,
        image_url    TEXT,
        location     VARCHAR(255),
        time         VARCHAR(255),
        category     VARCHAR(255),
        extra        TEXT,
        PRIMARY KEY (title, museum_name),
        CONSTRAINT fk_museum
            FOREIGN KEY (museum_name)
            REFERENCES taipei_museums_info(name)
            ON UPDATE CASCADE
            ON DELETE RESTRICT
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(create_sql)
            # 舊資料表沒有這幾個欄位，補上
            for col, ddl in (
                ("start_date", "DATE NULL"),
                ("end_date", "DATE NULL"),
                ("is_permanent", "TINYINT(1) NOT NULL DEFAULT 0"),
            ):
                cur.execute(f"SHOW COLUMNS FROM {TABLE_NAME} LIKE %s", (col,))
                if not cur.fetchone():
                    cur.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {col} {ddl}")

            # 舊資料表的主鍵只有 title，不同館的同名展覽會互相覆蓋，改成 (title, museum_name)
            cur.execute(f"SHOW KEYS FROM {TABLE_NAME} WHERE Key_name = 'PRIMARY'")
            pk_cols = [row[4] for row in cur.fetchall()]  # Column_name
            if pk_cols == ["title"]:
                cur.execute(
                    f"ALTER TABLE {TABLE_NAME} "
                    f"DROP PRIMARY KEY, ADD PRIMARY KEY (title, museum_name)"
                )

            # 舊館名換成新館名；新館名已有同名展覽時，刪掉舊館名那筆
            for old_name, new_name in MUSEUM_ALIASES.items():
                cur.execute(
                    f"DELETE old FROM {TABLE_NAME} AS old "
                    f"JOIN {TABLE_NAME} AS cur "
                    f"  ON cur.title = old.title AND cur.museum_name = %s "
                    f"WHERE old.museum_name = %s",
                    (new_name, old_name),
                )
                cur.execute(
                    f"UPDATE {TABLE_NAME} SET museum_name = %s WHERE museum_name = %s",
                    (new_name, old_name),
                )
        conn.commit()
    finally:
        conn.close()

def save_to_mysql(exhibitions):
    """
    將展覽資料存入 MySQL。
    - (title, museum_name) 為 PRIMARY KEY，不同館的同名展覽各自一筆
    - 已存在的展覽只會更新 start_date / end_date / is_permanent
    """
    if not exhibitions:
        print("⚠️ 沒有展覽資料，不寫入 MySQL。")
        return

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = f"""
            INSERT INTO {TABLE_NAME}
            (title, museum_name, date, start_date, end_date, is_permanent, topic,
             url, image_url, location, time, category, extra)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                start_date   = VALUES(start_date),
                end_date     = VALUES(end_date),
                is_permanent = VALUES(is_permanent);
            """

            data = []
            for ex in exhibitions:
                title = ex.get("title", "")
                museum = ex.get("museum", "")
                date = ex.get("date", "")
                start_date = clean_date(ex.get("start_date"))
                end_date = clean_date(ex.get("end_date"))
                is_permanent = 1 if ex.get("is_permanent") else 0
                topic = ex.get("topic", "")
                url = ex.get("url", "")
                image_url = ex.get("image_url", "")
                location = ex.get("location", "")
                time_ = ex.get("time", "")
                category = ex.get("category", "")
                extra = ex.get("extra", "")

                # 若沒有展覽名稱，就略過，避免主鍵是空字串
                if not title:
                    continue

                data.append((
                    title,
                    museum,   # 對應 taipei_museums_info.name
                    date,
                    start_date,
                    end_date,
                    is_permanent,
                    topic,
                    url,
                    image_url,
                    location,
                    time_,
                    category,
                    extra,
                ))

            cur.executemany(sql, data)
        conn.commit()
        print(f"✅ MySQL 寫入完成（嘗試寫入 {len(data)} 筆，"
              f"已存在的展覽只更新日期 / is_permanent）")
    finally:
        conn.close()


# ==================== 收集展覽資料 =====================

SCRAPERS = [
    ("松山文創園區", "松山", fetch_songshan_exhibitions),
    ("國立故宮博物院", "故宮", fetch_npm_exhibitions),
    ("當代藝術館", "當代", fetch_moca_exhibitions),
    ("華山1914文創園區", "華山", fetch_huashan_exhibitions),
    ("富邦美術館", "富邦", fetch_fubon_exhibitions),
    ("臺北市立美術館", "北美館", fetch_tfam_exhibitions),
    ("師大美術館", "師大", fetch_ntnu_exhibitions),
]


def collect_all_exhibitions():
    """依序抓取各館；單一館失敗只略過該館，不影響其他館與後續寫入。"""
    all_exhibitions = []

    for full_name, short_name, fetch in SCRAPERS:
        print(f"👉 抓取 {full_name}...")
        try:
            all_exhibitions.extend(fetch())
        except Exception as e:
            print(f"⚠️ {full_name} 抓取失敗，略過：{type(e).__name__}: {e}")
            continue
        print(f"   {short_name}累積筆數：{len(all_exhibitions)}")

    return all_exhibitions


def save_to_csv(filename, exhibitions):
    print(f"👉 準備寫入 CSV：{filename}（共 {len(exhibitions)} 筆）")
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for ex in exhibitions:
            writer.writerow(normalize(ex))
    print("✅ CSV 寫入完成")


def main():
    print("👉 app.py 開始執行")
    print("👉 當前工作目錄:", os.getcwd())

    try:
        # 建表（若尚未存在）
        print("👉 檢查 / 建立 MySQL 資料表...")
        init_table()

        # 收集展覽
        exhibitions = collect_all_exhibitions()
        print(f"👉 全部抓完，共 {len(exhibitions)} 筆")

        # 寫 CSV
        save_to_csv("all_museums_exhibitions.csv", exhibitions)

        # 寫 MySQL（舊資料只更新起訖日期與常設展欄位）
        save_to_mysql(exhibitions)

        print("🎉 程式執行完畢")
    except Exception:
        print("❌ main() 執行過程中發生錯誤：")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
