"""
字幕生成模块
使用 faster-whisper 对配音音频进行转写，输出 SRT 字幕文件

依赖: faster-whisper>=1.0.3
"""

import os
import re
from pathlib import Path


def format_timestamp(seconds: float) -> str:
    """将秒数转为 SRT 时间戳格式 HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def transcribe_audio(
    audio_path: str,
    model_size: str = "small",
    language: str = "zh",
    device: str = "auto",
) -> list[dict]:
    """
    转写音频文件，返回带时间戳的片段列表。

    Args:
        audio_path:  音频文件路径 (.mp3 / .wav)
        model_size:  Whisper 模型大小 (tiny/base/small/medium/large-v3)
        language:    语言代码，中文用 "zh"
        device:      推理设备 ("auto" / "cpu" / "cuda")

    Returns:
        List of {"start": float, "end": float, "text": str}
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "请安装 faster-whisper: pip install faster-whisper"
        )

    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    compute_type = "float16" if device == "cuda" else "int8"
    print(f"[字幕] 加载模型 {model_size} ({device}/{compute_type})...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    print(f"[字幕] 转写: {audio_path}")
    segments, info = model.transcribe(
        audio_path,
        language=language,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )

    print(f"[字幕] 检测语言: {info.language} (置信度: {info.language_probability:.2f})")

    results = []
    for seg in segments:
        results.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        })
    return results


def segments_to_srt(segments: list[dict]) -> str:
    """将片段列表转为 SRT 格式字符串"""
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def generate_subtitle(
    audio_path: str,
    output_path: str = None,
    model_size: str = "small",
    language: str = "zh",
    device: str = "auto",
) -> str:
    """
    为音频文件生成 SRT 字幕。

    Args:
        audio_path:   音频文件路径
        output_path:  输出 SRT 文件路径（默认与音频同名）
        model_size:   Whisper 模型大小
        language:     语言
        device:       推理设备

    Returns:
        生成的 SRT 文件路径
    """
    if output_path is None:
        output_path = str(Path(audio_path).with_suffix(".srt"))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    segments = transcribe_audio(audio_path, model_size, language, device)
    srt_content = segments_to_srt(segments)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    print(f"[字幕] 已生成 {len(segments)} 条字幕 → {output_path}")
    return output_path


def batch_generate_subtitles(
    audio_dir: str,
    output_dir: str = None,
    model_size: str = "small",
    language: str = "zh",
    device: str = "auto",
    pattern: str = "*.mp3",
):
    """
    批量为目录下所有音频文件生成字幕。

    Args:
        audio_dir:   音频文件目录
        output_dir:  字幕输出目录（默认与 audio_dir 相同）
        model_size:  Whisper 模型大小
        language:    语言
        device:      推理设备
        pattern:     文件匹配模式
    """
    audio_files = sorted(Path(audio_dir).glob(pattern))
    if not audio_files:
        print(f"[字幕] 未找到音频文件: {audio_dir}/{pattern}")
        return

    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    for audio_path in audio_files:
        if output_dir:
            srt_path = os.path.join(output_dir, audio_path.stem + ".srt")
        else:
            srt_path = None  # 与音频同目录

        if srt_path and os.path.exists(srt_path):
            print(f"[跳过] 字幕已存在: {srt_path}")
            continue

        try:
            generate_subtitle(
                str(audio_path),
                output_path=srt_path,
                model_size=model_size,
                language=language,
                device=device,
            )
        except Exception as e:
            print(f"[错误] {audio_path.name}: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="faster-whisper 字幕生成")
    subparsers = parser.add_subparsers(dest="command")

    # 单文件模式
    single = subparsers.add_parser("single", help="为单个音频生成字幕")
    single.add_argument("audio", help="音频文件路径")
    single.add_argument("-o", "--output", help="输出 SRT 路径")
    single.add_argument("--model", default="small", help="Whisper 模型大小")
    single.add_argument("--lang", default="zh", help="语言代码")
    single.add_argument("--device", default="auto", help="推理设备")

    # 批量模式
    batch = subparsers.add_parser("batch", help="批量生成字幕")
    batch.add_argument("audio_dir", help="音频目录")
    batch.add_argument("-o", "--output-dir", help="字幕输出目录")
    batch.add_argument("--model", default="small", help="Whisper 模型大小")
    batch.add_argument("--lang", default="zh", help="语言代码")
    batch.add_argument("--device", default="auto", help="推理设备")
    batch.add_argument("--pattern", default="*.mp3", help="文件匹配模式")

    args = parser.parse_args()

    if args.command == "single":
        generate_subtitle(args.audio, args.output, args.model, args.lang, args.device)
    elif args.command == "batch":
        batch_generate_subtitles(
            args.audio_dir, args.output_dir, args.model, args.lang, args.device, args.pattern
        )
    else:
        parser.print_help()
