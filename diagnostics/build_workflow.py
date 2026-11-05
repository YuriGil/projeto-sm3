#!/usr/bin/env python3
"""Build the 07F n8n workflow from the 07E Sheets node contracts."""
import copy
import json
from pathlib import Path
from uuid import uuid4

package = Path(__file__).resolve().parents[2]
previous = package.parent / "PROJETO_SM3_07E_MANUAL_EDIT_STATE_v1_VERIFIED_COMMIT.json"
assert previous.is_file(), "07E workflow template missing during package build"
template = json.loads(previous.read_text(encoding="utf-8"))
read_template = next(n for n in template["nodes"] if n["name"] == "READ — EDIT SESSION CONTROL STATE")
update_template = next(n for n in template["nodes"] if n["name"] == "UPDATE — MANUAL EDIT CONTROL STATE")
nodes, edges = [], {}

def add(name, node_type, x, y, params=None, base=None, opts=None):
    node = copy.deepcopy(base) if base else {}
    node.update({"name": name, "id": str(uuid4()), "type": node_type, "position": [x, y],
                 "parameters": params if params is not None else node.get("parameters", {})})
    node.setdefault("typeVersion", {"n8n-nodes-base.code": 2, "n8n-nodes-base.httpRequest": 4.5,
                                     "n8n-nodes-base.switch": 3.2,
                                     "n8n-nodes-base.readWriteFile": 1.1,
                                     "n8n-nodes-base.googleDrive": 3,
                                     "n8n-nodes-base.manualTrigger": 1}.get(node_type, 4.7))
    node.update(opts or {})
    nodes.append(node)
    return name

def code(name, x, y, js, mode="runOnceForAllItems"):
    return add(name, "n8n-nodes-base.code", x, y, {"mode": mode, "jsCode": js})

def link(a, b, output=0):
    outputs = edges.setdefault(a, {"main": []})["main"]
    while len(outputs) <= output:
        outputs.append([])
    outputs[output].append({"node": b, "type": "main", "index": 0})

def route(name, x, y, field, values):
    rules = []
    for value in values:
        rules.append({"conditions": {"options": {"caseSensitive": True, "leftValue": "",
                            "typeValidation": "strict", "version": 3},
                     "conditions": [{"leftValue": "={{ $json."+field+" }}", "rightValue": value,
                                     "operator": {"type": "string", "operation": "equals"},
                                     "id": str(uuid4())}], "combinator": "and"},
                     "renameOutput": True, "outputKey": value})
    return add(name, "n8n-nodes-base.switch", x, y,
               {"rules": {"values": rules}, "options": {}})

def read_sheet(name, sheet_id, cached_name, x, y):
    node = copy.deepcopy(read_template)
    node["parameters"]["sheetName"]["value"] = sheet_id
    node["parameters"]["sheetName"]["cachedResultName"] = cached_name
    node["executeOnce"] = True
    return add(name, node["type"], x, y, base=node)

add("MANUAL — RENDER EDIT PREVIEWS", "n8n-nodes-base.manualTrigger", -1600, 0)
add("WORKER — HEALTH 2.6.0", "n8n-nodes-base.httpRequest", -1400, 0,
    {"url": "http://media-worker:8090/health", "options": {"timeout": 30000}})
