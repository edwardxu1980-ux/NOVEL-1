"""
科幻小说分集视频制作流水线
Novel → Episodes → Scripts → TTS → Video → Subtitles → Final

依赖: anthropic, edge-tts, moviepy, faster-whisper
可选: SILICONFLOW_API_KEY 环境变量 (用于自动视频生成)
"""

import os
import json
import asyncio
import anthropic

# ─────────────────────────────────────────────
# 1. 读取小说文本
# ─────────────────────────────────────────────

def load_novel(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


# ─────────────────────────────────────────────
# 2. 用 Claude 拆分分集剧本
# ─────────────────────────────────────────────

SPLIT_SYSTEM_PROMPT = """你是一名资深科幻影视编剧。
你的任务是将用户提供的科幻小说原文拆分为分集视频脚本。

输出格式为 JSON 数组，每个元素代表一集：
[
  {
    "episode": 1,
    "title": "集名",
    "summary": "本集剧情概要（100字以内）",
    "scenes": [
      {
        "scene_id": 1,
        "description": "场景视觉描述（英文，用于AI生图/生视频）",
        "narration": "旁白/台词（中文）",
        "duration_sec": 10
      }
    ]
  }
]

要求：
- 每集 8~12 个场景
- scene description 使用英文，适合 Stable Diffusion / Wan2.2 的 prompt 格式
- 科幻氛围突出，包含宇宙、飞船、外星、未来城市等元素
"""

def split_into_episodes(novel_text: str, num_episodes: int = 6) -> list[dict]:
    client = anthropic.Anthropic()

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8096,
        system=SPLIT_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"请将以下科幻小说拆分为 {num_episodes} 集视频脚本：\n\n{novel_text[:30000]}"
            }
        ]
    )

    raw = message.content[0].text
    # 提取 JSON
    start = raw.find("[")
    end = raw.rfind("]") + 1
    return json.loads(raw[start:end])


# ─────────────────────────────────────────────
# 3. 生成配音文本文件
# ─────────────────────────────────────────────

def export_narration_scripts(episodes: list[dict], output_dir: str = "output/scripts"):
    os.makedirs(output_dir, exist_ok=True)
    for ep in episodes:
        ep_num = ep["episode"]
        lines = []
        for scene in ep.get("scenes", []):
            lines.append(scene["narration"])
        script_path = os.path.join(output_dir, f"ep{ep_num:02d}_narration.txt")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(lines))
        print(f"[剧本] 第{ep_num}集旁白已保存: {script_path}")


# ─────────────────────────────────────────────
# 4. 生成视频 Prompt 文件 (供 Wan2.2 / Open-Sora 使用)
# ─────────────────────────────────────────────

def export_video_prompts(episodes: list[dict], output_dir: str = "output/prompts"):
    os.makedirs(output_dir, exist_ok=True)
    for ep in episodes:
        ep_num = ep["episode"]
        prompts = []
        for scene in ep.get("scenes", []):
            prompts.append({
                "scene_id": scene["scene_id"],
                "prompt": scene["description"],
                "duration": scene.get("duration_sec", 10)
            })
        prompt_path = os.path.join(output_dir, f"ep{ep_num:02d}_prompts.json")
        with open(prompt_path, "w", encoding="utf-8") as f:
            json.dump(prompts, f, ensure_ascii=False, indent=2)
        print(f"[提示词] 第{ep_num}集视频提示词已保存: {prompt_path}")


# ─────────────────────────────────────────────
# 5. 生成 edge-tts 配音命令脚本
# ─────────────────────────────────────────────

TTS_VOICE = "zh-CN-YunxiNeural"  # 中文男声，可换: zh-CN-XiaoxiaoNeural(女声)

