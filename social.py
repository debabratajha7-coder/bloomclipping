"""Optional direct publishing. Tokens stay in the process environment."""
import json
import math
from contextlib import contextmanager
import os
import sqlite3
import threading
import time
import uuid
from urllib.parse import urlparse

from fastapi import HTTPException
import requests

from timeline import media_path

YT = "https://www.googleapis.com/youtube/v3"
IG = "https://graph.instagram.com/v26.0"
TT = "https://open.tiktokapis.com/v2"
PLATFORMS = ("youtube","instagram","tiktok")


from social_accounts import access_token as token


def call(method,url,platform=None,**kwargs):
    headers=kwargs.pop("headers",{})
    if platform:
        headers={**headers,"Authorization":"Bearer "+token(platform)}
    try:
        response=requests.request(method,url,headers=headers,timeout=(10,120),allow_redirects=False,**kwargs)
    except requests.RequestException:
        raise ValueError("Platform connection failed. Check the post on the platform before retrying.") from None
    if not 200<=response.status_code<300:
        raise ValueError(f"Platform returned HTTP {response.status_code}. Check authorization, post settings and platform history.")
    return response


def tt(path,body):
    result=call("POST",TT+path,"tiktok",json=body).json()
    if result.get("error",{}).get("code")!="ok":
        raise ValueError("TikTok declined the request: "+str(result.get("error",{}).get("code","unknown"))[:80])
    return result["data"]


def account(platform):
    if platform=="youtube":
        items=call("GET",YT+"/channels",platform,params={"part":"snippet","mine":"true"}).json()["items"]
        if not items:raise ValueError("No YouTube channel is connected.")
        return {"id":items[0]["id"],"name":items[0]["snippet"]["title"],"privacy":["private","unlisted","public"]}
    if platform=="instagram":
        row=call("GET",IG+"/me",platform,params={"fields":"user_id,username"}).json()
        return {"id":str(row["user_id"]),"name":row["username"],"privacy":["account visibility"]}
    if platform=="tiktok":
        row=tt("/post/publish/creator_info/query/",{})
        return {"id":row["creator_username"],"name":row["creator_nickname"],"privacy":row["privacy_level_options"],
                "max_duration":row["max_video_post_duration_sec"]}
    raise ValueError("Choose YouTube, Instagram or TikTok.")


def upload_url(value,hosts):
    parsed=urlparse(value)
    if parsed.scheme!="https" or parsed.username or parsed.hostname not in hosts:
        raise ValueError("Platform returned an unexpected upload destination.")
    return value


def publish(row,data):
    platform=row["platform"]
    acct=account(platform)
    if acct["id"]!=row["account"] or row["privacy"] not in acct["privacy"]:
        raise ValueError("The destination account or visibility choices changed.")
    media=media_path(data,row["clip"])
    size=media.stat().st_size
    if platform=="youtube":
        response=call("POST","https://www.googleapis.com/upload/youtube/v3/videos",platform,
                      params={"uploadType":"resumable","part":"snippet,status"},
                      headers={"X-Upload-Content-Length":str(size),"X-Upload-Content-Type":"video/mp4"},
                      json={"snippet":{"title":row["title"][:100],"description":row["title"]},
                            "status":{"privacyStatus":row["privacy"]}})
        dest=upload_url(response.headers["Location"],{"www.googleapis.com","youtube.googleapis.com"})
        with media.open("rb") as file:
            return call("PUT",dest,platform,data=file,headers={"Content-Type":"video/mp4"}).json()["id"]
    if platform=="instagram":
        source=row["media_url"]
        if not source.startswith("https://"):
            raise ValueError("Instagram requires the public HTTPS URL of this exact export.")
        endpoint=IG+"/"+acct["id"]
        container=call("POST",endpoint+"/media",platform,data={"media_type":"REELS","video_url":source,"caption":row["title"]}).json()["id"]
        for _ in range(60):
            status=call("GET",IG+"/"+container,platform,params={"fields":"status_code"}).json()["status_code"]
            if status=="FINISHED":break
            if status in ("ERROR","EXPIRED"):raise ValueError("Instagram could not prepare this Reel.")
            time.sleep(5)
        else:raise ValueError("Instagram timed out preparing the Reel.")
        return call("POST",endpoint+"/media_publish",platform,data={"creation_id":container}).json()["id"]
    chunk=min(size,16*1024*1024)
    count=size//chunk
    response=tt("/post/publish/video/init/",{"post_info":{"title":row["title"],"privacy_level":row["privacy"],
                "disable_comment":True,"disable_duet":True,"disable_stitch":True,
                "brand_content_toggle":row.get("paid",False),"brand_organic_toggle":row.get("own_brand",False)},
                "source_info":{"source":"FILE_UPLOAD","video_size":size,"chunk_size":chunk,"total_chunk_count":count}})
    dest=upload_url(response["upload_url"],{"open-upload.tiktokapis.com","open-upload-va.tiktokapis.com","open-upload-sg.tiktokapis.com"})
    with media.open("rb") as file:
        for i in range(count):
            start=file.tell()
            content=file.read(size-start if i==count-1 else chunk)
            call("PUT",dest,data=content,headers={"Content-Type":"video/mp4","Content-Range":f"bytes {start}-{file.tell()-1}/{size}"})
    return response["publish_id"]


