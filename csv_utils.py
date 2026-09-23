"""CSV 輸出共用工具。"""


def csv_safe(value):
    """避免以 = + - @ 開頭的爬取內容在 Excel 被當成公式執行（CSV injection）。"""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value