def export_tts_commands(episodes: list[dict], output_dir: str = "output/tts"):
    os.makedirs(output_dir, exist_ok=True)
    commands = []
    for ep in episodes:
        ep_num = ep["episode"]
        narration_file = f"output/scripts/ep{ep_num:02d}_narration.txt"
        audio_output = os.path.join(output_dir, f"ep{ep_num:02d}_voice.mp3")
        cmd = f'edge-tts --voice {TTS_VOICE} --file "{narration_file}" --write-media "{audio_output}"'
        commands.append(cmd)

    cmd_script = "output/run_tts.sh"
    with open(cmd_script, "w") as f:
        f.write("#!/bin/bash\n")
        f.write("# 运行此脚本生成所有集数的配音\n\n")
        f.write("\n".join(commands))
    os.chmod(cmd_script, 0o755)
    print(f"[配音] TTS 命令脚本已生成: {cmd_script}")


# ─────────────────────────────────────────────
# 6. 生成 FFmpeg 合成命令 (视频+音频+字幕)
# ─────────────────────────────────────────────

def export_ffmpeg_commands(episodes: list[dict], output_dir: str = "output"):
    commands = []
    for ep in episodes:
        ep_num = ep["episode"]
        # 假设视频片段已由 Wan2.2 等工具生成到 output/video/ep01/
        video_concat = f"output/video/ep{ep_num:02d}/concat.mp4"
        audio = f"output/tts/ep{ep_num:02d}_voice.mp3"
        subtitle = f"output/subtitles/ep{ep_num:02d}.srt"
        final = f"{output_dir}/final/ep{ep_num:02d}_final.mp4"
        cmd = (
            f'ffmpeg -i "{video_concat}" -i "{audio}" '
            f'-vf "subtitles={subtitle}" '
            f'-c:v libx264 -c:a aac -shortest "{final}"'
        )
        commands.append(cmd)

    os.makedirs(f"{output_dir}/final", exist_ok=True)
    cmd_script = f"{output_dir}/run_ffmpeg.sh"
    with open(cmd_script, "w") as f:
        f.write("#!/bin/bash\n")
        f.write("# 运行此脚本合成所有集数的最终视频\n\n")
        f.write("\n".join(commands))
    os.chmod(cmd_script, 0o755)
    print(f"[合成] FFmpeg 合成命令已生成: {cmd_script}")


# ─────────────────────────────────────────────
# 7. edge-tts 直接配音（异步）
# ─────────────────────────────────────────────

async def run_tts_for_episode(ep_num: int, narration_file: str, audio_output: str):
    """使用 edge-tts 直接生成单集配音"""
    try:
        import edge_tts
    except ImportError:
        raise ImportError("请安装 edge-tts: pip install edge-tts")

    os.makedirs(os.path.dirname(audio_output), exist_ok=True)
    with open(narration_file, "r", encoding="utf-8") as f:
        text = f.read().strip()

    communicate = edge_tts.Communicate(text, TTS_VOICE)
    await communicate.save(audio_output)
    print(f"[配音] 第{ep_num}集配音已生成: {audio_output}")


async def run_tts_all(episodes: list[dict]):
    """并发生成所有集数配音"""
    tasks = []
    for ep in episodes:
        ep_num = ep["episode"]
        narration_file = f"output/scripts/ep{ep_num:02d}_narration.txt"
        audio_output = f"output/tts/ep{ep_num:02d}_voice.mp3"
        if os.path.exists(audio_output):
            print(f"[跳过] 第{ep_num}集配音已存在: {audio_output}")
            continue
        tasks.append(run_tts_for_episode(ep_num, narration_file, audio_output))
    if tasks:
        await asyncio.gather(*tasks)


# ─────────────────────────────────────────────
# 8. 字幕生成（调用 subtitle_generator）
# ─────────────────────────────────────────────

