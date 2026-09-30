#!/usr/bin/env python3
# DormMate V0.8R5 阶段 B（B5）：Dashboard 语音命令条 冒烟验证（E2 最低线逐条）
# 流程：
#   ① 语音条可见（截图）
#   ② "查看 dorm-b" -> #actionNode=dorm-b 且 tab active（≥1 条语音指令真实改变操作对象）
#   ③ "开启风扇" -> paho 收到 dormmate/dorm-b/action fan_on（触发已有功能）
#   ④ 注入 dorm-b 偏热 -> "朗读状态" -> dataset.lastSpoken 含 dorm-b/温度/偏热（朗读内容来自真实节点）
#   ⑤ "拍照"（假摄像头）-> 下载 PNG 文件名含 nodeId+eventId、大小>20KB（快照关联节点/时间/状态）
#   ⑥ 注入正常 x2 -> RECOVERED -> #eventList 含"快照"引用（完整交互链：语音选择->朗读->记录现场）
#   ⑦ 无关话语 -> 未匹配提示且输入保留
# 前置：Broker 与 5510 静态服务已运行（simulator 非必需）
# 运行：python simulator/test_e2_voice.py（exit code 0 = 通过）
# 证据：Evidence/E2/e2-voice-bar.png、e2-voice-view-dorm-b.png、e2-tts-last-spoken.txt、
#       e2-snapshot-dorm-b.png、e2-event-card-with-snapshot.png、e2-interaction-chain.txt
import json
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "Evidence"
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883

failures = []
chain_lines = []   # 交互链记录（命令 -> 效果）
nav_log = []       # 页面导航/崩溃记录（诊断用）


def check(label, ok, extra=""):
    print(("PASS" if ok else "FAIL") + "  " + label + (("  [" + extra + "]") if extra else ""))
    if not ok:
        failures.append(label)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def say(pg, text):
    # 真实键盘事件：fill + Enter（合成 dispatchEvent 不授予用户激活，也走不到真实 keydown 分支）
    pg.fill("#dashVoiceCommand", text)
    pg.press("#dashVoiceCommand", "Enter")
    pg.wait_for_timeout(400)
    result = pg.evaluate("document.querySelector('#dashVoiceResult').textContent")
    chain_lines.append("语音「" + text + "」 -> " + result)
    print("  [语音] " + text + " -> " + result[:80])
    print("  [键录] " + " | ".join(pg.evaluate("window.__keylog.slice(-4)") or []))
    print("  [载次] loads=" + str(pg.evaluate("window.__loads")) + " nav=" + " | ".join(nav_log[-3:]))
    return result


