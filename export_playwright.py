#!/usr/bin/env python3
"""
微信公众号文章批量导出工具 - 傻瓜版（自动登录）
使用方法：
    pip install playwright html2text
    playwright install chromium
    python3 export_playwright.py
"""

import json
import os
import re
import time
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "wechat_articles")


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


def fetch_article_content(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(1)
    content = page.evaluate("""() => {
        const el = document.getElementById('js_content');
        return el ? el.innerHTML : '';
    }""")
    return content or ""


def get_all_articles(page, token, headers_dict):
    import requests
    all_articles = []
    begin = 0
    count = 20

    # 从 playwright 拿 cookie 字符串
    cookies = page.context.cookies()
    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

    headers = {
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://mp.weixin.qq.com/",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }

    # 获取总数
    url = f"https://mp.weixin.qq.com/cgi-bin/appmsg?action=list_ex&begin=0&count=1&type=9&token={token}&lang=zh_CN"
    resp = requests.get(url, headers=headers, timeout=15)
    total = resp.json().get("app_msg_cnt", 0)
    print(f"  共找到 {total} 篇文章")

    while begin < total:
        print(f"  获取列表 第{begin+1}-{min(begin+count, total)}篇...")
        url = f"https://mp.weixin.qq.com/cgi-bin/appmsg?action=list_ex&begin={begin}&count={count}&type=9&token={token}&lang=zh_CN"
        resp = requests.get(url, headers=headers, timeout=15)
        items = resp.json().get("app_msg_list", [])
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

    return all_articles, cookie_str


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("请先安装依赖：")
        print("  pip install playwright html2text")
        print("  playwright install chromium")
        return

    try:
        import requests
    except ImportError:
        print("请先安装 requests：pip install requests")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 55)
    print("  微信公众号文章批量导出工具")
    print("=" * 55)
    print()
    print("即将打开浏览器，请扫码登录微信公众平台...")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        context = browser.new_context(
            viewport={"width": 1200, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # 打开登录页
        page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded")

        # 等待登录完成（检测 slave_sid cookie 出现）
        print("等待扫码登录...")
        for _ in range(120):  # 最多等 2 分钟
            cookies = {c['name']: c['value'] for c in context.cookies()}
            if 'slave_sid' in cookies:
                print("✓ 登录成功！\n")
                break
            time.sleep(1)
        else:
            print("登录超时，请重试")
            browser.close()
            return

        # 导航到文章列表页，从 URL 获取 token
        page.goto("https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit&isNew=1&type=10&token=0&lang=zh_CN")
        time.sleep(2)
        current_url = page.url
        token_match = re.search(r'token=(\d+)', current_url)
        if not token_match:
            # 备用：从任意后台页面获取 token
            page.goto("https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN&token=0")
            time.sleep(2)
            current_url = page.url
            token_match = re.search(r'token=(\d+)', current_url)

        if not token_match:
            print("无法获取 token，请重试")
            browser.close()
            return

        token = token_match.group(1)
        print(f"Token: {token}")

        # 获取文章列表
        print("\n【第一步】获取文章列表...")
        articles, cookie_str = get_all_articles(page, token, {})

        # 逐篇下载正文
        print(f"\n【第二步】下载正文，共 {len(articles)} 篇...\n")
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
                content_html = fetch_article_content(page, link)
                content_md = html_to_markdown(content_html)
                md_content = f"# {title}\n\n> 发布日期：{date_str}\n\n---\n\n{content_md}\n"

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(md_content)

                print(f"  ✓ 保存成功")
                success += 1
            except Exception as e:
                print(f"  ✗ 失败: {e}")
                failed += 1

            time.sleep(1)

        browser.close()

    print()
    print("=" * 55)
    print(f"完成！成功 {success} 篇，跳过 {skipped} 篇，失败 {failed} 篇")
    print(f"文件保存在：{OUTPUT_DIR}")
    print("=" * 55)


if __name__ == "__main__":
    main()
