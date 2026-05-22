"""
Core fetcher — 整合搜索、浏览器渲染、解析、下载、解压的全流程。

流程：
  1. 已知出版社 URL 模式匹配
  2. 搜索引擎查找模板页面
  3. 访问页面（普通请求 或 Playwright JS 渲染）
  4. 解析 HTML 提取下载链接
  5. 下载模板文件
  6. 解压 ZIP
  7. 以上均失败时 → DeepSeek AI 兜底
"""

import logging
import random
import re
import time
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import (
    ALLOWED_EXTS,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    TEMPLATES_ROOT,
    get_headers,
)
from searcher import create_searcher

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 已知出版社模板 URL
# ──────────────────────────────────────────────
PUBLISHER_URLS: dict[str, list[str]] = {
    "ieee": [
        "https://template-selector.ieee.org/",
        "https://www.ieee.org/conferences/publishing/templates.html",
    ],
    "elsevier": [
        "https://www.elsevier.com/authors/tools-and-resources",
    ],
    "springer": [
        "https://www.springer.com/gp/authors-editors/book-authors-editors/manuscript-preparation",
    ],
    "nature": [
        "https://www.nature.com/nature/for-authors",
        "https://www.nature.com/srep/journal-author-resources",
    ],
    "mdpi": [
        "https://www.mdpi.com/authors",
    ],
    "taylor & francis": [
        "https://authorservices.taylorandfrancis.com/",
    ],
    "wiley": [
        "https://authorservices.wiley.com/author-resources/index.html",
    ],
    "science": [
        "https://www.science.org/content/page/science-information-authors",
    ],
    "acm": [
        "https://www.acm.org/publications/authors/manuscript-template",
    ],
    "sage": [
        "https://us.sagepub.com/en-us/nam/journal-author-archives",
    ],
    "iop": [
        "https://publishingsupport.iopscience.iop.org/",
    ],
    "oxford": [
        "https://academic.oup.com/pages/authoring",
    ],
    "cambridge": [
        "https://www.cambridge.org/core/services/authors",
    ],
}


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────


def slugify(name: str) -> str:
    """期刊名 → 合法文件夹名。"""
    s = name.strip().lower()
    s = re.sub(r"[^\w一-鿿]+", "_", s)
    return s.strip("_")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_template_url(url: str) -> bool:
    """判断 URL 是否指向模板文件。"""
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in ALLOWED_EXTS)


def is_template_page_link(href: str, text: str) -> bool:
    """判断链接是否指向模板相关页面。"""
    combined = (href + " " + text).lower()
    keywords = [
        "template", "sample", "manuscript", "format", "style",
        "latex", "word", "doc", "zip", "guideline", "instruction",
        "author", "preparation", "download", "submission",
    ]
    return any(kw in combined for kw in keywords)


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name)


# ──────────────────────────────────────────────
# HTTP 请求
# ──────────────────────────────────────────────


def smart_get(
    url: str,
    session: Optional[requests.Session] = None,
    stream: bool = False,
) -> Optional[requests.Response]:
    """带超时和自动重试的 GET。"""
    sess = session or requests.Session()
    try:
        resp = sess.get(url, headers=get_headers(), timeout=REQUEST_TIMEOUT, stream=stream)
        if resp.status_code == 200:
            return resp

        logger.warning("HTTP %d for %s", resp.status_code, url)
        if resp.status_code in (403, 429, 503):
            wait = random.uniform(5, 12)
            logger.info("等待 %.1fs 后重试 …", wait)
            time.sleep(wait)
            resp = sess.get(
                url,
                headers=get_headers(referer=url),
                timeout=REQUEST_TIMEOUT,
                stream=stream,
            )
            if resp.status_code == 200:
                return resp
        return None
    except requests.RequestException as e:
        logger.warning("请求失败 %s: %s", url, e)
        return None


# ──────────────────────────────────────────────
# HTML 解析：提取下载链接
# ──────────────────────────────────────────────


