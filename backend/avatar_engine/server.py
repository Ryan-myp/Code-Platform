"""数字人引擎服务（SadTalker）：单图 + 音频 → 口型说话视频。

端口 9890，接口语义对齐 ACE-Step 服务（平台 music_factory 同款调用模式）：
- POST /release_task  提交任务（multipart: image + audio + 可选参数）→ task_id
- GET  /query_result   查询任务（data 为 list，result 为 JSON 字符串）
- GET  /v1/video?path= 下载产物
- GET  /health         健康检查

推理约束：M4 Pro 24GB 统一内存 → 串行推理（ThreadPoolExecutor(1)），
模型懒加载；Face Renderer Conv3D 在 MPS 不可用 → CPU + 多线程优化。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("avatar_engine")

app = FastAPI(title="Avatar Engine (SadTalker)", version="0.1.0")

OUTPUT_ROOT = os.path.expanduser("~/ai-models/SadTalker/outputs")
os.makedirs(OUTPUT_ROOT, exist_ok=True)

_tasks: dict = {}  # task_id -> {status, result(JSON str), error, created_at, finished_at}
_tasks_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=1)  # 串行推理：24GB 内存限制

_STATUS_QUEUE = ("pending", "running", "success", "failed", "user_cancelled")


def _set_task(task_id: str, **fields) -> None:
    with _tasks_lock:
        _tasks[task_id].update(fields)


def _run_inference(task_id: str, image_path: str, audio_path: str, opts: dict) -> None:
    from sad_engine import get_engine

    def _stage(stage: str) -> None:
        _set_task(task_id, stage=stage)

    t0 = time.monotonic()
    try:
        _set_task(task_id, status="running", stage="loading", started_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        out_dir = os.path.join(OUTPUT_ROOT, task_id)
        os.makedirs(out_dir, exist_ok=True)
        mp4 = get_engine().generate(
            image_path, audio_path, out_dir,
            pose_style=int(opts.get("pose_style", 0)),
            size=int(opts.get("size", 256)),
            still=bool(opts.get("still", True)),
            preprocess=str(opts.get("preprocess", "crop")),
            batch_size=int(opts.get("batch_size", 4)),
            expression_scale=float(opts.get("expression_scale", 1.5)),
            progress=_stage,
        )
        rel = os.path.relpath(mp4, os.path.expanduser("~"))
        result = json.dumps([{"file": rel}], ensure_ascii=False)
        _set_task(task_id, status="success", result=result,
                  elapsed=round(time.monotonic() - t0, 1))
        logger.info(f"task {task_id} 完成，耗时 {time.monotonic() - t0:.1f}s")
    except Exception as e:  # noqa: BLE001 — 任务级错误上报，不中断服务
        logger.exception(f"task {task_id} 失败")
        _set_task(task_id, status="failed", error=str(e),
                  elapsed=round(time.monotonic() - t0, 1))
    finally:
        for p in (image_path, audio_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass


@app.get("/health")
def health():
    running = sum(1 for t in _tasks.values() if t["status"] == "running")
    return {"status": "ok", "tasks": len(_tasks), "running": running}


@app.post("/release_task")
async def release_task(
    image: UploadFile = File(...),
    audio: UploadFile = File(...),
    pose_style: int = Form(0),
    size: int = Form(256),
    still: bool = Form(True),
    preprocess: str = Form("crop"),
    batch_size: int = Form(4),
    expression_scale: float = Form(1.5),
):
    task_id = uuid.uuid4().hex[:12]
    tmp = os.path.join(OUTPUT_ROOT, "_tmp")
    os.makedirs(tmp, exist_ok=True)
    img_path = os.path.join(tmp, f"{task_id}{os.path.splitext(image.filename or 'x')[1] or '.png'}")
    aud_path = os.path.join(tmp, f"{task_id}{os.path.splitext(audio.filename or 'x')[1] or '.wav'}")
    with open(img_path, "wb") as f:
        f.write(await image.read())
    with open(aud_path, "wb") as f:
        f.write(await audio.read())

    with _tasks_lock:
        _tasks[task_id] = {
            "task_id": task_id, "status": "pending", "stage": "",
            "result": "", "error": "", "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    opts = {"pose_style": pose_style, "size": size, "still": still,
            "preprocess": preprocess, "batch_size": batch_size,
            "expression_scale": expression_scale}
    _pool.submit(_run_inference, task_id, img_path, aud_path, opts)
    return JSONResponse({"code": 200, "message": "task released", "data": {"task_id": task_id}})


@app.get("/query_result")
def query_result(task_id: str = ""):
    with _tasks_lock:
        if task_id:
            task = _tasks.get(task_id)
            items = [task] if task else []
        else:
            items = sorted(_tasks.values(), key=lambda t: t["created_at"], reverse=True)[:20]
    return {"code": 200, "data": items}


@app.get("/v1/video")
def get_video(path: str = ""):
    if not path:
        return JSONResponse({"code": 400, "message": "path required"}, status_code=400)
    full = os.path.normpath(os.path.join(os.path.expanduser("~"), path))
    if not full.startswith(os.path.expanduser("~")):
        return JSONResponse({"code": 403, "message": "forbidden"}, status_code=403)
    if not os.path.isfile(full):
        return JSONResponse({"code": 404, "message": "not found"}, status_code=404)
    return FileResponse(full, media_type="video/mp4", filename=os.path.basename(full))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9890, log_level="info")
