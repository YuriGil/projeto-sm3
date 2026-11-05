import re
PROJECT_RE=re.compile(r"^TATTOO_\d{4}$")
def validate_project_id(x):
    if not PROJECT_RE.fullmatch(x): raise ValueError("INVALID_PROJECT_ID")
    return x
def media_key(drive_file_id): return f"gdrive:{drive_file_id}"
def classify(existing_drive_ids, incoming):
    out=[]
    seen=set(existing_drive_ids)
    for f in incoming:
        fid=f["drive_file_id"]
        if fid in seen:
            out.append({"drive_file_id":fid,"action":"SKIP_EXISTING"})
        else:
            out.append({"drive_file_id":fid,"action":"INDEX_NEW"})
            seen.add(fid)
    return out
