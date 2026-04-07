#!/usr/bin/env python3
"""
角色形象图片生成器
基于角色画像文档，调用 SiliconFlow 图片生成 API 生成高质量人物形象图

用法:
    python generate_character_portrait.py --character 叶枫 --api-key YOUR_KEY
    python generate_character_portrait.py --character 叶枫 --variant all --api-key YOUR_KEY
    python generate_character_portrait.py --list-variants 叶枫
"""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

# ─── 角色提示词库 ────────────────────────────────────────────────────────────

CHARACTER_PROMPTS = {
    "叶枫": {
        "description": "《外交官》男主角，中国年轻男性，22-25岁，第二元意识觉醒者",
        "base_positive": (
            "Chinese young man, approximately 23 years old, "
            "defined strong facial features with sharp bone structure, "
            "very short straight jet-black hair with no styling, "
            "thick straight black eyebrows, "
            "calm steady dark eyes with a hint of weariness beyond his years, "
            "medium warm skin tone, "
            "lean but sturdy athletic build, upright confident posture, "
            "slight air of world-weariness and quiet resolve on face, "
            "realistic portrait, photorealistic, 8k uhd, "
            "cinematic lighting, detailed face, subsurface scattering"
        ),
        "base_negative": (
            "anime, cartoon, illustration, painting, sketch, "
            "blurry, low quality, deformed, ugly, bad anatomy, "
            "extra limbs, missing fingers, watermark, signature, "
            "childish, feminine, long hair, curly hair, dyed hair, "
            "jewelry, earrings, makeup, western features"
        ),
        "variants": {
            "标准半身像": {
                "positive_suffix": (
                    "half body portrait, dark steel-blue military academy uniform with simple collar, "
                    "neutral composed expression, slight shadows under eyes showing past hardship, "
                    "soft cinematic side lighting, bokeh background of sci-fi corridor"
                ),
                "size": "768x1024",
                "filename": "叶枫_标准半身像",
            },
            "正脸特写": {
                "positive_suffix": (
                    "close-up face portrait, looking directly at camera, "
                    "expression calm and unreadable, eyes like still water hiding depth, "
                    "dramatic Rembrandt lighting, dark background, "
                    "shows slight battle scar or fatigue on face, strong jawline"
                ),
                "size": "768x1024",
                "filename": "叶枫_正脸特写",
            },
            "狙击手姿态": {
                "positive_suffix": (
                    "three-quarter body shot, holding a sleek white bolt-action sniper rifle (Byakuya), "
                    "left arm braced on bent knee in shooting stance, "
                    "dark steel-blue military uniform, "
                    "expression absolutely calm and focused, eyes locked on distant target, "
                    "dramatic sci-fi battlefield backdrop, dynamic lighting from below"
                ),
                "size": "1024x768",
                "filename": "叶枫_狙击手姿态",
            },
            "外交官学院制服站姿": {
                "positive_suffix": (
                    "full body standing shot, dark steel-blue military academy uniform, "
                    "standing at ease, arms slightly relaxed at sides, "
                    "calm dignified expression, slight tired look in eyes, "
                    "sci-fi academy plaza background with modernist sculpture, "
                    "natural daylight, cinematic composition"
                ),
                "size": "768x1024",
                "filename": "叶枫_学院制服站姿",
            },
            "情感时刻": {
                "positive_suffix": (
                    "medium close-up, soft warm indoor lighting, "
                    "expression showing rare gentle warmth, slight softening of eyes, "
                    "almost imperceptible upward curve of lips, "
                    "hand reaching out slightly toward camera, "
                    "sci-fi dormitory corridor bokeh background, golden hour light"
                ),
                "size": "768x1024",
                "filename": "叶枫_情感时刻",
            },
        },
    },
    "路佳": {
        "description": "《外交官》女主角，中国年轻女性，约22岁，火鸟班班长",
        "base_positive": (
            "Chinese young woman, approximately 22 years old, "
            "refined delicate face with elegant crescent-shaped jaw profile, "
            "beautiful clear expressive eyes full of quiet determination, "
            "soft short straight black hair with gentle wispy bangs lightly framing forehead, "
            "slender figure with upright military posture, "
            "clean fair skin, subtle natural beauty, "
            "realistic portrait, photorealistic, 8k uhd, "
            "cinematic lighting, detailed face, subsurface scattering"
        ),
        "base_negative": (
            "anime, cartoon, illustration, painting, sketch, "
            "blurry, low quality, deformed, ugly, bad anatomy, "
            "extra limbs, missing fingers, watermark, signature, "
            "heavy makeup, dramatic eyeshadow, long hair, curly hair, "
            "revealing clothing, ponytail"
        ),
        "variants": {
            "标准半身像": {
                "positive_suffix": (
                    "half body portrait, deep crimson dark red military academy uniform with clean lines, "
                    "calm composed expression with subtle warmth in eyes, "
                    "soft diffused cinematic lighting, "
                    "sci-fi academy interior background, bokeh"
                ),
                "size": "768x1024",
                "filename": "路佳_标准半身像",
            },
            "班长指挥": {
                "positive_suffix": (
                    "medium shot, deep crimson military uniform, "
                    "serious focused expression giving orders, "
                    "fine bangs swaying slightly in breeze, "
                    "forested training ground background, natural light, "
                    "confident commanding posture, slight tension in brow"
                ),
                "size": "1024x768",
                "filename": "路佳_班长指挥",
            },
            "情感破防": {
                "positive_suffix": (
                    "close-up portrait, deep crimson uniform, "
                    "face slowly lifting upward, "
                    "slightly reddened eye rims with tears barely contained, "
                    "icily controlled expression masking deep emotion, "
                    "dramatic backlight from sci-fi hangar at dusk, "
                    "one single tear caught in light"
                ),
                "size": "768x1024",
                "filename": "路佳_情感破防",
            },
        },
    },
    "左胧月": {
        "description": "《外交官》第三主角，卡达米亚人，大元首之女，三色外形",
        "base_positive": (
            "Young woman of otherworldly beauty, "
            "STRICT three-color monochrome appearance: "
            "long straight jet-black hair, deep void-black eyes, "
            "snow-white porcelain skin, vivid crimson scarlet lips, "
            "three thin vertical black marks on forehead (觉醒者印记), "
            "tall elegant aristocratic bearing, "
            "otherworldly alien-human hybrid appearance, cold distant expression, "
            "realistic portrait, photorealistic, 8k uhd, "
            "cinematic lighting, detailed face, subsurface scattering"
        ),
        "base_negative": (
            "anime, cartoon, illustration, painting, sketch, "
            "blurry, low quality, deformed, ugly, bad anatomy, "
            "extra limbs, missing fingers, watermark, signature, "
            "warm skin tone, brown eyes, colored hair, pink lips, "
            "smiling, friendly expression, casual clothing"
        ),
        "variants": {
            "标准半身像": {
                "positive_suffix": (
                    "half body portrait, black military uniform with silver trim, "
                    "long black hair falling over one shoulder, "
                    "icy distant expression, eyes like deep voids, "
                    "dramatic high-contrast lighting emphasizing black-white-red palette, "
                    "dark sci-fi academy background"
                ),
                "size": "768x1024",
                "filename": "左胧月_标准半身像",
            },
            "窗边俯视": {
                "positive_suffix": (
                    "standing by window looking downward, black silver-trim uniform, "
                    "long black hair, calculating cold gaze directed downward, "
                    "arms lightly crossed, "
                    "sci-fi academy architecture seen through window, cool blue ambient light, "
                    "three forehead marks visible"
                ),
                "size": "768x1024",
                "filename": "左胧月_窗边俯视",
            },
            "印记显现": {
                "positive_suffix": (
                    "extreme close-up face portrait, "
                    "snow-white skin, crimson lips slightly parted, "
                    "right hand knuckle slowly wiping makeup from forehead "
                    "to reveal three thin vertical black ritual marks, "
                    "moonlit garden bokeh background, silver light, "
                    "quiet solemn moment, alien flower (white petals, crimson inner, black stripes) in background"
                ),
                "size": "768x1024",
                "filename": "左胧月_印记显现",
            },
            "觉醒爆发": {
                "positive_suffix": (
                    "dramatic power pose, black hair streaming, "
                    "three forehead marks crackling with deep crimson electricity and energy, "
                    "intense glowing energy emanating from body, "
                    "eyes locked forward with overwhelming intensity, "
                    "dark sci-fi interior, ultra dramatic lighting, "
                    "energy burst visual effects surrounding figure"
                ),
                "size": "768x1024",
                "filename": "左胧月_觉醒爆发",
            },
        },
    },
}

