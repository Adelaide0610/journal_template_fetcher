#!/usr/bin/env python3
"""
Journal Template Fetcher — 学术期刊论文模板下载工具。

用法：
    python -m journal_template_fetcher "IEEE Transactions on Industrial Informatics"
    python -m journal_template_fetcher "Nature" --browser
    python -m journal_template_fetcher "Elsevier" --deepseek
    python -m journal_template_fetcher                           # 交互模式
"""

import argparse
import logging
import sys
from pathlib import Path

from config import DEEPSEEK_API_KEY, TEMPLATES_ROOT
from deepseek_helper import parse_with_deepseek
from fetcher import (
    download_file,
    ensure_dir,
    fetch_templates,
    slugify,
    smart_get,
)
from searcher import create_searcher


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")


def deepseek_fallback(journal_name: str) -> list[str]:
    """DeepSeek 兜底：将候选页面 HTML 发给 AI 提取链接。"""
    print("\n[DeepSeek 兜底] 正在调用 AI 解析模板页面 …")

    searcher = create_searcher()
    all_links: list[str] = []

    query = f"{journal_name} author template LaTeX Word download"
    results = searcher.search(query, num_results=5)

    for r in results[:3]:
        print(f"  分析: {r.url}")
        resp = smart_get(r.url)
        if resp is None:
            continue
        links = parse_with_deepseek(resp.text, journal_name)
        all_links.extend(links)

    if not all_links:
        print("  DeepSeek 未能找到模板下载链接。")
        return []

    save_dir = ensure_dir(Path(TEMPLATES_ROOT) / slugify(journal_name))
    downloaded: list[str] = []
    for url in all_links:
        local = download_file(url, save_dir)
        if local is not None:
            downloaded.append(str(local))
            print(f"  ✓ {local.name}")

    return downloaded


def main():
    parser = argparse.ArgumentParser(
        description="下载学术期刊的论文模板（LaTeX / Word）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "journal",
        nargs="?",
        help='期刊名称，例如 "IEEE Transactions on Industrial Informatics"',
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="对 JS 动态页面启用 Playwright 浏览器渲染",
    )
    parser.add_argument(
        "--deepseek",
        action="store_true",
        help="启用 DeepSeek API 兜底（常规搜索 + 浏览器均失败时）",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="DeepSeek API Key（也可设环境变量 DEEPSEEK_API_KEY）",
    )
    parser.add_argument(
        "--search-engine",
        default="auto",
        choices=["auto", "duckduckgo", "google", "playwright"],
        help="搜索引擎 (默认 auto = 自动选择)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="输出详细调试信息",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger("main")

    # ── 交互模式 ──
    journal_name = args.journal
    if not journal_name:
        print("=" * 50)
        print("  学术期刊论文模板下载工具")
        print("=" * 50)
        journal_name = input("  请输入期刊名称: ").strip()
        if not journal_name:
            print("  未输入期刊名称，退出。")
            sys.exit(1)

    print(f"\n▶ 目标期刊 : {journal_name}")
    print(f"▶ 保存目录 : {TEMPLATES_ROOT}/{slugify(journal_name)}/")
    print(f"▶ 搜索引擎 : {args.search_engine}")
    print(f"▶ 浏览器   : {'启用' if args.browser else '关闭'}")
    print(f"▶ DeepSeek : {'启用' if args.deepseek else '关闭'}")
    print()

    # ── 执行抓取 ──
    result = fetch_templates(
        journal_name,
        use_browser=args.browser,
        search_engine=args.search_engine,
    )

    # ── 输出结果 ──
    print("\n" + "=" * 50)
    print("  结果汇总")
    print("=" * 50)

    if result.get("method"):
        print(f"\n  使用方式: {result['method']}")

    if result["downloaded"]:
        print(f"\n  ✓ 下载了 {len(result['downloaded'])} 个文件:")
        for f in result["downloaded"]:
            print(f"    · {Path(f).name}")
    else:
        print("\n  ✗ 常规抓取未找到模板文件。")

    if result["extracted"]:
        tex_files = [f for f in result["extracted"] if Path(f).suffix in {".tex", ".sty", ".cls"}]
        other_files = [f for f in result["extracted"] if Path(f).suffix not in {".tex", ".sty", ".cls"}]
        print(f"\n  📦 解压出 {len(result['extracted'])} 个文件:")
        if tex_files:
            print(f"     LaTeX 核心 ({len(tex_files)}):")
            for f in tex_files:
                print(f"      · {Path(f).name}")
        if other_files:
            print(f"     其他 ({len(other_files)}):")
            for f in other_files[:5]:
                print(f"      · {Path(f).name}")
            if len(other_files) > 5:
                print(f"      … 等 {len(other_files)} 个文件")

    if result.get("errors"):
        print(f"\n  ⚠ 提示 ({len(result['errors'])}):")
        for e in result["errors"]:
            print(f"    - {e}")

    # ── DeepSeek 兜底 ──
    ds_downloaded: list[str] = []
    if not result["downloaded"] and args.deepseek:
        api_key = args.api_key or DEEPSEEK_API_KEY
        if api_key:
            import os
            os.environ["DEEPSEEK_API_KEY"] = api_key
            ds_downloaded = deepseek_fallback(journal_name)
            if ds_downloaded:
                result["downloaded"].extend(ds_downloaded)
                result["deepseek_used"] = True
        else:
            print("\n  ⚠ 已启用 --deepseek 但未设置 API Key。")
            print("     请通过 --api-key 参数或环境变量 DEEPSEEK_API_KEY 设置。")

    # ── 最终提示 ──
    print()
    if result["downloaded"]:
        print(f"  ✅ 文件已保存到: {Path(TEMPLATES_ROOT) / slugify(journal_name)}")
        print(f"     共 {len(result['downloaded'])} 个文件\n")
    else:
        print("  ❌ 未能下载任何模板文件。可以尝试:\n")
        print(f"     python -m journal_template_fetcher \"{journal_name}\" --browser")
        print(f"     python -m journal_template_fetcher \"{journal_name}\" --deepseek --api-key sk-xxx")
        print("     python -m journal_template_fetcher \"{journal}\" --search-engine google\n")


if __name__ == "__main__":
    main()
