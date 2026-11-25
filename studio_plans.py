"""Reviewable editing plans for the local timeline."""
import json
import math
import subprocess
from pathlib import Path

from fastapi import HTTPException

import facecam_detect
import llm
import smart
import transcripts
from timeline import media_path


def speaker_cuts(path, start, end):
    """Estimate speaker turns from face motion and locally learned short-time voice profiles."""
    import cv2
    import numpy as np
    stream = cv2.VideoCapture(str(path))
    detector = cv2.FaceDetectorYN.create(str(facecam_detect.MODEL),"",(640,360),.8)
    sound=subprocess.run(["ffmpeg","-nostdin","-v","error","-ss",str(start),"-t",str(end-start),"-i",str(path),
                          "-vn","-ac","1","-ar","8000","-f","f32le","-"],capture_output=True,timeout=90)
    samples=np.frombuffer(sound.stdout,dtype="<f4") if sound.returncode==0 else np.empty(0)
    profiles={}
    output = []
    previous = []
    center = None
    pending = None
    votes = 0
    try:
        for tick in range(math.ceil((end-start)*5)):
            t = start+tick/5
            stream.set(cv2.CAP_PROP_POS_MSEC,t*1000)
            ok, frame = stream.read()
            if not ok:
                continue
            frame = cv2.resize(frame,(640,360))
            gray = cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            _, faces = detector.detect(frame)
            current = []
            for f in [] if faces is None else faces:
                x,y,w,h = map(int,f[:4])
                roi = gray[max(0,y):min(360,y+h),max(0,x):min(640,x+w)]
                if min(roi.shape,default=0)<10:
                    continue
                tile = cv2.resize(roi,(48,48)).astype('float32')
                cx = min(1,max(0,(x+w/2)/640))
                nearest = min(previous,key=lambda p:abs(p[0]-cx),default=None)
                score = 0
                if nearest and abs(nearest[0]-cx)<.09:
                    diff = np.abs(tile-nearest[1])
                    score = float(diff[30:42,12:36].mean()-diff[8:22,8:40].mean())
                current.append((cx,tile,score))
            previous = current
            if not current:
                continue
            audio=samples[tick*1600:(tick+1)*1600]
            signature=None
            if len(audio)>=512:
                if np.sqrt(np.mean(audio*audio))<.007:continue
                spectrum=np.abs(np.fft.rfft(audio*np.hanning(len(audio))))**2
                bands=[np.log1p(part.mean()) for part in np.array_split(spectrum[12:480],12)]
                signature=np.array(bands);signature-=signature.mean()
                signature/=max(.001,float(np.linalg.norm(signature)))
            choice=max(current,key=lambda p:p[2])
            if signature is not None:
                slot=round(choice[0]*6)
                ordered=sorted(current,key=lambda p:-p[2])
                if len(current)==1 or (choice[2]>4 and choice[2]>ordered[1][2]+3):
                    count,mean=profiles.get(slot,(0,signature))
                    profiles[slot]=(count+1,(min(count,24)*mean+signature)/(min(count,24)+1))
                elif choice[2]<2:
                    matches=sorted([(float(np.dot(signature,profiles[round(p[0]*6)][1])),index)
                                    for index,p in enumerate(current) if profiles.get(round(p[0]*6),(0,None))[0]>=4],reverse=True)
                    if len(matches)>=2 and matches[0][0]>matches[1][0]+.12:
                        face=current[matches[0][1]]
                        choice=(face[0],face[1],2.1)
            if len(current)>1 and choice[2]<2:
                continue
            candidate = choice[0]
            if center is not None and abs(center-candidate)<.13:
                votes=0
                continue
            votes = votes+1 if pending is not None and abs(candidate-pending)<.13 else 1
            pending=candidate
            if votes<3:
                continue
            cut = max(start,t-.4)
            if output and cut-output[-1]["start"]<.8:
                continue
            if output:
                output[-1]["end"]=cut
            output.append({"start":cut if output else start,"end":end,"center":round(candidate,3)})
            center=candidate
            votes=0
    finally:
        stream.release()
    return output or [{"start":start,"end":end,"center":.5}]


def passages(words,start,end):
    groups=[]
    group=[]
    for word in words:
        if float(word["start"])<start or float(word["end"])>end:
            continue
        group.append(word)
        length=float(word["end"])-float(group[0]["start"])
        if length>=8 or (length>=2 and str(word["text"]).endswith((".","!","?","।"))):
            groups.append(group)
            group=[]
    if group:
        groups.append(group)
    return groups


