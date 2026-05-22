"""
DeepSeek API 辅助模块 — 当常规爬虫找不到下载链接时，让 AI 直接解析 HTML。
"""

import json
import logging
from typing import Any

import requests

from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL, get_headers

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个学术期刊模板抓取助手。你的任务是从给定的网页 HTML 中提取作者论文模板的下载链接。

要求：
1. 只返回 LaTeX (.zip) 或 Word (.doc/.docx) 模板的**直接下载链接**。
2. 以 JSON 数组格式返回：["url1", "url2", ...]
3. 如果页面没有模板下载链接，返回空数组 []。
4. 不要包含任何其他文字说明。
5. 确保链接是完整的绝对 URL。"""


def parse_with_deepseek(html: str, journal_name: str) -> list[str]:
    """
    将页面 HTML 发送给 DeepSeek API，返回解析出的模板下载链接。

    参数
    ----------
    html : str
        页面 HTML 内容（自动截断控制 token 消耗）
    journal_name : str
        期刊名称（仅用于日志）

    返回
    -------
    list[str]
        下载链接列表
    """
    if not DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY 未设置，跳过 DeepSeek 调用。")
        return []

    # 截断 HTML — 保留头尾
    if len(html) > 50_000:
        html = html[:30_000] + "\n\n<!-- ... [truncated] ... -->\n\n" + html[-10_000:]

    payload: dict[str, Any] = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"请从以下页面 HTML 中提取 '{journal_name}' 的论文模板下载链接：\n\n{html}",
            },
        ],
        "temperature": 0.1,
        "max_tokens": 2048,
    }

    headers = {
        **get_headers(),
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()

        # 清理 markdown 代码块标记
        if content.startswith("```"):
            content = content.strip("`").strip()
            if content.startswith("json"):
                content = content[4:].strip()

        links: list[str] = json.loads(content)
        logger.info("DeepSeek 返回 %d 个链接", len(links))
        return links

    except json.JSONDecodeError:
        logger.warning("DeepSeek 返回的不是合法 JSON:\n%s", content)  # type: ignore
        return []
    except (requests.RequestException, KeyError) as e:
        logger.warning("DeepSeek API 调用失败: %s", e)
        return []
