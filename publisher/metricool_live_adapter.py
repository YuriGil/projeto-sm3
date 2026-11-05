from datetime import datetime
def _dt(x): return datetime.fromisoformat(x)
def preflight(job, now_iso, scheduled_ids=()):
    if job.get("status")!="APROVADO" or job.get("approval_decision")!="APROVAR": return "BLOCKED_APPROVAL"
    if job.get("render_qa")!="PASS" or not job.get("media"): return "BLOCKED_ASSET_QA"
    if job.get("content_id") in set(scheduled_ids): return "BLOCKED_DUPLICATE"
    if _dt(job["date"]) <= _dt(now_iso): return "BLOCKED_PAST_SLOT"
    return "READY"

def metricool_info(job):
    if not job.get("media"): raise ValueError("MEDIA_REQUIRED")
    providers=[{"network":n} for n in job["networks"]]
    info={"autoPublish":bool(job.get("auto_publish",False)),"draft":False,"descendants":[],
          "firstCommentText":"","hasNotReadNotes":False,"media":job["media"],
          "mediaAltText":[],"providers":providers,
          "publicationDate":{"dateTime":job["date"][:19],"timezone":job["timezone"]},
          "shortener":False,"smartLinkData":{"ids":[]},"text":job.get("text","")}
    if "instagram" in job["networks"]:
        info["instagramData"]={"type":job.get("instagram_type","POST"),"collaborators":[],
                               "showReelOnFeed":True,"isAiGenerated":bool(job.get("ig_ai_generated",False))}
    if "tiktok" in job["networks"]:
        info["tiktokData"]={"disableComment":False,"disableDuet":False,"disableStitch":False,
          "privacyOption":"PUBLIC_TO_EVERYONE","commercialContentThirdParty":False,
          "commercialContentOwnBrand":False,"title":job.get("tiktok_title",""),
          "autoAddMusic":False,"photoCoverIndex":0,"isAigc":bool(job.get("tt_ai_generated",False))}
    return info