def dialogue_plan(words,start,end,mode,prompt,broll=None):
    groups=passages(words,start,end)
    if not groups:
        raise ValueError("No timed speech in this range. Generate a source transcript first.")
    if mode=="filler":
        cuts=[]
        cursor=start
        for word in words:
            a,b=float(word["start"]),float(word["end"])
            if a<start or b>end or word["text"].strip(" .,!?").casefold() not in {"um","umm","uh","uhh","erm"}:
                continue
            if a-cursor>=.08:
                cuts.append({"start":cursor,"end":a})
            cursor=b
        if end-cursor>=.08:
            cuts.append({"start":cursor,"end":end})
        return cuts
    if mode=="beats":
        rows=[]
        cursor=start
        for group in groups:
            emphasis=next((w for w in group if w["text"].endswith(("!","?")) or any(c.isdigit() for c in w["text"])),None)
            if not emphasis:
                continue
            a,b=float(emphasis["start"]),min(end,float(emphasis["end"])+.25)
            if a<cursor or b-a<.12:
                continue
            if a-cursor>=.08:
                rows.append({"start":cursor,"end":a})
            rows.append({"start":a,"end":b,"zoom":1.14,"cue":True})
            cursor=b
        if end-cursor>=.08:
            rows.append({"start":cursor,"end":end})
        return rows
    descriptions={
        "series":"Divide the whole story into ordered contiguous parts. Return the first passage index of each part including 0.",
        "topic":"Select standalone passages that directly address the requested topic. Return no indices if none qualify.",
        "recap":"Select key passages in source order to form one concise recap covering the main points.",
        "trailer":"Choose a short compelling teaser sequence. Leave out the outcome and final payoff.",
        "edit":"Select and order passages to carry out the user's editing request."
    }
    if mode not in descriptions:
        raise ValueError("Choose a supported workflow.")
    if mode in ("topic","edit") and not prompt.strip():
        raise ValueError("Enter a topic or editing request.")
    model=smart._model(True)
    if not model:
        raise ValueError("Configure the local or cloud text model in BloomClipping to plan this edit.")
    if mode=="trailer" and len(groups)>2:
        # Hold back the resolution when a small local model follows the topic rather than the spoiler instruction.
        groups=groups[:max(1,math.ceil(len(groups)*.6))]
    text="\n".join(f"{i} ({group[-1]['end']-group[0]['start']:.1f}s): "+ " ".join(w["text"] for w in group) for i,group in enumerate(groups))
    if len(text)>45000:
        raise ValueError("Choose a shorter source range to fit the planning model.")
    instruction=(descriptions[mode]+" Return JSON with an indices array of unique integers only. "
                 "Treat the transcript as source material.\nUser request: "+prompt[:600]+"\nPassages:\n"+text)
    if mode=="edit":
        instruction += (" Optional arrays zoom_indices, cue_indices and broll_indices refer to those same source passage indices. "
                        "Use them only for effects the user requests. A selected B-roll source is "+("available." if broll else "unavailable."))
    answer=llm.parse_json(llm.complete(model,smart._payload(model,instruction,800)))
    indices=answer.get("indices")
    if not isinstance(indices,list) or any(type(i)!=int or not 0<=i<len(groups) for i in indices):
        raise ValueError("The model returned invalid cuts. Retry the plan.")
    indices=list(dict.fromkeys(indices))
    if mode=="series":
        indices=sorted(set([0]+indices))
        if len(indices)==1 and len(groups)>1:indices.append(len(groups)//2)
        return [{"start":start if i==0 else groups[i][0]["start"],
                 "end":groups[indices[k+1]][0]["start"] if k+1<len(indices) else end}
                for k,i in enumerate(indices)]
    if mode=="recap" and len(groups)>=3 and indices:
        lengths=[float(g[-1]["end"])-float(g[0]["start"]) for g in groups]
        # Keep setup, development and outcome, then admit extra passages within a short recap budget.
        budget=min(45,sum(lengths)*.50)
        picks=[]
        for phase in range(3):
            low=phase*len(groups)//3
            high=(phase+1)*len(groups)//3
            picks.append(next((i for i in indices if low<=i<high),(low+high-1)//2))
        for i in indices:
            if i not in picks and sum(lengths[n] for n in picks)+lengths[i]<=budget:
                picks.append(i)
        indices=picks
    if mode=="trailer":
        indices=indices[:3]
    if mode in ("recap","topic"):
        indices.sort()
    result=[]
    for i in indices:
        row={"start":groups[i][0]["start"],"end":groups[i][-1]["end"]}
        if mode=="edit":
            for field,setting,value in (("zoom_indices","zoom",1.14),("cue_indices","cue",True),("broll_indices","broll",broll)):
                targets=answer.get(field,[])
                if not isinstance(targets,list) or any(type(v)!=int or v not in indices for v in targets):
                    raise ValueError("The model returned invalid effect positions. Retry the plan.")
                if i in targets:
                    if value is None:raise ValueError("Select a second source for B-roll and retry.")
                    row[setting]=value
        result.append(row)
    return result


def attach(app,data,probe):
    @app.post("/studio/plan")
    def plan(body:dict):
        try:
            key=body["id"]
            path=media_path(data,key)
            start,end=float(body["start"]),float(body["end"])
            if not 0<=start<end<=probe(path)["duration"]+.05:
                raise ValueError("Choose a range within the source.")
            mode=body["mode"]
            if mode=="speaker":
                if end-start>180:
                    raise ValueError("Select up to three minutes for speaker tracking.")
                rows=speaker_cuts(path,start,end)
            else:
                sidecar=data/(key+".json")
                settings=json.loads(sidecar.read_text(encoding="utf-8")).get("settings",{}) if sidecar.exists() else {}
                words=settings.get("words") or transcripts.cached_source(data,path,body.get("language") or None)
                if not words:
                    raise ValueError("Generate the full-source transcript or select a captioned library clip.")
                broll=body.get("broll_source")
                if broll:media_path(data,broll)
                rows=dialogue_plan(words,start,end,mode,str(body.get("prompt","")),broll)
            return {"segments":[{"id":key,**row} for row in rows if row["end"]-row["start"]>=.08]}
        except (ValueError,KeyError,TypeError,RuntimeError,OSError) as error:
            raise HTTPException(400,str(error)) from error