code("ASSERT — EDIT PREVIEW CONTRACT", -1200, 0, """
const h=$json;
if(h.ok!==true||h.version!=='2.6.0'||h.edit_preview_renderer!==true||
   h.edit_preview_contract!=='SM3_EDIT_PREVIEW_V1'||h.edit_session_save_contract!=='SM3_EDIT_SAVE_V1')
  throw new Error('SM3_07F_WORKER_CONTRACT_INVALID');
return {json:{status:'WORKER_2_6_0_VERIFIED'}};
""", "runOnceForEachItem")
read_sheet("READ — 04_CONTEUDOS", 733071962, "04_CONTEUDOS", -1000, 0)
read_sheet("READ — 03_MIDIAS", 444966540, "03_MIDIAS", -800, 0)
code("BUILD — EDIT SOURCE QUEUE", -600, 0, """
const contents=$('READ — 04_CONTEUDOS').all().map(i=>i.json), media=$input.all().map(i=>i.json);
const norm=x=>String(x??'').trim(), up=x=>norm(x).toUpperCase();
const counts=new Map(), mediaCounts=new Map();
for(const c of contents){const k=norm(c.ID_CONTEÚDO);if(k)counts.set(k,(counts.get(k)||0)+1)}
for(const m of media){const k=norm(m.ID_MIDIA);if(k)mediaCounts.set(k,(mediaCounts.get(k)||0)+1)}
const chosen=contents.filter(c=>up(c.EDIT_SESSION_STATUS)==='SAVED'&&up(c.REVISION_MODE)==='MANUAL_EDIT'
    &&up(c.PIPELINE_STATE)==='EDIT_SESSION_READY');
if(!chosen.length)return [{json:{route:'NO_WORK',status:'NO_SAVED_MANUAL_EDITS'}}];
const queue=new Map();
for(const c of chosen){
  const content=norm(c.ID_CONTEÚDO),project=norm(c.ID_PROJETO),session=norm(c.EDIT_SESSION_ID);
  if(counts.get(content)!==1||!/^TATTOO_[A-Za-z0-9_-]+$/.test(project)||
     !/^ES_[A-Za-z0-9_-]+$/.test(session)||up(c.STATE_VERSION)!=='SM3_STATE_V5'||
     norm(c.EDIT_RECIPE_VERSION)!=='SM3_EDIT_RECIPE_V1'||
     norm(c.PRODUCTION_CONTRACT_VERSION)!=='SM3_PRODUCTION_EDIT_V1')
     throw new Error('SM3_07F_SHEET_CONTROL_INVALID:'+content);
  const ids=[...new Set(norm(c.BRUTOS_USADOS).match(/M\\d{4,}/g)||[])];
  if(!ids.length)throw new Error('SM3_07F_MEDIA_IDS_MISSING:'+content);
  for(const id of ids){
    if(mediaCounts.get(id)!==1)throw new Error('SM3_07F_MEDIA_REGISTRY_NOT_UNIQUE:'+id);
    const m=media.find(x=>norm(x.ID_MIDIA)===id);
    if(!norm(m.DRIVE_FILE_ID))throw new Error('SM3_07F_DRIVE_ID_MISSING:'+id);
    const safe=norm(m.ARQUIVO||id+'.bin').replace(/[^A-Za-z0-9._-]+/g,'_').slice(-100);
    const tipo=norm(m.TIPO).normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toUpperCase();
    const mime=norm(m.MIME_TYPE).toLowerCase(),ext=(safe.toLowerCase().match(/\\.([a-z0-9]+)$/)||[])[1];
    const video=['mp4','mov','m4v','avi','mkv','webm','3gp','mts','mpeg','mpg','wmv','flv','ts'].includes(ext);
    const image=['jpg','jpeg','png','webp','bmp','tif','tiff','heic','heif','avif','gif'].includes(ext);
    if(!(video||image||mime.startsWith('video/')||mime.startsWith('image/')))
       throw new Error('SM3_07F_MEDIA_TYPE_UNSUPPORTED:'+id);
    const kind=(video||mime.startsWith('video/')||tipo==='VIDEO')?'video':'image';
    const path='/data/media/inbox/edit_'+id+'_'+safe;
    if(!queue.has(id))queue.set(id,{route:'DOWNLOAD',ID_MIDIA:id,DRIVE_FILE_ID:norm(m.DRIVE_FILE_ID),
                                      ARQUIVO:norm(m.ARQUIVO||safe),kind,worker_source_path:path});
  }
}
return [...queue.values()].map(json=>({json}));
""")
route("ROUTE — SOURCE QUEUE", -400, 0, "route", ["DOWNLOAD", "NO_WORK"])
add("DOWNLOAD — ORIGINAL MEDIA", "n8n-nodes-base.googleDrive", -200, -160,
    {"resource":"file","operation":"download",
     "fileId":{"__rl":True,"value":"={{ $json.DRIVE_FILE_ID }}","mode":"id"},
     "options":{"binaryPropertyName":"data","fileName":"={{ $json.ARQUIVO }}"}},
    opts={"credentials":{"googleDriveOAuth2Api":{"id":"ZG0KCgnKM9HjrMsm","name":"Google Drive account"}},
          "retryOnFail":True,"maxTries":3,"waitBetweenTries":5000,"onError":"stopWorkflow"})
