"""Exercise resumed rendering and the timeline through their actual API handlers."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

# This standalone integration check must never read or modify a creator's library.
def main():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        os.environ.update(BLOOMCLIPPING_DATA_DIR=tmp, BLOOMCLIPPING_NO_AUTOUPDATE='1')
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        import app
        from fastapi.testclient import TestClient
        import transcripts
        client=TestClient(app.app,client=('127.0.0.1',50000))
        key='a'*32
        path=Path(tmp)/(key+'.mp4')
        subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=12','-f','lavfi','-i','sine=frequency=440','-t','6','-c:v','libx264','-c:a','aac',str(path)],check=True)
        words=[{'text':'hello','start':i+.05,'end':i+.35} for i in range(6)]
        def wait(job):
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                row=client.get('/make/'+job).json()
                if row['status']!='running':return row
                time.sleep(.1)
            raise AssertionError('timeout')
        export=app.start_export
        calls=[]
        def fail_second(body,job):
            calls.append(body)
            if len(calls)==2:
                app.state[job]={'status':'error','error':'test interruption'}
                return {'job':job}
            return export(body,job)
        payload={'id':key,'cam_auto':False,'resolution':720,'moments':[{'start':0,'end':2},{'start':3,'end':5}]}
        with patch.object(transcripts,'cached_source',return_value=words),patch.object(app,'start_export',side_effect=fail_second):
            original=client.post('/make',json=payload).json()['job']
            first=wait(original)
        assert first['status']=='error' and first['can_resume'],first
        with patch('smart.find',side_effect=AssertionError('analysis repeated')),patch.object(app,'start_export',wraps=export) as exporter:
            job=client.post('/make/'+original+'/resume').json()['job']
            final=wait(job)
            assert final['status']=='done' and len(final['clips'])==2,final
            assert exporter.call_count==1 and first['clips'][0]['file']==final['clips'][0]['file']
        print('PASS: saved analysis and first MP4 reused, only failed clip rendered.')
        app.app.processing_queue.close()

if __name__=='__main__':
    main()

