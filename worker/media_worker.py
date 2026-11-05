from pathlib import Path
from PIL import Image, ImageOps
import hashlib, json, subprocess

def sha256_file(path, chunk=1024*1024):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        while True:
            b=f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def inspect_image(path):
    p=Path(path)
    with Image.open(p) as im:
        raw_size=im.size
        orientation=im.getexif().get(274)
        oriented=ImageOps.exif_transpose(im)
        return {"kind":"image","raw_width":raw_size[0],"raw_height":raw_size[1],
                "width":oriented.width,"height":oriented.height,
                "exif_orientation":orientation,"sha256":sha256_file(p),"bytes":p.stat().st_size}

def make_image_proxy(source, output, max_edge=960, quality=82):
    s,o=Path(source),Path(output)
    if s.resolve()==o.resolve(): raise ValueError("REFUSE_OVERWRITE_ORIGINAL")
    with Image.open(s) as im:
        im=ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((max_edge,max_edge), Image.Resampling.LANCZOS)
        o.parent.mkdir(parents=True,exist_ok=True)
        im.save(o,"JPEG",quality=quality,optimize=True)
    return str(o)

def build_video_probe(path):
    return ["ffprobe","-v","error","-show_entries",
            "format=duration,size:stream=codec_type,width,height,avg_frame_rate,rotation",
            "-of","json",str(path)]

def build_video_proxy(source, output, max_edge=960):
    s,o=Path(source),Path(output)
    if s.resolve()==o.resolve(): raise ValueError("REFUSE_OVERWRITE_ORIGINAL")
    vf=f"scale='if(gt(iw,ih),{max_edge},-2)':'if(gt(iw,ih),-2,{max_edge})'"
    return ["ffmpeg","-y","-i",str(s),"-vf",vf,"-c:v","libx264","-preset","veryfast",
            "-crf","27","-c:a","aac","-b:a","96k",str(o)]

def analysis_payload(meta, proxy_path, project_id, media_id):
    return {"project_id":project_id,"media_id":media_id,"proxy_path":proxy_path,
            "metadata":meta,"required_output_contract":"media_analysis.schema.json",
            "original_is_read_only":True}
