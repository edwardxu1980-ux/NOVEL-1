"""
科幻小说分集视频制作流水线 — Web UI
基于 Gradio，提供可视化操作界面

依赖: pip install gradio>=4.0
"""

import os
import sys
import json
import asyncio
import threading
from pathlib import Path

# 确保可以 import 同目录下的模块
sys.path.insert(0, str(Path(__file__).parent))

try:
    import gradio as gr
except ImportError:
    raise ImportError("请安装 Gradio: pip install gradio>=4.0")

from config import get_config
from novel_to_episode import (
    load_novel,
    split_into_episodes,
    export_narration_scripts,
    export_video_prompts,
    export_tts_commands,
    export_ffmpeg_commands,
)


# ─────────────────────────────────────────────
# 流水线步骤函数（供 UI 调用）
# ─────────────────────────────────────────────

def _log(msg: str, logs: list[str]) -> str:
    logs.append(msg)
    return "\n".join(logs)


def step_split_novel(novel_file, num_episodes: int, logs: list[str]):
    """步骤1：读取小说并用 Claude 拆分"""
    if novel_file is None:
        return None, "❌ 请先上传小说文件", ""

    cfg = get_config()
    os.makedirs("output", exist_ok=True)

    novel_text = load_novel(novel_file.name)
    msg = _log(f"✅ 读取小说完成，字数：{len(novel_text)}", logs)
    yield None, msg, ""

    msg = _log(f"⏳ 正在用 Claude 拆分为 {num_episodes} 集...", logs)
    yield None, msg, ""

    try:
        episodes = split_into_episodes(novel_text, num_episodes)
    except Exception as e:
        msg = _log(f"❌ 分集失败：{e}", logs)
        yield None, msg, ""
        return

    with open("output/episodes.json", "w", encoding="utf-8") as f:
        json.dump(episodes, f, ensure_ascii=False, indent=2)

    export_narration_scripts(episodes)
    export_video_prompts(episodes)

    msg = _log(f"✅ 已生成 {len(episodes)} 集脚本", logs)
    summary = _build_episode_summary(episodes)
    yield "output/episodes.json", msg, summary


def _build_episode_summary(episodes: list[dict]) -> str:
    lines = []
    for ep in episodes:
        lines.append(f"**第{ep['episode']}集：{ep.get('title', '')}**")
        lines.append(ep.get("summary", ""))
        scenes = ep.get("scenes", [])
        lines.append(f"共 {len(scenes)} 个场景")
        lines.append("")
    return "\n".join(lines)


def step_extract_characters(novel_file, logs: list[str]):
    """步骤2：提取角色信息"""
    if novel_file is None:
        return "❌ 请先上传小说文件", ""

    from character_tracker import extract_and_save

    msg = _log("⏳ 正在提取角色信息...", logs)
    yield msg, ""

    try:
        novel_text = load_novel(novel_file.name)
        registry = extract_and_save(novel_text, "output/characters.json")
    except Exception as e:
        msg = _log(f"❌ 角色提取失败：{e}", logs)
        yield msg, ""
        return

    msg = _log("✅ 角色提取完成", logs)
    yield msg, registry.summary()


