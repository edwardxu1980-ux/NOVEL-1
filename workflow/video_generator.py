"""
SiliconFlow 视频生成模块
调用 SiliconFlow API 将场景描述批量生成视频片段

支持模型: Wan2.2-T2V-14B, CogVideoX-5B
"""

import os
import time
import json
import requests
from pathlib import Path


SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1"
DEFAULT_MODEL = "Wan/Wan2.2-T2V-14B"
DEFAULT_IMAGE_SIZE = "1280x720"
DEFAULT_NUM_FRAMES = 81  # ~5秒 @16fps


class SiliconFlowVideoGenerator:
    def __init__(self, api_key: str = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or os.environ.get("SILICONFLOW_API_KEY")
        if not self.api_key:
            raise ValueError(
                "未找到 SiliconFlow API Key。\n"
                "请设置环境变量: export SILICONFLOW_API_KEY=your_key\n"
                "或在初始化时传入: SiliconFlowVideoGenerator(api_key='your_key')"
            )
        self.model = model
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def submit_video_task(
        self,
        prompt: str,
        image_size: str = DEFAULT_IMAGE_SIZE,
        num_frames: int = DEFAULT_NUM_FRAMES,
        seed: int = None,
    ) -> str:
        """提交视频生成任务，返回 task_id"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "image_size": image_size,
            "num_frames": num_frames,
        }
        if seed is not None:
            payload["seed"] = seed

        resp = self.session.post(f"{SILICONFLOW_API_URL}/video/submit", json=payload)
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("requestId") or data.get("task_id") or data["id"]
        return task_id

    def poll_task(self, task_id: str, poll_interval: int = 10, timeout: int = 600) -> str:
        """轮询任务状态，返回视频下载 URL"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self.session.get(f"{SILICONFLOW_API_URL}/video/status/{task_id}")
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "").lower()

            if status in ("succeeded", "completed", "success"):
                video_url = (
                    data.get("video_url")
                    or data.get("output", {}).get("video_url")
                    or data["results"][0]["url"]
                )
                return video_url
            elif status in ("failed", "error"):
                raise RuntimeError(f"任务 {task_id} 失败: {data.get('message', '未知错误')}")

            print(f"  [等待] 任务 {task_id[:8]}... 状态: {status}")
            time.sleep(poll_interval)

        raise TimeoutError(f"任务 {task_id} 超时（{timeout}秒）")

    def download_video(self, url: str, output_path: str) -> str:
        """下载视频到本地"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with self.session.get(url, stream=True) as resp:
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        return output_path


def generate_episode_videos(
    prompts_file: str,
    output_dir: str,
    api_key: str = None,
    model: str = DEFAULT_MODEL,
    image_size: str = DEFAULT_IMAGE_SIZE,
    num_frames: int = DEFAULT_NUM_FRAMES,
    dry_run: bool = False,
):
    """
    读取分集提示词文件，批量生成并下载视频片段。

    Args:
        prompts_file: JSON 提示词文件路径 (output/prompts/ep01_prompts.json)
        output_dir:   视频输出目录 (output/video/ep01/)
        api_key:      SiliconFlow API Key (可选，优先读取环境变量)
        model:        使用的模型名称
        image_size:   视频分辨率
        num_frames:   帧数
        dry_run:      仅打印任务，不实际调用 API
    """
    with open(prompts_file, "r", encoding="utf-8") as f:
        scenes = json.load(f)

    if dry_run:
        print(f"[DRY RUN] 将为 {len(scenes)} 个场景生成视频:")
        for scene in scenes:
            print(f"  场景 {scene['scene_id']}: {scene['prompt'][:60]}...")
        return

    gen = SiliconFlowVideoGenerator(api_key=api_key, model=model)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 提交所有任务
    tasks = []
    for scene in scenes:
        print(f"[提交] 场景 {scene['scene_id']}: {scene['prompt'][:50]}...")
        task_id = gen.submit_video_task(
            prompt=scene["prompt"],
            image_size=image_size,
            num_frames=num_frames,
        )
        tasks.append({"scene_id": scene["scene_id"], "task_id": task_id})
        time.sleep(0.5)  # 避免限速

    # 保存任务列表（便于中断后恢复）
    tasks_file = os.path.join(output_dir, "tasks.json")
    with open(tasks_file, "w") as f:
        json.dump(tasks, f, indent=2)
    print(f"[任务] 已保存任务列表: {tasks_file}")

    # 轮询并下载
    for task in tasks:
        scene_id = task["scene_id"]
        task_id = task["task_id"]
        output_path = os.path.join(output_dir, f"scene_{scene_id:02d}.mp4")

        if os.path.exists(output_path):
            print(f"[跳过] 场景 {scene_id} 已存在: {output_path}")
            continue

        print(f"[等待] 场景 {scene_id} (task: {task_id[:8]}...)")
        try:
            video_url = gen.poll_task(task_id)
            gen.download_video(video_url, output_path)
            print(f"[完成] 场景 {scene_id} → {output_path}")
        except Exception as e:
            print(f"[错误] 场景 {scene_id}: {e}")

    # 生成 FFmpeg concat 列表
    concat_file = os.path.join(output_dir, "concat.txt")
    video_files = sorted(Path(output_dir).glob("scene_*.mp4"))
    with open(concat_file, "w") as f:
        for vf in video_files:
            f.write(f"file '{vf.name}'\n")
    print(f"[合并] FFmpeg concat 列表已生成: {concat_file}")

    # 合并视频片段
    concat_output = os.path.join(output_dir, "concat.mp4")
    os.system(
        f'ffmpeg -y -f concat -safe 0 -i "{concat_file}" -c copy "{concat_output}" 2>/dev/null'
    )
    if os.path.exists(concat_output):
        print(f"[合并] 视频片段已合并: {concat_output}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SiliconFlow 视频批量生成")
    parser.add_argument("prompts_file", help="提示词 JSON 文件路径")
    parser.add_argument("output_dir", help="视频输出目录")
    parser.add_argument("--api-key", help="SiliconFlow API Key")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="使用的模型")
    parser.add_argument("--size", default=DEFAULT_IMAGE_SIZE, help="视频分辨率")
    parser.add_argument("--frames", type=int, default=DEFAULT_NUM_FRAMES, help="帧数")
    parser.add_argument("--dry-run", action="store_true", help="仅打印任务，不调用 API")
    args = parser.parse_args()

    generate_episode_videos(
        prompts_file=args.prompts_file,
        output_dir=args.output_dir,
        api_key=args.api_key,
        model=args.model,
        image_size=args.size,
        num_frames=args.frames,
        dry_run=args.dry_run,
    )
