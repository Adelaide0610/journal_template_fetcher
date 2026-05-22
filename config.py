"""
Configuration settings for the journal template fetcher.
"""

import os
import random

# ============================================================
# User-Agent 池
# ============================================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
]

# ============================================================
# 请求设置
# ============================================================
REQUEST_TIMEOUT = 30
REQUEST_DELAY = (2, 5)

# ============================================================
# 下载与输出
# ============================================================
# 模板下载到运行目录下的 templates/ 中（开源友好，不污染源码目录）
TEMPLATES_ROOT = os.path.join(os.getcwd(), "templates")

TEX_EXTENSIONS = {".tex", ".sty", ".cls", ".bst", ".bib", ".ins", ".dtx"}
DOC_EXTENSIONS = {".doc", ".docx"}
ZIP_EXTENSIONS = {".zip", ".tar", ".gz", ".bz2"}
ALLOWED_EXTS = TEX_EXTENSIONS | DOC_EXTENSIONS | ZIP_EXTENSIONS

# ============================================================
# 搜索引擎设置
# ============================================================
SEARCH_ENGINE = "auto"  # auto | duckduckgo | google | playwright
SEARCH_TIMEOUT = 15

# Google Custom Search API (可选，最稳定)
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CX = os.environ.get("GOOGLE_CX", "")

# ============================================================
# Playwright (可选，用于 JS 渲染 + Google 搜索)
# ============================================================
PLAYWRIGHT_HEADLESS = True
PLAYWRIGHT_TIMEOUT = 30000  # ms

# ============================================================
# DeepSeek API（可选）
# ============================================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"


# ============================================================
# 辅助函数
# ============================================================


def get_random_ua() -> str:
    return random.choice(USER_AGENTS)


def get_headers(referer: str = "") -> dict:
    headers = {
        "User-Agent": get_random_ua(),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        headers["Referer"] = referer
    return headers
