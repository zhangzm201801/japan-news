# 日本ニュース热点 TOP 20

每日自动抓取日本最新 Top 20 热点新闻，生成静态网页一览，点击标题进入详情页。

## 数据源

| 来源 | 类型 |
|------|------|
| Yahoo! Japan ニュース | RSS |
| NHK ニュース | RSS |
| Google News Japan | RSS |
| 朝日新聞 | RSS |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 手动刷新（单次）
python fetch_news.py      # 抓取新闻 → data/news.json
python generate_site.py   # 生成静态站点 → output/

# 3. 浏览器打开
# output/index.html
```

## 定时调度

```bash
# 后台运行，每 2 小时自动刷新
python scheduler.py

# 单次运行
python scheduler.py --once
```

## 项目结构

```
japan-news/
├── fetch_news.py          # 4 源并发抓取 + 去重排序
├── generate_site.py       # Jinja2 静态站点生成
├── scheduler.py           # 定时调度器
├── requirements.txt       # Python 依赖
├── data/
│   └── news.json          # Top 20 新闻数据
├── templates/
│   ├── index.html         # 列表页模板
│   └── detail.html        # 详情页模板
└── output/
    ├── index.html         # 生成的列表页
    ├── style.css          # 日式简约样式
    └── detail/            # 20 个详情页
```

## 技术栈

- **Python 3** — feedparser / Jinja2 / requests / schedule
- **前端** — 纯 HTML/CSS（响应式布局，日式配色）
- **分类** — 基于关键词自动标注（政治/経済/社会/国際/科技/スポーツ/エンタメ）