add("WRITE — ORIGINAL MEDIA TEMP", "n8n-nodes-base.readWriteFile", 0, -160,
    {"operation":"write","fileName":"={{ $json.worker_source_path }}","dataPropertyName":"data","options":{}},
    opts={"retryOnFail":True,"maxTries":2,"waitBetweenTries":1000,"onError":"stopWorkflow"})
code("BUILD — EDIT PREVIEW JOBS", 200, -160, """
const written=$input.all().map(i=>i.json),contents=$('READ — 04_CONTEUDOS').all().map(i=>i.json),
  map=new Map(written.map(x=>[String(x.ID_MIDIA),x]));
const chosen=contents.filter(c=>String(c.EDIT_SESSION_STATUS||'').trim().toUpperCase()==='SAVED'
  &&String(c.REVISION_MODE||'').trim().toUpperCase()==='MANUAL_EDIT'
  &&String(c.PIPELINE_STATE||'').trim().toUpperCase()==='EDIT_SESSION_READY');
return chosen.map(c=>{
  const ids=[...new Set(String(c.BRUTOS_USADOS||'').match(/M\\d{4,}/g)||[])];
  const sources=ids.map(id=>map.get(id));
  if(!ids.length||sources.some(x=>!x))throw new Error('SM3_07F_SOURCE_WRITE_INCOMPLETE:'+c.ID_CONTEÚDO);
  return {json:{project_id:String(c.ID_PROJETO),content_id:String(c.ID_CONTEÚDO),
    edit_session_id:String(c.EDIT_SESSION_ID),sheet_render_status:String(c.RENDER_STATUS||'').trim(),
    source_media:sources.map(x=>({media_id:x.ID_MIDIA,kind:x.kind,source_path:x.worker_source_path,file_name:x.ARQUIVO}))}};
});
""")
add("WORKER — GET SAVED WORKSPACE", "n8n-nodes-base.httpRequest", 400, -160,
    {"url":"={{ 'http://media-worker:8090/production/editor-workspace/' + encodeURIComponent($json.project_id) + '/' + encodeURIComponent($json.content_id) + '/' + encodeURIComponent($json.edit_session_id) }}",
     "options":{"timeout":30000}})
code("ASSERT — REVISION AND SOURCES", 600, -160, """
const w=$json, job=$('BUILD — EDIT PREVIEW JOBS').all().map(i=>i.json).find(x=>x.edit_session_id===w.edit_session_id);
if(!job||w.ok!==true||w.status!=='SAVED'||w.current_revision<2||w.read_only!==false||
   w.workspace_contract_version!=='SM3_EDITOR_WORKSPACE_V1'||
   !/^[a-f0-9]{64}$/.test(String(w.state_etag||''))||w.project_id!==job.project_id||
   w.content_id!==job.content_id||w.preview?.verified!==true)
   throw new Error('SM3_07F_WORKSPACE_REVISION_INVALID:'+String(w.edit_session_id));
const required=new Set([...(w.recipe?.media_order||[]),...(w.recipe?.timeline||[]).map(x=>x.media_id)]);
const sources=job.source_media.filter(x=>required.has(x.media_id));
if(!required.size||required.size!==sources.length||new Set(sources.map(x=>x.media_id)).size!==required.size)
   throw new Error('SM3_07F_RECIPE_SOURCE_MISMATCH:'+w.content_id);
return {json:{...job,source_media:sources,expected_revision:w.current_revision,expected_state_etag:w.state_etag,fps:24,max_seconds:12}};
""", "runOnceForEachItem")
add("WORKER — RENDER SAVED REVISION", "n8n-nodes-base.httpRequest", 800, -160,
    {"method":"POST","url":"http://media-worker:8090/production/edit-session/render-preview",
     "sendBody":True,"contentType":"json","specifyBody":"json",
     "jsonBody":"={{ {project_id:$json.project_id,content_id:$json.content_id,edit_session_id:$json.edit_session_id,expected_revision:$json.expected_revision,expected_state_etag:$json.expected_state_etag,source_media:$json.source_media,fps:$json.fps,max_seconds:$json.max_seconds} }}",
     "options":{"timeout":1800000}},
    opts={"retryOnFail":True,"maxTries":2,"waitBetweenTries":5000,"onError":"stopWorkflow"})