def step_enrich_prompts(logs: list[str]):
    """步骤3：将角色外貌注入视频提示词"""
    if not os.path.exists("output/episodes.json"):
        return _log("❌ 请先完成分集步骤", logs)
    if not os.path.exists("output/characters.json"):
        return _log("❌ 请先完成角色提取步骤", logs)

    from character_tracker import CharacterRegistry

    registry = CharacterRegistry.load("output/characters.json")
    with open("output/episodes.json", "r", encoding="utf-8") as f:
        episodes = json.load(f)

    enriched = registry.enrich_episodes(episodes)
    export_video_prompts(enriched, output_dir="output/prompts")

    with open("output/episodes_enriched.json", "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    return _log("✅ 已将角色外貌注入视频提示词 → output/prompts/", logs)


def step_tts(tts_backend: str, voice: str, cosyvoice_speaker: str, logs: list[str]):
    """步骤4：配音合成"""
    if not os.path.exists("output/episodes.json"):
        return _log("❌ 请先完成分集步骤", logs)

    with open("output/episodes.json", "r", encoding="utf-8") as f:
        episodes = json.load(f)

    msg = _log(f"⏳ 使用 {tts_backend} 生成配音...", logs)

    try:
        from cosyvoice_tts import generate_episode_audio
        generate_episode_audio(
            episodes,
            backend=tts_backend,
            voice=voice,
            cosyvoice_speaker=cosyvoice_speaker,
        )
        msg = _log("✅ 配音生成完成 → output/tts/", logs)
    except Exception as e:
        msg = _log(f"❌ 配音失败：{e}", logs)

    return msg


def step_generate_video(dry_run: bool, logs: list[str]):
    """步骤5：调用 SiliconFlow 生成视频"""
    if not os.path.exists("output/prompts"):
        return _log("❌ 请先完成提示词步骤", logs)

    from video_generator import generate_episode_videos

    prompt_files = sorted(Path("output/prompts").glob("ep*_prompts.json"))
    if not prompt_files:
        return _log("❌ 未找到提示词文件", logs)

    msg = _log(f"⏳ 开始生成视频（{'DRY RUN' if dry_run else '实际调用 API'}）...", logs)

    for pf in prompt_files:
        ep_num = pf.stem.replace("_prompts", "")
        output_dir = f"output/video/{ep_num}"
        try:
            generate_episode_videos(str(pf), output_dir, dry_run=dry_run)
            msg = _log(f"✅ {ep_num} 视频生成完成", logs)
        except Exception as e:
            msg = _log(f"❌ {ep_num} 生成失败：{e}", logs)

    return msg


def step_subtitles(whisper_model: str, logs: list[str]):
    """步骤6：生成字幕"""
    audio_files = sorted(Path("output/tts").glob("ep*_voice.mp3")) if Path("output/tts").exists() else []
    if not audio_files:
        return _log("❌ 请先完成配音步骤", logs)

    from subtitle_generator import generate_subtitle

    msg = _log(f"⏳ 使用 {whisper_model} 模型生成字幕...", logs)
    os.makedirs("output/subtitles", exist_ok=True)

    for af in audio_files:
        srt_path = f"output/subtitles/{af.stem.replace('_voice', '')}.srt"
        if os.path.exists(srt_path):
            msg = _log(f"  跳过 {af.name}（字幕已存在）", logs)
            continue
        try:
            generate_subtitle(str(af), srt_path, model_size=whisper_model)
            msg = _log(f"  ✅ {af.name} → {srt_path}", logs)
        except Exception as e:
            msg = _log(f"  ❌ {af.name}: {e}", logs)

    return msg


# ─────────────────────────────────────────────
# Gradio UI 构建
# ─────────────────────────────────────────────

def build_ui() -> gr.Blocks:
    cfg = get_config()

    with gr.Blocks(
        title="科幻小说分集视频制作流水线",
        theme=gr.themes.Soft(),
        css=".log-box { font-family: monospace; font-size: 12px; }",
    ) as demo:

        gr.Markdown("# 科幻小说分集视频制作流水线\n自动将科幻小说拆分为分集视频剧本，生成配音、字幕和视频。")

        logs_state = gr.State([])

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 第一步：上传小说")
                novel_file = gr.File(label="上传小说文件 (.txt)", file_types=[".txt"])
                num_episodes = gr.Slider(2, 20, value=cfg.get("output", "episodes") or 6,
                                         step=1, label="拆分集数")
                btn_split = gr.Button("▶ 拆分分集", variant="primary")

                gr.Markdown("## 第二步：角色提取")
                btn_extract = gr.Button("▶ 提取角色信息")
                btn_enrich = gr.Button("▶ 注入角色外貌到提示词")

            with gr.Column(scale=1):
                gr.Markdown("## 第三步：配音")
                tts_backend = gr.Radio(
                    ["auto", "cosyvoice", "edge-tts"],
                    value=cfg.get("tts", "backend") or "auto",
                    label="TTS 后端",
                )
                tts_voice = gr.Textbox(
                    value=cfg.get("tts", "voice") or "zh-CN-YunxiNeural",
                    label="edge-tts 声音",
                )
                cosyvoice_speaker = gr.Textbox(
                    value=cfg.get("tts", "cosyvoice_speaker") or "中文男性旁白",
                    label="CosyVoice 说话人",
                )
                btn_tts = gr.Button("▶ 生成配音")

                gr.Markdown("## 第四步：字幕")
                whisper_model = gr.Dropdown(
                    ["tiny", "base", "small", "medium", "large-v3"],
                    value=cfg.get("whisper", "model_size") or "small",
                    label="Whisper 模型",
                )
                btn_subtitles = gr.Button("▶ 生成字幕")

        with gr.Row():
            with gr.Column():
                gr.Markdown("## 第五步：视频生成")
                dry_run = gr.Checkbox(label="Dry Run（仅打印任务，不消耗 API）", value=True)
                btn_video = gr.Button("▶ 生成视频 (SiliconFlow)", variant="secondary")

        with gr.Row():
            with gr.Column(scale=2):
                log_output = gr.Textbox(
                    label="运行日志",
                    lines=12,
                    max_lines=20,
                    interactive=False,
                    elem_classes=["log-box"],
                )
            with gr.Column(scale=1):
                episode_summary = gr.Markdown(label="分集摘要")

        # 角色摘要
        character_summary = gr.Textbox(label="角色信息", lines=8, interactive=False)

        # 文件下载
        with gr.Row():
            episodes_file = gr.File(label="下载分集脚本 (episodes.json)", interactive=False)

        # ── 事件绑定 ──
        btn_split.click(
            fn=step_split_novel,
            inputs=[novel_file, num_episodes, logs_state],
            outputs=[episodes_file, log_output, episode_summary],
        )

        btn_extract.click(
            fn=step_extract_characters,
            inputs=[novel_file, logs_state],
            outputs=[log_output, character_summary],
        )

        btn_enrich.click(
            fn=step_enrich_prompts,
            inputs=[logs_state],
            outputs=[log_output],
        )

        btn_tts.click(
            fn=step_tts,
            inputs=[tts_backend, tts_voice, cosyvoice_speaker, logs_state],
            outputs=[log_output],
        )

        btn_subtitles.click(
            fn=step_subtitles,
            inputs=[whisper_model, logs_state],
            outputs=[log_output],
        )

        btn_video.click(
            fn=step_generate_video,
            inputs=[dry_run, logs_state],
            outputs=[log_output],
        )

    return demo


def launch(config_path: str = None):
    """启动 Web UI"""
    cfg = get_config(config_path)
    demo = build_ui()
    demo.launch(
        server_name=cfg.get("ui", "host") or "0.0.0.0",
        server_port=cfg.get("ui", "port") or 7860,
        share=cfg.get("ui", "share") or False,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="科幻小说视频流水线 Web UI")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--port", type=int, default=None, help="端口号（覆盖 config.yaml）")
    parser.add_argument("--share", action="store_true", help="生成公网分享链接")
    args = parser.parse_args()

    cfg = get_config(args.config)
    demo = build_ui()
    demo.launch(
        server_name=cfg.get("ui", "host") or "0.0.0.0",
        server_port=args.port or cfg.get("ui", "port") or 7860,
        share=args.share or cfg.get("ui", "share") or False,
    )
