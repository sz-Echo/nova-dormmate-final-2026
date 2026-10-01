"""DormMate V0.8R5 演示视频录制（simulator/record_demo.py）

按任务书 p22 故事线录制 8 幕演示（一条 dorm-b 事件闭环主线），再用 ffmpeg 合并为
docs/demo/demo-v08r5-full.webm（纯画面无声音，配音见 add_dub.py）。

故事线（任务书 p22）：dorm-b 偏热 → 系统标记重点 → Web/移动端/3D 同步 → Camera 快照 →
执行处理 → 新数据恢复 → 多端事件更新 → 制造一次故障（错误 JSON）并修复 →
从关闭状态启动主要组件并跑通链路 → Rule/ML 对照。

设计要点：
  - 只发布、不重断言：demo 以画面为准；MQTT 数据全部脚本发布（剧本确定性）
  - 双 iframe 同屏：左 Dashboard / 右 3D 或报告（沿用旧版做法）
  - S3/S5 移动端同屏：ffmpeg gdigrab 按窗口标题录微信开发者工具，后期 xstack 合成
    （需用户预先打开小程序并保持窗口可见；标题匹配失败回退 --mobile-area 区域录制）
  - S7 冷启动段：真实重启 Broker 与 simulator，stdout 渲染进画面内 console 面板
  - 每幕独立 context + 计时打点；单幕可重录（--scene s7）
  - 5510 静态服务自启自停（与验收脚本一致）；录制结束恢复 data/ 程序产物

用法：
  python simulator/record_demo.py                 # 8 幕全录 + 合并
  python simulator/record_demo.py --scene s3      # 只录第 3 幕
  python simulator/record_demo.py --no-merge      # 只录不合并
  python simulator/record_demo.py --no-mobile     # S3/S5 跳过移动端录窗（调试用）
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
BASE = "http://127.0.0.1:5510"
NODES = ("dorm-a", "dorm-b", "dorm-c")
VIEWPORT = {"width": 1600, "height": 900}

MOSQUITTO_EXE = r"D:\Mosquitto\mosquitto.exe"
MOSQUITTO_CONF = r"D:\Mosquitto\mosquitto.conf"
FFMPEG = None   # 延迟初始化（imageio_ffmpeg）

SCENE_TIMING = {}   # {scene: {"start": ts, "dur": s}} 打点（供 add_dub 台词时间轴）


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
        [sys.executable, "-m", "http.server", "5510", "--bind", "127.0.0.1"],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if not wait_port(5510, 10):
        server.terminate()
        raise RuntimeError("5510 静态服务启动失败")
    return server


def start_logged(cmd_args, log_path, desc):
    """真实启动组件，stdout/stderr 追加到日志文件（S7 冷启动 console 面板素材）。"""
    f = open(log_path, "a", encoding="utf-8", errors="replace")
    f.write(f"\n$ {' '.join(cmd_args)}\n")
    f.flush()
    proc = subprocess.Popen(cmd_args, stdout=f, stderr=subprocess.STDOUT, cwd=str(ROOT))
    print(f"[冷启动] {desc} PID {proc.pid}（日志 {log_path}）")
    return proc, f


def pub_env(client, node, t, h, dt):
    client.publish(f"dormmate/{node}/env", json.dumps({
        "nodeId": node, "temperature": t, "humidity": h, "status": "",
        "time": dt.strftime("%Y-%m-%d %H:%M:%S"), "action": ""
    }), qos=0)


def fill_history(pub, now, minutes=30):
    """趋势图预跑（P4a 修订）：批量发布时间回填的正常数据，Dashboard 趋势图立即有曲线。

    每节点 30 条（now-60min ~ now-31min，每分钟一条、间隔 0.15s），约 5 秒完成。
    替代"启动 simulator 等 60 秒"：simulator 随机游走会干扰 S2 的优先叙事
    （随机偏冷/偏湿改变横幅），回填正常数据确定性可控——computeStreak 纯按记录
    序列无时间 gap 容忍，正常回填不进入异常链（priority.js 已核实）。
    """
    t = now - timedelta(minutes=minutes + 30)
    for _ in range(minutes):
        for n in NODES:
            pub_env(pub, n, 25, 60, t)
        t += timedelta(minutes=1)
        time.sleep(0.15)


def click_3d_building(page, right, node_id):
    """iframe 版点击 3D 楼体（复用 test_upgrade.CLICK_X 比例坐标），供开场默认选中。"""
    from test_upgrade import CLICK_X
    box = right.locator("#canvasContainer canvas").bounding_box()
    if not box:
        return False
    for fx, fy in [(CLICK_X[node_id], 0.5), (CLICK_X[node_id], 0.55), (CLICK_X[node_id], 0.45)]:
        page.mouse.click(box["x"] + box["width"] * fx, box["y"] + box["height"] * fy)
        page.wait_for_timeout(500)
        try:
            if right.locator("#sideNodeId").inner_text().startswith(node_id):
                return True
        except Exception:
            pass
    return False


def demo_page_html(left_src, right_src):
    """空白父页 + 左右两个同尺寸 iframe（55%/45%），黑底细缝分隔；底部 console 面板可选。"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<style>
