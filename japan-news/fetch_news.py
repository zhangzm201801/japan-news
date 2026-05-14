"""
日本新闻热点抓取脚本
从多个 RSS 源并行抓取新闻，去重排序后取 Top 20，存入 data/news.json
"""
import json
import os
import re
import hashlib
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import mktime

import feedparser
import requests

JST = timezone(timedelta(hours=9))

RSS_SOURCES = [
    {
        "name": "Yahoo! Japan",
        "url": "https://news.yahoo.co.jp/rss/topics/top-picks.xml",
    },
    {
        "name": "NHK",
        "url": "https://www.nhk.or.jp/rss/news/cat0.xml",
    },
    {
        "name": "Google News Japan",
        "url": "https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja",
    },
    {
        "name": "朝日新聞",
        "url": "https://www.asahi.com/rss/asahi/newsheadlines.rdf",
    },
]

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "news.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

CATEGORY_KEYWORDS = {
    "政治": ["政治", "選挙", "国会", "首相", "政権", "党", "議員", "内閣", "省"],
    "経済": ["経済", "株", "円", "ドル", "企業", "市場", "金融", "貿易", "景気", "GDP"],
    "社会": ["事件", "事故", "裁判", "犯罪", "警察", "消防", "死亡", "被害"],
    "国際": ["国際", "海外", "国連", "米", "中", "韓", "露", "ウクライナ", "紛争"],
    "科技": ["AI", "IT", "宇宙", "科学", "技術", "ロケット", "半導体", "EV", "AI"],
    "スポーツ": ["野球", "サッカー", "大谷", "WBC", "五輪", "オリンピック", "テニス", "ゴルフ"],
    "エンタメ": ["芸能", "映画", "ドラマ", "音楽", "アニメ", "漫画", "歌手", "俳優"],
}


def extract_summary(entry):
    """从 feed entry 中提取摘要文本，尝试多个字段"""
    candidates = []

    # 1) summary / description
    for field in ("summary", "description"):
        val = entry.get(field)
        if val:
            candidates.append(val)

    # 2) content[0].value (Atom feed)
    content_list = entry.get("content") or []
    if content_list:
        val = content_list[0].get("value", "")
        if val:
            candidates.append(val)

    # 3) media_description
    media_desc = entry.get("media_description") or ""
    if media_desc:
        candidates.append(media_desc)

    # 4) dc:description (Dublin Core in RDF)
    dc_desc = entry.get("dc_description") or entry.get("dc:description") or ""
    if dc_desc:
        candidates.append(dc_desc)

    # HTML 实体解码映射
    html_entities = {
        "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "&apos;": "'",
    }

    def clean_text(raw):
        text = re.sub(r"<[^>]*>", "", raw).strip()
        for ent, ch in html_entities.items():
            text = text.replace(ent, ch)
        text = re.sub(r"&[a-z]+;", "", text)  # 移除其余 HTML 实体
        text = re.sub(r"\s+", " ", text)
        return text

    # 取第一个有实质内容的
    for raw in candidates:
        text = clean_text(raw)
        if len(text) >= 10:
            if len(text) > 200:
                text = text[:200] + "..."
            return text

    # 所有字段都无有效内容时返回空
    for raw in candidates:
        text = clean_text(raw)
        if text:
            if len(text) > 200:
                text = text[:200] + "..."
            return text

    return ""


