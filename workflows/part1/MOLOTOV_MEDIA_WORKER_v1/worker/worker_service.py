from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PIL import Image, ImageOps, ImageDraw

MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "/data/media")).resolve()
INBOX = (MEDIA_ROOT / "inbox").resolve()
PROXIES = (MEDIA_ROOT / "proxies").resolve()
CONTACTS = (MEDIA_ROOT / "contact_sheets").resolve()

for p in (MEDIA_ROOT, INBOX, PROXIES, CONTACTS):
    p.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="MOLOTOV Media Worker", version="1.0.0")


class ProcessRequest(BaseModel):
    project_id: str
    media_id: str
    kind: Literal["image", "video"]
    source_path: str
    file_name: Optional[str] = None
    delete_source_after: bool = True


def _safe_component(value: str) -> str:
    value = "".join(c if c.isalnum() or c in "-_." else "_" for c in value.strip())
    return value[:160] or "unnamed"


def _ensure_under(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise HTTPException(400, f"PATH_OUTSIDE_ALLOWED_ROOT: {resolved}")
    return resolved


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def inspect_image(path: Path) -> dict:
    with Image.open(path) as im:
        raw_w, raw_h = im.size
        orientation = im.getexif().get(274)
        oriented = ImageOps.exif_transpose(im)
        return {
            "kind": "image",
            "raw_width": raw_w,
            "raw_height": raw_h,
            "width": oriented.width,
            "height": oriented.height,
            "exif_orientation": orientation,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }


def make_image_proxy(source: Path, output: Path, max_edge: int = 1280, quality: int = 84) -> None:
    if source.resolve() == output.resolve():
        raise RuntimeError("REFUSE_OVERWRITE_ORIGINAL")
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        im.save(output, "JPEG", quality=quality, optimize=True)


def ffprobe(path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size:stream=codec_type,width,height,avg_frame_rate,rotation",
        "-of", "json", str(path)
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout or "{}")
    duration = None
    try:
        duration = float(data.get("format", {}).get("duration"))
    except Exception:
        pass
    return {
        "kind": "video",
        "duration_seconds": duration,
        "bytes": int(data.get("format", {}).get("size") or path.stat().st_size),
        "streams": data.get("streams", []),
        "sha256": sha256_file(path),
    }


def make_video_proxy(source: Path, output: Path, max_edge: int = 960) -> None:
    if source.resolve() == output.resolve():
        raise RuntimeError("REFUSE_OVERWRITE_ORIGINAL")
    output.parent.mkdir(parents=True, exist_ok=True)
    vf = f"scale='if(gt(iw,ih),{max_edge},-2)':'if(gt(iw,ih),-2,{max_edge})'"
    cmd = [
        "ffmpeg", "-y", "-i", str(source),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        str(output),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def make_contact_sheet(source: Path, output: Path, duration: Optional[float], count: int = 6) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    frames_dir = output.parent / f".frames_{output.stem}"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    try:
        if not duration or duration <= 0:
            points = [0]
        else:
            points = [duration * (i + 1) / (count + 1) for i in range(count)]

        frame_paths = []
        for idx, sec in enumerate(points):
            fp = frames_dir / f"{idx:02d}.jpg"
            cmd = [
                "ffmpeg", "-y", "-ss", f"{sec:.3f}", "-i", str(source),
                "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "3", str(fp)
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            if fp.exists():
                frame_paths.append(fp)

        if not frame_paths:
            raise RuntimeError("NO_CONTACT_SHEET_FRAMES")

        images = [Image.open(p).convert("RGB") for p in frame_paths]
        thumb_w = max(im.width for im in images)
        thumb_h = max(im.height for im in images)
        cols = 3
        rows = (len(images) + cols - 1) // cols
        canvas = Image.new("RGB", (thumb_w * cols, thumb_h * rows), "white")
        draw = ImageDraw.Draw(canvas)
        for i, im in enumerate(images):
            x = (i % cols) * thumb_w
            y = (i // cols) * thumb_h
            canvas.paste(im, (x, y))
            draw.rectangle((x, y, x + im.width - 1, y + im.height - 1), outline="black", width=2)
        canvas.save(output, "JPEG", quality=84, optimize=True)
        for im in images:
            im.close()
    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "molotov-media-worker",
        "version": "1.0.0",
        "media_root": str(MEDIA_ROOT),
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
    }


@app.post("/process-path")
def process_path(req: ProcessRequest):
    project = _safe_component(req.project_id)
    media = _safe_component(req.media_id)
    src = _ensure_under(Path(req.source_path), INBOX)

    if not src.exists() or not src.is_file():
        raise HTTPException(404, f"SOURCE_NOT_FOUND: {src}")

    try:
        if req.kind == "image":
            meta = inspect_image(src)
            proxy = _ensure_under(PROXIES / project / f"{media}.jpg", PROXIES)
            make_image_proxy(src, proxy)
            contact = None
        else:
            meta = ffprobe(src)
            proxy = _ensure_under(PROXIES / project / f"{media}.mp4", PROXIES)
            make_video_proxy(src, proxy)
            contact = _ensure_under(CONTACTS / project / f"{media}.jpg", CONTACTS)
            make_contact_sheet(src, contact, meta.get("duration_seconds"))

        result = {
            "ok": True,
            "project_id": req.project_id,
            "media_id": req.media_id,
            "kind": req.kind,
            "original_is_read_only": True,
            "content_hash": meta["sha256"],
            "metadata": meta,
            "proxy_path": str(proxy),
            "proxy_bytes": proxy.stat().st_size,
            "contact_sheet_path": str(contact) if contact else None,
            "contact_sheet_bytes": contact.stat().st_size if contact and contact.exists() else None,
            "source_temp_path": str(src),
            "source_deleted": False,
        }

        if req.delete_source_after:
            src.unlink(missing_ok=True)
            result["source_deleted"] = True

        return result
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "")[-4000:]
        raise HTTPException(500, f"MEDIA_COMMAND_FAILED: {stderr}")
    except Exception as e:
        raise HTTPException(500, f"MEDIA_WORKER_FAILED: {type(e).__name__}: {e}")
