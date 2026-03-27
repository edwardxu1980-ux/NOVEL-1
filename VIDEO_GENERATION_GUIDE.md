# 视频生成工具快速上手指南

## Wan2.2 (推荐 - 阿里万象)

最适合科幻题材的开源视频生成模型，电影级画质，文本遵循度最佳。

### 安装
```bash
pip install diffusers transformers accelerate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

### 文生视频示例
```python
import torch
from diffusers import AutoPipelineForText2Video

pipe = AutoPipelineForText2Video.from_pretrained(
    "Wan-AI/Wan2.2-T2V-A14B",
    torch_dtype=torch.bfloat16
).to("cuda")

prompt = "A massive alien spacecraft descends through orange clouds above a futuristic city, cinematic lighting, 8K"
video_frames = pipe(prompt=prompt, num_frames=81).frames[0]

from diffusers.utils import export_to_video
export_to_video(video_frames, "scene_01.mp4", fps=16)
```

---

## Open-Sora 2.0 (HPC-AI Tech)

完整的训练+推理流水线，支持多种分辨率和时长。

### 安装
```bash
git clone https://github.com/hpcaitech/Open-Sora
cd Open-Sora && pip install -e .
```

### 推理示例
```bash
python scripts/inference.py configs/opensora-v2-0/inference/sample.py \
  --prompt "Deep space exploration, astronaut floating in zero gravity, nebula background" \
  --num-frames 4s \
  --resolution 720p
```

---

## HunyuanVideo (腾讯)

13B参数，图生视频支持镜头运动控制，适合需要角色一致性的场景。

### 安装
```bash
git clone https://github.com/Tencent-Hunyuan/HunyuanVideo
cd HunyuanVideo && pip install -r requirements.txt
```

---

## CogVideoX-5B (智谱AI)

中文提示词友好，本地 RTX 4090 可运行。

### 快速使用
```python
from diffusers import CogVideoXPipeline
import torch

pipe = CogVideoXPipeline.from_pretrained(
    "THUDM/CogVideoX-5b",
    torch_dtype=torch.bfloat16
).to("cuda")

prompt = "科幻飞船在星云中穿行，蓝色推进器火焰，电影级镜头"
video = pipe(prompt=prompt, num_videos_per_prompt=1, num_inference_steps=50).frames[0]
```

---

## CosyVoice 2 配音 (阿里)

高质量中文TTS，支持音色克隆，适合科幻旁白。

### 安装
```bash
git clone https://github.com/FunAudioLLM/CosyVoice
cd CosyVoice && pip install -r requirements.txt
```

### 使用示例
```python
from cosyvoice.cli.cosyvoice import CosyVoice2

cosyvoice = CosyVoice2("pretrained_models/CosyVoice2-0.5B")
output = cosyvoice.inference_sft(
    "银河系边缘，一艘孤独的飞船正驶向未知的黑暗...",
    "中文男性旁白"
)
```

---

## edge-tts 免费配音

零成本，质量良好的微软TTS，适合快速原型。

```bash
pip install edge-tts

# 中文男声旁白
edge-tts --voice zh-CN-YunxiNeural --text "银河系边缘，一艘孤独的飞船..." --write-media output.mp3

# 查看所有中文声音
edge-tts --list-voices | grep zh-CN
```

---

## FFmpeg 视频合成

### 合并多个视频片段
```bash
# 生成 concat 列表
ls output/video/ep01/*.mp4 | sed "s/^/file '/;s/$/'/" > concat_list.txt
ffmpeg -f concat -safe 0 -i concat_list.txt -c copy ep01_raw.mp4
```

### 添加音频和字幕
```bash
ffmpeg -i ep01_raw.mp4 -i ep01_voice.mp3 \
  -vf "subtitles=ep01.srt:force_style='FontSize=24,PrimaryColour=&HFFFFFF'" \
  -c:v libx264 -c:a aac -shortest \
  ep01_final.mp4
```

### 添加片头/片尾
```bash
ffmpeg -i intro.mp4 -i ep01_final.mp4 -i outro.mp4 \
  -filter_complex "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1" \
  ep01_with_intro.mp4
```

---

## 云端 GPU 方案 (无需本地GPU)

| 平台 | 特点 | 价格参考 |
|------|------|---------|
| **SiliconFlow** | 支持 Wan2.2/CogVideoX API 调用 | 按token计费 |
| **Replicate** | 一行代码调用各类模型 | 按秒计费 |
| **RunPod** | 租用 A100/H100 GPU | ~$2-4/小时 |
| **ComfyUI Cloud** | 可视化工作流云端运行 | 按用量计费 |

### SiliconFlow API 示例
```python
import requests

response = requests.post(
    "https://api.siliconflow.cn/v1/video/submit",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={
        "model": "Wan/Wan2.2-T2V-14B",
        "prompt": "A futuristic spacecraft entering hyperspace, cinematic",
        "image_size": "1280x720",
        "num_frames": 81
    }
)
```
