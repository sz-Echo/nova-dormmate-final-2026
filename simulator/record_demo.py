"""DormMate 演示视频录制（simulator/record_demo.py）

按三段剧本全自动录制 A/B/C 计划达成效果演示（Playwright record_video + 单页双 iframe 同屏），
再用 ffmpeg（imageio-ffmpeg 自带静态二进制）合并为 docs/demo/demo-full.webm。
旁白文案见 docs/demo/demo-script.md（视频纯画面无声音，配合现场讲解使用）。

设计要点：
  - 只发布、不重断言：demo 以画面为准（与 test_final.py 解耦），关键节点留足停留时间
  - 双 iframe 同屏：左 Dashboard / 右 3D 或报告，两条链的反应在同一画面里
  - Broker：1883 未启动时脚本自启 mosquitto，结束时只杀自己启动的进程
  - 5500 静态服务：脚本自启自停；MQTT 数据全部脚本发布（剧本确定性，不改任何产品代码）
  - A 段会导出事件并重生成 data/report.html，录制结束后用 git checkout 恢复三个程序产物，
    仓库保持干净（新增文件仅 docs/demo/ 与本脚本）

用法：
  python simulator/record_demo.py              # 三段全录 + 合并
  python simulator/record_demo.py --seg a      # 只录 A 段
  python simulator/record_demo.py --no-merge   # 只录不合并
"""
import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "demo"
BASE = "http://127.0.0.1:5500"
NODES = ("dorm-a", "dorm-b", "dorm-c")
VIEWPORT = {"width": 1600, "height": 900}

MOSQUITTO_EXE = r"D:\Mosquitto\mosquitto.exe"
MOSQUITTO_CONF = r"D:\Mosquitto\mosquitto.conf"


def run(args):
    return subprocess.run([sys.executable] + args, capture_output=True, text=True,
                          cwd=str(ROOT), encoding="utf-8", errors="replace")