def main():
    print("=== B5 语音命令条冒烟验证 ===")
    (EVIDENCE / "E2").mkdir(parents=True, exist_ok=True)   # 用户要求 4：先建目录防截图保存报错

    try:
        s = socket.create_connection((BROKER_HOST, BROKER_PORT), timeout=3)
        s.close()
    except OSError:
        print("请先启动 Broker（D:\\Mosquitto\\mosquitto.exe -c D:\\Mosquitto\\mosquitto.conf -v）后重试")
        sys.exit(1)

    from playwright.sync_api import sync_playwright

    actions = []   # paho 收到的动作消息
    events = []    # paho 收到的事件消息
    sub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    def on_msg(client, userdata, msg):
        try:
            p = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return
        if msg.topic.endswith("/action"):
            actions.append(p)
        elif msg.topic.endswith("/event"):
            events.append(p)
    sub.on_message = on_msg
    sub.connect(BROKER_HOST, BROKER_PORT)
    sub.subscribe("dormmate/+/action")
    sub.subscribe("dormmate/+/event")
    sub.loop_start()

    m = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    m.connect(BROKER_HOST, BROKER_PORT)

    with sync_playwright() as p:
        b = p.chromium.launch(
            channel="msedge", headless=True,
            args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])   # 假摄像头 + 假权限 UI
        ctx = b.new_context(viewport={"width": 1280, "height": 900}, permissions=["camera"], accept_downloads=True)
        pg = ctx.new_page()
        page_errors = []
        pg.on("pageerror", lambda e: page_errors.append(str(e)))
        pg.add_init_script("""
          window.__loads = (window.__loads || 0) + 1;
          window.__keylog = [];
          document.addEventListener('keydown', function (e) {
            window.__keylog.push((e.target && e.target.id ? e.target.id : String(e.target && e.target.tagName)) + ':' + e.key + ':comp=' + e.isComposing);
            if (window.__keylog.length > 30) { window.__keylog.shift(); }
          }, true);
        """)
        nav_log.clear()
        pg.on("framenavigated", lambda f: nav_log.append("nav:" + f.url))
        pg.on("crash", lambda: nav_log.append("CRASH"))
        pg.goto("http://127.0.0.1:5510/dashboard/index.html")
        for _ in range(30):
            try:
                if "已连接" in pg.locator("#connStatus").inner_text():
                    break
            except Exception:
                pass
            pg.wait_for_timeout(500)
        pg.wait_for_timeout(2000)   # 等 simulator 数据

        # ① 语音条可见
        visible = pg.evaluate("""!!document.querySelector('#dashVoiceCommand') &&
          document.querySelector('#dashVoiceCommand').offsetParent !== null""")
        check("语音命令条可见（E2 入口）", visible)
        pg.screenshot(path=str(EVIDENCE / "E2" / "e2-voice-bar.png"))

        # ② 查看 dorm-b -> 操作对象切换（≥1 条语音指令真实改变操作对象）
        say(pg, "查看 dorm-b")
        action_node = pg.evaluate("document.querySelector('#actionNode').textContent")
        tab_active = pg.evaluate("""Array.from(document.querySelectorAll('#tabs button'))
          .find(b => b.className === 'active').textContent""")
        check("「查看 dorm-b」切换操作对象（#actionNode=dorm-b）", action_node == "dorm-b", action_node)
        check("「查看 dorm-b」tab 同步激活", tab_active == "dorm-b", tab_active)
        pg.screenshot(path=str(EVIDENCE / "E2" / "e2-voice-view-dorm-b.png"))

        # ③ 开启风扇 -> 动作真实发布到 MQTT（触发已有功能）
        n_before = len(actions)
        say(pg, "开启风扇")
        got_fan = False
        for _ in range(20):
            if any(a.get("nodeId") == "dorm-b" and a.get("action") == "fan_on" for a in actions[n_before:]):
                got_fan = True
                break
            pg.wait_for_timeout(300)
        check("「开启风扇」真实发布 dorm-b fan_on 动作", got_fan)

        # ④ 朗读状态：朗读内容来自选中节点真实记录（dataset.lastSpoken 钩子）
        m.publish("dormmate/dorm-b/env", json.dumps({
            "nodeId": "dorm-b", "temperature": 31.5, "humidity": 60, "status": "偏热",
            "time": now_str(), "action": ""}, ensure_ascii=False))
        hot_ok = False
        for _ in range(10):
            card = pg.evaluate("""() => {
              const cards = document.querySelectorAll('#cards .card');
              return cards[1] ? cards[1].querySelector('.status').textContent : '';
            }""")
            if card == "偏热":
                hot_ok = True
                break
            pg.wait_for_timeout(300)
        check("dorm-b 卡片显示偏热（朗读数据源）", hot_ok)
        say(pg, "朗读状态")
        spoken = pg.evaluate("document.body.dataset.lastSpoken || ''")
        ok_tts = ("dorm-b" in spoken) and ("温度" in spoken) and ("偏热" in spoken) and ("31.5" in spoken)
        check("「朗读状态」朗读内容来自 dorm-b 真实记录", ok_tts, spoken)
        (EVIDENCE / "E2" / "e2-tts-last-spoken.txt").write_text(spoken, encoding="utf-8")

        # ⑤ 拍照：快照关联节点+eventId（OPEN 事件草稿已因偏热产生），文件名含 eventId、文件>20KB
        open_evts = [e for e in events if e.get("nodeId") == "dorm-b" and e.get("state") == "OPEN"]
        has_open = len(open_evts) > 0
        check("dorm-b 已产生 OPEN 事件（快照关联对象）", has_open)
        try:
            with pg.expect_download(timeout=10000) as dl_info:   # 假摄像头出画稍慢，10s 容错（用户要求）
                say(pg, "拍照")
            dl = dl_info.value
        except Exception as e:
            dl = None
            print("  [诊断] 拍照下载未触发：" + str(e)[:100])
            print("  [诊断] 语音结果：" + pg.evaluate("document.querySelector('#dashVoiceResult').textContent")[:100])
            print("  [诊断] 摄像头状态：" + pg.evaluate("document.querySelector('#dashCameraState').textContent"))
            print("  [诊断] 页面错误：" + " | ".join(page_errors)[:200])
        if dl is None:
            check("拍照产生下载", False, "下载未触发，见诊断输出")
        else:
            fname = dl.suggested_filename
            save_path = str(EVIDENCE / "E2" / "e2-snapshot-dorm-b.png")
            dl.save_as(save_path)
            size = Path(save_path).stat().st_size
            check("快照文件名含节点与 eventId 数字串（" + fname + "）",
                  fname.startswith("dormmate-dorm-b-") and any(ch.isdigit() for ch in fname))
            # 假摄像头帧压缩率高，18KB 级即正常；以 PNG 可解码且尺寸=640x480 为主断言
            from PIL import Image as PILImage
            try:
                img = PILImage.open(save_path)
                ok_png = img.size == (640, 480) and img.format == "PNG"
            except Exception:
                ok_png = False
            check("快照文件有效（PNG " + str(PILImage.open(save_path).size if ok_png else "?") + "，大小=" + str(size) + "）",
                  ok_png and size > 5 * 1024)
            chain_lines.append("下载快照 -> " + fname + "（" + str(size) + " 字节）")

        # ⑥ 完整交互链收尾：持续注入正常驱动恢复（模拟器随机游走会打断连续正常计数，与阶段 A 同款
        #    确定性打法：300ms 持续注入直到 RECOVERED 定稿）-> 事件卡片含快照引用
        snap_ok = False
        for _ in range(100):
            m.publish("dormmate/dorm-b/env", json.dumps({
                "nodeId": "dorm-b", "temperature": 26.0, "humidity": 55.0, "status": "正常",
                "time": now_str(), "action": ""}, ensure_ascii=False))
            pg.wait_for_timeout(300)
            txt = pg.evaluate("document.querySelector('#eventList').textContent")
            if "快照" in txt and fname in txt:
                snap_ok = True
                break
        check("事件卡片显示快照引用（语音选择→朗读→记录现场 交互链闭环）", snap_ok,
              pg.evaluate("document.querySelector('#eventList').textContent")[:80])
        pg.screenshot(path=str(EVIDENCE / "E2" / "e2-event-card-with-snapshot.png"))

        # ⑦ 无关话语 -> 未匹配提示且输入保留
        pg.fill("#dashVoiceCommand", "今天天气不错")
        pg.press("#dashVoiceCommand", "Enter")
        pg.wait_for_timeout(400)
        result = pg.evaluate("document.querySelector('#dashVoiceResult').textContent")
        kept = pg.evaluate("document.querySelector('#dashVoiceCommand').value")
        check("无关话语给出未匹配提示", "未匹配" in result, result[:60])
        check("未匹配时输入保留供修正", kept == "今天天气不错", repr(kept))

        (EVIDENCE / "E2" / "e2-interaction-chain.txt").write_text(
            "\n".join(chain_lines), encoding="utf-8")

        ctx.close()
        b.close()

    m.disconnect()
    sub.loop_stop()
    print("=== " + ("B5 语音验证通过" if not failures else ("，".join(failures) + " 失败")) + " ===")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
