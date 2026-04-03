"""
CosyVoice 高质量配音模块
支持 CosyVoice2，提供中文科幻旁白级别的 TTS 合成。
当 CosyVoice 不可用时自动降级到 edge-tts。

安装参考: https://github.com/FunAudioLLM/CosyVoice
  git clone https://github.com/FunAudioLLM/CosyVoice --recursive
  pip install -r CosyVoice/requirements.txt
"""

import os
import io
import asyncio
from pathlib import Path


# ─────────────────────────────────────────────
# CosyVoice 后端
# ─────────────────────────────────────────────

class CosyVoiceTTS:
    """CosyVoice2 TTS 封装"""

    BUILTIN_SPEAKERS = [
        "中文女性", "中文男性", "英文女性", "英文男性",
        "中文男性旁白", "中文女性旁白",
    ]

    def __init__(self, model_dir: str = "pretrained_models/CosyVoice2-0.5B"):
        try:
            import sys
            # CosyVoice 需要将其目录加入 sys.path
            cosyvoice_root = os.environ.get("COSYVOICE_ROOT", "")
            if cosyvoice_root and cosyvoice_root not in sys.path:
                sys.path.insert(0, cosyvoice_root)

            from cosyvoice.cli.cosyvoice import CosyVoice2
        except ImportError:
            raise ImportError(
                "CosyVoice 未安装。\n"
                "请参考 https://github.com/FunAudioLLM/CosyVoice 安装，\n"
                "并设置环境变量: export COSYVOICE_ROOT=/path/to/CosyVoice"
            )

        print(f"[CosyVoice] 加载模型: {model_dir}")
        self.model = CosyVoice2(model_dir)
        self.model_dir = model_dir

    def synthesize(
        self,
        text: str,
        speaker: str = "中文男性旁白",
        output_path: str = None,
        speed: float = 1.0,
    ) -> bytes:
        """
        合成语音。

        Args:
            text:        要合成的文本
            speaker:     说话人名称（内置或克隆）
            output_path: 保存路径（可选）
            speed:       语速倍数（0.5~2.0）

        Returns:
            WAV 格式音频的 bytes
        """
        import torchaudio

        output = self.model.inference_sft(text, speaker, speed=speed)
        # output 是生成器，取第一个结果
        result = next(iter(output))
        audio_data = result["tts_speech"]  # torch.Tensor
        sample_rate = self.model.sample_rate

        buf = io.BytesIO()
        torchaudio.save(buf, audio_data, sample_rate, format="wav")
        wav_bytes = buf.getvalue()

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            # 转为 mp3（需要 ffmpeg）
            if output_path.endswith(".mp3"):
                import subprocess
                subprocess.run(
                    ["ffmpeg", "-y", "-i", "pipe:0", output_path],
                    input=wav_bytes,
                    capture_output=True,
                    check=True,
                )
            else:
                with open(output_path, "wb") as f:
                    f.write(wav_bytes)

        return wav_bytes

    def synthesize_long(
        self,
        text: str,
        speaker: str = "中文男性旁白",
        output_path: str = None,
        chunk_size: int = 200,
        speed: float = 1.0,
    ) -> str:
        """
        对长文本分段合成后拼接，适用于集级别旁白（数千字）。

        Args:
            text:        长文本
            speaker:     说话人
            output_path: 输出文件路径（mp3/wav）
            chunk_size:  每段最大字数
            speed:       语速

        Returns:
            输出文件路径
        """
        import subprocess

        # 按标点分段，确保不截断句子
        chunks = _split_text(text, chunk_size)
        print(f"[CosyVoice] 文本分为 {len(chunks)} 段合成...")

        chunk_files = []
        tmp_dir = Path(output_path).parent / "_tmp_chunks" if output_path else Path("_tmp_chunks")
        tmp_dir.mkdir(parents=True, exist_ok=True)

        for i, chunk in enumerate(chunks):
            chunk_path = str(tmp_dir / f"chunk_{i:03d}.wav")
            self.synthesize(chunk, speaker=speaker, output_path=chunk_path, speed=speed)
            chunk_files.append(chunk_path)

        # 用 ffmpeg 拼接
        concat_list = tmp_dir / "concat.txt"
        with open(concat_list, "w") as f:
            for fp in chunk_files:
                f.write(f"file '{os.path.abspath(fp)}'\n")

        final_path = output_path or "output_voice.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(concat_list), final_path],
            capture_output=True,
            check=True,
        )

        # 清理临时文件
        for fp in chunk_files:
            os.remove(fp)
        os.remove(concat_list)
        tmp_dir.rmdir()

        print(f"[CosyVoice] 合成完成: {final_path}")
        return final_path


# ─────────────────────────────────────────────
# edge-tts 降级后端
# ─────────────────────────────────────────────

