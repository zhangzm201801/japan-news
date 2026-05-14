"""
静态站点生成器
读取 data/news.json，使用 Jinja2 渲染 index.html 和 20 个详情页
"""
import json
import os
import shutil
from datetime import datetime, timezone, timedelta

from jinja2 import Environment, FileSystemLoader

JST = timezone(timedelta(hours=9))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "news.json")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def load_news_data():
    """加载新闻 JSON 数据"""
    if not os.path.exists(DATA_FILE):
        print(f"[ERROR] 数据文件不存在: {DATA_FILE}")
        print("  请先运行: python fetch_news.py")
        return None
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_index(data):
    """生成列表页 index.html"""
    template = env.get_template("index.html")
    # 格式化更新时间
    updated_raw = data.get("updated_at", "")
    try:
        dt = datetime.fromisoformat(updated_raw)
        updated_display = dt.strftime("%H:%M")
    except Exception:
        updated_display = updated_raw

    html = template.render(
        date=data["date"],
        updated_at=updated_display,
        items=data["items"],
    )
    out_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [OK] index.html")


def generate_detail_pages(data):
    """为每条新闻生成详情页"""
    template = env.get_template("detail.html")
    date_str = data["date"]
    detail_dir = os.path.join(OUTPUT_DIR, "detail", date_str)
    os.makedirs(detail_dir, exist_ok=True)

    for item in data["items"]:
        html = template.render(item=item, date=date_str)
        out_path = os.path.join(detail_dir, f"{item['id']}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

    print(f"  [OK] detail/{date_str}/ (共 {len(data['items'])} 页)")


def copy_static_assets():
    """复制 CSS 等静态资源（style.css 已在 output/ 下，这里做验证）"""
    css_src = os.path.join(OUTPUT_DIR, "style.css")
    if not os.path.exists(css_src):
        print("  [WARN] style.css 不存在于 output/ 目录")
    else:
        print("  [OK] style.css")


def generate_all():
    """执行完整站点生成"""
    print(f"[{datetime.now(JST).strftime('%H:%M:%S')}] 开始生成静态站点...")

    data = load_news_data()
    if data is None:
        return False

    generate_index(data)
    generate_detail_pages(data)
    copy_static_assets()

    index_path = os.path.join(OUTPUT_DIR, "index.html")
    print(f"\n  完成! 请用浏览器打开:\n  file:///{index_path.replace(os.sep, '/')}")
    return True


if __name__ == "__main__":
    generate_all()
