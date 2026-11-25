"""Reversible cuts and framing. Render a draft from local media without changing inputs."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
import math
import subprocess
import tempfile
import threading
import uuid
from urllib.parse import urlparse
import requests
from pathlib import Path

from fastapi import HTTPException
import encoders


def media_path(data, key):
    if not isinstance(key, str) or not key.isalnum():
        raise ValueError("Choose a local video.")
    path = data / (key + ".mp4")
    if not path.is_file():
        raise ValueError("A draft source is missing.")
    return path


def ff(args):
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode:
        raise ValueError(proc.stderr[-700:] or "Media processing failed.")
    return proc.stdout


def assemble(data, rows, output, probe, update, music=None):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 240:
        raise ValueError("Choose 1 to 240 timeline segments.")
    metadata = {}
    total = 0
    plan = []
    for row in rows:
        path = media_path(data, row["id"])
        picture = media_path(data, row["broll"]) if row.get("broll") else path
        for media in (picture, path):
            if media not in metadata:
                metadata[media] = probe(media)
        start, end = float(row["start"]), float(row["end"])
        if not 0 <= start < end <= metadata[path]["duration"] + .05 or end-start < .08:
            raise ValueError("A cut falls outside its source or is shorter than 0.08 seconds.")
        center = float(row.get("center", .5))
        zoom = float(row.get("zoom", 1))
        if not 0 <= center <= 1 or not 1 <= zoom <= 2:
            raise ValueError("Invalid framing.")
        speed=float(row.get("speed",1))
        freeze=float(row.get("freeze",0))
        if not .5<=speed<=2 or not 0<=freeze<=3:
            raise ValueError("Choose a speed from 0.5 to 2 and a freeze of up to 3 seconds.")
        total += (end-start)/speed+freeze
        if total > 1800:
            raise ValueError("Choose up to 30 minutes per timeline export.")
        plan.append((path,picture,start,end-start,center,zoom,bool(row.get("cue")),speed,freeze))
    with tempfile.TemporaryDirectory(dir=data) as temp:
        folder = Path(temp)
        available = encoders.h264()
        audio = {}
        for path in {entry[0] for entry in plan}:
            audio[path]=bool(ff(["ffprobe","-v","error","-select_streams","a:0","-show_entries","stream=index","-of","csv=p=0",str(path)]).strip())
        workers=1
        if available[0][1]=="h264_nvenc" and len(plan)>1:
            try:
                free_mib=int(ff(["nvidia-smi","--query-gpu=memory.free","--format=csv,noheader,nounits"]).splitlines()[0])
                # Local 1080x1920 benchmark: ~250 MiB per encoder. Leave 640 MiB for open desktop apps.
                workers=max(1,min(len(plan),os.cpu_count() or 1,(free_mib-640)//260))
            except (OSError,ValueError,IndexError):
                pass
        def render_one(entry):
            index,(path,picture,start,length,center,zoom,cue,speed,freeze)=entry
            update(f"Rendering segment {index+1} of {len(plan)}")
            cmd = ["ffmpeg","-nostdin","-y","-v","error","-ss",str(start),"-i",str(path)]
            vi,ai = 0,0
            if picture != path:
                cmd += ["-stream_loop","-1","-i",str(picture)]
                vi = 1
            if not audio[path]:
                ai = vi+1
                cmd += ["-f","lavfi","-i","anullsrc=r=48000:cl=stereo"]
            # x denotes the centre of the source crop, as in the studio preview.
            video = (f"[{vi}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                     f"crop=trunc(1080/{zoom}/2)*2:trunc(1920/{zoom}/2)*2:"
                     f"max(0\\,min(iw-ow\\,iw*{center}-ow/2)):(ih-oh)/2,"
                     f"scale=1080:1920,setsar=1,trim=duration={length},setpts=(PTS-STARTPTS)/{speed},"
                     f"tpad=stop_mode=clone:stop_duration={freeze},fps=30,format=yuv420p[v]")
            sound = f"[{ai}:a]atrim=duration={length},asetpts=PTS-STARTPTS,atempo={speed},aresample=48000,aformat=channel_layouts=stereo,apad"
            if cue:
                sound += "[bed];sine=frequency=720:duration=0.09,afade=t=out:st=0.02:d=0.07,volume=0.3[tone];[bed][tone]amix=inputs=2:duration=first:normalize=0"
            graph = video + ";" + sound + "[a]"
            target = folder/f"{index}.mov"
            for codec in available:
                try:
                    ff(cmd+["-filter_complex",graph,"-map","[v]","-map","[a]","-t",str(length/speed+freeze),*codec,"-c:a","pcm_s16le","-ar","48000","-ac","2",str(target)])
                    break
                except ValueError:
                    if codec == available[-1]:
                        raise
            # Keep segments uniform, including the video codec and audio layout.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for _ in pool.map(render_one,enumerate(plan)):
                pass
        manifest = folder/"cuts.txt"
        manifest.write_text("".join(f"file '{i}.mov'\n" for i in range(len(plan))),encoding="utf-8")
        command=["ffmpeg","-nostdin","-y","-v","error","-f","concat","-safe","1","-i",str(manifest)]
        if music:
            from styling import asset_path
            track=asset_path(data,music,"audio")
            if not track:raise ValueError("Music file is unavailable. Import it again.")
            graph=("[0:a]asplit=2[voice][key];[1:a]volume=0.20[bed];"
                   "[bed][key]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=300[duck];"
                   "[voice][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.98[a]")
            command+=["-stream_loop","-1","-i",str(track),"-filter_complex",graph,"-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-shortest"]
        else:command+=["-c:v","copy","-c:a","aac","-b:a","160k"]
        ff(command+["-movflags","+faststart",str(output)])


def attach(app, data, state, probe):
    def stock_api(path,params=None):
        key=os.getenv("BLOOMCLIPPING_PEXELS_KEY")
        if not key:raise HTTPException(409,"Configure BLOOMCLIPPING_PEXELS_KEY for stock search, or import your own B-roll.")
        try:
            result=requests.get("https://api.pexels.com/videos/"+path,params=params,headers={"Authorization":key},timeout=20,allow_redirects=False)
            result.raise_for_status()
            return result.json()
        except (requests.RequestException,ValueError):
            raise HTTPException(502,"Pexels did not return a result. Check the key and connection.") from None

    @app.get("/studio/stock")
    def stock(q:str):
        if not 1<=len(q.strip())<=120:raise HTTPException(400,"Enter a short footage search.")
        videos=stock_api("search",{"query":q,"orientation":"portrait","per_page":8}).get("videos",[])
        return [{"id":v["id"],"author":v.get("user",{}).get("name","Pexels"),"page":v["url"],"duration":v["duration"]} for v in videos]

    @app.post("/studio/stock/{stock_id}")
    def import_stock(stock_id:int):
        if stock_id<=0:raise HTTPException(400,"Choose a stock video.")
        row=stock_api("videos/"+str(stock_id))
        choices=[f for f in row.get("video_files",[]) if f.get("file_type")=="video/mp4" and f.get("width") and f.get("height")]
        if not choices:raise HTTPException(404,"This video has no MP4 rendition.")
        file=min(choices,key=lambda f:abs(min(f["width"],f["height"])-1080))
        url=file["link"];parsed=urlparse(url)
        if parsed.scheme!="https" or parsed.hostname not in ("videos.pexels.com","player.vimeo.com"):
            raise HTTPException(422,"Pexels returned an unsupported media host.")
        key=uuid.uuid4().hex;target=data/(key+".mp4")
        try:
            with requests.get(url,stream=True,timeout=(10,60),allow_redirects=False) as response:
                if response.status_code!=200:raise ValueError("Footage is unavailable from this CDN.")
                with target.open("wb") as output:
                    for chunk in response.iter_content(1024*1024):
                        output.write(chunk)
                        if output.tell()>512*1024**2:raise ValueError("This rendition exceeds the 512 MB stock import limit.")
            meta=probe(target)
        except Exception:
            target.unlink(missing_ok=True)
            raise HTTPException(502,"Stock import failed. Choose another rendition or import a file.") from None
        return {"id":key,**meta,"credit":row.get("user",{}).get("name","Pexels"),"page":row["url"]}

    @app.get("/studio/source/{key}")
    def source(key:str):
        try:return probe(media_path(data,key))
        except ValueError as error:raise HTTPException(400,str(error)) from error

    @app.post("/studio/render")
    def render(body: dict):
        rows = body.get("segments")
        if not isinstance(rows,list) or not rows:
            raise HTTPException(400,"Add a segment first.")
        job = uuid.uuid4().hex
        state[job] = {"status":"running","stage":"Preparing timeline"}
        def run():
            output = data/(job+".mp4")
            try:
                assemble(data,rows,output,probe,lambda message:state[job].update(stage=message),body.get("music"))
                meta = probe(output)
                result = {"status":"done","file":job,"meta":meta}
                # An assembled export is a new editable flat source with a separate cut list.
                record = {"source":job,"settings":{"title":str(body.get("title") or "Timeline edit")[:150],
                          "start":0,"end":meta["duration"],"layout":"fill","cam":{"x":0,"y":0,"w":1,"h":1},
                          "game":{"x":0,"y":0,"w":1,"h":1},"words":[]},"segments":rows,"result":result}
                (data/(job+".json")).write_text(json.dumps(record),encoding="utf-8")
                state[job] = result
            except Exception as error:
                output.unlink(missing_ok=True)
                state[job] = {"status":"error","error":str(error)}
        threading.Thread(target=run,daemon=True).start()
        return {"job":job}
