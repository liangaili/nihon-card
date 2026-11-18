# -*- coding: utf-8 -*-
"""校验下载完整性，生成书籍目录索引页与汇总报告。"""
import json, os, html as htmlmod
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(BASE, "articles")
IMAGES_DIR = os.path.join(BASE, "images")
META_DIR = os.path.join(BASE, "metadata")
LIST_PATH = os.path.join(META_DIR, "articles_list.json")

def main():
    data = json.load(open(LIST_PATH, encoding="utf-8"))
    arts = data["articles"]
    total = len(arts)

    rows = []
    ok = missing = 0
    total_imgs = 0
    broken_img_refs = 0
    for i, a in enumerate(arts):
        seq = i + 1
        art_file = os.path.join(ARTICLES_DIR, f"{seq:03d}", "article.html")
        exists = os.path.exists(art_file) and os.path.getsize(art_file) > 500
        img_dir = os.path.join(IMAGES_DIR, f"{seq:03d}")
        nimgs = len([f for f in os.listdir(img_dir)]) if os.path.isdir(img_dir) else 0
        total_imgs += nimgs
        if exists:
            ok += 1
            with open(art_file, encoding="utf-8") as f:
                content = f.read()
            # 检查 HTML 引用的本地图片是否都存在
            import re
            refs = re.findall(r'src="([^"]*images/[^"]+)"', content)
            for ref in refs:
                p = os.path.normpath(os.path.join(os.path.dirname(art_file), ref))
                if not os.path.exists(p):
                    broken_img_refs += 1
        else:
            missing += 1
        rows.append({
            "seq": seq, "title": a["title"], "date": a.get("date", ""),
            "url": a["url"], "exists": exists, "imgs": nimgs
        })

    # 生成目录索引页
    items = []
    for r in rows:
        cls = "" if r["exists"] else " class='missing'"
        link = f"articles/{r['seq']:03d}/article.html"
        items.append(
            f"<li{cls}><span class='seq'>{r['seq']:03d}</span>"
            f"<a href='{link}'>{htmlmod.escape(r['title'])}</a>"
            f"<span class='date'>{htmlmod.escape(r['date'])}</span>"
            f"<span class='img'>{r['imgs']} 图</span></li>"
        )
    index_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>日语趣味单词卡 · 文章目录</title>
<style>
body {{ margin:0; background:#faf9f6; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif; color:#333; }}
.wrap {{ max-width:820px; margin:0 auto; padding:40px 24px 80px; }}
h1 {{ font-size:30px; margin:0 0 8px; color:#1a1a1a; }}
.sub {{ color:#888; font-size:14px; margin-bottom:32px; border-bottom:2px solid #e8e3d8; padding-bottom:20px; }}
ul {{ list-style:none; padding:0; margin:0; }}
li {{ display:flex; align-items:center; gap:12px; padding:11px 8px; border-bottom:1px solid #eceae4; }}
li:hover {{ background:#fff; }}
li.missing a {{ color:#c00; text-decoration:line-through; }}
.seq {{ color:#b0a99a; font-size:13px; width:34px; font-variant-numeric:tabular-nums; }}
a {{ color:#2b5b84; text-decoration:none; flex:1; line-height:1.5; }}
a:hover {{ text-decoration:underline; }}
.date {{ color:#999; font-size:13px; white-space:nowrap; }}
.img {{ color:#aaa; font-size:12px; width:46px; text-align:right; white-space:nowrap; }}
.stat {{ background:#fff; padding:16px 20px; border-radius:8px; margin-bottom:28px; font-size:14px; color:#555; line-height:1.9; }}
.stat b {{ color:#2b5b84; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>日语趣味单词卡</h1>
  <div class="sub">文章目录 · 共 {total} 篇 · 按发表时间排序</div>
  <div class="stat">
    <div>已下载文章：<b>{ok}</b> / {total}　｜　本地图片：<b>{total_imgs}</b> 张</div>
    <div>缺失文章：<b>{missing}</b>　｜　失效图片引用：<b>{broken_img_refs}</b></div>
  </div>
  <ul>
{chr(10).join(items)}
  </ul>
</div>
</body>
</html>"""
    with open(os.path.join(BASE, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    report = {
        "total_articles": total, "downloaded": ok, "missing": missing,
        "total_images": total_imgs, "broken_image_refs": broken_img_refs,
        "missing_details": [r for r in rows if not r["exists"]]
    }
    with open(os.path.join(META_DIR, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
