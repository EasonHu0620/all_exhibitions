"""共用的 requests Session：保持 HTTPS 憑證驗證開啟。

- 使用作業系統的信任憑證庫（truststore），才能驗證政府憑證（如故宮）。
- 部分站台的憑證缺少 Subject Key Identifier，Python 3.13 的嚴格模式會拒絕，
  因此只關閉 VERIFY_X509_STRICT；憑證鏈與主機名稱仍會完整驗證。
"""
import ssl

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import truststore
    _base_ctx = lambda: truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
except ImportError:  # 沒裝 truststore 就退回預設（certifi）憑證庫
    _base_ctx = ssl.create_default_context


class _RelaxedStrictAdapter(HTTPAdapter):
    def _ctx(self):
        ctx = _base_ctx()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        return ctx

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._ctx()
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs["ssl_context"] = self._ctx()
        return super().proxy_manager_for(*args, **kwargs)


def make_session() -> requests.Session:
    session = requests.Session()
    # 部分站台回應很慢（單次約 8 秒），偶發逾時或 5xx 時自動重試，只重試 GET
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    session.mount("https://", _RelaxedStrictAdapter(max_retries=retry))
    return session
