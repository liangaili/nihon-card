# -*- coding: utf-8 -*-
"""批量下载微信公众号文章：保留原排版 HTML + 本地化图片。"""
import json, os, re, sys, time, html as htmlmod
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(BASE, "articles")
IMAGES_DIR = os.path.join(BASE, "images")
META_DIR = os.path.join(BASE, "metadata")
LIST_PATH = os.path.join(META_DIR, "articles_list.json")
PROGRESS_PATH = os.path.join(META_DIR, "progress.json")

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
IMG_REFERER = "https://mp.weixin.qq.com/"

def safe_name(s, maxlen=60):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", s).strip().strip(".")
    return s[:maxlen] if s else "untitled"

def fetch_url(url, referer=None, retries=3, timeout=30):
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except Exception as e:
            last = e
            time.sleep(1.2 * (i + 1))
    raise last

def ext_from_ctype(ctype, url):
    ct = (ctype or "").lower()
    m = re.search(r'image/(\w+)', ct)
    if m:
        e = m.group(1).lower()
        return {"jpeg": ".jpg", "jpg": ".jpg", "png": ".png", "gif": ".gif",
                "webp": ".webp", "svg+xml": ".svg"}.get(e, "." + e)
    m = re.search(r'wx_fmt=(\w+)', url)
    if m:
        return "." + m.group(1).lower().replace("jpeg", "jpg")
    return ".jpg"

def build_html(title, date, source_url, inner_html, css_map):
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{htmlmod.escape(title)}</title>
<style>
body {{ margin:0; background:#f5f5f5; font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue","PingFang SC","Microsoft YaHei",sans-serif; }}
.book-page {{ max-width:677px; margin:0 auto; background:#fff; padding:24px 20px 40px; box-sizing:border-box; }}
.article-meta {{ border-bottom:1px solid #eee; padding-bottom:16px; margin-bottom:22px; }}
.article-meta h1 {{ font-size:22px; line-height:1.4; margin:0 0 10px; color:#222; font-weight:600; }}
.article-meta .meta-line {{ font-size:13px; color:#888; }}
.article-meta a {{ color:#576b95; text-decoration:none; }}
.rich_media_content {{ font-size:16px; line-height:1.75; color:#333; word-wrap:break-word; }}
.rich_media_content img {{ max-width:100% !important; height:auto !important; display:block; margin:0 auto; }}
.rich_media_content p {{ margin:8px 0; }}
.rich_media_content section {{ margin:8px 0; }}
{css_map}
</style>
</head>
<body>
<div class="book-page">
  <div class="article-meta">
    <h1>{htmlmod.escape(title)}</h1>
    <div class="meta-line">发表于 {htmlmod.escape(date)} · 原文：<a href="{htmlmod.escape(source_url)}" target="_blank">点击查看</a></div>
  </div>
  <div class="rich_media_content" id="js_content">
{inner_html}
  </div>
</div>
</body>
</html>"""
    return page

def process_article(args):
    idx, art = args
    seq = idx + 1
    art_dir = os.path.join(ARTICLES_DIR, f"{seq:03d}")
    os.makedirs(art_dir, exist_ok=True)
    article_file = os.path.join(art_dir, "article.html")
    if os.path.exists(article_file) and os.path.getsize(article_file) > 500:
        return {"seq": seq, "status": "skip", "title": art["title"], "imgs": 0}

    result = {"seq": seq, "title": art["title"], "status": "ok", "imgs": 0, "errors": []}
    try:
        raw, _ = fetch_url(art["url"], retries=4)
        doc = raw.decode("utf-8", "ignore")
        if "环境异常" in doc[:3000] or ("验证" in doc[:1000] and "js_content" not in doc):
            raise RuntimeError("触发风控验证页")

        soup = BeautifulSoup(doc, "html.parser")
        content = soup.find(id="js_content")
        if not content:
            raise RuntimeError("未找到 js_content 正文容器")

        # 提取正文内联样式规则（微信把部分样式写在 <style> 里）
        css_rules = []
        for st in soup.find_all("style"):
            txt = st.get_text()
            if txt and (".rich_media" in txt or ".js_" in txt or "@media" in txt):
                css_rules.append(txt[:200000])
        css_map = "\n".join(css_rules[-3:])

        # 图片本地化
        imgs = content.find_all("img")
        img_dir = os.path.join(IMAGES_DIR, f"{seq:03d}")
        os.makedirs(img_dir, exist_ok=True)
        for j, im in enumerate(imgs):
            src = im.get("data-src") or im.get("src") or ""
            if not src or src.startswith("data:"):
                continue
            src = htmlmod.unescape(src)
            try:
                data, ctype = fetch_url(src, referer=IMG_REFERER, retries=3)
                ext = ext_from_ctype(ctype, src)
                fn = f"{j:02d}{ext}"
                with open(os.path.join(img_dir, fn), "wb") as f:
                    f.write(data)
                im["src"] = f"../../images/{seq:03d}/{fn}"
                im["data-src"] = f"../../images/{seq:03d}/{fn}"
                for attr in ("data-cropor", "data-s", "data-ratio"):
                    if attr in im.attrs:
                        del im[attr]
                result["imgs"] += 1
            except Exception as e:
                result["errors"].append(f"img{j}: {e}")

        inner = content.decode_contents()
        page = build_html(art["title"], art.get("date", ""), art["url"], inner, css_map)
        with open(article_file, "w", encoding="utf-8") as f:
            f.write(page)
        result["bytes"] = len(page.encode("utf-8"))
    except Exception as e:
        result["status"] = "error"
        result["errors"].append(str(e))
    return result

def main():
    data = json.load(open(LIST_PATH, encoding="utf-8"))
    arts = data["articles"]
    total = len(arts)
    print(f"total articles: {total}", flush=True)

    progress = {"done": 0, "ok": 0, "skip": 0, "error": 0, "details": []}
    if os.path.exists(PROGRESS_PATH):
        try:
            progress = json.load(open(PROGRESS_PATH, encoding="utf-8"))
        except Exception:
            pass

    workers = 4
    batch_size = 20
    start = 0  # 始终从 0 扫描，靠文件存在性跳过
    for batch_start in range(start, total, batch_size):
        batch = [(i, arts[i]) for i in range(batch_start, min(batch_start + batch_size, total))]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(process_article, a): a for a in batch}
            for fut in as_completed(futs):
                r = fut.result()
                d = progress["details"]
                d[:] = [x for x in d if x["seq"] != r["seq"]]
                d.append(r)
                progress["done"] = len(d)
                progress["ok"] = sum(1 for x in d if x["status"] == "ok")
                progress["skip"] = sum(1 for x in d if x["status"] == "skip")
                progress["error"] = sum(1 for x in d if x["status"] == "error")
                if r["status"] == "error":
                    print(f"  [ERR #{r['seq']:03d}] {r['title'][:24]}: {r['errors'][0][:80]}", flush=True)
        json.dump(progress, open(PROGRESS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"progress: {progress['done']}/{total} ok={progress['ok']} skip={progress['skip']} err={progress['error']}", flush=True)
        time.sleep(1)

if __name__ == "__main__":
    main()
