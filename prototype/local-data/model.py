"""Minimal NVIDIA hosted chat adapter. Never log headers or credentials."""
import json
import os
from pathlib import Path
import time
from urllib import request, error

HERE=Path(__file__).resolve().parent
MODEL='nvidia/nemotron-3.5-lightning-30b-a3b'
ENDPOINT='https://integrate.api.nvidia.com/v1/chat/completions'

def provider_schema(value):
    # NVIDIA's constrained grammar does not implement uniqueItems; validate locally.
    if isinstance(value,dict):return {k:provider_schema(v) for k,v in value.items() if k!='uniqueItems'}
    if isinstance(value,list):return [provider_schema(v) for v in value]
    return value

class ProviderError(RuntimeError):
    def __init__(self,status,retry_after=None):
        super().__init__(f'NVIDIA HTTP {status}')
        self.status=status
        self.retry_after=retry_after

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Provider redirect refused')

class Model:
    def __init__(self):
        self.key=os.environ.get('NVIDIA_API_KEY') or (HERE/'.private/nvidia-key').read_text().strip()
        if not self.key: raise ValueError('NVIDIA_API_KEY is missing')

    def complete(self,messages,tools=None,tool_choice='auto',max_tokens=2048,*,model_name=None,enable_thinking=False,timeout=90):
        body={'model':model_name or MODEL,'messages':messages,'temperature':0,
              'stream':False,'chat_template_kwargs':{'enable_thinking':enable_thinking}}
        if max_tokens is not None:body['max_tokens']=max_tokens
        if tools:
            body.update(tools=provider_schema(tools),tool_choice=tool_choice)
            if isinstance(tool_choice,dict): body['parallel_tool_calls']=False
        req=request.Request(ENDPOINT,data=json.dumps(body).encode(),headers={
            'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        start=time.monotonic()
        try:
            with request.build_opener(NoRedirect()).open(req,timeout=timeout) as response:
                raw=response.read(2000001)
        except error.HTTPError as e:
            # Do not expose response bodies that might echo request data or credentials.
            retry=e.headers.get('Retry-After','') if e.headers else ''
            delay=int(retry) if retry.isdecimal() else None
            raise ProviderError(e.code,delay) from None
        except error.URLError:
            raise RuntimeError('NVIDIA connection failed') from None
        if len(raw)>2000000: raise RuntimeError('Provider response exceeds size limit')
        data=json.loads(raw)
        choice=data['choices'][0]
        msg=choice['message']
        message={k:msg[k] for k in ('role','content','tool_calls') if k in msg and msg[k] is not None}
        return {'message':message,'usage':data.get('usage'), 'finish_reason':choice.get('finish_reason'),
                'model':data.get('model',body['model']),'seconds':time.monotonic()-start}

if __name__=='__main__':
    function={'type':'function','function':{'name':'connection_check','description':'Return the supplied text.',
              'parameters':{'type':'object','properties':{'text':{'type':'string'}},'required':['text'],'additionalProperties':False}}}
    response=Model().complete([{'role':'user','content':'Call connection_check with text hello.'}],[function],tool_choice='required',max_tokens=128)
    path=HERE/'generated/connection-check.json'
    path.write_text(json.dumps(response,indent=2)+'\n')
    print(json.dumps(response,indent=2))
