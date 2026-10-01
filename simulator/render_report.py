"""TECHNICAL_REPORT.md 渲染管线（V0.8R5 阶段 C2）

md → 简易 HTML（A4 版式、Microsoft YaHei）→ chromium headless 打印 PDF → 数页。
页数口径 = 渲染 PDF 页数（任务书"10-15 页正文"）。

用法：python simulator/render_report.py
产出：docs/V08R5_Plans/TECHNICAL_REPORT.pdf（控制台打印页数）
零新依赖：md 解析为手写子集（标题/表格/代码块/图片/列表/引用/粗体/行内代码）；
证据拼图用 PIL（matplotlib 依赖）；PDF 页数按 "/Type /Page" 统计。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "V08R5_Plans"
EVIDENCE = ROOT / "Evidence"
MD = DOC / "TECHNICAL_REPORT.md"
PDF = DOC / "TECHNICAL_REPORT.pdf"


def compose_evidence():
    """把 Evidence 截图合成为横向拼图（省页数、便于阅读），输出到 DOC 目录。"""
    from PIL import Image
    specs = [
        ("evidence-D1.png", [
            EVIDENCE / "D1" / "d1-three-nodes-online.png",
            EVIDENCE / "D1" / "d1-3d-three-buildings.png",
            EVIDENCE / "D1" / "d1-new-message-drives-update.png"]),
        ("evidence-D2.png", [
            EVIDENCE / "D2" / "d2-priority-group1.png",
            EVIDENCE / "D2" / "d2-priority-group2.png",
            EVIDENCE / "D2" / "d2-priority-group3.png"]),
        ("evidence-D3.png", [
            EVIDENCE / "D3" / "d3-handling-dashboard.png",
            EVIDENCE / "D3" / "d3-handling-3d.png",
            EVIDENCE / "D3" / "d3-recovered-dashboard.png"]),
        ("evidence-D5.png", [
            EVIDENCE / "D5" / "d5-report-ml-section.png"]),
    ]
    for name, paths in specs:
        imgs = [Image.open(p) for p in paths]
        tw = 400  # 每张目标宽度
        heights = [int(im.height * tw / im.width) for im in imgs]
        canvas = Image.new("RGB", (tw * len(imgs) + 12 * (len(imgs) - 1), max(heights)), "white")
        x = 0
        for im, h in zip(imgs, heights):
            canvas.paste(im.resize((tw, h)), (x, 0))
            x += tw + 12
        out = DOC / name
        canvas.save(out)
        print("composed:", out, canvas.size)


def md_to_html(text):
    """手写 markdown 子集 → HTML 片段（本项目文档元素范围）。"""
    lines = text.split("\n")
    out = []
    i = 0
    in_code = False
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            in_code = not in_code
            out.append("</pre>" if not in_code else "<pre>")
            i += 1
            continue
        if in_code:
            out.append(esc(line))
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue
        m = re.match(r"^!\[(.*?)\]\((.*?)\)", line)
        if m:
            out.append(f'<p class="fig"><img src="{m.group(2)}"/></p>')
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|?$", lines[i + 1]):
            out.append("<table>")
            out.append("<tr>" + "".join(f"<th>{inline(c.strip())}</th>" for c in line.strip("|").split("|")) + "</tr>")
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                out.append("<tr>" + "".join(f"<td>{inline(c.strip())}</td>" for c in lines[i].strip("|").split("|")) + "</tr>")
                i += 1
            out.append("</table>")
            continue
        if line.startswith("- "):
            out.append("<ul>")
            while i < len(lines) and lines[i].startswith("- "):
                out.append(f"<li>{inline(lines[i][2:])}</li>")
                i += 1
            out.append("</ul>")
            continue
        if line.startswith(">"):
            out.append(f"<blockquote>{inline(line.lstrip('> '))}</blockquote>")
            i += 1
            continue
        if line.startswith("---"):
            out.append("<hr/>")
            i += 1
            continue
        if line.strip() == "":
            i += 1
            continue
        # 段落（连续非空行合并）
        para = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|\||```|- |> |!\[|---)", lines[i]):
            para.append(lines[i])
            i += 1
        out.append("<p>" + inline(" ".join(para)) + "</p>")
    return "\n".join(out)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(s):
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; @bottom-center { content: counter(page) " / " counter(pages); font-size: 9px; color: #8899aa; } }
body { font-family: "Microsoft YaHei", "SimSun", sans-serif; font-size: 10.5pt; line-height: 1.65; color: #24313f; }
h1 { font-size: 19pt; border-bottom: 3px solid #2563a8; padding-bottom: 6px; margin-bottom: 10px; }
h2 { font-size: 13.5pt; color: #2563a8; border-bottom: 1px solid #d5dde6; padding-bottom: 3px; margin-top: 16px; }
h3 { font-size: 11.5pt; color: #2b3a48; margin-top: 10px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9.5pt; page-break-inside: avoid; }
th, td { border: 1px solid #c8d0d8; padding: 4px 7px; text-align: left; }
th { background: #f0f4f8; }
code { background: #f2f4f6; padding: 1px 4px; border-radius: 3px; font-family: Consolas, monospace; font-size: 9pt; }
pre { background: #f6f8fa; border: 1px solid #e3e8ee; border-radius: 5px; padding: 8px 10px; font-size: 9pt; line-height: 1.45; white-space: pre-wrap; page-break-inside: avoid; }
blockquote { margin: 8px 0; padding: 4px 12px; border-left: 4px solid #c9a227; background: #fffbe8; font-size: 9.5pt; color: #5b4a1a; }
img { max-width: 100%; }
p.fig { text-align: center; margin: 10px 0 2px 0; }
ul { margin: 6px 0; padding-left: 22px; }
li { margin: 2px 0; }
hr { border: none; border-top: 1px solid #e3e8ee; margin: 12px 0; }
"""


def main():
    compose_evidence()
    text = MD.read_text(encoding="utf-8")
    body = md_to_html(text)
    html = ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>" + CSS +
            "</style></head><body>" + body + "</body></html>")
    tmp = DOC / "report-render.html"
    tmp.write_text(html, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page()
        pg.goto("file:///" + str(tmp.resolve()).replace("\\", "/"))
        pg.wait_for_timeout(800)
        pg.pdf(path=str(PDF), format="A4", print_background=True,
               display_header_footer=False, margin={"top": "18mm", "bottom": "18mm", "left": "16mm", "right": "16mm"})
        b.close()
    tmp.unlink()
    data = PDF.read_bytes()
    pages = data.count(b"/Type /Page") - data.count(b"/Type /Pages")
    print(f"PDF 已生成：{PDF}，页数 = {pages}")
    if not (10 <= pages <= 15):
        print(f"警告：页数 {pages} 不在 [10,15] 区间，需要调整内容")
        sys.exit(2)
    print(f"页数达标 [10,15]（{pages} 页）")


if __name__ == "__main__":
    main()