def metrics(platform,external):
    if platform=="youtube":
        items=call("GET",YT+"/videos",platform,params={"part":"statistics","id":external}).json()["items"]
        if not items:raise ValueError("YouTube statistics are unavailable.")
        row=items[0]["statistics"]
        return {k:int(row[v]) for k,v in (("views","viewCount"),("likes","likeCount"),("comments","commentCount")) if v in row}
    if platform=="instagram":
        rows=call("GET",IG+"/"+external+"/insights",platform,params={"metric":"views,likes,comments,shares"}).json()["data"]
        return {r["name"]:int(r["values"][0]["value"]) for r in rows if r.get("values")}
    info=tt("/post/publish/status/fetch/",{"publish_id":external})
    ids=info.get("publicaly_available_post_id") or info.get("publicly_available_post_id")
    if not ids:raise ValueError("TikTok has no public post ID yet.")
    result=tt("/video/query/?fields=id,view_count,like_count,comment_count,share_count",{"filters":{"video_ids":[str(ids[0])]}})
    v=result["videos"][0]
    return {k:int(v[f]) for k,f in (("views","view_count"),("likes","like_count"),("comments","comment_count"),("shares","share_count")) if f in v}


@contextmanager
def connect(data):
    db=sqlite3.connect(data/"jobs.sqlite3",timeout=15)
    db.row_factory=sqlite3.Row
    try:
        with db:yield db
    finally:
        db.close()


def pick_post_slot(earliest, previous, gap_minutes, daily_cap, tz_minutes):
    """Find the first permitted local-day slot without moving other queued posts."""
    gap = gap_minutes * 60
    offset = tz_minutes * 60
    candidate = earliest
    for past in sorted(previous):
        if gap and abs(candidate - past) < gap:
            candidate = past + gap
    while daily_cap:
        day = math.floor((candidate + offset) / 86400)
        if sum(math.floor((stamp + offset) / 86400) == day for stamp in previous) < daily_cap:
            break
        candidate = (day + 1) * 86400 - offset
        for past in sorted(previous):
            if gap and abs(candidate - past) < gap:
                candidate = past + gap
    return candidate


