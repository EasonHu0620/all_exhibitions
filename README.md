# 雙北展覽資料爬蟲

自動蒐集台北主要美術館、博物館與文創園區的**展覽資訊**與**館舍資訊**，輸出成 CSV，並同步寫入 MySQL。

## 功能

- 爬取 7 個場館目前的展覽：名稱、日期（含統一格式的開始／結束日期）、連結、圖片、地點、時間等
- 透過 Google Places API (New) 取得雙北博物館／美術館的基本資料：地址、座標、電話、網站、評分、營業時間
- 輸出 CSV，並寫入 MySQL（展覽表以外鍵連結館舍表）

### 支援的場館

| 場館 | 檔案 | 抓取方式 |
|---|---|---|
| 松山文創園區 | `songshan.py` | requests + BeautifulSoup |
| 國立故宮博物院 | `npm_museum.py` | requests + BeautifulSoup |
| 台北當代藝術館 | `moca.py` | requests + BeautifulSoup |
| 富邦美術館 | `fubon.py` | requests + BeautifulSoup |
| 師大美術館 | `ntnu.py` | requests + BeautifulSoup |
| 華山1914文創園區 | `huashan.py` | Selenium + requests |
| 臺北市立美術館 | `tfam.py` | Selenium + requests |

## 專案結構

```
.
├── app.py                        # 主程式：爬取所有展覽 → CSV + MySQL
├── museums_info.py               # 館舍資料：Google Places API → CSV + MySQL
├── config.py                     # 讀取 .env / 環境變數（金鑰、資料庫帳密）
├── http_client.py                # 共用的 requests Session（憑證驗證、重試）
├── songshan.py / npm_museum.py / moca.py / fubon.py / ntnu.py / huashan.py / tfam.py
├── all_museums_exhibitions.csv   # 輸出：全部展覽
├── taipei_museums_info.csv       # 輸出：館舍資料
├── requirements.txt
├── .env.example                  # 環境變數範本
└── .gitignore
```

## 環境需求

- Python 3.13（其他 3.x 版本未測試）
- MySQL 8.0
- Google Chrome（華山、北美館使用 Selenium，Selenium 會自動管理 driver）
- Google Cloud 的 **Places API (New)** 金鑰

## 安裝

```bash
# 1. 建立虛擬環境並安裝套件
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux：source .venv/bin/activate
pip install -r requirements.txt

# 2. 建立設定檔
copy .env.example .env            # macOS / Linux：cp .env.example .env
```

### 設定 `.env`

```
GOOGLE_API_KEY=你的 Google Places API 金鑰
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=你的資料庫帳號
DB_PASSWORD=你的資料庫密碼
DB_NAME=exhibitions
```

> ⚠️ `.env` 已被 `.gitignore` 排除，**請勿 commit**。也可以直接設定同名的系統環境變數，環境變數的優先權高於 `.env`。

### 建立資料庫

程式會自動建立資料表，但不會建立資料庫本身，請先建立資料庫與專用帳號：

```sql
CREATE DATABASE exhibitions CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'huku'@'localhost' IDENTIFIED BY '你的密碼';
GRANT ALL PRIVILEGES ON exhibitions.* TO 'huku'@'localhost';
```

帳號只需要 `exhibitions` 資料庫的權限，不要使用 root。

## 使用方式

**請依序執行**，因為展覽表的外鍵會參照館舍表：

```bash
# 1. 先更新館舍資料（建立 taipei_museums_info）
python museums_info.py

# 2. 再爬取展覽資料（建立 taipei_exhibitions）
python app.py
```

執行後會產生或更新 `taipei_museums_info.csv` 與 `all_museums_exhibitions.csv`，同時寫入 MySQL。

## 資料表

### `taipei_museums_info`（場館）
| 欄位 | 說明 |
|---|---|
| `name`（主鍵） | 館名 |
| `place_id` | Google Place ID |
| `address`、`lat`、`lng` | 地址與座標 |
| `website`、`phone` | 網站與電話 |
| `rating`、`opening_hours` | 評分與營業時間 |

寫入方式：**upsert**，同名的館會被更新。

### `taipei_exhibitions`（展覽）
| 欄位 | 說明 |
|---|---|
| `title`（主鍵） | 展覽名稱 |
| `museum_name`（外鍵） | 對應 `taipei_museums_info.name` |
| `date` | 展期原始字串（各館格式不同，僅供參考） |
| `start_date`、`end_date` | 統一格式的開始／結束日期（`DATE`，`YYYY-MM-DD`），無法解析時為 `NULL` |
| `is_permanent` | 是否為常設／長期展：`1` = 是，`0` = 否 |
| `time`、`location` | 時間、地點 |
| `topic`、`category`、`extra` | 主題、類別、備註 |
| `url`、`image_url` | 展覽連結與圖片 |

