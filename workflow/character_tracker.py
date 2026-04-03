"""
角色一致性追踪模块
从小说中提取角色信息，并在场景提示词中注入外貌描述，
确保跨集跨场景的视觉一致性。
"""

import os
import json
import anthropic
from pathlib import Path


EXTRACT_SYSTEM_PROMPT = """你是一名专业的影视角色设定师。
请从提供的科幻小说文本中，提取所有出现的角色信息。

输出格式为 JSON 数组：
[
  {
    "name": "角色中文名",
    "alias": ["别名或英文名"],
    "role": "主角/配角/反派/次要角色",
    "gender": "男/女/未知",
    "age_desc": "年龄描述（如：30岁左右、中年、老年）",
    "appearance": {
      "face": "面部特征（英文，用于AI生图prompt）",
      "hair": "发型发色（英文）",
      "build": "体型特征（英文）",
      "outfit": "典型服装（英文）",
      "special": "特殊标志（如疤痕、义肢、发光眼睛等，英文）"
    },
    "personality": "性格简述（中文，1-2句）",
    "first_appearance": "首次出现的章节或场景描述"
  }
]

注意：
- appearance 字段使用英文，便于 Stable Diffusion / Wan2.2 使用
- 若某字段信息不足，设为 null
- 仅提取有实质描述的角色，忽略路人甲乙
"""


def extract_characters(novel_text: str, api_key: str = None, model: str = "claude-opus-4-6") -> list[dict]:
    """
    调用 Claude 从小说中提取角色信息。

    Args:
        novel_text: 小说原文
        api_key:    Anthropic API Key（可选，优先读取环境变量）
        model:      使用的模型

    Returns:
        角色信息列表
    """
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=EXTRACT_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"请从以下科幻小说中提取角色信息：\n\n{novel_text[:40000]}"
        }]
    )

    raw = message.content[0].text
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start == -1:
        return []
    return json.loads(raw[start:end])


def build_character_prompt(character: dict) -> str:
    """将角色外貌信息拼接为适合 AI 生图的英文 prompt 片段"""
    app = character.get("appearance") or {}
    parts = []

    gender_map = {"男": "male", "女": "female"}
    gender = gender_map.get(character.get("gender", ""), "")
    if gender:
        parts.append(gender)

    age = character.get("age_desc", "")
    if age:
        parts.append(age)

    for field in ("face", "hair", "build", "outfit", "special"):
        val = app.get(field)
        if val:
            parts.append(val)

    return ", ".join(p for p in parts if p)


