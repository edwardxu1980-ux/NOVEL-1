#!/bin/bash
# ============================================================
# 叶枫 角色形象生成 - 本地运行脚本
# 在您自己的电脑上执行此脚本
# ============================================================

set -e

# ── 1. 克隆/同步仓库（如果还没有的话）──────────────────────
# git clone https://github.com/edwardxu1980-ux/novel-1.git
# cd novel-1
# git checkout claude/continue-work-uGqSS

# ── 2. 安装依赖 ─────────────────────────────────────────────
pip install requests -q

# ── 3. 设置 API Key ─────────────────────────────────────────
export SILICONFLOW_API_KEY="sk-wnizmvyhboqtcwdeqbkxtxwtvtcucdrijebnliuebkqoabkq"

# ── 4. 生成叶枫的全部形象图 ──────────────────────────────────
echo "=== 开始生成叶枫角色形象 ==="

python3 workflow/generate_character_portrait.py \
  --character 叶枫 \
  --variant 标准半身像 \
  --model black-forest-labs/FLUX.1-dev \
  --steps 30

# 验证效果满意后，再生成其余变体：
# python3 workflow/generate_character_portrait.py --character 叶枫 --variant all

echo ""
echo "=== 图片已保存到 characters/portraits/ 目录 ==="
ls -lh characters/portraits/*.png 2>/dev/null || echo "（目录为空，请检查是否有报错）"
