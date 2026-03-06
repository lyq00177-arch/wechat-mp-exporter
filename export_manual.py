#!/usr/bin/env python3
"""
微信公众号文章批量导出工具 - 手动 Cookie 版
适合有一定技术基础的用户。

使用方法：
    1. 登录 mp.weixin.qq.com
    2. 按 F12 → Application → Cookies → 找到 slave_sid 和 slave_user 填入下方
    3. 从地址栏 URL 复制 token= 后面的数字
    4. pip install requests html2text
    5. python3 export_manual.py
"""

import requests
import os
import re
import time
from datetime import datetime

# ===== 请填写以下信息 =====
TOKEN = "你的token"         # 从后台地址栏 URL 获取，如 token=894289594
SLAVE_SID = "你的slave_sid"  # F12 → Application → Cookies → slave_sid
SLAVE_USER = "你的slave_user" # F12 → Application → Cookies → slave_user
# ==========================

OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "wechat_articles")

COOKIE_BASE = (
    "mm_lang=zh_CN; "
    f"slave_sid={SLAVE_SID}; "
    f"slave_user={SLAVE_USER}"
)

HEADERS = {
    "Cookie": COOKIE_BASE,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://mp.weixin.qq.com/",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def sanitize_filename(title):
    cleaned = re.sub(r'[<>:"/\\|?*，。！？、；：""\'\'【】《》\n\r]', '', title)
    return cleaned.strip()[:60]


def html_to_markdown(html):
    try:
        import html2text
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        h.body_width = 0
        return h.handle(html).strip()
    except ImportError:
        text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<p[^>]*>', '\n', text)
        text = re.sub(r'</p>', '', text)
        text = re.sub(r'<[^>]+>', '', text)
        for entity, char in [('&nbsp;', ' '), ('&lt;', '<'), ('&gt;', '>'), ('&amp;', '&')]:
            text = text.replace(entity, char)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


def fetch_article_content(url):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.encoding = "utf-8"
    html = resp.text
    match = re.search(r'<div[^>]+id=["\']js_content["\'][^>]*>(.*?)</div>', html, re.DOTALL)
    if match:
        return match.group(1)
    return html


def get_all_articles():
    all_articles = []
    begin = 0
    count = 20

    data = requests.get(
        f"https://mp.weixin.qq.com/cgi-bin/appmsg?action=list_ex&begin=0&count=1&type=9&token={TOKEN}&lang=zh_CN",
        headers=HEADERS, timeout=15
    ).json()
    total = data.get("app_msg_cnt", 0)
    print(f"  共 {total} 篇文章")

    while begin < total:
        print(f"  获取列表 第{begin+1}-{min(begin+count, total)}篇...")
        url = f"https://mp.weixin.qq.com/cgi-bin/appmsg?action=list_ex&begin={begin}&count={count}&type=9&token={TOKEN}&lang=zh_CN"
        items = requests.get(url, headers=HEADERS, timeout=15).json().get("app_msg_list", [])
        if not items:
            break
        for item in items:
            all_articles.append({
                "title": item.get("title", "无标题"),
                "link": item.get("link", ""),
                "create_time": item.get("create_time", 0),
            })
        begin += count
        time.sleep(1)

    return all_articles


def main():
    if TOKEN == "你的token":
        print("请先在脚本顶部填写 TOKEN、SLAVE_SID、SLAVE_USER")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("=" * 50)
    print("微信公众号文章批量导出（手动 Cookie 版）")
    print("=" * 50)
    print()
    print("【第一步】获取文章列表...")
    articles = get_all_articles()
    print(f"\n共找到 {len(articles)} 篇文章\n")

    print("【第二步】下载正文...\n")
    success, skipped, failed = 0, 0, 0

    for i, article in enumerate(articles):
        title = article["title"]
        link = article["link"]
        create_time = article["create_time"]

        date_str = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d") if create_time else "unknown"
        safe_title = sanitize_filename(title)
        filename = f"{date_str}-{safe_title}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        if os.path.exists(filepath):
            print(f"[{i+1}/{len(articles)}] 跳过（已存在）: {filename}")
            skipped += 1
            continue

        print(f"[{i+1}/{len(articles)}] 下载: {title}")

        try:
            content_html = fetch_article_content(link)
            content_md = html_to_markdown(content_html)
            md_content = f"# {title}\n\n> 发布日期：{date_str}\n\n---\n\n{content_md}\n"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"  ✓ 保存成功")
            success += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            failed += 1

        time.sleep(1.5)

    print()
    print("=" * 50)
    print(f"完成！成功 {success} 篇，跳过 {skipped} 篇，失败 {failed} 篇")
    print(f"文件保存在：{OUTPUT_DIR}")
    print("=" * 50)


if __name__ == "__main__":
    main()