def wait_port(port, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        s = socket.socket()
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except OSError:
            time.sleep(0.3)
    return False


def port_open(port):
    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        return False


def ensure_broker():
    """1883 未启动则自启 mosquitto；返回自启的进程（None = 复用已运行 Broker）。"""
    if port_open(1883):
        print("[Broker] 检测到 1883 已在运行，直接复用")
        return None
    proc = subprocess.Popen([MOSQUITTO_EXE, "-c", MOSQUITTO_CONF, "-v"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_port(1883, 10):
        print("[Broker] mosquitto 启动失败（1883 未就绪）", file=sys.stderr)
        proc.terminate()
        return None
    print("[Broker] 已自启 mosquitto（录制结束自动停止）")
    return proc


def start_server():
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "5500", "--bind", "127.0.0.1"],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if not wait_port(5500, 10):
        server.terminate()
        raise RuntimeError("5500 静态服务启动失败")
    return server


def pub_env(client, node, t, h, dt):
    client.publish(f"dormmate/{node}/env", json.dumps({
        "nodeId": node, "temperature": t, "humidity": h, "status": "",
        "time": dt.strftime("%Y-%m-%d %H:%M:%S"), "action": ""
    }), qos=0)


def demo_page_html(left_src, right_src):
    """空白父页 + 左右两个同尺寸 iframe（55%/45%），黑底细缝分隔。"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<style>
html,body {{ margin:0; height:100%; background:#111; }}
.wrap {{ display:flex; height:100vh; gap:3px; }}
iframe {{ border:0; width:55%; height:100%; }}
iframe.right {{ width:calc(45% - 3px); }}
</style></head>
<body><div class="wrap">
<iframe name="left" src="{left_src}"></iframe>
<iframe name="right" class="right" src="{right_src}"></iframe>
</div></body></html>"""


def switch_right(page, url):
    page.evaluate("u => { document.querySelector('iframe[name=right]').src = u; }", url)
    page.wait_for_timeout(1500)


def switch_right_srcdoc(page, html_text):
    page.evaluate("h => { document.querySelector('iframe[name=right]').srcdoc = h; }", html_text)
    page.wait_for_timeout(1500)


def scroll_right_to(page, heading):
    page.frames[1].evaluate(
        "t => { const h = [...document.querySelectorAll('h1,h2,h3')].find(e => e.textContent.includes(t));"
        " if (h) h.scrollIntoView({block:'start'}); }", heading)
    page.wait_for_timeout(800)


def new_context(browser, seg):
    seg_dir = OUT / ("rec-" + seg)
    shutil.rmtree(seg_dir, ignore_errors=True)
    seg_dir.mkdir(parents=True, exist_ok=True)
    return browser.new_context(viewport=VIEWPORT,
                               record_video_dir=str(seg_dir),
                               record_video_size=VIEWPORT)


def save_video(context, seg):
    video = context.pages[0].video
    target = OUT / f"demo-{seg}.webm"
    context.close()   # Playwright 要求先关闭 context，视频文件才最终落盘、可 save_as
    if video:
        video.save_as(target)
        print(f"[视频] {target}（{target.stat().st_size // 1024} KB）")
    return target


# ---------------- 三段剧本 ----------------

def segment_a(browser, pub):
    """A 组闭环：A1 优先关注 → A2 开风扇（3D 联动）→ A3 新数据恢复 → A4 事件复盘进报告。"""
    print("===== 录制 A 段（A1-A4） =====")
    context = new_context(browser, "a")
    page = context.new_page()
    page.set_content(demo_page_html(BASE + "/dashboard/index.html", BASE + "/three3d/index.html"))
    left = page.frame_locator("iframe[name=left]")
    right = page.frame_locator("iframe[name=right]")
    left.locator("#connStatus.online").wait_for(timeout=20000)
    right.locator("#connStatus.online").wait_for(timeout=20000)

    now = datetime.now().replace(microsecond=0)
    try:
        # 开场：三节点正常（3D 三栋楼状态色 + 总览成句）
        for n in NODES:
            pub_env(pub, n, 25, 60, now)
        page.wait_for_timeout(4500)

        # A1：dorm-b 连续偏热（时间回填，形成连续异常链）
        pub_env(pub, "dorm-b", 32, 82, now - timedelta(minutes=10))
        pub_env(pub, "dorm-b", 32.5, 81, now - timedelta(minutes=7))
        pub_env(pub, "dorm-b", 33, 80, now - timedelta(minutes=5))
        page.wait_for_timeout(4500)   # 优先关注横幅出现

        # 3D 先选中 dorm-b（building x=0 → 画布中心），侧栏后续显示动作状态
        box = right.locator("#canvasContainer canvas").bounding_box()
        if box:
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_timeout(1200)

        # A2：Dashboard tab 选 dorm-b → 开启风扇（动作通道 → 3D 风扇转 + 开窗）
        left.locator("#tabs button").filter(has_text="dorm-b").first.click()
        page.wait_for_timeout(1500)
        left.locator("#fanOnBtn").click()
        page.wait_for_timeout(6000)   # 卡片"处理中" + 3D 风扇转动/开窗

        # A3：降温新数据 → 仍偏热保持处理中 → 连续 2 条正常 → 已恢复 + 自动关扇
        pub_env(pub, "dorm-b", 30, 76, now + timedelta(minutes=1))
        page.wait_for_timeout(4000)
        pub_env(pub, "dorm-b", 27, 65, now + timedelta(minutes=2))
        page.wait_for_timeout(2500)
        pub_env(pub, "dorm-b", 26, 62, now + timedelta(minutes=3))
        page.wait_for_timeout(5000)   # "已恢复" + 3D 风扇停

        # A4：事件面板 → 导出 events.json → 右侧切到 report.html"事件复盘"区
        page.wait_for_timeout(2500)
        try:
            with page.expect_download(timeout=8000) as dl_info:
                left.locator("#exportEventsBtn").click()
            dl_info.value.save_as(ROOT / "data" / "events.json")
        except Exception as exc:   # 下载失败不影响画面叙事（事件面板本身已展示完整事件）
            print("[A4] 事件导出下载未捕获（仅影响报告区新事件）：", exc)
        run(["analysis/analyze.py", str(ROOT / "data" / "final-dormmate.csv"), "--out", str(ROOT / "data")])
        switch_right(page, BASE + "/data/report.html")
        scroll_right_to(page, "事件复盘")
        page.wait_for_timeout(6000)
    finally:
        save_video(context, "a")


def segment_b(browser, pub):
    """B 组信息闭环：B1 总览成句 → B2 依据卡片 → B4 朗读提醒 → B3 今日摘要（换 seed 重生成）。"""
    print("===== 录制 B 段（B1-B4） =====")
    # B3 前置：换 seed 生成一份新的模拟日数据与今日摘要（产物放 docs/demo/，不碰 data/）
    run(["analysis/make_day_data.py", "--out", str(OUT / "sim-day-demo"), "--seed", "5"])
    run(["analysis/daily_summary.py", "--day", str(OUT / "sim-day-demo")])

    context = new_context(browser, "b")
    page = context.new_page()
    page.set_content(demo_page_html(BASE + "/dashboard/index.html",
                                    BASE + "/docs/demo/sim-day-demo/report.html"))
    left = page.frame_locator("iframe[name=left]")
    left.locator("#connStatus.online").wait_for(timeout=20000)
    scroll_right_to(page, "今日摘要")   # 右侧报告先定位到摘要区（B3 内容在画面右侧）

    now = datetime.now().replace(microsecond=0)
    try:
        # B1：三节点正常 → 总览程序成句
        for n in NODES:
            pub_env(pub, n, 25, 60, now)
        page.wait_for_timeout(4500)

        # B1+B2：dorm-c 偏湿 → 总览自动更新 + 依据卡片（指标 + 来源 + 优先标注）
        pub_env(pub, "dorm-c", 25, 80, now + timedelta(minutes=1))
        page.wait_for_timeout(6000)

        # B4：朗读提醒（真实 TTS 朗读当前总览；视频无声，配合旁白说明）
        left.locator("#speakOverviewBtn").click()
        page.wait_for_timeout(4000)

        # B3：右侧报告停留在"今日摘要"区（seed 5 新摘要，≥2 事件叙事）
        page.wait_for_timeout(6000)
    finally:
        save_video(context, "b")


def segment_c(browser, pub):
    """C 组轻量 ML 闭环：C1 数据分离 / C2 对照（控制台）→ C3 report"ML 异常分析" → C4 案例与说明。"""
    print("===== 录制 C 段（C1-C4） =====")
    # 重跑对照，捕获真实控制台输出（random_state=42，与已提交结果一致）
    r = run(["analysis/c_ml.py"])
    console_html = ("<html><head><meta charset='UTF-8'><style>"
                    "body{background:#0d1117;color:#c9d1d9;font:14px/1.6 Consolas,monospace;padding:16px;white-space:pre-wrap;}"
                    "</style></head><body><pre>" +
                    _escape(str(r.stdout)) + "</pre></body></html>")

    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    # 只取 C 组与已知限制两段（C4 案例 + 替代原因），不整页塞进 iframe
    def grab(section_title):
        i = readme_text.find(section_title)
        j = readme_text.find("\n## ", i + 10)
        return readme_text[i:j if j > 0 else None]

    c_block = grab("C 组轻量 ML") or readme_text[:4000]
    limit_block = grab("已知限制") or ""
    readme_html = ("<html><head><meta charset='UTF-8'><style>"
                   "body{background:#f5f7fa;color:#2c3e50;font:15px/1.7 'Microsoft YaHei',sans-serif;padding:20px;white-space:pre-wrap;}"
                   "</style></head><body><pre style='white-space:pre-wrap;font-family:inherit'>" +
                   _escape(c_block + "\n\n" + limit_block[:2500]) + "</pre></body></html>")

    context = new_context(browser, "c")
    page = context.new_page()
    page.set_content(demo_page_html(BASE + "/data/report.html", "about:blank"))
    page.frames[1].wait_for_load_state(timeout=20000)   # 左 iframe 报告
    try:
        # C3：左屏 report.html 顶部即"ML 异常分析"区（三列并排 + 3 行高亮差异）
        page.wait_for_timeout(6000)

        # C2：右屏 srcdoc 展示 c_ml.py 真实控制台输出（对照表 + "发现 3 组…"）
        switch_right_srcdoc(page, console_html)
        page.wait_for_timeout(7000)

        # C2：右屏切换 c_compare.json（Chromium 原生 JSON 查看器 = 对照结果已保留）
        switch_right(page, BASE + "/data/c_compare.json")
        page.wait_for_timeout(4500)

        # C1：两份数据严格分离（新数据 → 历史，时间零重叠）
        switch_right(page, BASE + "/data/c_new.csv")
        page.wait_for_timeout(4000)
        switch_right(page, BASE + "/data/c_history.csv")
        page.wait_for_timeout(4000)

        # C4：README 不理想案例（27.5℃/70%）与 sklearn 替代原因
        switch_right_srcdoc(page, readme_html)
        page.wait_for_timeout(7000)
    finally:
        save_video(context, "c")


def _escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------- 合并 ----------------

def merge_videos():
    """标题卡 + 三段视频经 filter_complex 统一重编码合并为 demo-full.webm。"""
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        print(f"[合并] imageio-ffmpeg 不可用（{exc}），保留三段独立视频")
        return False

    titles = {
        "a": "A 组：发现异常 → 优先关注 → 开启风扇 → 验证恢复 → 事件复盘",
        "b": "B 组：把已有信息讲清楚 —— 总览 / 依据 / 今日摘要 / 合适表达",
        "c": "C 组：轻量 ML 应用闭环 —— 历史数据 → 对照 → 接回报告 → 留下不理想案例",
    }
    tmp = OUT / "rec-merge"
    tmp.mkdir(exist_ok=True)
    title_files = []
    try:
        for i, seg in enumerate(("a", "b", "c")):
            tf = tmp / f"title-{seg}.txt"
            tf.write_text(titles[seg], encoding="utf-8")
            card = tmp / f"title-{seg}.webm"
            # 路径中的盘符冒号需转义，否则会被 filter 解析器当作选项分隔符截断
            tf_escaped = tf.as_posix().replace(":", "\\:")
            cmd = [ffmpeg, "-y", "-f", "lavfi",
                   "-i", "color=c=0x1a2b3c:s=1600x900:d=3:r=25",
                   "-vf", f"drawtext=fontfile='C\\:/Windows/Fonts/msyh.ttc':textfile='{tf_escaped}':"
                          "fontsize=44:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
                   "-c:v", "libvpx-vp9", "-crf", "35", "-b:v", "1M", "-an", str(card)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if not card.exists() or card.stat().st_size == 0:
                print(f"[合并] 标题卡 {seg} 生成失败（回退纯拼接）: {r.stderr[-300:]}")
                title_files = []
                break
            title_files.append(card)

        segs = ["a", "b", "c"]
        inputs = []
        for i, seg in enumerate(segs):
            if title_files:
                inputs.extend([str(title_files[i]), str(OUT / f"demo-{seg}.webm")])
            else:
                inputs.append(str(OUT / f"demo-{seg}.webm"))
        n = len(inputs)
        filter_parts = []
        for i in range(n):
            filter_parts.append(f"[{i}:v]scale=1600:900,fps=25,format=yuv420p,setsar=1[v{i}]")
        filter_parts.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vout]")
        out_path = OUT / "demo-full.webm"
        cmd = [ffmpeg, "-y"] + sum((["-i", p] for p in inputs), []) + \
              ["-filter_complex", ";".join(filter_parts), "-map", "[vout]",
               "-c:v", "libvpx-vp9", "-crf", "35", "-b:v", "2M", "-an", str(out_path)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not out_path.exists():
            print("[合并] 失败（保留三段独立视频）：", r.stderr[-400:])
            return False
        print(f"[合并] {out_path}（{out_path.stat().st_size // 1024} KB）")
        # 另转一份 H.264 mp4（剪映等剪辑软件兼容性最好，便于配声音/字幕）
        mp4_path = OUT / "demo-full.mp4"
        r2 = subprocess.run([ffmpeg, "-y", "-i", str(out_path),
                             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-an",
                             "-movflags", "+faststart", str(mp4_path)],
                            capture_output=True, text=True)
        if r2.returncode == 0:
            print(f"[转码] {mp4_path}（{mp4_path.stat().st_size // 1024} KB）")
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------- 主流程 ----------------

def main():
    parser = argparse.ArgumentParser(description="DormMate A/B/C 演示视频录制")
    parser.add_argument("--seg", choices=("a", "b", "c"), help="只录指定段（默认全部）")
    parser.add_argument("--no-merge", action="store_true", help="只录制不合并")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)

    import paho.mqtt.client as mqtt
    from playwright.sync_api import sync_playwright

    broker = ensure_broker()
    if broker is None and not port_open(1883):
        print("[错误] Broker 未就绪，退出", file=sys.stderr)
        return 1

    server = start_server()
    pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    pub.connect("127.0.0.1", 1883)
    pub.loop_start()

    segs = [args.seg] if args.seg else ["a", "b", "c"]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for seg in segs:
                {"a": segment_a, "b": segment_b, "c": segment_c}[seg](browser, pub)
            browser.close()
    finally:
        pub.loop_stop()
        pub.disconnect()
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        if broker is not None:
            broker.terminate()

    # 恢复 A 段期间重生成的三个程序产物（demo 不改变仓库内容；新增文件只有 docs/demo/ 与本脚本）
    restored = subprocess.run(
        ["git", "checkout", "--", "data/events.json", "data/report.html", "data/trend.png"],
        cwd=str(ROOT), capture_output=True, text=True)
    if restored.returncode != 0:
        print("[提示] 产物恢复未执行（可能无改动）：", restored.stderr[-200:])
    else:
        print("[恢复] data/events.json、report.html、trend.png 已恢复到已提交状态")

    if len(segs) == 3 and not args.no_merge:
        merge_videos()
    print("录制完成：", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
