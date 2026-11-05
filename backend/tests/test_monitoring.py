import json
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.monitoring import RequestMonitoring

def test_request_monitoring_omits_sensitive_inputs_and_exception_details():
    app=FastAPI();app.add_middleware(RequestMonitoring)
    @app.post('/private/{item_id}')
    def broken(item_id:str):raise RuntimeError('private-health-data provider-key=secret')
    with patch('backend.app.monitoring.logger.log') as log,TestClient(app) as client:
        response=client.post('/private/personal-id?code=oauth-secret',json={'password':'secret-password'},headers={'Authorization':'Bearer private-token','X-Request-ID':'attacker-controlled'})
        assert response.status_code==500
        request_id=response.headers['x-request-id']
        assert len(request_id)==32 and response.json()['request_id']==request_id
        assert response.headers['cache-control']=='no-store'
        record=json.loads(log.call_args.args[1])
        assert record['route']=='/private/{item_id}' and record['event']=='request_failed'
        assert set(record)=={'event','request_id','method','route','status','duration_ms'}
        combined=json.dumps(record)+response.text
        for private in ['personal-id','oauth-secret','secret-password','private-token','private-health-data','provider-key','attacker-controlled']:
            assert private not in combined

def test_unmatched_paths_are_not_logged_and_request_ids_are_unique():
    app=FastAPI();app.add_middleware(RequestMonitoring)
    with patch('backend.app.monitoring.logger.log') as log,TestClient(app) as client:
        first=client.get('/unknown/private-path?token=secret')
        second=client.get('/another-private-path')
        assert first.status_code==404 and second.status_code==404
        assert first.headers['x-request-id']!=second.headers['x-request-id']
        assert all(json.loads(call.args[1])['route']=='unmatched' for call in log.call_args_list)
