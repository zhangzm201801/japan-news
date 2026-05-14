"""
定时调度器 — 每 2 小时检查新闻新鲜度，自动刷新
后台运行: python scheduler.py
单次运行: python scheduler.py --once
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import schedule

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "news.json")

# 新闻保鲜期（小时）
MAX_AGE_HOURS = 3


def news_is_stale():
    """检查新闻数据是否过期"""
    if not os.path.exists(DATA_FILE):
        return True
    try:
        mtime = os.path.getmtime(DATA_FILE)
        age = time.time() - mtime
        return age > MAX_AGE_HOURS * 3600
    except Exception:
        return True


def run_job():
    """执行一次抓取 + 生成"""
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    if news_is_stale():
        print(f"\n{'='*50}")
        print(f"[{now}] 新闻数据过期，开始刷新...")
        print(f"{'='*50}")

        from fetch_news import main as fetch_main
        from generate_site import generate_all
        data = fetch_main()
        if data:
            generate_all()
            print(f"[{datetime.now(JST).strftime('%H:%M:%S')}] 刷新完成。")
        else:
            print(f"[{datetime.now(JST).strftime('%H:%M:%S')}] 抓取失败，跳过本次刷新。")
    else:
        print(f"[{now}] 新闻数据仍在保鲜期内，跳过刷新。")


def main_loop():
    """主循环 — 定时检查"""
    print("=" * 50)
    print("  日本ニュース热点 — 自動調度器")
    print(f"  检查间隔: 每 2 小时")
    print(f"  保鲜期: {MAX_AGE_HOURS} 小时")
    print(f"  启动时间: {datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 启动时立即检查一次
    run_job()

    # 每 2 小时检查
    schedule.every(2).hours.do(run_job)

    print("\n调度器运行中，按 Ctrl+C 停止...\n")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n调度器已停止。")


def run_once():
    """单次执行"""
    run_job()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="日本新闻热点调度器")
    parser.add_argument("--once", action="store_true", help="只运行一次，不进入循环")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        main_loop()
