import csv
import traceback

print("👉 app.py 開始執行")

# 先確認目前工作目錄（看是不是在 exhibitions 資料夾）
import os
print("👉 當前工作目錄:", os.getcwd())

# 嘗試匯入七個模組
try:
    print("👉 開始匯入模組...")
    from songshan import fetch_songshan_exhibitions
    from npm_museum import fetch_npm_exhibitions
    from moca import fetch_moca_exhibitions
    from huashan import fetch_huashan_exhibitions
    from fubon import fetch_fubon_exhibitions
    from tfam import fetch_tfam_exhibitions
    from ntnu import fetch_ntnu_exhibitions
    print("✅ 模組匯入成功")
except Exception as e:
    print("❌ 匯入模組時發生錯誤：")
    traceback.print_exc()
    input("按 Enter 結束")
    raise


FIELDNAMES = [
    "館別",
    "展覽名稱",
    "展覽日期",
    "展覽主題",
    "展覽連結",
    "展覽圖片",
    "展覽地點",
    "展覽時間",
    "展覽類別",
    "備註",
]


def normalize(ex):
    return {
        "館別": ex.get("museum", ""),
        "展覽名稱": ex.get("title", ""),
        "展覽日期": ex.get("date", ""),
        "展覽主題": ex.get("topic", ""),
        "展覽連結": ex.get("url", ""),
        "展覽圖片": ex.get("image_url", ""),
        "展覽地點": ex.get("location", ""),
        "展覽時間": ex.get("time", ""),
        "展覽類別": ex.get("category", ""),
        "備註": ex.get("extra", ""),
    }


def collect_all_exhibitions():
    all_exhibitions = []

    print("👉 抓取 松山文創園區...")
    all_exhibitions.extend(fetch_songshan_exhibitions())
    print(f"   松山累積筆數：{len(all_exhibitions)}")

    print("👉 抓取 國立故宮博物院...")
    all_exhibitions.extend(fetch_npm_exhibitions())
    print(f"   故宮累積筆數：{len(all_exhibitions)}")

    print("👉 抓取 當代藝術館...")
    all_exhibitions.extend(fetch_moca_exhibitions())
    print(f"   當代累積筆數：{len(all_exhibitions)}")

    print("👉 抓取 華山1914文創園區...")
    all_exhibitions.extend(fetch_huashan_exhibitions())
    print(f"   華山累積筆數：{len(all_exhibitions)}")

    print("👉 抓取 富邦美術館...")
    all_exhibitions.extend(fetch_fubon_exhibitions())
    print(f"   富邦累積筆數：{len(all_exhibitions)}")

    print("👉 抓取 臺北市立美術館...")
    all_exhibitions.extend(fetch_tfam_exhibitions())
    print(f"   北美館累積筆數：{len(all_exhibitions)}")

    print("👉 抓取 師大美術館...")
    all_exhibitions.extend(fetch_ntnu_exhibitions())
    print(f"   師大累積筆數：{len(all_exhibitions)}")

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
    print("👉 進入 main()")
    try:
        exhibitions = collect_all_exhibitions()
        print(f"👉 全部抓完，共 {len(exhibitions)} 筆")
        save_to_csv("all_museums_exhibitions.csv", exhibitions)
        print("🎉 程式執行完畢")
    except Exception as e:
        print("❌ main() 執行過程中發生錯誤：")
        traceback.print_exc()
        input("按 Enter 結束")
        raise


if __name__ == "__main__":
    print(f"👉 __name__ = {__name__}")
    main()