def attach(app,data,state,probe):
    with connect(data) as db:
        db.execute("CREATE TABLE IF NOT EXISTS posts(id TEXT PRIMARY KEY, payload TEXT, status TEXT, external TEXT, metrics TEXT, error TEXT)")
    def run(body):
        job=uuid.uuid4().hex
        state[job]={"status":"running","stage":"Sending to platform"}
        def worker():
            sending=False
            try:
                with connect(data) as db:
                    changed=db.execute("UPDATE posts SET status='sending' WHERE id=? AND status='waiting'",(body["post"],)).rowcount
                    if not changed:raise ValueError("This post was already attempted. Check its platform status.")
                    row=json.loads(db.execute("SELECT payload FROM posts WHERE id=?",(body["post"],)).fetchone()[0])
                media_path(data,row['clip'])
                current=account(row['platform'])
                if current['id']!=row['account'] or row['privacy'] not in current['privacy']:
                    raise ValueError("The publishing account or visibility changed. Check the destination.")
                sending=True
                external=publish(row,data)
                with connect(data) as db:db.execute("UPDATE posts SET status='submitted',external=? WHERE id=?",(external,body["post"]))
                state[job]={"status":"done","stage":"Submitted to "+row["platform"]}
            except Exception as e:
                error=str(e) if isinstance(e,ValueError) else "Posting failed. Check the platform account."
                stage='check platform' if sending else 'retryable'
                with connect(data) as db:db.execute("UPDATE posts SET status=?,error=? WHERE id=? AND status='sending'",(stage,error,body.get("post","")))
                state[job]={"status":"error","error":error}
        threading.Thread(target=worker,daemon=True).start()
        return {"job":job}

    @app.get("/social/account/{platform}")
    def destination(platform:str):
        try:return account(platform)
        except (ValueError,KeyError,IndexError) as error:raise HTTPException(400,str(error)) from error

    @app.get("/social/posts")
    def posts():
        with connect(data) as db:
            jobs={json.loads(j["payload"]).get("post"):dict(j) for j in db.execute("SELECT id,status,payload,created,updated,not_before FROM jobs WHERE kind='social' ORDER BY created")}
            return [{"id":r["id"],"job":jobs.get(r["id"],{}).get("id"),
                     "status":jobs.get(r["id"],{}).get("status","waiting") if r["status"]=="waiting" else r["status"],"external":r["external"],"metrics":json.loads(r["metrics"] or "{}"),
                     "error":r["error"],
                     "scheduled_at":jobs.get(r['id'],{}).get('not_before'),
                     "submitted_at":jobs.get(r['id'],{}).get('updated') if r['status']=='submitted' else None,
                     **json.loads(r["payload"])} for r in db.execute("SELECT * FROM posts ORDER BY rowid DESC LIMIT 100")]

    @app.post("/social/posts")
    def submit(body:dict):
        try:
            platform=body["platform"]
            acct=account(platform)
            if body.get("account")!=acct["id"] or body.get("privacy") not in acct["privacy"]:raise ValueError("Review the destination account and visibility.")
            clip=body["clip"]; path=media_path(data,clip)
            record=json.loads((data/(clip+".json")).read_text(encoding="utf-8"))
            if record.get("result",{}).get("status")!="done":raise ValueError("Select a finished library export.")
            if platform=="tiktok" and probe(path)["duration"]>acct["max_duration"]:raise ValueError("Clip exceeds this account's TikTok duration limit.")
            title=str(body.get("title","")).strip()
            if not title or len(title)>(100 if platform=="youtube" else 2200):raise ValueError("Enter a title within the platform limit.")
            when=float(body.get("when",0))
            if when and not time.time()<when<time.time()+366*86400:raise ValueError("Choose a future time within one year.")
            minutes=int(body.get('gap_minutes',0));cap=int(body.get('daily_cap',0));offset=int(body.get('offset_minutes',0))
            if not (0<=minutes<=1440 and 0<=cap<=24 and -720<=offset<=840):raise ValueError('Check the post interval and daily limit.')
            row={"platform":platform,"account":acct["id"],"name":acct["name"],"clip":clip,"title":title,"when":when,
                 "privacy":body["privacy"],"media_url":str(body.get("media_url","")) if platform=="instagram" else "",
                 "own_brand":bool(body.get("own_brand")),"paid":bool(body.get("paid")),
                 "gap_minutes":minutes,"daily_cap":cap,"offset_minutes":offset}
            if platform=="instagram" and not row["media_url"].startswith("https://"):raise ValueError("Enter the hosted HTTPS URL of the selected clip.")
            identifier=uuid.UUID(body["request_id"]).hex
            with connect(data) as db:
                db.execute("BEGIN IMMEDIATE")
                existing=db.execute("SELECT payload FROM posts WHERE id=?",(identifier,)).fetchone()
                if existing:
                    if json.loads(existing[0])!=row:raise ValueError("Use a fresh post request.")
                    return {"post":identifier}
                draft=body.get('draft') is True
                db.execute("INSERT INTO posts VALUES(?,?,?,NULL,NULL,NULL)",(identifier,json.dumps(row),'draft' if draft else 'waiting'))
                if not draft:
                    queue_post(db,identifier,row)
            if not draft:app.processing_queue.wake.set()
            return {"post":identifier}
        except (OSError,KeyError,ValueError,TypeError,OverflowError) as error:raise HTTPException(400,str(error)) from error

    def queue_post(db, identifier, row):
        now=time.time()
        records=db.execute(
            """SELECT p.payload,p.status,j.created,j.updated,j.not_before
               FROM posts p JOIN jobs j ON json_extract(j.payload,'$.post')=p.id
               WHERE p.id!=? AND j.kind='social' AND j.status!='canceled'
                 AND p.status IN ('waiting','sending','check platform','submitted')""",
            (identifier,),
        )
        previous=[]
        for record in records:
            other=json.loads(record['payload'])
            if (other['platform'],other['account'])!=(row['platform'],row['account']):continue
            previous.append(record['updated'] if record['status']=='submitted' else record['not_before'] or record['created'])
        when=pick_post_slot(max(float(row.get('when',0)),now),previous,row.get('gap_minutes',0),row.get('daily_cap',0),row.get('offset_minutes',0))
        db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)",(uuid.uuid4().hex,"social",json.dumps({"post":identifier}),"queued",now,now,when,None,"{}",0))
        return when

    @app.post('/social/posts/{post}/approve')
    def approve(post:str):
        with connect(data) as db:
            db.execute("BEGIN IMMEDIATE")
            draft=db.execute("SELECT payload,status FROM posts WHERE id=?",(post,)).fetchone()
            if not draft or draft['status'] not in ('draft','retryable'):
                raise HTTPException(409,'This draft is no longer awaiting approval.')
            row=json.loads(draft['payload'])
            when=queue_post(db,post,row)
            db.execute("UPDATE posts SET status='waiting',error=NULL WHERE id=?",(post,))
        app.processing_queue.wake.set()
        return {'scheduled_at':when}

    @app.post("/social/posts/{post}/metrics")
    def refresh(post:str):
        with connect(data) as db:
            row=db.execute("SELECT * FROM posts WHERE id=?",(post,)).fetchone()
            if not row or not row["external"]:raise HTTPException(409,"No submitted post yet.")
            try:
                settings=json.loads(row["payload"]);result=metrics(settings["platform"],row["external"])
            except (ValueError,KeyError,IndexError) as error:raise HTTPException(400,str(error)) from error
            db.execute("UPDATE posts SET metrics=? WHERE id=?",(json.dumps(result),post))
        return result
    return run


def duration_preferences(data):
    """Small platform-relative tie breaker after at least six measured posts on a platform."""
    if not (data/"jobs.sqlite3").exists():return {}
    by_platform={}
    with connect(data) as db:
        for row in db.execute("SELECT payload,metrics FROM posts WHERE metrics IS NOT NULL"):
            settings=json.loads(row["payload"]);m=json.loads(row["metrics"])
            if m.get("views",0)<100:continue
            try:
                record=json.loads((data/(settings["clip"]+".json")).read_text(encoding="utf-8"))
                bucket=int(record["result"]["meta"]["duration"]//15)
            except (OSError,KeyError,ValueError):continue
            by_platform.setdefault((settings["platform"],settings["account"]),[]).append((bucket,(m.get("likes",0)+m.get("comments",0))/m["views"]))
    scores={}
    for rows in by_platform.values():
        if len(rows)<6:continue
        baseline=sum(rate for _,rate in rows)/len(rows)
        if baseline<=0:continue
        for bucket,rate in rows:scores.setdefault(bucket,[]).append(rate/baseline-1)
    return {k:max(-.03,min(.03,.03*sum(v)/len(v))) for k,v in scores.items() if len(v)>=2}