#### 日期欄位規則

| 情況 | `start_date` | `end_date` | `is_permanent` |
|---|---|---|---|
| 有開始與結束日期 | 開始日 | 結束日 | `0` |
| 單日活動（松山、華山只有一個日期） | 該日 | 同一天 | `0` |
| 只有開始日期、沒有結束（故宮 `2023-12-01~`、師大 `2024/7/1 起`） | 開始日 | `NULL` | `1` |
| 故宮「常設展」 | `NULL` | `NULL` | `1` |

因此 `end_date IS NULL` 只會出現在長期或常設展。

各館的原始日期格式不同，解析規則寫在各館檔案的 `parse_xxx_date()`。

CSV 對應欄位為「開始日期」「結束日期」「是否常設展」。

寫入方式：新的展覽名稱會新增；已存在的展覽名稱**不會覆蓋**原有內容，只會更新 `museum_name`、`start_date`、`end_date`、`is_permanent`（讓舊資料補上日期，館名有改也會同步）。

## 注意事項

- **舊資料不會被刪除**：資料庫只新增、不清除，已結束的展覽會一直留著，查詢時請用 `start_date` / `end_date` 過濾（常設展的 `end_date` 為 `NULL`，可搭配 `is_permanent` 判斷）。
- **展覽名稱是主鍵**：不同場館若有同名展覽，後者會被略過。
- **館名必須對得上**：展覽的 `museum_name` 若不在 `taipei_museums_info` 中，整批寫入會因外鍵錯誤（1452）而失敗。新增場館時，請確認館名與館舍表一致。
- **Selenium 失敗不會中斷**：如果 Chrome 無法啟動，華山或北美館會被略過並印出警告，其他場館照常執行。
- **網站改版**：爬蟲依賴各網站的 HTML 結構，網站改版後可能需要調整對應的檔案。

## 資安設計

- 金鑰與密碼從環境變數讀取，程式碼與 git 歷史中沒有機密。
- 所有 HTTPS 請求都啟用憑證驗證（`http_client.py`）。部分政府站台的憑證需要系統信任庫，因此使用 `truststore`，並只放寬 Python 3.13 的 `VERIFY_X509_STRICT`，憑證鏈與主機名稱仍會驗證。
- SQL 全部使用參數化查詢。
- 華山爬蟲只會跟隨官網網域的連結。
- CSV 輸出會處理以 `=`、`+`、`-`、`@` 開頭的內容，避免 Excel 公式注入。
- 建議：
  - 將 Google 金鑰限制為只能呼叫 Places API (New)。
  - MySQL 只監聽 `127.0.0.1`（`my.ini` 設定 `bind-address=127.0.0.1`）。
  - 在 GitHub 開啟 Secret scanning 與 Push protection。

## 疑難排解

| 現象 | 原因與處理 |
|---|---|
| `缺少環境變數 XXX` | 尚未建立 `.env`，或缺少該欄位，請參考 `.env.example` |
| Places API 回 `403`，訊息提到 IP 限制 | 金鑰設有 IP 限制而你的 IP 已變動，請到 GCP 更新，或改為只設 API 限制 |
| MySQL `1045 Access denied` | `.env` 的帳密與資料庫不一致，或設定檔尚未存檔 |
| `Unknown database 'exhibitions'` | 尚未建立資料庫，請見「建立資料庫」 |
| 外鍵錯誤 `fk_museum` | 尚未執行 `museums_info.py`，請先執行 |
| `CERTIFICATE_VERIFY_FAILED` | 請確認已安裝 `truststore`（`pip install -r requirements.txt`）。不要用關閉驗證的方式繞過 |
| 華山、北美館沒有資料 | Chrome 未安裝或無法啟動，查看終端機的 `⚠️` 警告 |
| 某個網站讀取逾時 | 部分站台回應很慢，程式會自動重試 3 次，仍失敗再重新執行即可 |

## 新增場館

1. 新增一個檔案，實作 `fetch_xxx_exhibitions()`，回傳字典的列表。
2. 每筆至少包含：`museum`、`title`、`date`、`url`、`image_url`、`location`、`time`、`topic`、`category`、`extra`。
   另請提供 `start_date`、`end_date`（`YYYY-MM-DD` 或 `None`）與 `is_permanent`（`0` / `1`），規則見「日期欄位規則」。
3. 使用 `from http_client import make_session` 取得 session，不要關閉憑證驗證。
4. 在 `app.py` 的 `collect_all_exhibitions()` 加入呼叫。
5. 確認 `museum` 的名稱與 `taipei_museums_info.name` 一致。

## 授權與資料來源

展覽與館舍資料取自各場館官方網站與 Google Places API，僅供個人學習與研究使用，使用時請遵守各網站的使用條款與 Google Maps Platform 的服務條款。
