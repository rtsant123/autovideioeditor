#!/usr/bin/env python3
"""
Web layer for Railway: upload a script, choose a size, get ORDERED CLIPS (zip).

Generation runs in a background thread; the page polls /status until done,
then offers the zip of numbered clips (01.mp4, 02.mp4, ...) + shotlist.txt
for your video editor.

Railway start command:
    uvicorn app:app --host 0.0.0.0 --port $PORT
"""

import uuid
import threading
import pathlib

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

import engine

app = FastAPI(title="Auto Clip Engine")
JOBS = {}  # job_id -> {status, error}


def _worker(job_id, script_text, size):
    JOBS[job_id]["status"] = "running"
    try:
        engine.run(script_text, size=size, project=job_id)
        JOBS[job_id]["status"] = "done"
    except Exception as e:
        JOBS[job_id].update(status="error", error=str(e))


PAGE = """
<!doctype html><meta charset=utf-8>
<title>Script to Clips</title>
<style>
 body{font-family:system-ui;max-width:560px;margin:40px auto;padding:0 16px}
 h1{font-size:20px} textarea{width:100%;height:200px;font:14px monospace}
 select,button{padding:8px 12px;font-size:15px;margin-top:10px}
 button{background:#111;color:#fff;border:0;border-radius:8px;cursor:pointer}
 .row{margin-top:12px} #status{min-height:24px}
</style>
<h1>Script &rarr; Ordered Clips</h1>
<textarea id=script placeholder="Paste your script (any topic)..."></textarea>
<div class=row>
 Size:
 <select id=size>
   <option value=vertical>Vertical 9:16 (Shorts/Reels)</option>
   <option value=landscape>Landscape 16:9 (YouTube)</option>
   <option value=square>Square 1:1</option>
 </select>
</div>
<div class=row><button onclick=go()>Generate clips</button></div>
<div class=row id=status></div>
<script>
let timer=null;
async function go(){
  const s=document.getElementById('script').value.trim();
  if(!s){alert('Paste a script first');return;}
  const fd=new FormData();
  fd.append('script_text',s);
  fd.append('size',document.getElementById('size').value);
  setStatus('Starting...');
  const r=await fetch('/generate',{method:'POST',body:fd});
  const j=await r.json();
  poll(j.job);
}
function poll(job){
  clearInterval(timer);
  timer=setInterval(async()=>{
    const r=await fetch('/status/'+job);
    const j=await r.json();
    if(j.status==='done'){
      clearInterval(timer);
      setStatus('Done. <a href="/download/'+job+'" download>Download clips (zip)</a>');
    }else if(j.status==='error'){
      clearInterval(timer);
      setStatus('Error: '+j.error);
    }else{
      setStatus('Working... ('+j.status+')');
    }
  },4000);
}
function setStatus(html){document.getElementById('status').innerHTML=html;}
</script>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE


@app.post("/generate")
def generate(script_text: str = Form(...), size: str = Form("vertical")):
    job_id = "job_" + uuid.uuid4().hex[:8]
    JOBS[job_id] = {"status": "queued", "error": None}
    threading.Thread(target=_worker, args=(job_id, script_text, size),
                     daemon=True).start()
    return {"job": job_id}


@app.get("/status/{job}")
def status(job: str):
    return JOBS.get(job, {"status": "unknown"})


@app.get("/download/{job}")
def download(job: str):
    path = pathlib.Path("output") / job / "clips.zip"
    if not path.exists():
        return JSONResponse(status_code=404, content={"error": "not found"})
    return FileResponse(path, media_type="application/zip", filename=f"{job}_clips.zip")