def extract_published(entry):
    """从 feed entry 中提取发布时间，尝试多种日期格式"""
    from email.utils import parsedate_to_datetime as parse_rfc2822
    from datetime import timezone as tz_mod, timedelta as td_mod

    # 优先使用 feedparser 解析好的 struct_time
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                dt = datetime.fromtimestamp(mktime(parsed), tz=JST)
                return dt.strftime("%Y-%m-%d %H:%M"), dt
            except Exception:
                pass

    # 尝试解析字符串格式的日期
    for attr in ("published", "updated", "dc_date", "dc:date"):
        raw = entry.get(attr, "")
        if not raw:
            continue
        # 尝试多种解析方式
        for parser in (
            lambda s: parse_rfc2822(s),
            lambda s: datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"),
            lambda s: datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S"),
            lambda s: datetime.strptime(s[:16], "%Y-%m-%dT%H:%M"),
        ):
            try:
                dt = parser(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=JST)
                else:
                    dt = dt.astimezone(JST)
                return dt.strftime("%Y-%m-%d %H:%M"), dt
            except Exception:
                continue

    # fallback: 当前时间
    now = datetime.now(JST)
    return now.strftime("%Y-%m-%d %H:%M"), now


def classify_title(title):
    """根据标题关键词推断新闻分类"""
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in title:
                return cat
    return "総合"


def normalize_title(title):
    """标准化标题用于去重比较"""
    t = re.sub(r"[【】「」『』！？、。・\s]+", "", title)
    # 移除 emoji
    t = re.sub(r"[\U0001F300-\U0001F9FF]", "", t)
    return t[:30]


def deduplicate_items(all_items):
    """基于标题 MD5 去重，保留摘要更长的版本"""
    seen = {}
    result = []
    for item in all_items:
        norm = normalize_title(item["title"])
        key = hashlib.md5(norm.encode("utf-8")).hexdigest()
        if key not in seen:
            seen[key] = item
            result.append(item)
        else:
            existing = seen[key]
            if len(item["summary"]) > len(existing["summary"]):
                result.remove(existing)
                result.append(item)
                seen[key] = item
    return result


def fetch_single_source(source):
    """抓取单个 RSS 源，返回新闻条目列表"""
    items = []
    try:
        resp = requests.get(source["url"], headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue

            summary = extract_summary(entry)
            published_str, published_dt = extract_published(entry)
            category = classify_title(title)

            items.append({
                "title": title,
                "url": link,
                "summary": summary,
                "source": source["name"],
                "published": published_str,
                "published_dt": published_dt.isoformat() if published_dt else "",
                "category": category,
            })
    except Exception as e:
        print(f"  [WARN] {source['name']}: {e}")

    return items


def fetch_all_news():
    """并行抓取所有 RSS 源，去重排序后返回 Top 20"""
    print(f"[{datetime.now(JST).strftime('%H:%M:%S')}] 开始抓取新闻...")
    all_items = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch_single_source, src): src for src in RSS_SOURCES}
        for future in as_completed(futures):
            src = futures[future]
            try:
                items = future.result()
                print(f"  [OK] {src['name']}: {len(items)} 条")
                all_items.extend(items)
            except Exception as e:
                print(f"  [ERR] {src['name']}: {e}")

    unique_items = deduplicate_items(all_items)
    print(f"  去重后: {len(unique_items)} 条")

    # 按发布时间降序排序，时间相同按来源优先级排序
    source_order = {s["name"]: i for i, s in enumerate(RSS_SOURCES)}
    unique_items.sort(
        key=lambda x: (
            x.get("published", ""),
            -source_order.get(x.get("source", ""), 99),
        ),
        reverse=True,
    )

    top20 = unique_items[:20]
    for i, item in enumerate(top20):
        item["id"] = i + 1
        item.pop("published_dt", None)

    return top20


def save_news(items):
    """保存新闻数据到 JSON 文件"""
    today_str = datetime.now(JST).strftime("%Y-%m-%d")
    data = {
        "date": today_str,
        "updated_at": datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "items": items,
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  已保存到 {DATA_FILE}")
    return data


def main():
    items = fetch_all_news()
    if not items:
        print("[ERROR] 未能抓取到任何新闻，请检查网络连接。")
        return None
    data = save_news(items)
    print(f"  完成: 共 {len(items)} 条新闻 ({data['date']})")
    return data


if __name__ == "__main__":
    main()
