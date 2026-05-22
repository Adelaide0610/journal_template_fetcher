---
name: journal-template-fetcher
description: 学术期刊论文模板下载工具 — 自动搜索并下载期刊的 LaTeX/Word 模板
trigger: 用户要求下载期刊论文模板、查找期刊模板、获取 LaTeX/Word 模板
---

# Journal Template Fetcher

自动搜索并下载学术期刊的论文模板（LaTeX / Word）。

## 用法

```bash
# 交互模式
python -m journal_template_fetcher

# 直接指定期刊
python -m journal_template_fetcher "IEEE Transactions on Industrial Informatics"

# 启用 Playwright 浏览器渲染（处理 JS 动态页面）
python -m journal_template_fetcher "Nature" --browser

# 启用 DeepSeek AI 兜底（常规搜索失败时用 AI 解析）
python -m journal_template_fetcher "Elsevier" --deepseek --api-key sk-xxx

# 指定搜索引擎
python -m journal_template_fetcher "MDPI" --search-engine google
```

## 环境变量

| 变量 | 用途 |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `GOOGLE_API_KEY` | Google Custom Search API 密钥 |
| `GOOGLE_CX` | Google Custom Search 引擎 ID |

## 触发词

当用户提到以下关键词时自动调用本技能：
- 下载/查找 期刊模板
- 期刊 LaTeX/Word 模板
- 某期刊的论文模板
- 投稿模板、author template、manuscript template
