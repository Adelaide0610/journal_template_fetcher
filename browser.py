"""
Playwright 浏览器自动化模块。

用途：
  1. 渲染 JavaScript 动态页面，获取完整的 HTML（解决 requests 拿不到动态内容的问题）
  2. 通过 Playwright 驱动 Google 搜索（比纯爬虫更稳定）

使用前需要安装：
    pip install playwright
    playwright install chromium
"""

import logging
import time
from typing import Optional

from config import PLAYWRIGHT_HEADLESS, PLAYWRIGHT_TIMEOUT, get_random_ua

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 同步上下文管理器
# ──────────────────────────────────────────────


class BrowserManager:
    """Playwright 浏览器管理器（同步 API）。

    用法：
        with BrowserManager() as bm:
            html = bm.render_page("https://example.com")
    """

    def __init__(self, headless: Optional[bool] = None):
        self.headless = headless if headless is not None else PLAYWRIGHT_HEADLESS
        self._playwright = None
        self._browser = None

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().__enter__()
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox"],
            )
            logger.debug("Playwright 浏览器已启动 (headless=%s)", self.headless)
        except ImportError:
            logger.warning("playwright 未安装, 请运行: pip install playwright && playwright install chromium")
            raise
        except Exception as e:
            logger.warning("Playwright 启动失败: %s", e)
            raise
        return self

    def __exit__(self, *args):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.__exit__(*args)
        logger.debug("Playwright 浏览器已关闭")

    # ── 公共方法 ──

    def new_page(self):
        """创建一个新的浏览器页面。"""
        context = self._browser.new_context(
            user_agent=get_random_ua(),
            locale="zh-CN",
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        page = context.new_page()
        return page

    def render_page(self, url: str, wait_seconds: int = 3) -> str:
        """访问页面并等待 JS 渲染完成，返回完整 HTML。"""
        page = self.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=PLAYWRIGHT_TIMEOUT)
            # 额外等待异步渲染
            if wait_seconds:
                page.wait_for_timeout(wait_seconds * 1000)
            html = page.content()
            logger.info("页面渲染完成: %s (%d chars)", url, len(html))
            return html
        except Exception as e:
            logger.warning("页面渲染失败: %s - %s", url, e)
            # 即使超时也可能有部分内容
            try:
                return page.content()
            except Exception:
                return ""
        finally:
            page.context.close()

    def search_google(self, query: str, num_results: int = 10) -> list[dict]:
        """使用 Google 搜索并返回结果列表 [{url, title}]。"""
        from urllib.parse import quote

        results: list[dict] = []
        page = self.new_page()
        try:
            search_url = f"https://www.google.com/search?q={quote(query)}&hl=zh-CN"
            page.goto(search_url, wait_until="networkidle", timeout=PLAYWRIGHT_TIMEOUT)
            page.wait_for_timeout(2000)

            # 处理可能的 Cookie 弹窗
            try:
                accept_btn = page.query_selector('button:has-text("接受")')
                if accept_btn:
                    accept_btn.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            # 提取搜索结果链接
            for link in page.query_selector_all("a[href]"):
                href = link.get_attribute("href")
                if not href:
                    continue
                if not href.startswith("http"):
                    continue
                from urllib.parse import urlparse
                if "google" in urlparse(href).netloc:
                    continue
                title = link.inner_text().strip()
                if title:
                    results.append({"url": href, "title": title})
                if len(results) >= num_results:
                    break

            logger.info("Google 搜索完成: 获取 %d 条结果", len(results))
        except Exception as e:
            logger.warning("Google 搜索失败: %s", e)
        finally:
            page.context.close()

        return results


# ──────────────────────────────────────────────
# 便捷函数：渲染单个页面（自动管理浏览器生命周期）
# ──────────────────────────────────────────────


def render_page(url: str, wait_seconds: int = 3) -> str:
    """一键渲染 JS 页面，返回 HTML。"""
    try:
        with BrowserManager() as bm:
            return bm.render_page(url, wait_seconds=wait_seconds)
    except Exception as e:
        logger.warning("render_page 失败: %s", e)
        return ""


def search_google_playwright(query: str, num_results: int = 10) -> list[dict]:
    """一键 Google 搜索（Playwright）。"""
    try:
        with BrowserManager() as bm:
            return bm.search_google(query, num_results=num_results)
    except Exception as e:
        logger.warning("search_google_playwright 失败: %s", e)
        return []
