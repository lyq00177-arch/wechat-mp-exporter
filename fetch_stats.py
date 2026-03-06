#!/usr/bin/env python3
"""
微信公众号文章统计数据补抓脚本
功能：为已导出的 Markdown 文件补充阅读量、点赞、分享等数据（写入 YAML frontmatter）
使用方法：
    python3 fetch_stats.py
"""

import requests
import json
import os
import re
import time
from datetime import datetime

# ===== 配置 =====
TOKEN = "你的token"
SLAVE_SID = "你的slave_sid"
SLAVE_USER = "你的slave_user"

OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "wechat_articles")
# ================

HEADERS = {
    "Cookie": f"mm_lang=zh_CN; slave_sid={SLAVE_SID}; slave_user={SLAVE_USER}",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://mp.weixin.qq.com/",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def get_all_stats():
    """从 appmsgpublish 接口拉取所有文章及统计数据"""
    all_articles = []
    begin = 0
    count = 10

    # 先获取总数
    url = f"https://mp.weixin.qq.com/cgi-bin/appmsgpublish?sub=list&begin=0&count=1&token={TOKEN}&lang=zh_CN&f=json"
    resp = requests.get(url, headers=HEADERS, timeout=15).json()
    publish_page = json.loads(resp["publish_page"])
    total = publish_page.get("total_count", 0)
    print(f"  共 {total} 条发布记录")

    while begin < total:
        print(f"  获取第 {begin+1}-{min(begin+count, total)} 条...")
        url = f"https://mp.weixin.qq.com/cgi-bin/appmsgpublish?sub=list&begin={begin}&count={count}&token={TOKEN}&lang=zh_CN&f=json"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        data = resp.json()

        if data.get("base_resp", {}).get("ret") != 0:
            print("  API 错误，Cookie 可能已过期")
            break

        publish_page = json.loads(data["publish_page"])
        publish_list = publish_page.get("publish_list", [])

        if not publish_list:
            break

        for pub in publish_list:
            try:
                pub_info = json.loads(pub.get("publish_info", "{}"))
                sent_time = pub_info.get("sent_info", {}).get("time", 0)
                appmsg_list = pub_info.get("appmsg_info", [])

                for msg in appmsg_list:
                    all_articles.append({
                        "title": msg.get("title", ""),
                        "appmsgid": msg.get("appmsgid", ""),
                        "sent_time": sent_time,
                        "read_num": msg.get("read_num", 0),
                        "like_num": msg.get("like_num", 0),
                        "old_like_num": msg.get("old_like_num", 0),
                        "share_num": msg.get("share_num", 0),
                        "comment_num": msg.get("comment_num", 0),
                        "reprint_num": msg.get("reprint_num", 0),
                        "reward_money": msg.get("reward_money", "0.00"),
                    })
            except Exception as e:
                pass

        begin += count
        time.sleep(0.8)

    return all_articles


def build_frontmatter(article):
    date_str = datetime.fromtimestamp(article["sent_time"]).strftime("%Y-%m-%d") if article["sent_time"] else ""
    lines = [
        "---",
        f"title: \"{article['title'].replace('\"', '')}\"",
        f"date: {date_str}",
        f"read_num: {article['read_num']}",
        f"like_num: {article['like_num']}",
        f"old_like_num: {article['old_like_num']}",
        f"share_num: {article['share_num']}",
        f"comment_num: {article['comment_num']}",
        f"reprint_num: {article['reprint_num']}",
        f"reward_money: {article['reward_money']}",
        "---",
        "",
    ]
    return "\n".join(lines)


def sanitize_for_match(title):
    """清理标题用于文件名匹配"""
    return re.sub(r'[<>:"/\\|?*，。！？、；：""\'\'【】《》\n\r\s]', '', title).lower()


def inject_frontmatter(filepath, frontmatter):
    """将 frontmatter 注入到 markdown 文件开头（替换已有的）"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 移除已有的 frontmatter
    content = re.sub(r'^---\n.*?\n---\n\n?', '', content, flags=re.DOTALL)

    new_content = frontmatter + content
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)


def main():
    if TOKEN == "你的token":
        print("请先在脚本顶部填写 TOKEN、SLAVE_SID、SLAVE_USER")
        return

    print("=" * 55)
    print("  微信公众号统计数据补抓工具")
    print("=" * 55)
    print()

    print("【第一步】获取统计数据...")
    articles = get_all_stats()
    print(f"\n共获取 {len(articles)} 篇文章的统计数据\n")

    if not articles:
        return

    # 保存原始统计数据 JSON（备用）
    stats_json_path = os.path.join(OUTPUT_DIR, "_stats.json")
    with open(stats_json_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"原始数据已保存至 {stats_json_path}\n")

    print("【第二步】匹配并注入 frontmatter...\n")

    # 建立文件名索引
    md_files = {}
    for fname in os.listdir(OUTPUT_DIR):
        if fname.endswith(".md") and fname != "_stats.json":
            key = sanitize_for_match(os.path.splitext(fname)[0][11:])  # 去掉日期前缀
            md_files[key] = os.path.join(OUTPUT_DIR, fname)

    updated, not_found = 0, 0
    for article in articles:
        title = article["title"]
        key = sanitize_for_match(title)

        # 尝试匹配文件（模糊匹配前30个字符）
        matched_path = None
        for file_key, filepath in md_files.items():
            if key[:30] in file_key or file_key[:30] in key:
                matched_path = filepath
                break

        if not matched_path:
            print(f"  未找到文件: {title[:40]}")
            not_found += 1
            continue

        frontmatter = build_frontmatter(article)
        inject_frontmatter(matched_path, frontmatter)
        print(f"  ✓ 阅读{article['read_num']} 点赞{article['like_num']} 分享{article['share_num']} | {title[:35]}")
        updated += 1

    print()
    print("=" * 55)
    print(f"完成！更新 {updated} 篇，未匹配 {not_found} 篇")
    print("=" * 55)


if __name__ == "__main__":
    main()