def generate_subtitles_for_all(episodes: list[dict], model_size: str = "small"):
    """为所有集数生成字幕"""
    try:
        from subtitle_generator import generate_subtitle
    except ImportError:
        from workflow.subtitle_generator import generate_subtitle

    os.makedirs("output/subtitles", exist_ok=True)
    for ep in episodes:
        ep_num = ep["episode"]
        audio_path = f"output/tts/ep{ep_num:02d}_voice.mp3"
        srt_path = f"output/subtitles/ep{ep_num:02d}.srt"

        if not os.path.exists(audio_path):
            print(f"[跳过] 第{ep_num}集音频不存在，跳过字幕生成")
            continue
        if os.path.exists(srt_path):
            print(f"[跳过] 第{ep_num}集字幕已存在: {srt_path}")
            continue

        generate_subtitle(audio_path, srt_path, model_size=model_size)


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="科幻小说分集视频制作流水线")
    parser.add_argument("novel_file", help="小说文本文件路径 (.txt)")
    parser.add_argument("--episodes", type=int, default=6, help="拆分集数（默认6集）")
    parser.add_argument("--tts", action="store_true", help="自动生成配音 (需要 edge-tts)")
    parser.add_argument("--subtitles", action="store_true", help="自动生成字幕 (需要 faster-whisper)")
    parser.add_argument("--generate-video", action="store_true",
                        help="调用 SiliconFlow API 生成视频 (需要 SILICONFLOW_API_KEY)")
    parser.add_argument("--whisper-model", default="small",
                        help="Whisper 模型大小 (tiny/base/small/medium/large-v3，默认 small)")
    parser.add_argument("--dry-run", action="store_true", help="视频生成仅打印，不实际调用 API")
    args = parser.parse_args()

    print("=" * 50)
    print("科幻小说分集视频制作流水线")
    print("=" * 50)

    # 步骤 1: 读取小说
    print(f"\n[1/7] 读取小说: {args.novel_file}")
    novel_text = load_novel(args.novel_file)
    print(f"      字数: {len(novel_text)}")

    # 步骤 2: 拆分分集
    print(f"\n[2/7] 用 Claude 拆分为 {args.episodes} 集...")
    episodes = split_into_episodes(novel_text, args.episodes)
    with open("output/episodes.json", "w", encoding="utf-8") as f:
        json.dump(episodes, f, ensure_ascii=False, indent=2)
    print(f"      已生成 {len(episodes)} 集脚本 → output/episodes.json")

    # 步骤 3: 导出旁白脚本
    print("\n[3/7] 导出旁白脚本...")
    export_narration_scripts(episodes)

    # 步骤 4: 导出视频提示词
    print("\n[4/7] 导出视频生成提示词...")
    export_video_prompts(episodes)

    # 步骤 5: 生成配音
    print("\n[5/7] 生成配音...")
    if args.tts:
        asyncio.run(run_tts_all(episodes))
    else:
        export_tts_commands(episodes)
        print("      (使用 --tts 参数可自动生成配音，或手动运行 output/run_tts.sh)")

    # 步骤 6: 生成字幕
    print("\n[6/7] 生成字幕...")
    if args.subtitles:
        generate_subtitles_for_all(episodes, model_size=args.whisper_model)
    else:
        print("      (使用 --subtitles 参数可自动生成字幕)")

    # 步骤 7: 视频生成 + FFmpeg 合成命令
    print("\n[7/7] 视频生成与合成...")
    if args.generate_video:
        try:
            from video_generator import generate_episode_videos
        except ImportError:
            from workflow.video_generator import generate_episode_videos

        for ep in episodes:
            ep_num = ep["episode"]
            prompts_file = f"output/prompts/ep{ep_num:02d}_prompts.json"
            output_dir = f"output/video/ep{ep_num:02d}"
            print(f"  生成第{ep_num}集视频...")
            generate_episode_videos(
                prompts_file=prompts_file,
                output_dir=output_dir,
                dry_run=args.dry_run,
            )
    else:
        export_ffmpeg_commands(episodes)
        print("      (使用 --generate-video 参数可通过 SiliconFlow API 自动生成视频)")

    print("\n" + "=" * 50)
    print("流水线完成！输出目录结构：")
    print("  output/")
    print("  ├── episodes.json          # 分集脚本")
    print("  ├── scripts/ep*_narration.txt  # 旁白文本")
    print("  ├── prompts/ep*_prompts.json   # 视频提示词")
    print("  ├── tts/ep*_voice.mp3          # 配音音频")
    print("  ├── subtitles/ep*.srt          # 字幕文件")
    print("  ├── video/ep*/                 # 视频片段")
    print("  └── final/ep*_final.mp4        # 最终成片")
    print("=" * 50)


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    main()
