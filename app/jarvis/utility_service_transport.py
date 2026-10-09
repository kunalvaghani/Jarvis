"""SDK dependency isolation and bounded approved service jobs; no shell execution."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from .harness_process import OwnedJob,hidden_spawn

CREDENTIALS={'mongodb':{'JARVIS_MONGODB_URI'},'redis':{'JARVIS_REDIS_HOST','JARVIS_REDIS_PORT','JARVIS_REDIS_PASSWORD'},
 'slack_approval':{'JARVIS_SLACK_WEBHOOK_URL','SLACK_WEBHOOK_URL'},'github_comment':{'JARVIS_GITHUB_TOKEN','GITHUB_TOKEN'},
 'sms_send':{'TWILIO_ACCOUNT_SID','TWILIO_AUTH_TOKEN','TWILIO_PHONE_NUMBER'}}


def call(actions,name,args,cancelled):
    allowed=CREDENTIALS.get(name,set());environment={k:v for k,v in os.environ.items() if k in allowed or k.upper() in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP'}}
    python=Path(actions.base)/'.venv-skills/Scripts/python.exe';job=OwnedJob();process=None
    with tempfile.TemporaryFile() as source,tempfile.TemporaryFile() as output:
        source.write(json.dumps({'name':name,'arguments':args}).encode());source.seek(0)
        try:
            process=hidden_spawn(job,subprocess.Popen)([str(python),'-m','jarvis.utility_service_transport','--worker'],cwd=actions.base,env=environment,stdin=source,stdout=output,stderr=subprocess.DEVNULL)
            deadline=time.monotonic()+30
            while process.poll() is None:
                if cancelled() or time.monotonic()>deadline:raise ValueError('Service stopped or timed out; inspect before repeating, no automatic retry.')
                time.sleep(.05)
            output.seek(0);raw=output.read(1000001)
            if len(raw)>1000000:raise ValueError('Service output budget exceeded.')
            result=json.loads(raw)
            if result.get('ok') is not True:raise ValueError('Service failed: '+result.get('error_type','Unknown')+'; inspect local setup. Credentials and response contents are not logged.')
            return result['value']
        finally:
            job.close()
            if process is not None and process.poll() is None:process.kill();process.wait(timeout=5)


if __name__=='__main__':
    import sys
    from .utility_services import execute
    try:
        request=json.loads(sys.stdin.buffer.read(1000000));result={'ok':True,'value':execute(request['name'],request['arguments'])}
    except Exception as error:result={'ok':False,'error_type':type(error).__name__}
    print(json.dumps(result))
