# 科幻小说分集视频制作工具链

本文档梳理了将科幻小说转化为分集视频的完整开源工具链及工作流方案。

---

## 一、整体制作流程

```
小说文本
  │
  ▼
[1] 剧本分集拆解 (LLM / Claude API)
  │
  ▼
[2] 分镜脚本生成 (LLM → 场景描述)
  │
  ├──► [3a] 关键帧图像生成 (Stable Diffusion / FLUX)
  │          │
  │          ▼
  │    [3b] 图生视频 (Wan2.2-I2V / HunyuanVideo)
  │
  ├──► [4] 文字直出视频 (Open-Sora / Wan2.2-T2V)
  │
  ▼
[5] AI 配音 / 旁白 (CosyVoice / ElevenLabs / edge-tts)
  │
  ▼
[6] 字幕生成 (faster-whisper / WhisperX)
  │
  ▼
[7] 视频剪辑合成 (FFmpeg / MoviePy)
  │
  ▼
[8] 分集成片输出
```

---

## 二、端到端故事转视频框架

### ViMax (最推荐)
- **定位**: 多智能体导演框架，"导演+编剧+制片+视频生成"一体化
- **功能**: 长文本 RAG 分集、分镜设计、角色/场景一致性追踪、全自动装配
- **GitHub**: `github.com/HKUDS/ViMax`
- **适合场景**: 长篇科幻小说整体拆解

### ShortGPT
- **定位**: Python 自动化视频生成框架
- **功能**: LLM 编剧 → ElevenLabs/edge-tts 配音 → 素材匹配 → 自动剪辑
- **GitHub**: `github.com/RayVentura/ShortGPT`
- **适合场景**: 快速生成短集预告或片段

### StoryFlux
- **定位**: 全自动文本到视频+发布流水线
- **功能**: 内容生成 → TTS → 视频合成 → YouTube 自动上传
- **GitHub**: `github.com/MeetRajput00/StoryFlux`

---

## 三、AI 视频生成模型

### 文生视频 (Text-to-Video)

| 模型 | 机构 | 特点 | 获取方式 |
|------|------|------|----------|
| **Wan2.2-T2V-A14B** | 阿里万象 | MoE 架构，电影级质量，文本遵循度最佳 | HuggingFace |
| **Open-Sora 2.0** | HPC-AI Tech | 完整训练+推理流水线，可扩展 | `github.com/hpcaitech/Open-Sora` |
| **SkyReels V1** | 天工AI | 电影叙事风格，真实人物，33种表情 | HuggingFace |
| **HunyuanVideo** | 腾讯 | 13B参数，成熟生态，I2V+数字人 | `github.com/Tencent-Hunyuan/HunyuanVideo` |
| **CogVideoX-5B** | 智谱AI | 中文友好，本地可运行 | `github.com/THUDM/CogVideo` |
| **LTX-Video** | Lightricks | 快速推理，RTX 4090可运行 | HuggingFace |

### 图生视频 (Image-to-Video)

| 模型 | 特点 |
|------|------|
| **Wan2.2-I2V-A14B** | 静态图→流畅视频序列，最推荐 |
| **HunyuanVideo-I2V** | 高一致性，支持镜头运动控制 |
| **Stable Video Diffusion** | Stability AI，社区生态完善 |

---

## 四、AI 图像生成（关键帧/分镜）

| 工具 | 特点 | 适合科幻场景 |
|------|------|-------------|
| **FLUX.1-dev** | 当前最佳开源图像模型 | ★★★★★ |
| **Stable Diffusion XL** | 丰富LoRA/ControlNet生态 | ★★★★☆ |
| **ComfyUI** | 可视化工作流，集成SD/FLUX | 工作流编排 |
| **Automatic1111 WebUI** | 用户友好，插件丰富 | 快速出图 |

---

## 五、AI 配音 / 语音合成

| 工具 | 语言支持 | 开源 | 特点 |
|------|----------|------|------|
| **CosyVoice 2** | 中英多语 | ✅ | 阿里出品，音色克隆，`github.com/FunAudioLLM/CosyVoice` |
| **Fish Audio** | 中英多语 | ✅ | 高质量TTS，支持情感控制 |
| **edge-tts** | 100+语言 | ✅ | 微软TTS，免费，零延迟 |
| **F5-TTS** | 中英 | ✅ | 流式合成，`github.com/SWivid/F5-TTS` |
| **ElevenLabs** | 多语言 | ❌ | 商业，质量最高，有免费额度 |

---

## 六、字幕生成

| 工具 | 特点 |
|------|------|
| **faster-whisper** | OpenAI Whisper加速版，本地运行，`github.com/SYSTRAN/faster-whisper` |
| **WhisperX** | 带词级时间戳对齐，`github.com/m-bain/whisperX` |
| **Subtitle Edit** | 字幕编辑+格式转换GUI工具 |

---

## 七、视频剪辑与后期自动化

| 工具 | 用途 |
|------|------|
| **FFmpeg** | 底层视频处理，合并/剪切/转码/加字幕 |
| **MoviePy** | Python视频编辑库，适合自动化流水线 |
| **Auto-Editor** | 智能自动剪辑，`github.com/WyattBlue/auto-editor` |
| **Remotion** | 代码驱动视频生成（React/TS）|

---

## 八、流水线编排工具

| 工具 | 特点 |
|------|------|
| **ComfyUI** | 可视化节点工作流，支持SD/视频/TTS集成 |
| **n8n** | 开源工作流自动化，可连接各类API |
| **Prefect / Airflow** | 数据工程级任务调度，适合批量生产 |
| **LangGraph** | LLM多智能体编排，适合剧本生成阶段 |

---

## 九、推荐硬件配置

| 阶段 | 最低配置 | 推荐配置 |
|------|---------|---------|
| 剧本生成 | 任意CPU | Claude API / 本地LLM |
| 图像生成 | RTX 3080 (10GB) | RTX 4090 (24GB) |
| 视频生成 | RTX 4090 (24GB) | A100/H100 80GB |
| 配音+字幕 | 任意CPU/GPU | RTX 3060+ |

> **云端方案**: SiliconFlow / Replicate / RunPod 按需调用，无需本地GPU

---

## 十、下一步操作

1. **上传小说文件** → 分析章节结构
2. **运行分集脚本** → 将小说拆分为 N 集，每集约 5-15 分钟内容
3. **选择视频生成后端** → 根据硬件/预算选择 Wan2.2 / Open-Sora / HunyuanVideo
4. **配置配音方案** → CosyVoice（中文推荐）或 ElevenLabs
5. **搭建自动化流水线** → 基于 ShortGPT 或 ViMax 框架定制