class CharacterRegistry:
    """角色注册表，管理角色信息并提供提示词注入"""

    def __init__(self, characters: list[dict] = None):
        self._chars: dict[str, dict] = {}
        if characters:
            for c in characters:
                self.register(c)

    def register(self, character: dict):
        """注册一个角色"""
        name = character["name"]
        self._chars[name] = character
        # 同时以别名注册
        for alias in character.get("alias") or []:
            self._chars[alias] = character

    def get(self, name: str) -> dict | None:
        return self._chars.get(name)

    def all_main_characters(self) -> list[dict]:
        """返回去重的主要角色列表（主角/配角/反派）"""
        seen = set()
        result = []
        for c in self._chars.values():
            cid = id(c)
            if cid not in seen and c.get("role") in ("主角", "配角", "反派"):
                seen.add(cid)
                result.append(c)
        return result

    def enrich_scene_prompt(self, scene: dict) -> dict:
        """
        检测场景描述中出现的角色名，将外貌描述注入 prompt。

        Args:
            scene: 包含 "description" 和 "narration" 字段的场景字典

        Returns:
            更新后的场景字典（新增 "characters_in_scene" 和修改 "description"）
        """
        # 在旁白/描述中搜索角色名
        text = (scene.get("narration", "") or "") + " " + (scene.get("description", "") or "")
        found = []
        for name, char in self._chars.items():
            if name in text:
                # 避免重复添加同一角色
                if not any(c["name"] == char["name"] for c in found):
                    found.append(char)

        if not found:
            return scene

        # 构建角色外貌描述并注入 prompt
        char_prompts = []
        for char in found:
            cp = build_character_prompt(char)
            if cp:
                char_prompts.append(f"{char['name']}({cp})")

        enriched = dict(scene)
        enriched["characters_in_scene"] = [c["name"] for c in found]
        if char_prompts:
            enriched["description"] = (
                scene.get("description", "") +
                ", featuring " + "; ".join(char_prompts)
            )
        return enriched

    def enrich_episodes(self, episodes: list[dict]) -> list[dict]:
        """批量为所有分集的场景注入角色外貌"""
        enriched_eps = []
        for ep in episodes:
            enriched_ep = dict(ep)
            enriched_ep["scenes"] = [
                self.enrich_scene_prompt(scene)
                for scene in ep.get("scenes", [])
            ]
            enriched_eps.append(enriched_ep)
        return enriched_eps

    def save(self, path: str):
        """保存角色注册表到 JSON 文件"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        unique = {}
        for c in self._chars.values():
            unique[c["name"]] = c
        with open(path, "w", encoding="utf-8") as f:
            json.dump(list(unique.values()), f, ensure_ascii=False, indent=2)
        print(f"[角色] 角色信息已保存: {path} ({len(unique)} 个角色)")

    @classmethod
    def load(cls, path: str) -> "CharacterRegistry":
        """从 JSON 文件加载角色注册表"""
        with open(path, "r", encoding="utf-8") as f:
            characters = json.load(f)
        return cls(characters)

    def summary(self) -> str:
        """返回角色摘要文本"""
        unique = {}
        for c in self._chars.values():
            unique[c["name"]] = c
        lines = [f"共 {len(unique)} 个角色："]
        for name, c in unique.items():
            role = c.get("role", "未知")
            gender = c.get("gender", "")
            lines.append(f"  [{role}] {name}（{gender}）— {c.get('personality', '')}")
        return "\n".join(lines)


def extract_and_save(
    novel_text: str,
    output_path: str = "output/characters.json",
    api_key: str = None,
    model: str = "claude-opus-4-6",
) -> CharacterRegistry:
    """提取角色并保存，返回 CharacterRegistry 实例"""
    print("[角色] 正在从小说中提取角色信息...")
    characters = extract_characters(novel_text, api_key=api_key, model=model)
    registry = CharacterRegistry(characters)
    registry.save(output_path)
    print(registry.summary())
    return registry


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="角色一致性提取工具")
    subparsers = parser.add_subparsers(dest="command")

    extract_cmd = subparsers.add_parser("extract", help="从小说提取角色")
    extract_cmd.add_argument("novel_file", help="小说文本文件")
    extract_cmd.add_argument("-o", "--output", default="output/characters.json")
    extract_cmd.add_argument("--model", default="claude-opus-4-6")

    enrich_cmd = subparsers.add_parser("enrich", help="为已有 episodes.json 注入角色外貌")
    enrich_cmd.add_argument("characters_file", help="角色 JSON 文件")
    enrich_cmd.add_argument("episodes_file", help="分集 episodes.json 文件")
    enrich_cmd.add_argument("-o", "--output", default="output/episodes_enriched.json")

    args = parser.parse_args()

    if args.command == "extract":
        with open(args.novel_file, "r", encoding="utf-8") as f:
            text = f.read()
        extract_and_save(text, args.output, model=args.model)

    elif args.command == "enrich":
        registry = CharacterRegistry.load(args.characters_file)
        with open(args.episodes_file, "r", encoding="utf-8") as f:
            episodes = json.load(f)
        enriched = registry.enrich_episodes(episodes)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)
        print(f"[角色] 已注入角色外貌 → {args.output}")
    else:
        parser.print_help()
