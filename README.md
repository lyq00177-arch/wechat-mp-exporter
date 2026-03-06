# 微信公众号文章批量导出工具

将你的微信公众号历史文章一键导出为 Markdown 文件，保存到本地。

---

## 两种使用方式

### 方式一：傻瓜版（推荐）

自动弹出浏览器，扫码登录，无需手动复制 Cookie。

**安装依赖：**
```bash
pip install requests html2text playwright
playwright install chromium
```

**运行：**
```bash
python3 export_playwright.py
```

运行后会弹出浏览器窗口，扫码登录公众号后台，脚本自动完成剩余全部操作。

文章默认保存在：`~/wechat_articles/`

---

### 方式二：手动 Cookie 版

适合熟悉浏览器开发者工具的用户，无需安装 Playwright。

**安装依赖：**
```bash
pip install requests html2text
```

**获取 Cookie：**
1. 用 Chrome 登录 [mp.weixin.qq.com](https://mp.weixin.qq.com)
2. 按 `F12` → `Application` → `Cookies` → `https://mp.weixin.qq.com`
3. 找到 `slave_sid` 和 `slave_user` 两行，复制 Value
4. 从地址栏 URL 复制 `token=` 后面的数字

**填入脚本顶部，运行：**
```bash
python3 export_manual.py
```

---

## 输出格式

每篇文章保存为一个 Markdown 文件，命名规则：

```
YYYY-MM-DD-文章标题.md
```

文件内容：
```markdown
# 文章标题

> 发布日期：2026-01-22

---

文章正文...
```

---

## 注意事项

- 本工具仅用于导出**自己的**公众号文章，请勿用于抓取他人内容
- Cookie 有时效性，失效后需重新获取
- 请勿频繁运行，已下载的文章会自动跳过

---

## OpenClaw 版本

如果你使用 [OpenClaw](https://github.com/anthropics/anthropic-quickstarts)（基于 Claude computer-use 的本地 AI 助手），可以直接让它完成整个流程：

> 打开 Chrome，登录微信公众号后台（mp.weixin.qq.com），扫码登录后，用开发者工具获取 slave_sid 和 slave_user 的值，以及地址栏中的 token，然后运行 export_manual.py 完成文章导出。

---

## License

MIT