def parse_for_downloads(page_url: str, html: str, domain: str) -> list[str]:
    """从 HTML 中提取模板下载链接。"""
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []
    seen: set[str] = set()

    # 清理干扰元素
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # ── 策略 1：直接的文件链接 ──
    for a in soup.find_all("a", href=True):
        full = urljoin(page_url, a["href"].strip())
        if full in seen:
            continue
        if is_template_url(full):
            seen.add(full)
            found.append(full)

    # ── 策略 2：模板区域的链接 ──
    for sel in [
        "[class*='template'] a[href]", "[id*='template'] a[href]",
        "[class*='download'] a[href]", "[id*='download'] a[href]",
        "[class*='author'] a[href]", "[id*='author'] a[href]",
        "[class*='submission'] a[href]",
    ]:
        for a in soup.select(sel):
            full = urljoin(page_url, a["href"].strip())
            if full not in seen:
                seen.add(full)
                found.append(full)

    # ── 策略 3：同域内页（可能指向下一个模板页面） ──
    for a in soup.find_all("a", href=True):
        full = urljoin(page_url, a["href"].strip())
        if full in seen:
            continue
        parsed = urlparse(full)
        if domain in parsed.netloc and is_template_page_link(full, a.get_text(strip=True)):
            seen.add(full)
            found.append(full)

    return found


# ──────────────────────────────────────────────
# BFS 遍历页面
# ──────────────────────────────────────────────


def bfs_find_templates(
    start_url: str,
    max_pages: int = 8,
    use_browser: bool = False,
) -> list[str]:
    """
    从 start_url 出发，广度优先遍历同域页面找模板下载链接。

    use_browser=True 时用 Playwright 渲染 JS 动态内容。
    """
    domain = urlparse(start_url).netloc
    visited: set[str] = set()
    queue: list[str] = [start_url]
    found: list[str] = []

    browser_mgr = None
    if use_browser:
        try:
            from browser import BrowserManager
            browser_mgr = BrowserManager().__enter__()
        except Exception as e:
            logger.warning("浏览器启动失败，回退到 HTTP: %s", e)

    session = requests.Session() if not browser_mgr else None

    try:
        while queue and len(visited) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            logger.debug("BFS: %s", url)

            html = ""
            if browser_mgr:
                html = browser_mgr.render_page(url, wait_seconds=2)
            else:
                resp = smart_get(url, session=session)
                if resp is not None:
                    html = resp.text

            if not html:
                continue

            links = parse_for_downloads(url, html, domain)
            for link in links:
                if is_template_url(link):
                    if link not in found:
                        found.append(link)
                else:
                    parsed = urlparse(link)
                    if domain == parsed.netloc and link not in visited:
                        queue.append(link)

            time.sleep(random.uniform(*REQUEST_DELAY))
    finally:
        if browser_mgr:
            browser_mgr.__exit__(None, None, None)

    return found


# ──────────────────────────────────────────────
# 下载与解压
# ──────────────────────────────────────────────


def download_file(url: str, save_dir: Path) -> Optional[Path]:
    """下载文件到 save_dir，返回本地路径。"""
    resp = smart_get(url, stream=True)
    if resp is None:
        return None

    # 从 Content-Disposition 或 URL 取文件名
    cd = resp.headers.get("Content-Disposition", "")
    fname = ""
    if "filename=" in cd:
        fname = re.findall(r'filename=["\']?([^"\';]+)', cd)
        fname = fname[0] if fname else ""

    if not fname:
        path_part = urlparse(url).path.split("/")[-1]
        fname = sanitize_filename(path_part) if path_part else f"template_{int(time.time())}.file"

    local = save_dir / sanitize_filename(fname)

    with open(local, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    logger.info("已下载: %s (%d bytes)", local.name, local.stat().st_size)
    return local


def extract_zip(zip_path: Path, dest: Path) -> list[Path]:
    """解压 ZIP 到 dest，返回所有解出文件路径。"""
    extracted: list[Path] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest)
            for name in zf.namelist():
                target = dest / name
                if target.is_file():
                    extracted.append(target)
        logger.info("已解压: %s → %d 个文件", zip_path.name, len(extracted))
    except zipfile.BadZipFile:
        logger.warning("损坏的 ZIP: %s", zip_path)
    return extracted


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────


