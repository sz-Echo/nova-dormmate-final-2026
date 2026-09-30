"""DormMate 演示视频配音 + 硬字幕（simulator/add_dub.py）

输入：docs/demo/demo-full.webm（record_demo.py 产物，2:09 纯画面无声音）
输出：
  docs/demo/demo-subtitles.srt —— 软字幕（供剪映等二次编辑）
  docs/demo/dub-lines.txt     —— 配音台词表（实际时间点 / 台词 / 任务书条目，供校对）
  docs/demo/demo-final.mp4    —— 成品：H.264 + AAC 配音 + 硬字幕 + 结尾 8s 黑屏收尾台词

配音：edge-tts（zh-CN-XiaoxiaoNeural 女声），每段独立生成、失败重试 2 次（服务依赖网络）。
时间轴防重叠：实际起点 = max(计划起点, 上一段结束 + 0.3s)，保证台词不叠音、不压过镜头切换。
字幕烧录用 libass + Microsoft YaHei（本机已验证可用），白字黑边底部居中。

用法：python simulator/add_dub.py [--rate -4%] [--voice zh-CN-XiaoxiaoNeural]
"""
import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "demo"
SRC = OUT / "demo-full.webm"
VOICE = "zh-CN-XiaoxiaoNeural"
VIDEO_END = 129.4   # demo-full.webm 时长（s），之后是 8s 黑屏收尾

# (计划起点秒, 台词, 对应任务书条目)；标题卡时段（0-3 / 47-50 / 78-81）不配音
LINES = [
    (4.0, "三个宿舍实时上报温湿度，看板和 3D 场景显示同一份数据，当前全部正常。", "A 开场"),
    (8.6, "dorm-b 连续偏热，横幅自动标出优先关注与原因。", "A1 优先关注"),
    (14.2, "点开启风扇，动作经 MQTT 发给系统：看板进入处理中，3D 风扇转动、窗户打开。", "A2 处理动作"),
    (24.2, "恢复必须由新数据触发：降温中仍偏热，保持处理中；连续两条正常数据后判定已恢复，并自动关扇。", "A3 恢复判断"),
    (37.7, "完整事件自动记录：异常、原因、动作、恢复时间齐全，导出后进入报告的事件复盘区。", "A4 事件复盘"),
    (51.0, "总览条按真实状态自动成句，dorm-c 变偏湿后立即更新；依据卡片逐项标注数据来源。", "B1+B2 总览与依据"),
    (62.0, "朗读提醒，用语音读出当前总览。", "B4 合适表达"),
    (66.2, "今日摘要由程序读取当天数据生成：谁出了问题、做了什么、结果如何，换数据重跑即重新生成。", "B3 今日摘要"),
    (81.5, "报告里规则与模型并排对照：规则判正常，模型发现与历史明显不同。", "C3 结果接回"),
    (88.5, "右侧是模型脚本的真实输出：历史数据训练隔离森林，对照表发现三组规则正常、模型判不同的数据。", "C2 规则/ML 对照"),
    (100.0, "历史与待判断新数据严格分离，固定随机种子，重跑结果完全一致。", "C1 数据准备"),
    (108.0, "最后保留一个不理想案例：27.5 度、70% 被模型标为明显不同，原因是历史数据太少、区间太窄。模型只是辅助，与固定规则并列。", "C4 不理想案例"),
    (VIDEO_END + 0.5, "以上就是 DormMate 的三组闭环演示，感谢观看。", "收尾"),
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
    global VOICE
    parser = argparse.ArgumentParser(description="DormMate 演示视频配音 + 硬字幕")
    parser.add_argument("--rate", default="", help="edge-tts 语速（如 -4%%），默认原速")
    parser.add_argument("--voice", default=VOICE, help="edge-tts 音色")
    args = parser.parse_args()
    VOICE = args.voice

    if not SRC.exists():
        print(f"[错误] 未找到 {SRC}，请先运行 python simulator/record_demo.py", file=sys.stderr)
        return 1

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
    srt_path = OUT / "demo-subtitles.srt"
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
    final = OUT / "demo-final.mp4"
    video_idx = len(schedule)   # 视频输入排在全部 mp3 之后
    ok = run_ffmpeg(
        inputs + ["-i", str(mid), "-filter_complex", filter_complex,
                  "-map", f"{video_idx}:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                  "-movflags", "+faststart", str(final)],
        "配音混入")
    if not ok:
        return 1

    print(f"[成品] {final}（{final.stat().st_size // 1024} KB，时长 {probe_duration(final):.1f}s）")
    print("[完成] 请试听 demo-final.mp4；如需调语速，用 --rate 参数重跑")
    return 0


if __name__ == "__main__":
    sys.exit(main())
