"""
配置文件加载器
支持 YAML 配置 + 环境变量覆盖 (${VAR_NAME} 语法)
"""

import os
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    raise ImportError("请安装 PyYAML: pip install pyyaml")


# 默认配置（代码内置，与 config.yaml 保持一致）
_DEFAULTS = {
    "anthropic": {
        "api_key": None,
        "model": "claude-opus-4-6",
    },
    "siliconflow": {
        "api_key": None,
        "model": "Wan/Wan2.2-T2V-14B",
        "image_size": "1280x720",
        "num_frames": 81,
    },
    "tts": {
        "backend": "edge-tts",
        "voice": "zh-CN-YunxiNeural",
        "cosyvoice_model": "pretrained_models/CosyVoice2-0.5B",
        "cosyvoice_speaker": "中文男性旁白",
    },
    "whisper": {
        "model_size": "small",
        "language": "zh",
        "device": "auto",
    },
    "characters": {
        "enabled": True,
        "extract_on_split": True,
        "enrich_prompts": True,
    },
    "output": {
        "dir": "output",
        "episodes": 6,
    },
    "ui": {
        "host": "0.0.0.0",
        "port": 7860,
        "share": False,
    },
}


def _resolve_env_vars(obj):
    """递归解析 ${VAR_NAME} 形式的环境变量引用"""
    if isinstance(obj, str):
        def replacer(m):
            var = m.group(1)
            return os.environ.get(var, m.group(0))  # 未设置时保留原文
        return re.sub(r"\$\{([^}]+)\}", replacer, obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars(i) for i in obj]
    return obj


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并两个字典，override 优先"""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class Config:
    """全局配置对象，支持点号访问"""

    def __init__(self, data: dict):
        self._data = data

    def get(self, *keys, default=None):
        """按路径获取配置值，例如 cfg.get('tts', 'voice')"""
        node = self._data
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def __repr__(self):
        import json
        safe = {k: v for k, v in self._data.items()}
        # 隐藏 API key
        for section in ("anthropic", "siliconflow"):
            if section in safe and isinstance(safe[section], dict):
                safe[section] = dict(safe[section])
                if safe[section].get("api_key"):
                    safe[section]["api_key"] = "***"
        return json.dumps(safe, ensure_ascii=False, indent=2)


def load_config(config_path: str = None) -> Config:
    """
    加载配置文件，合并默认值，解析环境变量。

    搜索顺序（首个找到的文件生效）：
      1. config_path 参数
      2. 当前目录 config.yaml
      3. 项目根目录 config.yaml（向上查找）
    """
    # 搜索配置文件
    candidates = []
    if config_path:
        candidates.append(Path(config_path))
    candidates.append(Path.cwd() / "config.yaml")
    # 向上最多 3 级查找
    p = Path.cwd()
    for _ in range(3):
        p = p.parent
        candidates.append(p / "config.yaml")

    file_data = {}
    for path in candidates:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                file_data = yaml.safe_load(f) or {}
            break

    merged = _deep_merge(_DEFAULTS, file_data)
    resolved = _resolve_env_vars(merged)
    return Config(resolved)


# 模块级单例，首次导入时加载
_instance: Config = None


def get_config(config_path: str = None) -> Config:
    """获取全局配置单例（懒加载）"""
    global _instance
    if _instance is None or config_path:
        _instance = load_config(config_path)
    return _instance
