"""
搜索引擎抽象层 — 统一接口，多后端支持。

后端选择顺序（auto 模式）：
  1. Google Custom Search API（最稳定，需 API Key）
  2. googlesearch 库（免费，但可能有验证码）
  3. Playwright Google 搜索（需要 playwright 已安装）
  4. DuckDuckGo HTML（零依赖，保底）
"""

import logging
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import (
    GOOGLE_API_KEY,
    GOOGLE_CX,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    SEARCH_ENGINE,
    get_headers,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────


@dataclass
class SearchResult:
    url: str
    title: str = ""
    snippet: str = ""


# ──────────────────────────────────────────────
# 抽象基类
# ──────────────────────────────────────────────


class BaseSearcher(ABC):
    """搜索引擎基类"""

    @abstractmethod
    def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


# ──────────────────────────────────────────────
# DuckDuckGo（零依赖，保底）
# ──────────────────────────────────────────────


class DuckDuckGoSearcher(BaseSearcher):
    @property
    def name(self) -> str:
        return "DuckDuckGo"

    def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        results: list[SearchResult] = []
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"

        try:
            resp = requests.get(url, headers=get_headers(), timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                logger.warning("DuckDuckGo returned HTTP %d", resp.status_code)
                return results

            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.select("a.result__a"):
                href = link.get("href")
                if not href:
                    continue
                title = link.get_text(strip=True)
                # DuckDuckGo 用重定向链接
                if "uddg=" in href:
                    from urllib.parse import parse_qs, urlparse

                    qs = parse_qs(urlparse(href).query)
                    href = qs.get("uddg", [href])[0]
                results.append(SearchResult(url=href, title=title))
                if len(results) >= num_results:
                    break
        except requests.RequestException as e:
            logger.warning("DuckDuckGo search failed: %s", e)

        return results


# ──────────────────────────────────────────────
# Google Custom Search API（最稳定，需 API Key + CX）
# ──────────────────────────────────────────────


class GoogleApiSearcher(BaseSearcher):
    @property
    def name(self) -> str:
        return "Google API"

    def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        results: list[SearchResult] = []
        if not GOOGLE_API_KEY or not GOOGLE_CX:
            logger.warning("GOOGLE_API_KEY 或 GOOGLE_CX 未设置，跳过 Google API 搜索。")
            return results

        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CX,
            "q": query,
            "num": min(num_results, 10),
        }
        try:
            resp = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("items", []):
                results.append(
                    SearchResult(
                        url=item.get("link", ""),
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                    )
                )
        except requests.RequestException as e:
            logger.warning("Google API search failed: %s", e)
        except (KeyError, ValueError) as e:
            logger.warning("Google API response parse error: %s", e)

        # API 只返回 10 条，如果不够尝试第二页
        if len(results) < num_results:
            params["start"] = 11
            params["num"] = min(num_results - len(results), 10)
            try:
                resp = requests.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("items", []):
                    results.append(
                        SearchResult(
                            url=item.get("link", ""),
                            title=item.get("title", ""),
                            snippet=item.get("snippet", ""),
                        )
                    )
            except Exception:
                pass

        return results


# ──────────────────────────────────────────────
# googlesearch 库（免费，爬取 Google）
# ──────────────────────────────────────────────


class GoogleLibSearcher(BaseSearcher):
    """依赖 googlesearch-python 包"""

    @property
    def name(self) -> str:
        return "Google (lib)"

    def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        results: list[SearchResult] = []
        try:
            from googlesearch import search as google_search

            for url in google_search(query, num_results=num_results, lang="zh-CN"):
                results.append(SearchResult(url=url, title=""))
                time.sleep(random.uniform(*REQUEST_DELAY))
        except ImportError:
            logger.warning("googlesearch-python 未安装，跳过。")
        except Exception as e:
            logger.warning("Google lib search failed: %s", e)
        return results


# ──────────────────────────────────────────────
# 浏览器搜索（Playwright 驱动 Google）
# ──────────────────────────────────────────────


class PlaywrightSearcher(BaseSearcher):
    @property
    def name(self) -> str:
        return "Playwright+Google"

    def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        results: list[SearchResult] = []
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=get_random_ua(),
                    locale="zh-CN",
                )
                page = context.new_page()
                page.goto(
                    f"https://www.google.com/search?q={requests.utils.quote(query)}&hl=zh-CN",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                page.wait_for_timeout(2000)

                for link in page.query_selector_all("a[href]"):
                    href = link.get_attribute("href")
                    if not href or not href.startswith("http"):
                        continue
                    # 跳过 Google 自己的链接
                    parsed = urlparse(href)
                    if "google" in parsed.netloc:
                        continue
                    results.append(
                        SearchResult(url=href, title=link.inner_text())
                    )
                    if len(results) >= num_results:
                        break

                browser.close()
        except ImportError:
            logger.warning("playwright 未安装，跳过。")
        except Exception as e:
            logger.warning("Playwright search failed: %s", e)

        return results


# ──────────────────────────────────────────────
# 自动选择工厂
# ──────────────────────────────────────────────


def create_searcher(engine: str = "") -> BaseSearcher:
    """根据配置创建最合适的搜索引擎实例。"""
    engine = engine or SEARCH_ENGINE

    if engine == "duckduckgo":
        return DuckDuckGoSearcher()
    if engine == "google":
        if GOOGLE_API_KEY and GOOGLE_CX:
            return GoogleApiSearcher()
        return GoogleLibSearcher()
    if engine == "playwright":
        return PlaywrightSearcher()

    # auto：按优先级尝试
    if GOOGLE_API_KEY and GOOGLE_CX:
        logger.info("使用 Google Custom Search API")
        return GoogleApiSearcher()

    try:
        import googlesearch  # noqa: F401
        logger.info("使用 googlesearch 库")
        return GoogleLibSearcher()
    except ImportError:
        pass

    try:
        import playwright  # noqa: F401
        logger.info("使用 Playwright + Google")
        return PlaywrightSearcher()
    except ImportError:
        pass

    logger.info("使用 DuckDuckGo（零依赖保底）")
    return DuckDuckGoSearcher()

