"""DormMate V0.8R5 演示视频配音 + 硬字幕（simulator/add_dub.py）

输入：docs/demo/demo-v08r5-full.webm（record_demo.py 8 幕产物，纯画面无声音；--src 可指定）
输出：
  docs/demo/demo-v08r5-subtitles.srt —— 软字幕（供剪映等二次编辑）
  docs/demo/dub-lines.txt            —— 配音台词表（实际时间点 / 台词 / 幕，供校对）
  docs/demo/demo-v08r5-final.mp4     —— 成品：H.264 + AAC 配音 + 硬字幕 + 结尾 8s 黑屏收尾台词

配音：edge-tts（zh-CN-XiaoxiaoNeural 女声），每段独立生成、失败重试 2 次（服务依赖网络）。
时间轴防重叠：实际起点 = max(计划起点, 上一段结束 + 0.3s)，保证台词不叠音、不压过镜头切换。
字幕烧录用 libass + Microsoft YaHei（本机已验证可用），白字黑边底部居中。
台词时间轴按 record_demo.py 产出的 scene-timing.json 各幕时长推算（录制后核对微调）。

用法：python simulator/add_dub.py [--src demo-v08r5-full.webm] [--rate -4%] [--voice zh-CN-XiaoxiaoNeural]
"""
import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "demo"
SRC = OUT / "demo-v08r5-full.webm"
VOICE = "zh-CN-XiaoxiaoNeural"
VIDEO_END = None   # 运行时 probe SRC 动态探测（不再硬编码）

# 8 幕台词：(计划起点秒, 台词, 幕)。起点在 main 中按 scene-timing.json 实际时长校正。
LINES = [
    (5.0, "三个宿舍实时上报温湿度，看板、3D 和移动端显示同一份数据，当前全部正常。", "S1 开场"),
    (18.0, "dorm-b 连续偏热：看板顶部横幅自动标出优先关注和原因，3D 里对应楼栋亮起优先光环，镜头自动聚焦。", "S2 标记重点"),
    (78.0, "移动端订阅同一个数据源：三节点状态、当前重点和事件徽标与看板保持一致，新消息到达两端同时更新。", "S3 多端同步"),
    (148.0, "用语音命令拍照：快照自动叠加节点、时间和状态，并关联到当前事件，事件卡片里能看到现场快照。", "S4 Camera 快照"),
    (190.0, "开启风扇：动作经 MQTT 发出，看板进入处理中，3D 风扇转动、窗户打开，移动端同步显示事件状态。", "S5 执行处理"),
    (238.0, "恢复必须由新数据触发：降温中仍偏热就保持处理中；连续两条正常数据后判定已恢复并自动关扇，多端同步更新。", "S6 新数据恢复"),
    (306.0, "制造一次真实故障：向系统发送一条坏 JSON，看板拦截告警、页面不受影响；修复后重发，立即恢复更新。", "S7a 故障修复"),
    (345.0, "最后从关闭状态启动主要组件：Broker、模拟节点依次真实启动，画面里是真实终端输出，链路重新跑通。", "S7b 冷启动"),
    (410.0, "报告里固定规则与模型并排对照：规则判正常，模型发现与历史明显不同，差异行高亮。", "S8 Rule/ML 对照"),
    (440.0, "最后保留一个不理想案例：27.5 度、70% 被模型标为明显不同，原因是历史数据太少、区间太窄。模型只是辅助，与固定规则并列。", "S8 C4 案例"),
    (VIDEO_END + 0.5 if VIDEO_END else -1.0, "以上就是 DormMate 的故事线演示，感谢观看。", "收尾"),
]