code("ASSERT — RENDER RESULT", 1000, -160, """
const m=$json, job=$('ASSERT — REVISION AND SOURCES').all().map(i=>i.json).find(x=>x.edit_session_id===m.edit_session_id);
if(!job||m.ok!==true||m.contract_version!=='SM3_EDIT_PREVIEW_V1'||m.project_id!==job.project_id||
  m.content_id!==job.content_id||m.revision!==job.expected_revision||
  m.state_etag!==job.expected_state_etag||m.preview_bytes<100||
  !/^[a-f0-9]{64}$/.test(String(m.preview_sha256||''))||m.final_render!==false)
  throw new Error('SM3_07F_RENDER_RESULT_INVALID:'+String(m.edit_session_id));
return {json:{project_id:m.project_id,content_id:m.content_id,edit_session_id:m.edit_session_id,
  revision:m.revision,etag:m.state_etag,preview_sha256:m.preview_sha256,
  sheet_render_status:job.sheet_render_status,reused_existing:m.reused_existing===true}};
""", "runOnceForEachItem")
add("WORKER — VERIFY PERSISTED PREVIEW", "n8n-nodes-base.httpRequest", 1200, -160,
    {"url":"={{ 'http://media-worker:8090/production/edit-session/preview/' + encodeURIComponent($json.project_id) + '/' + encodeURIComponent($json.content_id) + '/' + encodeURIComponent($json.edit_session_id) + '/' + $json.revision }}",
     "options":{"timeout":30000}})