html,body {{ margin:0; height:100%; background:#111; }}
.wrap {{ display:flex; height:calc(100% - {0 if False else 0}px); gap:3px; }}
iframe {{ border:0; width:55%; height:100%; }}
iframe.right {{ width:calc(45% - 3px); }}
#consolePanel {{ display:none; position:fixed; left:0; right:0; bottom:0; height:36%;
  background:#0d1117; color:#c9d1d9; font:13px/1.55 Consolas,monospace; padding:8px 14px;
  white-space:pre-wrap; overflow:hidden; border-top:2px solid #30363d; }}
</style></head>
<body><div class="wrap">
<iframe name="left" src="{left_src}"></iframe>
<iframe name="right" class="right" src="{right_src}"></iframe>
</div><div id="consolePanel"></div></body></html>"""


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


def show_console(page, text):
    """父页底部 console 面板显示终端输出（S7 冷启动）。"""
    page.evaluate("""t => { const el = document.getElementById('consolePanel');
        el.style.display = 'block'; el.textContent = t;
        document.querySelector('.wrap').style.height = '64%'; }""", text)
    page.wait_for_timeout(300)


def read_log_tail(path, limit=2000):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")[-limit:]
    except OSError:
        return ""


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
    context.close()   # 先关 context，视频才最终落盘
    if video:
        video.save_as(target)
        print(f"[视频] {target}（{target.stat().st_size // 1024} KB）")
    return target


def get_ffmpeg():
    global FFMPEG
    if FFMPEG is None:
        import imageio_ffmpeg
        FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
    return FFMPEG


def find_window_title(keyword):
    """PowerShell 枚举含关键字的窗口标题（gdigrab title 需精确匹配）。"""
    ps = ("Get-Process | Where-Object { $_.MainWindowTitle -like '*" + keyword +
          "*' } | Select-Object -ExpandProperty MainWindowTitle -Unique")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True, errors="replace")
    titles = [t.strip() for t in out.stdout.splitlines() if t.strip()]
    return titles


def find_window_rect():
    """查微信开发者工具可见窗口矩形（DPI 换算为物理像素）。

    返回 (left, top, w, h) 或 None。ctypes 枚举该进程的全部可见窗口，
    取面积最大者（devtools 主窗口句柄可能是隐藏窗口，模拟器渲染在子窗口）。
    gdigrab title 模式抓 GPU 渲染窗口是黑帧，故用 desktop + offset 区域捕获。
    """
    import ctypes
    from ctypes import wintypes

    # 1. 找进程 PID（PowerShell 一行，无转义负担）
    ps = "Get-Process -Name '微信开发者工具' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True, errors="replace")
    pids = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
    if not pids:
        print("[移动端] 未找到微信开发者工具进程——请先打开小程序。", file=sys.stderr)
        return None

    # 2. ctypes 枚举窗口（显式 argtypes/restype 防 64 位句柄截断）
    #    注意：devtools 是多进程应用（30+ 进程），可见窗口可能在任意子进程，须全部匹配
    user32 = ctypes.windll.user32
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [EnumProc, wintypes.LPARAM]
    user32.EnumWindows.restype = ctypes.c_bool
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = ctypes.c_bool
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = ctypes.c_bool
    user32.GetDpiForSystem.restype = wintypes.UINT
    rects = []

    def enum_cb(hwnd, _):
        win_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
        if win_pid.value in pids and user32.IsWindowVisible(hwnd):
            r = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(r)):
                w, h = r.right - r.left, r.bottom - r.top
                if w > 100 and h > 100:
                    rects.append((w * h, hwnd, r.left, r.top, w, h))
        return True

    user32.EnumWindows(EnumProc(enum_cb), 0)
    if not rects:
        print("[移动端] 未找到开发者工具的可见窗口——请还原/展开小程序窗口后重录本幕。", file=sys.stderr)
        return None
    # 选择逻辑：优先竖屏窗口（w/h < 1，手机模拟器特征——编辑器窗口是横屏且面积更大，
    # 曾选错过窗口）；无竖屏窗口时回退面积最大
    portrait = [r for r in rects if r[4] > r[5]]
    chosen = max(portrait, key=lambda r: r[0]) if portrait else max(rects)
    _, hwnd, l, t, w, h = chosen
    # DPI 换算物理像素
    dpi = user32.GetDpiForSystem()
    scale = dpi / 96.0
    l, t, w, h = (int(l * scale), int(t * scale), int(w * scale), int(h * scale))
    return (hwnd, l, t, w, h)


def set_window_topmost(hwnd, topmost):
    """置顶/取消置顶窗口（录制期间模拟器窗口须在最上层，否则 desktop 捕获抓到遮挡窗口）。"""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowPos.restype = ctypes.c_bool
    flag = 0x0001 | 0x0002 | 0x0040 if topmost else 0x0001 | 0x0002 | 0x0004
    return user32.SetWindowPos(hwnd, -1 if topmost else -2, 0, 0, 0, 0, flag)


class MobileGrab:
    """S3/S5 幕录微信开发者工具模拟器窗口（desktop 区域捕获 + ffmpeg，幕末停止）。

    GPU 渲染窗口 gdigrab title 模式抓黑帧，故用 -i desktop + offset/video_size 捕获窗口
    矩形区域；录制期间把模拟器窗口置顶（desktop 捕获抓屏幕最上层——用户正用 VS Code
    对话时会盖住模拟器，置顶保证画面不被遮挡），结束时恢复窗口层级。
    """

    def __init__(self, seg, duration):
        self.seg = seg
        self.duration = duration
        self.proc = None
        self.hwnd = None

    def start(self):
        rect = find_window_rect()
        if rect is None:
            print("[移动端] 未找到可见的微信开发者工具模拟器窗口（gdigrab 跳过）。"
                  "请打开小程序、还原并保持模拟器窗口可见后重录本幕。", file=sys.stderr)
            return False
        hwnd, l, t, w, h = rect
        # 屏幕边缘负坐标裁剪（gdigrab offset 不能为负）
        if l < 0:
            w += l
            l = 0
        if t < 0:
            h += t
            t = 0
        w -= w % 2
        h -= h % 2   # libvpx 要求偶数尺寸
        if set_window_topmost(hwnd, True):
            self.hwnd = hwnd
            print(f"[移动端] 模拟器窗口已置顶（录制期间不被遮挡）")
        else:
            print("[移动端] 置顶失败——请保持模拟器窗口不被其他窗口遮挡", file=sys.stderr)
        target = OUT / f"mobile-{self.seg}.webm"
        cmd = [get_ffmpeg(), "-y", "-f", "gdigrab", "-framerate", "25",
               "-offset_x", str(l), "-offset_y", str(t), "-video_size", f"{w}x{h}",
               "-i", "desktop", "-t", str(self.duration),
               "-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "1M", "-an", str(target)]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        time.sleep(2.0)
        if self.proc.poll() is not None:
            err = self.proc.stderr.read().decode("utf-8", "replace")[-300:] if self.proc.stderr else ""
            print(f"[移动端] gdigrab 启动失败：{err}", file=sys.stderr)
            self.proc = None
            if self.hwnd:
                set_window_topmost(self.hwnd, False)
            return False
        print(f"[移动端] desktop 区域捕获 ({l},{t}) {w}x{h}（{self.duration}s）")
        return True

    def stop(self):
        if self.proc is None:
            return False
        try:
            self.proc.wait(timeout=int(self.duration) + 20)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        if self.hwnd:
            set_window_topmost(self.hwnd, False)
            print("[移动端] 已恢复窗口层级")
        target = OUT / f"mobile-{self.seg}.webm"
        ok = target.exists() and target.stat().st_size > 1000
        if ok:
            print(f"[移动端] {target}（{target.stat().st_size // 1024} KB）")
        else:
            print(f"[移动端] 录窗失败或为空（{target}）", file=sys.stderr)
        return ok


# ---------------- 八幕剧本 ----------------

def scene_s1(browser, pub):
    """S1 开场：三节点正常，Dashboard + 3D 同屏。"""
    print("===== S1 开场：三节点正常 =====")
    t0 = time.time()
    context = new_context(browser, "s1")
    page = context.new_page()
    page.set_content(demo_page_html(BASE + "/dashboard/index.html", BASE + "/three3d/index.html"))
    left = page.frame_locator("iframe[name=left]")
    right = page.frame_locator("iframe[name=right]")
    left.locator("#connStatus.online").wait_for(timeout=20000)
    right.locator("#connStatus.online").wait_for(timeout=20000)
    now = datetime.now().replace(microsecond=0)
    try:
        fill_history(pub, now)   # 趋势图预跑：历史曲线完整可见
        page.wait_for_timeout(2000)
        click_3d_building(page, right, "dorm-a")   # 3D 默认选中 dorm-a，详情侧栏有内容
        for n in NODES:
            pub_env(pub, n, 25, 60, now)
        page.wait_for_timeout(4000)
        for n in NODES:   # 再来一轮，展示"持续刷新"（约 2.5s 一批）
            pub_env(pub, n, 25, 60, now + timedelta(seconds=10))
        page.wait_for_timeout(2600)
        for n in NODES:
            pub_env(pub, n, 25, 60, now + timedelta(seconds=20))
        page.wait_for_timeout(24000)
    finally:
        save_video(context, "s1")
    SCENE_TIMING["s1"] = {"dur": round(time.time() - t0, 1)}


def scene_s2(browser, pub):
    """S2 dorm-b 偏热：优先横幅 + 3D 优先光环 + 镜头聚焦。"""
    print("===== S2 dorm-b 偏热：标记重点 =====")
    t0 = time.time()
    context = new_context(browser, "s2")
    page = context.new_page()
    page.set_content(demo_page_html(BASE + "/dashboard/index.html", BASE + "/three3d/index.html"))
    left = page.frame_locator("iframe[name=left]")
    right = page.frame_locator("iframe[name=right]")
    left.locator("#connStatus.online").wait_for(timeout=20000)
    right.locator("#connStatus.online").wait_for(timeout=20000)
    now = datetime.now().replace(microsecond=0)
    try:
        fill_history(pub, now)   # 趋势图预跑
        for n in NODES:
            pub_env(pub, n, 25, 60, now)
        page.wait_for_timeout(3500)
        # dorm-b 连续偏热（时间回填形成连续异常链）
        pub_env(pub, "dorm-b", 31.5, 72, now - timedelta(minutes=12))
        pub_env(pub, "dorm-b", 32, 74, now - timedelta(minutes=9))
        pub_env(pub, "dorm-b", 32.5, 73, now - timedelta(minutes=6))
        page.wait_for_timeout(5000)   # 优先横幅 + 3D 光环 + 聚焦动画
        page.wait_for_timeout(36000)  # 停留展示
    finally:
        save_video(context, "s2")
    SCENE_TIMING["s2"] = {"dur": round(time.time() - t0, 1)}


def scene_s3(browser, pub, no_mobile=False):
    """S3 多端同步：Dashboard + 3D 左，微信开发者工具（gdigrab）右。"""
    print("===== S3 多端同步（移动端同屏） =====")
    t0 = time.time()
    context = new_context(browser, "s3")
    page = context.new_page()
    page.set_content(demo_page_html(BASE + "/dashboard/index.html", BASE + "/three3d/index.html"))
    left = page.frame_locator("iframe[name=left]")
    right = page.frame_locator("iframe[name=right]")
    left.locator("#connStatus.online").wait_for(timeout=20000)
    right.locator("#connStatus.online").wait_for(timeout=20000)
    now = datetime.now().replace(microsecond=0)
    grab = MobileGrab("s3", 58) if not no_mobile else None
    try:
        fill_history(pub, now)   # 趋势图预跑
        for n in NODES:
            pub_env(pub, n, 25, 60, now)
        page.wait_for_timeout(3000)
        pub_env(pub, "dorm-b", 31.5, 72, now)
        if grab:
            grab.start()
        page.wait_for_timeout(6000)   # 两端同步显示偏热
        pub_env(pub, "dorm-c", 25, 80, now + timedelta(minutes=1))
        page.wait_for_timeout(6000)
        pub_env(pub, "dorm-c", 25, 60, now + timedelta(minutes=2))
        page.wait_for_timeout(4000)
        if grab:
            grab.stop()
        page.wait_for_timeout(33000)
    finally:
        save_video(context, "s3")
    SCENE_TIMING["s3"] = {"dur": round(time.time() - t0, 1)}


def scene_s4(browser, pub):
    """S4 Camera 快照：语音命令条输入"拍照" → 快照叠加 nodeId/时间/状态。"""
    print("===== S4 Camera 快照（语音命令） =====")
    t0 = time.time()
    context = new_context(browser, "s4")
    page = context.new_page()
    page.set_content(demo_page_html(BASE + "/dashboard/index.html", BASE + "/three3d/index.html"))
    left = page.frame_locator("iframe[name=left]")
    right = page.frame_locator("iframe[name=right]")
    left.locator("#connStatus.online").wait_for(timeout=20000)
    right.locator("#connStatus.online").wait_for(timeout=20000)
    now = datetime.now().replace(microsecond=0)
    try:
        fill_history(pub, now)   # 趋势图预跑
        for n in NODES:
            pub_env(pub, n, 25, 60, now)
        page.wait_for_timeout(3000)
        pub_env(pub, "dorm-b", 31.5, 72, now)   # 让 dorm-b 保持异常（事件存在）
        page.wait_for_timeout(4000)
        # 语音命令条输入"查看 dorm-b"→ 选中 dorm-b（提交 = Enter，同 test_e2_voice.py）
        left.locator("#dashVoiceCommand").fill("查看 dorm-b")
        left.locator("#dashVoiceCommand").press("Enter")
        page.wait_for_timeout(3000)
        # 语音命令"拍照"（launch 已加假摄像头参数）
        left.locator("#dashVoiceCommand").fill("拍照")
        left.locator("#dashVoiceCommand").press("Enter")
        page.wait_for_timeout(6000)
        page.wait_for_timeout(16000)
    finally:
        save_video(context, "s4")
    SCENE_TIMING["s4"] = {"dur": round(time.time() - t0, 1)}


def scene_s5(browser, pub, no_mobile=False):
    """S5 执行处理：脚本以移动端同构 payload 发布 fan_on → 处理中 + 3D 风扇 + 移动端同步。"""
    print("===== S5 执行处理（开风扇，移动端同屏） =====")
    t0 = time.time()
    context = new_context(browser, "s5")
    page = context.new_page()
    page.set_content(demo_page_html(BASE + "/dashboard/index.html", BASE + "/three3d/index.html"))
    left = page.frame_locator("iframe[name=left]")
    right = page.frame_locator("iframe[name=right]")
    left.locator("#connStatus.online").wait_for(timeout=20000)
    right.locator("#connStatus.online").wait_for(timeout=20000)
    now = datetime.now().replace(microsecond=0)
    grab = MobileGrab("s5", 45) if not no_mobile else None
    try:
        fill_history(pub, now)   # 趋势图预跑
        for n in NODES:
            pub_env(pub, n, 25, 60, now)
        page.wait_for_timeout(3000)
        pub_env(pub, "dorm-b", 31.5, 72, now)
        page.wait_for_timeout(4000)   # 优先横幅出现
        if grab:
            grab.start()
        page.wait_for_timeout(3000)
        # 移动端同构 fan_on（与小程序 onFanOn 发布内容一致；P0 拍板方案 B）
        pub.publish("dormmate/dorm-b/action", json.dumps({
            "nodeId": "dorm-b", "action": "fan_on",
            "actionTime": (now + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S"),
        }), qos=0)
        page.wait_for_timeout(8000)   # Dashboard 处理中 + 3D 风扇转 + 移动端徽标
        if grab:
            grab.stop()
        page.wait_for_timeout(23000)
    finally:
        save_video(context, "s5")
    SCENE_TIMING["s5"] = {"dur": round(time.time() - t0, 1)}


def scene_s6(browser, pub):
    """S6 新数据恢复：仍异常保持处理中 → 连续 2 条正常 → 已恢复 + 多端事件更新 + 事件复盘。"""
    print("===== S6 新数据恢复 =====")
    t0 = time.time()
    context = new_context(browser, "s6")
    page = context.new_page()
    page.set_content(demo_page_html(BASE + "/dashboard/index.html", BASE + "/three3d/index.html"))
    left = page.frame_locator("iframe[name=left]")
    right = page.frame_locator("iframe[name=right]")
    left.locator("#connStatus.online").wait_for(timeout=20000)
    right.locator("#connStatus.online").wait_for(timeout=20000)
    now = datetime.now().replace(microsecond=0)
    try:
        fill_history(pub, now)   # 趋势图预跑
        for n in NODES:
            pub_env(pub, n, 25, 60, now)
        page.wait_for_timeout(3000)
        pub_env(pub, "dorm-b", 31.5, 72, now)
        page.wait_for_timeout(4000)
        pub.publish("dormmate/dorm-b/action", json.dumps({
            "nodeId": "dorm-b", "action": "fan_on",
            "actionTime": (now + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S"),
        }), qos=0)
        page.wait_for_timeout(6000)   # 处理中
        # 降温中仍偏热 → 保持处理中
        pub_env(pub, "dorm-b", 30, 76, now + timedelta(minutes=2))
        page.wait_for_timeout(5000)
        # 连续 2 条正常 → 已恢复 + 自动关扇（恢复瞬态：第二条后立即截画面停留）
        pub_env(pub, "dorm-b", 27, 65, now + timedelta(minutes=3))
        page.wait_for_timeout(2500)
        pub_env(pub, "dorm-b", 26, 62, now + timedelta(minutes=4))
        page.wait_for_timeout(4000)   # "已恢复"画面 + 3D 风扇停
        # 事件复盘：导出 events.json → 右侧 report.html 事件复盘区
        try:
            with page.expect_download(timeout=8000) as dl_info:
                left.locator("#exportEventsBtn").click()
            dl_info.value.save_as(ROOT / "data" / "events.json")
        except Exception as exc:
            print("[S6] 事件导出下载未捕获：", exc)
        run(["analysis/analyze.py", str(ROOT / "data" / "final-dormmate.csv"), "--out", str(ROOT / "data")])
        switch_right(page, BASE + "/data/report.html")
        scroll_right_to(page, "事件复盘")
        page.wait_for_timeout(22000)
    finally:
        save_video(context, "s6")
    SCENE_TIMING["s6"] = {"dur": round(time.time() - t0, 1)}


def scene_s7(browser, pub, broker_proc):
    """S7 故障 + 冷启动：错误 JSON 拦截 → 修复；真实重启 Broker/simulator，console 面板直播。"""
    print("===== S7 故障注入 + 冷启动 =====")
    t0 = time.time()
    context = new_context(browser, "s7")
    page = context.new_page()
    page.set_content(demo_page_html(BASE + "/dashboard/index.html", BASE + "/three3d/index.html"))
    left = page.frame_locator("iframe[name=left]")
    right = page.frame_locator("iframe[name=right]")
    left.locator("#connStatus.online").wait_for(timeout=20000)
    right.locator("#connStatus.online").wait_for(timeout=20000)
    now = datetime.now().replace(microsecond=0)
    log_path = OUT / "coldstart.log"
    log_path.write_text("", encoding="utf-8")
    cold_procs = []
    try:
        fill_history(pub, now)   # 趋势图预跑
        for n in NODES:
            pub_env(pub, n, 25, 60, now)
        page.wait_for_timeout(3000)

        # ---- 故障：错误 JSON ----
        # 发布后轮询确认告警横幅出现（D4 证据依赖此画面；横幅持续显示直到点击关闭）
        banner_ok = False
        for attempt in range(3):
            pub.publish("dormmate/dorm-b/env", "{bad json", qos=0)
            page.wait_for_timeout(2000)
            try:
                if not left.locator("#warnBanner").evaluate("el => el.hidden"):
                    banner_ok = True
                    break
            except Exception:
                pass
            print(f"[S7] 告警横幅未出现，重试发布坏 JSON（第 {attempt + 1} 次）", flush=True)
        page.wait_for_timeout(5000)   # 横幅展示停留（修复前）
        # D4 证据：元素级截图（FrameLocator/Frame 无 screenshot 方法，Locator 有）
        from test_upgrade import EVIDENCE
        (EVIDENCE / "D4").mkdir(parents=True, exist_ok=True)
        left.locator("#warnBanner").screenshot(path=str(EVIDENCE / "D4" / "d4-badjson-warning.png"))
        left.locator("#dropCount").screenshot(path=str(EVIDENCE / "D4" / "d4-drop-count.png"))
        print(f"[S7] 告警横幅出现={banner_ok}，D4 证据截图已保存", flush=True)
        # 修复：重发合法消息
        pub_env(pub, "dorm-b", 25, 60, now + timedelta(minutes=1))
        page.wait_for_timeout(5000)   # 恢复更新

        # ---- 冷启动：真实停掉 Broker 与 simulator，再按序重启 ----
        show_console(page, "正在关闭 Broker 与模拟节点，模拟从关闭状态冷启动…")
        pub.disconnect()
        if broker_proc is not None:
            broker_proc.terminate()
            try:
                broker_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                broker_proc.kill()
        page.wait_for_timeout(5000)   # 左侧显示断开（Dashboard 自动重连等待）
        show_console(page, "Broker 已停止。现在按顺序启动：1) Broker 2) 模拟节点 3) 静态服务已在运行。")
        page.wait_for_timeout(4000)
        # 重启 Broker（日志进 console 面板）
        b2, f1 = start_logged([MOSQUITTO_EXE, "-c", MOSQUITTO_CONF, "-v"], log_path, "Broker")
        cold_procs.extend([b2, f1])
        deadline = time.time() + 12
        while time.time() < deadline:
            if port_open(1883):
                break
            show_console(page, read_log_tail(log_path))
            page.wait_for_timeout(800)
        show_console(page, read_log_tail(log_path))
        page.wait_for_timeout(3000)
        # 重启 simulator
        sim, f2 = start_logged([sys.executable, "simulator/simulate.py"], log_path, "simulator")
        cold_procs.extend([sim, f2])
        for _ in range(6):
            page.wait_for_timeout(1500)
            show_console(page, read_log_tail(log_path))
        # 重新连接发布客户端（旧连接已断）
        pub.connect("127.0.0.1", 1883)
        pub.loop_start()
        time.sleep(1.0)
        pub_env(pub, "dorm-b", 25, 60, now + timedelta(minutes=2))
        page.wait_for_timeout(6000)   # 左侧自动重连 + 三端数据恢复
        show_console(page, read_log_tail(log_path) + "\n\n=== 链路已跑通：Broker + 模拟节点 + 三端实时更新 ===")
        page.wait_for_timeout(25000)
    finally:
        save_video(context, "s7")
        for p in cold_procs:
            try:
                if hasattr(p, "terminate") and p.poll() is None:
                    p.terminate()
                elif hasattr(p, "close"):
                    p.close()
            except Exception:
                pass
    SCENE_TIMING["s7"] = {"dur": round(time.time() - t0, 1)}


def scene_s8(browser, pub):
    """S8 Rule/ML 对照 + 收尾：report.html ML 区 + c_ml 控制台 + C4 案例。"""
    print("===== S8 Rule/ML 对照 =====")
    t0 = time.time()
    r = run(["analysis/c_ml.py"])
    console_html = ("<html><head><meta charset='UTF-8'><style>"
                    "body{background:#0d1117;color:#c9d1d9;font:14px/1.6 Consolas,monospace;padding:16px;white-space:pre-wrap;}"
                    "</style></head><body><pre>" +
                    _escape(str(r.stdout)) + "</pre></body></html>")
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    def grab(section_title):
        i = readme_text.find(section_title)
        j = readme_text.find("\n## ", i + 10)
        return readme_text[i:j if j > 0 else None]
    c_block = grab("C 组轻量 ML") or readme_text[:4000]
    readme_html = ("<html><head><meta charset='UTF-8'><style>"
                   "body{background:#f5f7fa;color:#2c3e50;font:15px/1.7 'Microsoft YaHei',sans-serif;padding:20px;white-space:pre-wrap;}"
                   "</style></head><body><pre style='white-space:pre-wrap;font-family:inherit'>" +
                   _escape(c_block[:3000]) + "</pre></body></html>")

    context = new_context(browser, "s8")
    page = context.new_page()
    page.set_content(demo_page_html(BASE + "/data/report.html", "about:blank"))
    page.frames[1].wait_for_load_state(timeout=20000)
    try:
        page.wait_for_timeout(6000)   # 左屏 ML 异常分析区（三列并排 + 差异高亮）
        switch_right_srcdoc(page, console_html)
        page.wait_for_timeout(7000)   # c_ml 真实控制台输出（对照表）
        switch_right(page, BASE + "/data/c_compare.json")
        page.wait_for_timeout(5000)
        switch_right_srcdoc(page, readme_html)
        page.wait_for_timeout(42000)  # C4 案例与说明停留
    finally:
        save_video(context, "s8")
    SCENE_TIMING["s8"] = {"dur": round(time.time() - t0, 1)}


def _escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------- 合并 ----------------

def merge_videos(scenes, has_mobile):
    """两步合并：① 每幕统一转 1600x900/25fps 中间 mp4（移动端幕先 xstack 合成）
    ② concat demuxer 拼接全部中间片 → demo-v08r5-full.webm + .mp4。"""
    ffmpeg = get_ffmpeg()
    tmp = OUT / "rec-merge"
    tmp.mkdir(exist_ok=True)
    mids = []

    def probe(p):
        rp = subprocess.run([ffmpeg, "-i", str(p)], capture_output=True, text=True)
        for line in rp.stderr.splitlines():
            if "Duration" in line:
                h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
        return 0.0

    try:
        for seg in scenes:
            main = OUT / f"demo-{seg}.webm"
            if not main.exists():
                print(f"[合并] 缺少 {main.name}，跳过", file=sys.stderr)
                return False
            mid = tmp / f"mid-{seg}.mp4"
            if seg in ("s3", "s5") and has_mobile and (OUT / f"mobile-{seg}.webm").exists():
                mob = OUT / f"mobile-{seg}.webm"
                mob_dur = probe(mob)
                # xstack 的 shortest 实测不生效：主画面显式 trim 到录窗时长，两路等长
                cmd = [ffmpeg, "-y", "-i", str(main), "-i", str(mob),
                       "-filter_complex",
                       f"[0:v]scale=1160:900,fps=25,format=yuv420p,setpts=PTS-STARTPTS,"
                       f"trim=end={mob_dur},setpts=PTS-STARTPTS[l];"
                       "[1:v]scale=437:900,fps=25,format=yuv420p,setpts=PTS-STARTPTS[r];"
                       "[l][r]xstack=inputs=2:layout=0_0|1163_0[v]",
                       "-map", "[v]", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                       "-an", str(mid)]
            else:
                cmd = [ffmpeg, "-y", "-i", str(main),
                       "-vf", "scale=1600:900,fps=25,format=yuv420p,setsar=1",
                       "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                       "-an", str(mid)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0 or not mid.exists() or mid.stat().st_size == 0:
                print(f"[合并] {seg} 中间片失败：{r.stderr[-300:]}", file=sys.stderr)
                return False
            mids.append(mid)
            print(f"[合并] {seg} 中间片 OK（{mid.stat().st_size // 1024} KB）")

        # ② concat demuxer
        list_file = tmp / "list.txt"
        list_file.write_text("".join(f"file '{m.as_posix()}'\n" for m in mids), encoding="utf-8")
        out_path = OUT / "demo-v08r5-full.webm"
        r = subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
                            "-c:v", "libvpx-vp9", "-crf", "35", "-b:v", "2M", "-an", str(out_path)],
                           capture_output=True, text=True)
        if r.returncode != 0 or not out_path.exists():
            print("[合并] concat 失败：", r.stderr[-400:])
            return False
        print(f"[合并] {out_path}（{out_path.stat().st_size // 1024} KB）")
        mp4_path = OUT / "demo-v08r5-full.mp4"
        r2 = subprocess.run([ffmpeg, "-y", "-i", str(out_path),
                             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-an",
                             "-movflags", "+faststart", str(mp4_path)], capture_output=True, text=True)
        if r2.returncode == 0:
            print(f"[转码] {mp4_path}（{mp4_path.stat().st_size // 1024} KB）")
        # 打点重建：从中间片实际时长推导各幕边界（供 add_dub 台词时间轴）
        timing, acc = {}, 0.0
        for seg, mid in zip(scenes, mids):
            d = probe(mid)
            timing[seg] = {"dur": round(d, 2)}
            acc += d
        timing_path = OUT / "scene-timing.json"
        timing_path.write_text(json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[打点] {timing_path}")
        print(f"[时长] 合计 {acc:.1f}s（{int(acc // 60)}:{int(acc % 60):02d}），任务书要求 5-8 分钟")
        if not (300 <= acc <= 480):
            print(f"[警告] 总时长 {acc:.0f}s 不在 5-8 分钟区间，需调整幕停留时长后重录对应幕")
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------- 主流程 ----------------

def main():
    parser = argparse.ArgumentParser(description="DormMate V0.8R5 故事线演示视频录制（8 幕）")
    parser.add_argument("--scene", help="只录指定幕（s1..s8）")
    parser.add_argument("--from", dest="from_scene", help="从指定幕录到 s8（如 --from s3）")
    parser.add_argument("--no-merge", action="store_true", help="只录制不合并")
    parser.add_argument("--no-mobile", action="store_true", help="S3/S5 跳过移动端录窗（调试用）")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)

    # P4a 修订：录制前重置系统状态——清空 events.json（事件面板/报告复盘从空白开始，
    # 避免旧数据残留；录制结束后 git checkout 恢复提交版基线）
    events_path = ROOT / "data" / "events.json"
    if events_path.exists():
        events_path.write_text("[]", encoding="utf-8")
        print("[重置] data/events.json 已清空（录制后自动恢复基线）")

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

    all_scenes = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]
    if args.scene:
        scenes = [args.scene]
    elif args.from_scene:
        scenes = all_scenes[all_scenes.index(args.from_scene):]
    else:
        scenes = all_scenes
    if args.scene:
        print(f"[提示] 单幕录制：{args.scene}（若为 s3/s5，请确认微信开发者工具已打开并可见）")
    elif args.from_scene:
        print(f"[提示] 从 {args.from_scene} 录到 s8（s3/s5 幕请确认微信开发者工具已打开并可见）")

    # 防残留：只删除将录制幕的旧移动端录窗（MobileGrab 跳过/失败时合并不得误用旧文件；
    # 不能删全部——单幕重录时会误删其他幕刚录好的文件）
    for seg in scenes:
        if seg in ("s3", "s5"):
            old = OUT / f"mobile-{seg}.webm"
            if old.exists():
                old.unlink()
                print(f"[清理] 删除旧移动端录窗 {old.name}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])   # S4 假摄像头（同 test_e2_voice.py）
            for seg in scenes:
                fn = {"s1": scene_s1, "s2": scene_s2, "s3": scene_s3, "s4": scene_s4,
                      "s5": scene_s5, "s6": scene_s6, "s7": scene_s7, "s8": scene_s8}[seg]
                if seg in ("s3", "s5"):
                    fn(browser, pub, no_mobile=args.no_mobile)
                elif seg == "s7":
                    fn(browser, pub, broker)
                    if broker is not None and broker.poll() is None:
                        broker.terminate()   # S7 自己重启了 Broker，旧句柄仅作记录
                else:
                    fn(browser, pub)
            browser.close()
    finally:
        try:
            pub.loop_stop()
            pub.disconnect()
        except Exception:
            pass
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        for p in ([broker] if broker is not None else []):
            if p.poll() is None:
                p.terminate()

    # 恢复录制期间重生成的程序产物（demo 不改变仓库内容）
    restored = subprocess.run(
        ["git", "checkout", "--", "data/events.json", "data/report.html", "data/trend.png"],
        cwd=str(ROOT), capture_output=True, text=True)
    if restored.returncode != 0:
        print("[提示] 产物恢复未执行（可能无改动）：", restored.stderr[-200:])
    else:
        print("[恢复] data/events.json、report.html、trend.png 已恢复到已提交状态")

    if not args.scene and not args.no_merge:
        merge_videos(all_scenes, has_mobile=not args.no_mobile)   # 合并以全部 8 幕为准（缺失报错）
    print("录制完成：", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
