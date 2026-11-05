"""Request telemetry with an allowlist; never serialize request or exception data."""
import json
import logging
import sys
import time
from uuid import uuid4
from starlette.responses import JSONResponse

logger=logging.getLogger('lossfit.monitoring')
if not logger.handlers:
    handler=logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate=False

class RequestMonitoring:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':
            return await self.app(scope,receive,send)
        request_id=uuid4().hex
        started=time.monotonic();status=500;headers_sent=False;complete=False;failed=False
        async def monitored_send(message):
            nonlocal status,headers_sent,complete
            if message['type']=='http.response.start':
                status=message['status'];headers_sent=True
                headers=list(message.get('headers',[]))
                headers.extend([(b'x-request-id',request_id.encode()),(b'x-content-type-options',b'nosniff'),(b'referrer-policy',b'no-referrer'),(b'cache-control',b'no-store')])
                message={**message,'headers':headers}
            if message['type']=='http.response.body' and not message.get('more_body',False):complete=True
            await send(message)
        try:
            await self.app(scope,receive,monitored_send)
        except Exception:
            failed=True
            if not headers_sent:
                await JSONResponse({'detail':'An unexpected error occurred. Please try again.','request_id':request_id},status_code=500)(scope,receive,monitored_send)
            elif not complete:
                await send({'type':'http.response.body','body':b'','more_body':False})
        finally:
            route=getattr(scope.get('route'),'path',None)
            method=scope.get('method','')
            record={'event':'request_failed' if failed else 'request_finished','request_id':request_id,'method':method if method in {'GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'} else 'OTHER','route':route or 'unmatched','status':status,'duration_ms':round((time.monotonic()-started)*1000,2)}
            logger.log(logging.ERROR if failed or status>=500 else logging.INFO,json.dumps(record,separators=(',',':')))