code("ASSERT — PREVIEW COMMITTED", 1400, -160, """
const v=$json, original=$('ASSERT — RENDER RESULT').all().map(i=>i.json).find(x=>x.edit_session_id===v.edit_session_id);
if(!original||v.ok!==true||v.contract_version!=='SM3_EDIT_PREVIEW_V1'||
   v.preview_sha256!==original.preview_sha256||v.state_etag!==original.etag||
   v.revision!==original.revision||v.content_id!==original.content_id||
   !String(v.asset_url||'').endsWith('/asset'))
   throw new Error('SM3_07F_PERSISTENCE_MISMATCH:'+String(v.edit_session_id));
return {json:{route:original.sheet_render_status==='EDIT_PREVIEW_READY'?'NO_WRITE':'WRITE',
  ID_CONTEÚDO:v.content_id,edit_session_id:v.edit_session_id,revision:v.revision,
  preview_sha256:v.preview_sha256,RENDER_STATUS:'EDIT_PREVIEW_READY',
  STATE_UPDATED_AT:new Date().toISOString(),asset_url:'http://localhost:8090'+v.asset_url,
  reused_existing:original.reused_existing}};
""", "runOnceForEachItem")
route("ROUTE — SHEET COMMIT", 1600, -160, "route", ["WRITE", "NO_WRITE"])
update = copy.deepcopy(update_template)
fields = ["ID_CONTEÚDO", "RENDER_STATUS", "STATE_UPDATED_AT"]
update["parameters"]["columns"]["value"] = {key:"={{ $json."+key+" }}" for key in fields}
update["parameters"]["columns"]["schema"] = [s for s in update["parameters"]["columns"]["schema"] if s["id"] in fields]
add("UPDATE — EDIT PREVIEW READY", "n8n-nodes-base.googleSheets", 1800, -300, base=update)
read_sheet("VERIFY READ — 04_CONTEUDOS", 733071962, "04_CONTEUDOS", 2000, -300)
code("ASSERT — SHEET COMMITTED", 2200, -300, """
const rows=$input.all().map(i=>i.json),items=$('ASSERT — PREVIEW COMMITTED').all().map(i=>i.json).filter(x=>x.route==='WRITE');
for(const item of items){const matches=rows.filter(r=>String(r.ID_CONTEÚDO||'')===item.ID_CONTEÚDO);
 if(matches.length!==1||matches[0].RENDER_STATUS!=='EDIT_PREVIEW_READY'||
    matches[0].EDIT_SESSION_STATUS!=='SAVED'||matches[0].REVISION_MODE!=='MANUAL_EDIT'||
    !String(matches[0].STATE_UPDATED_AT||''))
    throw new Error('SM3_07F_SHEET_PERSISTENCE_FAILED:'+item.ID_CONTEÚDO);
}
return [{json:{status:'SM3_07F_EDIT_PREVIEW_VERIFIED_COMMIT',committed_count:items.length,
  previews:items.map(x=>({content_id:x.ID_CONTEÚDO,revision:x.revision,preview_sha256:x.preview_sha256,asset_url:x.asset_url}))}}];
""")
code("AUDIT — PREVIEW ALREADY COMMITTED", 1800, 80, """
return $input.all().map(i=>({json:{status:'SM3_07F_ALREADY_COMMITTED',content_id:i.json.ID_CONTEÚDO,
 revision:i.json.revision,preview_sha256:i.json.preview_sha256,asset_url:i.json.asset_url}}));
""")
code("AUDIT — NO SAVED REVISIONS", -200, 100, """
return [{json:{status:'NO_SAVED_MANUAL_EDITS'}}];
""")

chain = ["MANUAL — RENDER EDIT PREVIEWS","WORKER — HEALTH 2.6.0",
         "ASSERT — EDIT PREVIEW CONTRACT","READ — 04_CONTEUDOS","READ — 03_MIDIAS",
         "BUILD — EDIT SOURCE QUEUE","ROUTE — SOURCE QUEUE"]
for a,b in zip(chain,chain[1:]):link(a,b)
link("ROUTE — SOURCE QUEUE","DOWNLOAD — ORIGINAL MEDIA",0)
link("ROUTE — SOURCE QUEUE","AUDIT — NO SAVED REVISIONS",1)
chain = ["DOWNLOAD — ORIGINAL MEDIA","WRITE — ORIGINAL MEDIA TEMP","BUILD — EDIT PREVIEW JOBS",
         "WORKER — GET SAVED WORKSPACE","ASSERT — REVISION AND SOURCES",
         "WORKER — RENDER SAVED REVISION","ASSERT — RENDER RESULT",
         "WORKER — VERIFY PERSISTED PREVIEW","ASSERT — PREVIEW COMMITTED","ROUTE — SHEET COMMIT"]
for a,b in zip(chain,chain[1:]):link(a,b)
link("ROUTE — SHEET COMMIT","UPDATE — EDIT PREVIEW READY",0)
link("ROUTE — SHEET COMMIT","AUDIT — PREVIEW ALREADY COMMITTED",1)
link("UPDATE — EDIT PREVIEW READY","VERIFY READ — 04_CONTEUDOS")
link("VERIFY READ — 04_CONTEUDOS","ASSERT — SHEET COMMITTED")

workflow={"name":"PROJETO SM3 — 07F — EDIT PREVIEWS — v1 VERIFIED COMMIT",
          "nodes":nodes,"connections":edges,"pinData":{},"settings":{"executionOrder":"v1"},
          "active":False,"versionId":str(uuid4()),"meta":{"templateCredsSetupCompleted":True}}
target=package / "PROJETO_SM3_07F_EDIT_PREVIEWS_v1_VERIFIED_COMMIT.json"
target.write_text(json.dumps(workflow,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(target.name, len(nodes), "nodes")