def fetch_templates(
    journal_name: str,
    use_browser: bool = False,
    search_engine: str = "auto",
) -> dict:
    """
    主函数：根据期刊名称抓取模板文件。

    返回
    -------
    {
        "journal": str,
        "save_dir": str,
        "downloaded": [str, ...],   # 下载成功的文件
        "extracted": [str, ...],    # 解压出的文件
        "errors": [str, ...],
        "deepseek_used": bool,
        "method": str,              # 成功使用的方法
    }
    """
    save_name = slugify(journal_name)
    save_dir = ensure_dir(Path(TEMPLATES_ROOT) / save_name)

    result: dict = {
        "journal": journal_name,
        "save_dir": str(save_dir),
        "downloaded": [],
        "extracted": [],
        "errors": [],
        "deepseek_used": False,
        "method": "",
    }

    # ── 第 1 步：收集候选 URL ──
    candidates: list[str] = []

    # 1a. 已知出版社模式
    name_lower = journal_name.lower()
    for publisher, urls in PUBLISHER_URLS.items():
        if publisher in name_lower:
            candidates.extend(urls)
            logger.info("匹配到已知出版社: %s → %s", publisher, urls[0])

    # 1b. 搜索引擎
    logger.info("搜索引擎搜索: '%s template LaTeX Word' …", journal_name)
    searcher = create_searcher(search_engine)
    query = f"{journal_name} author template LaTeX Word download"
    search_results = searcher.search(query, num_results=10)
    candidates.extend(r.url for r in search_results)

    logger.info("共 %d 个候选 URL", len(candidates))

    # ── 第 2 步：BFS 遍历找下载链接 ──
    logger.info("BFS 遍历页面查找模板下载链接 …")
    all_downloads: list[str] = []
    explored_urls = set()

    # 先试普通 HTTP
    for url in candidates[:5]:
        if url in explored_urls:
            continue
        explored_urls.add(url)
        logger.info("  普通模式: %s", url)
        dl_urls = bfs_find_templates(url, max_pages=6, use_browser=False)
        if dl_urls:
            all_downloads.extend(dl_urls)
            result["method"] = "HTTP"
            break
        time.sleep(random.uniform(*REQUEST_DELAY))

    # 如果普通模式没找到且 use_browser，尝试用 Playwright 渲染
    if not all_downloads and use_browser:
        logger.info("HTTP 模式未找到, 启用 Playwright JS 渲染 …")
        for url in candidates[:3]:
            if url in explored_urls:
                continue
            explored_urls.add(url)
            logger.info("  浏览器模式: %s", url)
            dl_urls = bfs_find_templates(url, max_pages=4, use_browser=True)
            if dl_urls:
                all_downloads.extend(dl_urls)
                result["method"] = "Playwright JS渲染"
                break
            time.sleep(random.uniform(*REQUEST_DELAY))

    # 去重
    all_downloads = list(dict.fromkeys(all_downloads))
    logger.info("找到 %d 个下载链接", len(all_downloads))

    if not all_downloads:
        result["errors"].append("未能找到任何模板下载链接。")
        # 留给 main.py 决定是否调用 DeepSeek
        return result

    # ── 第 3 步：下载文件 ──
    logger.info("开始下载模板文件 …")
    for url in all_downloads:
        if not is_template_url(url):
            continue
        local = download_file(url, save_dir)
        if local is not None:
            result["downloaded"].append(str(local))
            # 自动解压 ZIP
            if local.suffix.lower() == ".zip":
                extracted = extract_zip(local, save_dir)
                result["extracted"].extend(str(p) for p in extracted)
        time.sleep(random.uniform(0.5, 1.5))

    logger.info("完成！下载 %d 个文件，解压 %d 个文件", len(result["downloaded"]), len(result["extracted"]))
    return result
