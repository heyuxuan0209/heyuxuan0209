#!/usr/bin/env python3
"""刷新个人主页 README 里的 star 数和最新文章列表。

两块内容都靠 HTML 注释标记定位，正文随便改，标记别删：

  star 数     (<!--stars:仓库名-->123<!--/stars--> stars)
  文章列表    <!--articles-start--> ... <!--articles-end-->

数据来源都是公开的，不需要任何密钥：
  star 数  → GitHub API（CI 里用自带的 GITHUB_TOKEN 提限流）
  文章     → 个人站仓库里的 articles.generated.json，
             它本身由个人站的构建流程从飞书表 + 公众号 og 生成

本地想试跑：python3 .github/scripts/update_readme.py
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

USER = "heyuxuan0209"
SITE_REPO = f"{USER}/{USER}.github.io"
ARTICLES_URL = (
    f"https://raw.githubusercontent.com/{SITE_REPO}/main/src/data/articles.generated.json"
)
README = "README.md"
MAX_ARTICLES = 5

STAR_RE = re.compile(r"<!--stars:([^>]+)-->(.*?)<!--/stars-->", re.S)
ARTICLES_RE = re.compile(r"(<!--articles-start-->)(.*?)(<!--articles-end-->)", re.S)


def fetch(url, token=None, accept="application/json"):
    req = urllib.request.Request(url, headers={"User-Agent": f"{USER}-profile", "Accept": accept})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def human(n):
    """1234 → 1.2k，和一般 README 的写法一致；四位数以下原样显示"""
    if n < 1000:
        return str(n)
    if n < 10000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return f"{round(n / 1000)}k"


def update_stars(text, token):
    try:
        repos = fetch(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner", token)
    except (urllib.error.URLError, OSError) as e:
        print(f"⚠︎ 拉 star 数失败，保持原值：{e}")
        return text, 0

    stars = {r["name"].lower(): r["stargazers_count"] for r in repos}
    missing = []
    changed = 0

    def repl(m):
        nonlocal changed
        name, old = m.group(1).strip(), m.group(2)
        if name.lower() not in stars:
            missing.append(name)
            return m.group(0)
        new = human(stars[name.lower()])
        if new != old:
            changed += 1
            print(f"  {name}: {old} → {new}")
        return f"<!--stars:{name}-->{new}<!--/stars-->"

    text = STAR_RE.sub(repl, text)
    if missing:
        print(f"⚠︎ README 里这些仓库名在 API 结果里找不到（改过名？私有？）：{', '.join(missing)}")
    return text, changed


def update_articles(text):
    if not ARTICLES_RE.search(text):
        print("README 里没有 articles 标记，跳过文章更新")
        return text, 0
    try:
        posts = fetch(ARTICLES_URL, accept="application/vnd.github.raw")
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"⚠︎ 拉文章列表失败，保持原样：{e}")
        return text, 0

    rows = [p for p in posts if p.get("url") and p.get("title")][:MAX_ARTICLES]
    if not rows:
        print("⚠︎ 文章列表为空，保持原样")
        return text, 0

    lines = "\n".join(
        f"- 📖 [{p['title']}]({p['url']}) · {p.get('date', '').replace('-', '.')}".rstrip(" ·")
        for p in rows
    )
    block = f"\\1\n{lines}\n\\3"
    new_text = ARTICLES_RE.sub(block, text)
    changed = int(new_text != text)
    if changed:
        print(f"  文章列表更新为最新 {len(rows)} 篇")
    return new_text, changed


def main():
    if not os.path.exists(README):
        sys.exit(f"找不到 {README}，请在仓库根目录运行")

    original = open(README, encoding="utf-8").read()
    text, n_stars = update_stars(original, os.environ.get("GITHUB_TOKEN"))
    text, n_articles = update_articles(text)

    if text == original:
        print("没有变化。")
        return

    open(README, "w", encoding="utf-8").write(text)
    print(f"已更新 README（star {n_stars} 处，文章 {n_articles} 处）")


if __name__ == "__main__":
    main()
