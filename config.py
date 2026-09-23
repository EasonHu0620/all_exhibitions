"""從環境變數（或專案根目錄的 .env）讀取機密設定，避免把金鑰、密碼寫進程式碼。"""
import os
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        # 已存在的環境變數優先，.env 只補缺的
        os.environ.setdefault(key.strip(), value)


_load_dotenv(Path(__file__).resolve().parent / ".env")


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"缺少環境變數 {name}。請參考 .env.example 建立 .env，或在系統中設定。"
        )
    return value


def get_db_config() -> dict:
    config = {
        "host": os.environ.get("DB_HOST", "127.0.0.1"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": require_env("DB_USER"),
        "password": require_env("DB_PASSWORD"),
        "database": os.environ.get("DB_NAME", "exhibitions"),
        "charset": "utf8mb4",
    }
    # 連遠端資料庫時設定 DB_SSL_CA（CA 憑證路徑），以 TLS 加密並驗證伺服器憑證
    ssl_ca = os.environ.get("DB_SSL_CA")
    if ssl_ca:
        # 有 CA 時 PyMySQL 預設就會驗證憑證與主機名稱
        config["ssl"] = {"ca": ssl_ca}
    return config