# ─── SiliconFlow 图片生成 API ─────────────────────────────────────────────────

SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/images/generations"

# 推荐模型（按优先级排列）
RECOMMENDED_MODELS = [
    "black-forest-labs/FLUX.1-dev",       # 最高质量，适合写实风格
    "black-forest-labs/FLUX.1-schnell",   # 速度更快
    "Kwai-Kolors/Kolors",                  # 对亚洲面孔友好
    "stabilityai/stable-diffusion-3-5-large",
]


def generate_image(
    prompt: str,
    negative_prompt: str,
    size: str,
    model: str,
    api_key: str,
    steps: int = 30,
    seed: int = None,
    guidance_scale: float = 7.5,
) -> bytes:
    """调用 SiliconFlow API 生成图片，返回图片字节数据"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    width, height = map(int, size.split("x"))

    payload = {
        "model": model,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "image_size": size,
        "width": width,
        "height": height,
        "num_inference_steps": steps,
        "guidance_scale": guidance_scale,
        "batch_size": 1,
    }
    if seed is not None:
        payload["seed"] = seed

    print(f"  → 调用 SiliconFlow API [{model}] ...")
    resp = requests.post(SILICONFLOW_API_URL, headers=headers, json=payload, timeout=120)

    if resp.status_code != 200:
        raise RuntimeError(
            f"API 错误 {resp.status_code}: {resp.text[:300]}"
        )

    data = resp.json()

    # 响应格式: {"images": [{"url": "...", "b64_json": "..."}]}
    images = data.get("images") or data.get("data") or []
    if not images:
        raise RuntimeError(f"API 响应中无图片数据: {data}")

    img_data = images[0]

    # 优先使用 b64_json，否则下载 url
    if "b64_json" in img_data and img_data["b64_json"]:
        return base64.b64decode(img_data["b64_json"])
    elif "url" in img_data and img_data["url"]:
        img_resp = requests.get(img_data["url"], timeout=60)
        img_resp.raise_for_status()
        return img_resp.content
    else:
        raise RuntimeError(f"无法从响应中获取图片: {img_data}")


def generate_variant(
    character: str,
    variant_name: str,
    variant_cfg: dict,
    char_cfg: dict,
    output_dir: Path,
    model: str,
    api_key: str,
    steps: int,
    seed: int,
    dry_run: bool = False,
):
    """生成单个角色变体图片"""
    full_positive = f"{char_cfg['base_positive']}, {variant_cfg['positive_suffix']}"
    full_negative = char_cfg["base_negative"]
    size = variant_cfg.get("size", "768x1024")
    filename = variant_cfg["filename"]

    output_path = output_dir / f"{filename}.png"

    print(f"\n{'='*60}")
    print(f"角色: {character} | 变体: {variant_name}")
    print(f"尺寸: {size} | 输出: {output_path.name}")
    print(f"Prompt (前100字符): {full_positive[:100]}...")

    if dry_run:
        print("  [DRY RUN] 跳过实际生成")
        return None

    if output_path.exists():
        print(f"  → 文件已存在，跳过（使用 --overwrite 强制重新生成）")
        return output_path

    try:
        img_bytes = generate_image(
            prompt=full_positive,
            negative_prompt=full_negative,
            size=size,
            model=model,
            api_key=api_key,
            steps=steps,
            seed=seed,
        )
        output_path.write_bytes(img_bytes)
        print(f"  ✓ 已保存: {output_path} ({len(img_bytes)//1024} KB)")
        return output_path
    except Exception as e:
        print(f"  ✗ 生成失败: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="《外交官》角色形象图片生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--character", "-c",
        choices=list(CHARACTER_PROMPTS.keys()),
        help="要生成的角色名",
    )
    parser.add_argument(
        "--variant", "-v",
        default="标准半身像",
        help="变体名称（使用 --list-variants 查看可用变体），或 'all' 生成全部",
    )
    parser.add_argument(
        "--list-variants", "-l",
        metavar="CHARACTER",
        help="列出指定角色的所有可用变体",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("SILICONFLOW_API_KEY", ""),
        help="SiliconFlow API Key（也可通过环境变量 SILICONFLOW_API_KEY 设置）",
    )
    parser.add_argument(
        "--model",
        default="black-forest-labs/FLUX.1-dev",
        choices=RECOMMENDED_MODELS,
        help="图片生成模型",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent.parent / "characters" / "portraits"),
        help="图片输出目录",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=30,
        help="推理步数（越高质量越好但越慢，建议 20-40）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机种子（固定种子可复现相同结果）",
    )
    parser.add_argument(
        "--all-characters",
        action="store_true",
        help="为所有角色生成标准半身像",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="覆盖已存在的文件",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印提示词，不实际调用 API",
    )

    args = parser.parse_args()

    # 列出变体
    if args.list_variants:
        char = args.list_variants
        if char not in CHARACTER_PROMPTS:
            print(f"未知角色: {char}。可用角色: {list(CHARACTER_PROMPTS.keys())}")
            sys.exit(1)
        print(f"\n{char} 的可用变体:")
        for name, cfg in CHARACTER_PROMPTS[char]["variants"].items():
            print(f"  - {name}  [{cfg.get('size', '768x1024')}]  → {cfg['filename']}.png")
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not args.api_key and not args.dry_run:
        print("错误: 请通过 --api-key 或环境变量 SILICONFLOW_API_KEY 提供 API Key")
        print("申请地址: https://cloud.siliconflow.cn/")
        sys.exit(1)

    # 覆盖模式：删除已有文件
    # (在 generate_variant 内判断)

    results = []

    if args.all_characters:
        for char_name, char_cfg in CHARACTER_PROMPTS.items():
            variant_cfg = char_cfg["variants"].get("标准半身像")
            if variant_cfg:
                if args.overwrite and (output_dir / f"{variant_cfg['filename']}.png").exists():
                    (output_dir / f"{variant_cfg['filename']}.png").unlink()
                p = generate_variant(
                    char_name, "标准半身像", variant_cfg, char_cfg,
                    output_dir, args.model, args.api_key,
                    args.steps, args.seed, args.dry_run
                )
                results.append(p)
                if not args.dry_run:
                    time.sleep(2)

    elif args.character:
        char_cfg = CHARACTER_PROMPTS[args.character]

        if args.variant == "all":
            for variant_name, variant_cfg in char_cfg["variants"].items():
                if args.overwrite and (output_dir / f"{variant_cfg['filename']}.png").exists():
                    (output_dir / f"{variant_cfg['filename']}.png").unlink()
                p = generate_variant(
                    args.character, variant_name, variant_cfg, char_cfg,
                    output_dir, args.model, args.api_key,
                    args.steps, args.seed, args.dry_run
                )
                results.append(p)
                if not args.dry_run:
                    time.sleep(2)
        else:
            variant_cfg = char_cfg["variants"].get(args.variant)
            if not variant_cfg:
                print(f"未知变体: {args.variant}")
                print(f"可用变体: {list(char_cfg['variants'].keys())}")
                sys.exit(1)
            if args.overwrite and (output_dir / f"{variant_cfg['filename']}.png").exists():
                (output_dir / f"{variant_cfg['filename']}.png").unlink()
            p = generate_variant(
                args.character, args.variant, variant_cfg, char_cfg,
                output_dir, args.model, args.api_key,
                args.steps, args.seed, args.dry_run
            )
            results.append(p)
    else:
        parser.print_help()
        return

    # 汇总
    success = [r for r in results if r]
    print(f"\n{'='*60}")
    print(f"完成: 成功生成 {len(success)}/{len(results)} 张图片")
    for p in success:
        print(f"  ✓ {p}")


if __name__ == "__main__":
    main()
