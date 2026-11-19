"""拼装组内讲解页。

用法：python3 -I src/assemble.py
读 parts/ 下按章号排序的片段，写出两份：
- index.html：claude.ai Artifact 用的片段（发布时会被包上 html/head/body 外壳）
- explainer-local.html：本地直接用浏览器打开的完整页面
两份都引用同目录 assets/ 下的样式和脚本。
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PARTS = sorted((ROOT / "parts").glob("[0-9][0-9]-*.html"))
EXPECTED = ["00-ov", "01-pre", "02-aha", "03-sys", "04-arms", "05-funnel", "06-gen", "07-data", "08-eval",
            "09-cost", "10-steps", "11-team", "12-timeline", "13-risks", "14-train", "15-related", "16-reading", "17-gloss"]

TITLE = "小物体去哪了"
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
         '&family=Noto+Sans+SC:wght@400;500;600;700&display=swap">\n'
         '<link rel="stylesheet" href="assets/review.css">\n')
ANIM = ('<script>if(!(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches))'
        'document.documentElement.classList.add("ap-anim");</script>\n')
SCRIPTS = ["assets/widgets.js", "assets/widgets-proj.js", "assets/review.js", "assets/motion.js"]

HERO = """<h1>小物体去哪了</h1>
<p class="subtitle">用手机拍一段房间视频，让大模型 agent 把它搭成 Blender 场景。家具大多能搭出来，杯子、瓶子、书、遥控器却常常没了。这个项目要量清楚它们丢了多少、丢在哪一步，以及怎么补最划算。</p>
<div class="meta-row">
  <span class="chip">CIS 6220 期末项目</span><span class="chip">3Heads1GPU：Yifan · Mingjian · Yujing</span>
  <span class="chip blue">10/19 交提案</span><span class="chip blue">10/26 中期检查</span><span class="chip blue">11/23 初稿</span>
  <span class="chip red">12/7 终稿</span>
</div>

<div class="box plain">
<span class="box-label">这页怎么读</span>
<p>第 0 章用一张图讲完整个项目。第 1 章补前置知识，没有 3D 背景的话先读它。第 2、3 章讲 AHa-3D 原本怎么工作、我们的系统怎么搭。第 4 到 9 章是实验本身：实验组、漏斗、生成工具、数据、评测、算力和花费。第 10 到 14 章是执行：步骤、分工、时间线、风险、训练加分项。最后三章是相关工作、<a href="#reading">必读论文清单（带链接）</a>和术语表。</p>
<p>框的颜色有固定含义。<b>大白话</b>用生活里的事打比方，<b>细节</b>讲真实机制，<b>易错点</b>是最容易想错的地方，<b>必记</b>是要记住的结论。带"上一步 / 下一步"按钮的是逐步架构图，点一步亮一块；也可以直接点下面的步骤文字。</p>
</div>
"""

FOOT = ('<div class="page-foot">依据：<code>docs/design.md</code>（2026 年 10 月 14 日定稿）、'
        '<code>research/notes/</code> 四份调研笔记、英文一页提案。方案有变时先改设计文档，再同步这一页。'
        '2026 年 10 月 14 日建。</div>\n')


def main():
    names = [p.stem for p in PARTS]
    missing = [n for n in EXPECTED if n not in names]
    if missing:
        print("缺片段：", ", ".join(missing))
    body = []
    for p in PARTS:
        t = p.read_text(encoding="utf-8")
        if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", t):
            sys.exit(f"{p.name} 含控制字符")
        body.append(f"<!-- ===== {p.name} ===== -->\n" + t.strip() + "\n")
    content = HERO + "\n" + "\n".join(body) + "\n" + FOOT
    layout = ('<div class="layout">\n<nav class="toc" data-title="小物体去哪了 · 项目讲解" data-home="#reading" data-home-label="→ 必读论文与链接（第 16 章）"></nav>\n<main>\n'
              '<div class="content">\n' + content + '</div>\n</main>\n</div>\n')

    fragment = (f"<title>{TITLE}</title>\n" + FONTS + ANIM +
                '<script>document.body.setAttribute("data-page","proj-explainer");</script>\n' +
                layout + "".join(f'<script src="{s}"></script>\n' for s in SCRIPTS))
    (ROOT / "index.html").write_text(fragment, encoding="utf-8")

    local = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
             '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
             f"<title>{TITLE}</title>\n" + ANIM + FONTS +
             "".join(f'<script defer src="{s}"></script>\n' for s in SCRIPTS) +
             '</head>\n<body data-page="proj-explainer">\n' + layout + '</body>\n</html>\n')
    (ROOT / "explainer-local.html").write_text(local, encoding="utf-8")
    print(f"拼了 {len(PARTS)} 个片段 → index.html（{len(fragment)//1024} KB）、explainer-local.html")


if __name__ == "__main__":
    main()
