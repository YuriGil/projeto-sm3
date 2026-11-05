import sys,tempfile
from pathlib import Path
sys.path.insert(0,"worker")
from media_worker import *
from PIL import Image

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    src=td/"orientation6.jpg"; out=td/"proxy.jpg"
    im=Image.new("RGB",(40,20))
    ex=Image.Exif(); ex[274]=6
    im.save(src,exif=ex)
    m=inspect_image(src)
    assert (m["raw_width"],m["raw_height"])==(40,20)
    assert (m["width"],m["height"])==(20,40)
    make_image_proxy(src,out,max_edge=30)
    with Image.open(out) as p: assert p.height==30 and p.width==15
    try: make_image_proxy(src,src); raise AssertionError()
    except ValueError as e: assert str(e)=="REFUSE_OVERWRITE_ORIGINAL"
    cmd=build_video_proxy("in.mp4","out.mp4")
    assert cmd[0]=="ffmpeg" and "libx264" in cmd
    try: build_video_proxy("same.mp4","same.mp4"); raise AssertionError()
    except ValueError: pass
    payload=analysis_payload(m,str(out),"TATTOO_0002","M0001")
    assert payload["original_is_read_only"] is True
print("MEDIA_WORKER_ACCEPTANCE_PASS")
