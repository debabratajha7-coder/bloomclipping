"""Offline checks: never connect accounts or submit a real post."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from urllib.parse import parse_qs,urlparse

import social
import social_accounts
import studio_plans


class LocalStudio(unittest.TestCase):
    def setUp(self):
        self.words=[{"text":text,"start":i,"end":i+.8} for i,text in enumerate(
            ["The","first","scene.","Um","costs","25!","They","tried","again.","Then","it","worked."])]
    def test_filler_preserves_surrounding_audio(self):
        cuts=studio_plans.dialogue_plan(self.words,0,12,"filler","")
        self.assertEqual(cuts,[{"start":0,"end":3},{"start":3.8,"end":12}])
    def test_beats_are_bounded(self):
        cuts=studio_plans.dialogue_plan(self.words,0,12,"beats","")
        self.assertTrue(any(c.get("cue") and c["zoom"]>1 for c in cuts))
        self.assertAlmostEqual(sum(c["end"]-c["start"] for c in cuts),12)
    def test_ai_effects_only_reference_selected_passages(self):
        with patch.object(studio_plans.smart,"_model",return_value="local"),patch.object(studio_plans.llm,"complete",return_value='{"indices":[0],"broll_indices":[0],"zoom_indices":[0]}'):
            rows=studio_plans.dialogue_plan(self.words,0,12,"edit","zoom","stock")
        self.assertEqual(rows[0]["broll"],"stock")
        self.assertEqual(rows[0]["zoom"],1.14)
    def test_model_cannot_select_unknown_passage(self):
        with patch.object(studio_plans.smart,"_model",return_value="local"),patch.object(studio_plans.llm,"complete",return_value='{"indices":[99]}'):
            with self.assertRaises(ValueError):studio_plans.dialogue_plan(self.words,0,12,"recap","")
    def test_no_resolution_in_trailer_candidate_pool(self):
        with patch.object(studio_plans.smart,"_model",return_value="local"),patch.object(studio_plans.llm,"complete",return_value='{"indices":[0]}') as model:
            studio_plans.dialogue_plan(self.words,0,12,"trailer","")
        self.assertNotIn('worked.',model.call_args.args[1]['prompt'])


class NativePosting(unittest.TestCase):
    def test_queue_window_observes_daily_cap_and_spacing(self):
        self.assertEqual(120, social.pick_post_slot(60,[60],1,0,0))
        self.assertEqual(86400, social.pick_post_slot(120,[60],0,1,0))
        self.assertEqual(86400-19800, social.pick_post_slot(120,[60],0,1,330))
    def test_oauth_callback_bound_to_original_request_and_one_use(self):
        with patch.dict("os.environ",{"BLOOMCLIPPING_YOUTUBE_CLIENT_ID":"test-id","BLOOMCLIPPING_YOUTUBE_TOKEN":""}),patch.object(social_accounts,"vault") as vault,patch.object(social_accounts,"exchange",return_value={"access_token":"fixture"}) as exchange:
            url=social_accounts.begin("youtube")["url"]
            params=parse_qs(urlparse(url).query)
            self.assertIn("code_challenge",params)
            callback=params["redirect_uri"][0]+"?code=fixture&state="+params["state"][0]
            self.assertEqual(social_accounts.finish(callback)["platform"],"youtube")
            self.assertTrue(exchange.call_args.args[1]["code_verifier"])
            self.assertEqual(vault.call_args.args[1]["access_token"],"fixture")
            with self.assertRaises(ValueError):social_accounts.finish(callback)

    def test_changed_account_aborts_before_upload(self):
        with patch.object(social,"account",return_value={"id":"changed","privacy":["private"]}),patch.object(social,"call") as api:
            with self.assertRaises(ValueError):social.publish({"account":"old","platform":"youtube","privacy":"private"},Path("."))
            api.assert_not_called()

    def test_direct_upload_adapters_use_local_file_or_explicit_instagram_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);(data/"clip.mp4").write_bytes(b"test media")
            for platform in social.PLATFORMS:
                row={"clip":"clip","platform":platform,"account":"owner","privacy":"private","title":"test","media_url":"https://example.org/clip.mp4"}
                def reply(method,url,provider=None,**kwargs):
                    result=Mock()
                    if "googleapis.com/upload" in url:result.headers={"Location":"https://www.googleapis.com/session"}
                    elif url.endswith("/session"):result.json.return_value={"id":"yt"}
                    elif url.endswith("/media"):result.json.return_value={"id":"container"}
                    elif url.endswith("/container"):result.json.return_value={"status_code":"FINISHED"}
                    elif url.endswith("/media_publish"):result.json.return_value={"id":"ig"}
                    elif "video/init" in url:result.json.return_value={"error":{"code":"ok"},"data":{"publish_id":"tt","upload_url":"https://open-upload.tiktokapis.com/upload"}}
                    return result
                with self.subTest(platform=platform),patch.object(social,"account",return_value={"id":"owner","privacy":["private"]}),patch.object(social,"call",side_effect=reply):
                    self.assertEqual(social.publish(row,data),{"youtube":"yt","instagram":"ig","tiktok":"tt"}[platform])
    def test_duration_bias_needs_measured_comparable_posts(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)
            with social.connect(data) as db:
                db.execute("CREATE TABLE posts(payload TEXT,metrics TEXT)")
                for i in range(6):
                    key=str(i)
                    (data/(key+".json")).write_text(json.dumps({"result":{"meta":{"duration":12 if i<3 else 42}}}))
                    db.execute("INSERT INTO posts VALUES(?,?)",(json.dumps({"clip":key,"platform":"youtube","account":"one"}),json.dumps({"views":1000,"likes":50 if i<3 else 10})))
            bias=social.duration_preferences(data)
            self.assertGreater(bias[0],0)
            self.assertLess(bias[2],0)
    def test_scheduling_deduplicates_and_cancels_in_same_queue(self):
        import time
        import uuid
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import jobs
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data=Path(tmp);clip="b"*32
            (data/(clip+".mp4")).write_bytes(b"mock")
            (data/(clip+".json")).write_text('{"result":{"status":"done"}}')
            app=FastAPI();state={};handler=social.attach(app,data,state,lambda p:{"duration":5})
            jobs.attach(app,data,state,{"social":handler})
            try:
                with TestClient(app) as client,patch.object(social,"account",return_value={"id":"owner","name":"Creator","privacy":["private"]}),patch.object(social,"publish") as post:
                    body={"platform":"youtube","account":"owner","privacy":"private","title":"QA","clip":clip,"when":time.time()+3600,"request_id":str(uuid.uuid4())}
                    for _ in range(2):self.assertEqual(client.post("/social/posts",json=body).status_code,200)
                    result=client.get("/social/posts").json();self.assertEqual(len(result),1);self.assertEqual(result[0]["status"],"queued")
                    self.assertEqual(len(client.get("/queue").json()["jobs"]),1)
                    client.post("/queue/"+result[0]["job"]+"/cancel",json={}).raise_for_status()
                    self.assertEqual(client.get("/social/posts").json()[0]["status"],"canceled")
                    test_draft={**body,"request_id":str(uuid.uuid4()),"draft":True,"gap_minutes":10,"daily_cap":3}
                    saved=client.post("/social/posts",json=test_draft)
                    self.assertEqual(saved.status_code,200)
                    post_id=saved.json()["post"]
                    self.assertEqual(client.get("/social/posts").json()[0]["status"],"draft")
                    self.assertEqual(len(client.get("/queue").json()["jobs"]),1)
                    self.assertEqual(client.post(f"/social/posts/{post_id}/approve",json={}).status_code,200)
                    self.assertEqual(client.get("/social/posts").json()[0]["status"],"queued")
                    self.assertEqual(client.post(f"/social/posts/{post_id}/approve",json={}).status_code,409)
                    post.assert_not_called()
                    post.assert_not_called()
            finally:app.processing_queue.close()