async def _edge_tts_synthesize(text: str, voice: str, output_path: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


class EdgeTTSFallback:
    """edge-tts 封装，接口与 CosyVoiceTTS 保持兼容"""

    def __init__(self, voice: str = "zh-CN-YunxiNeural"):
        self.voice = voice

    def synthesize_long(self, text: str, speaker: str = None, output_path: str = None, **kwargs) -> str:
        asyncio.run(_edge_tts_synthesize(text, self.voice, output_path))
        print(f"[edge-tts] 合成完成: {output_path}")
        return output_path


# ─────────────────────────────────────────────
# 统一工厂函数
# ─────────────────────────────────────────────

def create_tts(backend: str = "auto", **kwargs):
    """
    创建 TTS 实例。

    Args:
        backend: "cosyvoice" | "edge-tts" | "auto"
                 auto = 优先 cosyvoice，不可用则降级到 edge-tts
        **kwargs: 传递给对应后端的参数
    """
    if backend == "cosyvoice":
        return CosyVoiceTTS(
            model_dir=kwargs.get("cosyvoice_model", "pretrained_models/CosyVoice2-0.5B")
        )
    if backend == "edge-tts":
        return EdgeTTSFallback(voice=kwargs.get("voice", "zh-CN-YunxiNeural"))

    # auto 模式
    try:
        tts = CosyVoiceTTS(
            model_dir=kwargs.get("cosyvoice_model", "pretrained_models/CosyVoice2-0.5B")
        )
        print("[TTS] 使用 CosyVoice 高质量配音")
        return tts
    except ImportError:
        print("[TTS] CosyVoice 未安装，降级到 edge-tts")
        return EdgeTTSFallback(voice=kwargs.get("voice", "zh-CN-YunxiNeural"))


def generate_episode_audio(
    episodes: list[dict],
    scripts_dir: str = "output/scripts",
    audio_dir: str = "output/tts",
    backend: str = "auto",
    **tts_kwargs,
):
    """
    批量为所有集数生成配音音频。

    Args:
        episodes:    分集数据列表
        scripts_dir: 旁白脚本目录
        audio_dir:   音频输出目录
        backend:     TTS 后端
        **tts_kwargs: 传给 create_tts 的额外参数
    """
    tts = create_tts(backend=backend, **tts_kwargs)
    os.makedirs(audio_dir, exist_ok=True)

    speaker = tts_kwargs.get("cosyvoice_speaker", "中文男性旁白")

    for ep in episodes:
        ep_num = ep["episode"]
        script_path = os.path.join(scripts_dir, f"ep{ep_num:02d}_narration.txt")
        audio_path = os.path.join(audio_dir, f"ep{ep_num:02d}_voice.mp3")

        if os.path.exists(audio_path):
            print(f"[TTS] 跳过第{ep_num}集（已存在）")
            continue
        if not os.path.exists(script_path):
            print(f"[TTS] 跳过第{ep_num}集（旁白脚本不存在: {script_path}）")
            continue

        with open(script_path, "r", encoding="utf-8") as f:
            text = f.read().strip()

        print(f"[TTS] 第{ep_num}集合成中...")
        tts.synthesize_long(text, speaker=speaker, output_path=audio_path)


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def _split_text(text: str, max_chars: int = 200) -> list[str]:
    """按标点符号将文本切分为不超过 max_chars 字的片段"""
    import re
    # 中英文句末标点
    sentence_endings = re.compile(r'(?<=[。！？…\.\!\?])\s*')
    sentences = sentence_endings.split(text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) <= max_chars:
            current += sent
        else:
            if current:
                chunks.append(current)
            # 若单句超长，强制截断
            while len(sent) > max_chars:
                chunks.append(sent[:max_chars])
                sent = sent[max_chars:]
            current = sent
    if current:
        chunks.append(current)
    return chunks


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TTS 配音生成")
    parser.add_argument("text_file", help="旁白文本文件路径")
    parser.add_argument("-o", "--output", default="output_voice.mp3", help="输出音频路径")
    parser.add_argument("--backend", default="auto", choices=["auto", "cosyvoice", "edge-tts"])
    parser.add_argument("--speaker", default="中文男性旁白", help="CosyVoice 说话人")
    parser.add_argument("--voice", default="zh-CN-YunxiNeural", help="edge-tts 声音")
    parser.add_argument("--model", default="pretrained_models/CosyVoice2-0.5B", help="CosyVoice 模型路径")
    args = parser.parse_args()

    with open(args.text_file, "r", encoding="utf-8") as f:
        text = f.read()

    tts = create_tts(
        backend=args.backend,
        cosyvoice_model=args.model,
        voice=args.voice,
    )
    tts.synthesize_long(text, speaker=args.speaker, output_path=args.output)