def ffmpeg_path():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args, desc):
    r = subprocess.run([ffmpeg_path(), "-y"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[失败] {desc}: {r.stderr[-400:]}", file=sys.stderr)
        return False
    print(f"[完成] {desc}")
    return True


def probe_duration(path):
    r = subprocess.run([ffmpeg_path(), "-i", str(path)], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return round(float(h) * 3600 + float(m) * 60 + float(s), 3)
    return 0.0


async def synth_one(text, path, rate):
    import edge_tts
    tts = edge_tts.Communicate(text, VOICE, rate=rate or "+0%")
    await tts.save(str(path))


def synth_with_retry(text, path, rate, attempts=3):
    for i in range(attempts):
        try:
            asyncio.run(synth_one(text, path, rate))
            if path.exists() and path.stat().st_size > 0:
                return True
        except Exception as exc:
            print(f"[TTS] 第 {i + 1} 次失败: {exc}")
    return False


def fmt_srt(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"


def main():
    global VOICE, VIDEO_END, SRC
    parser = argparse.ArgumentParser(description="DormMate 演示视频配音 + 硬字幕")
    parser.add_argument("--src", default=None, help="输入视频（默认 docs/demo/demo-v08r5-full.webm）")
    parser.add_argument("--rate", default="", help="edge-tts 语速（如 -4%%），默认原速")
    parser.add_argument("--voice", default=VOICE, help="edge-tts 音色")
    args = parser.parse_args()
    VOICE = args.voice
    if args.src:
        SRC = OUT / args.src

    if not SRC.exists():
        print(f"[错误] 未找到 {SRC}，请先运行 python simulator/record_demo.py", file=sys.stderr)
        return 1
    VIDEO_END = probe_duration(SRC)
    if VIDEO_END <= 0:
        print("[错误] 无法探测视频时长", file=sys.stderr)
        return 1
    print(f"[输入] {SRC.name}，时长 {VIDEO_END:.1f}s")
    LINES[-1] = (round(VIDEO_END + 0.5, 1), LINES[-1][1], LINES[-1][2])   # 收尾台词在结尾黑屏

    # 按 scene-timing.json 把台词起点校正到实际幕边界：起点 = 幕起点 + 幕内偏移
    timing_path = OUT / "scene-timing.json"
    if timing_path.exists():
        try:
            timing = json.loads(timing_path.read_text(encoding="utf-8"))
            starts, acc = {}, 0.0
            for seg in ("s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"):
                starts[seg] = acc
                acc += timing.get(seg, {}).get("dur", 0)
            # (幕名, 幕内偏移秒)
            place = {"S1": ("s1", 5), "S2": ("s2", 10), "S3": ("s3", 8), "S4": ("s4", 10),
                     "S5": ("s5", 10), "S6": ("s6", 8), "S7a": ("s7", 6), "S7b": ("s7", 42),
                     "S8": ("s8", 7)}
            for i, (planned, text, tag) in enumerate(LINES):
                key = tag.split(" ")[0]
                if key in place:
                    seg, off = place[key]
                    LINES[i] = (round(starts[seg] + off, 1), text, tag)
            print("[打点] 已按 scene-timing.json 校正台词起点（各幕边界 + 幕内偏移）")
        except Exception as exc:
            print(f"[打点] 校正失败，使用计划起点：{exc}")

    tmp = OUT / "dub-tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    print(f"共 {len(LINES)} 段台词，音色 {VOICE}，语速 {args.rate or '默认'}")

    # 1. 逐段生成配音（失败重试 2 次）
    schedule = []   # (实际起点, 时长, 文本, 条目)
    cursor = 0.0
    for i, (planned, text, tag) in enumerate(LINES):
        mp3 = tmp / f"l{i:02d}.mp3"
        if not synth_with_retry(text, mp3, args.rate):
            print(f"[错误] 第 {i} 段配音生成失败（已重试）: {text[:20]}...", file=sys.stderr)
            return 1
        dur = probe_duration(mp3)
        start = max(planned, cursor + 0.3)   # 防重叠：不早于上一段结束 + 0.3s
        schedule.append((start, dur, text, tag))
        cursor = start + dur
        print(f"[配音] {fmt_srt(start)} ~ {fmt_srt(cursor)}（{dur:.1f}s）{tag}: {text[:24]}…")

    # 2. SRT + 台词表
    srt_path = OUT / "demo-v08r5-subtitles.srt"
    srt = ""
    lines_txt = "DormMate 演示视频配音台词表（实际时间轴）\n\n"
    for i, (start, dur, text, tag) in enumerate(schedule, 1):
        srt += f"{i}\n{fmt_srt(start)} --> {fmt_srt(start + dur)}\n{text}\n\n"
        lines_txt += f"[{fmt_srt(start)} → {fmt_srt(start + dur)}] {tag}\n{text}\n\n"
    srt_path.write_text(srt, encoding="utf-8")
    (OUT / "dub-lines.txt").write_text(lines_txt, encoding="utf-8")
    print(f"[字幕] {srt_path}")

    # 3. 视频 + 结尾 8s 黑屏 + 烧录字幕（无音频中间件）
    srt_esc = srt_path.as_posix().replace(":", "\\:")
    mid = tmp / "video-sub.mp4"
    ok = run_ffmpeg(
        ["-i", str(SRC), "-f", "lavfi", "-i", "color=c=black:s=1600x900:d=8:r=25",
         "-filter_complex",
         f"[0:v][1:v]concat=n=2:v=1:a=0[v];[v]subtitles='{srt_esc}':"
         "force_style='FontName=Microsoft YaHei,FontSize=24,PrimaryColour=&H00FFFFFF,"
         "OutlineColour=&H00101010,BorderStyle=1,Outline=1,Shadow=0,MarginV=28,Alignment=2'[vsub]",
         "-map", "[vsub]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-an",
         str(mid)], "视频拼接 + 字幕烧录")
    if not ok:
        return 1

    # 4. 配音混入（各段 adelay 精确放置 → amix）
    inputs = []
    for p in (tmp / f"l{i:02d}.mp3" for i in range(len(schedule))):
        inputs += ["-i", str(p)]
    chains = []
    labels = []
    for i, (start, dur, _, _) in enumerate(schedule):
        ms = int(round(start * 1000))
        chains.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")   # mp3 是输入 0..N-1，视频是最后一个输入
        labels.append(f"[a{i}]")
    filter_complex = ";".join(chains) + ";" + "".join(labels) + \
                     f"amix=inputs={len(schedule)}:normalize=0[aout]"
    final = OUT / "demo-v08r5-final.mp4"
    video_idx = len(schedule)   # 视频输入排在全部 mp3 之后
    ok = run_ffmpeg(
        inputs + ["-i", str(mid), "-filter_complex", filter_complex,
                  "-map", f"{video_idx}:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                  "-movflags", "+faststart", str(final)],
        "配音混入")
    if not ok:
        return 1

    print(f"[成品] {final}（{final.stat().st_size // 1024} KB，时长 {probe_duration(final):.1f}s）")
    print("[完成] 请试听 demo-v08r5-final.mp4；如需调语速，用 --rate 参数重跑")
    return 0


if __name__ == "__main__":
    sys.exit(main())
