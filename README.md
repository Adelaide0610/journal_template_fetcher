# Journal Template Fetcher

学术期刊论文模板下载工具 — 自动搜索并下载期刊的 LaTeX/Word 模板。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 交互模式
python -m journal_template_fetcher

# 直接指定期刊
python -m journal_template_fetcher "IEEE Transactions on Industrial Informatics"
```

## 功能

- **多后端搜索引擎**：Google API / Google 搜索 / Playwright / DuckDuckGo，自动选择最优
- **浏览器渲染**：支持 JavaScript 动态页面（需安装 Playwright）
- **智能解析**：自动提取模板下载链接，支持 BFS 遍历
- **自动解压**：下载的 ZIP 包自动解压
- **AI 兜底**：集成 DeepSeek API，常规方式失败时由 AI 解析页面

## 安装

### 基础安装

```bash
pip install -r requirements.txt
```

### 可选增强

```bash
# Google 搜索结果抓取（零配置）
pip install googlesearch-python

# 浏览器渲染（处理 JS 动态页面）
pip install playwright
playwright install chromium
```

## 使用

```bash
# 交互模式
python -m journal_template_fetcher

# 直接指定期刊
python -m journal_template_fetcher "Nature"

# 启用浏览器渲染
python -m journal_template_fetcher "Nature" --browser

# 启用 DeepSeek AI 兜底
python -m journal_template_fetcher "Elsevier" --deepseek --api-key sk-xxx

# 指定搜索引擎
python -m journal_template_fetcher "MDPI" --search-engine google

# 详细日志
python -m journal_template_fetcher "IEEE Access" -v
```

### 参数说明

| 参数 | 说明 |
|---|---|
| `journal` | 期刊名称（留空则进入交互模式） |
| `--browser` | 启用 Playwright 浏览器渲染 |
| `--deepseek` | 启用 DeepSeek API 兜底 |
| `--api-key` | DeepSeek API 密钥（或设环境变量） |
| `--search-engine` | 搜索引擎：auto, duckduckgo, google, playwright |
| `-v, --verbose` | 输出详细调试信息 |

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 仅 `--deepseek` 时需要 | DeepSeek API 密钥 |
| `GOOGLE_API_KEY` | 仅 Google API 时需要 | Google Custom Search API 密钥 |
| `GOOGLE_CX` | 仅 Google API 时需要 | Google Custom Search 引擎 ID |

## 项目结构

```
journal_template_fetcher/
├── CLAUDE.md          # Claude Code 技能定义
├── README.md          # 本文档
├── LICENSE            # MIT 许可证
├── .gitignore
├── requirements.txt   # 依赖列表
├── __init__.py        # 包定义
├── main.py            # CLI 入口
├── config.py          # 配置项
├── searcher.py        # 搜索引擎抽象层
├── fetcher.py         # 核心抓取逻辑
├── browser.py         # Playwright 浏览器模块
└── deepseek_helper.py # DeepSeek API 辅助
```

## 许可证

MIT
