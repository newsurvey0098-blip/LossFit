from uuid import uuid4
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import io
import json, os, subprocess, sys
from PIL import Image
from fastapi.testclient import TestClient
from backend.app.main import app, Food, FoodServing
import backend.app.main as main
from backend.app.knowledge import cosine
from backend.app.food_import import normalize_foundation_food
from backend.app.deletion_ledger import export_ledger, verify_ledger

def register(client):
    suffix=uuid4().hex
    response=client.post('/api/v1/auth/register',json={"name":"Test User","email":f"{suffix}@gmail.com","password":"safe-password-987"})
    assert response.status_code==201
    user=response.json();client.headers.update({"Authorization":f"Bearer {user['access_token']}"})
    return user

def test_registration_meal_snapshot_summary_and_export():
    with TestClient(app) as client:
        register(client)
        csrf=client.cookies['lf_csrf']
        headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        meal=client.post('/api/v1/meals',headers=headers,json={"name":"Lunch","meal_type":"lunch","items":[{"food":"Rice","grams":150,"per100":{"kcal":130,"protein":2.7}}]})
        assert meal.status_code==201
        assert meal.json()['kcal']==195
        assert meal.json()['protein']==4.05
        assert client.get('/api/v1/analytics/daily').json()['totals']['kcal']==195
        assert len(client.get('/api/v1/privacy/export.json').json()['meals'])==1
        assert 'Lunch' in client.get('/api/v1/privacy/export.csv').text

def test_cookie_mutations_require_csrf_and_origin():
    with TestClient(app) as client:
        register(client)
        csrf=client.cookies['lf_csrf']
        assert client.post('/api/v1/auth/refresh').status_code==403
        bad=client.post('/api/v1/auth/refresh',headers={"origin":"https://bad.example","x-csrf-token":csrf})
        assert bad.status_code==403
        good=client.post('/api/v1/auth/refresh',headers={"origin":"http://localhost:5173","x-csrf-token":csrf})
        assert good.status_code==200 and good.json()['access_token']

def test_production_cookie_flags_and_restricted_paths(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT','production')
    with TestClient(app,base_url='https://testserver') as client:
        response=client.post('/api/v1/auth/register',json={"name":"Cookie flags","email":f"cookie-{uuid4().hex}@example.com","password":"safe-password-987"})
        assert response.status_code==201
        cookies=response.headers.get_list('set-cookie')
        refresh=next(cookie for cookie in cookies if cookie.startswith('lf_refresh='))
        csrf=next(cookie for cookie in cookies if cookie.startswith('lf_csrf='))
        assert 'HttpOnly' in refresh and 'Secure' in refresh and 'SameSite=lax' in refresh and 'Path=/api/v1/auth' in refresh
        assert 'HttpOnly' not in csrf and 'Secure' in csrf and 'SameSite=lax' in csrf and 'Path=/' in csrf
        # The refresh endpoint is the cookie-authenticated mutation. The separate
        # CSRF test verifies that it rejects absent tokens and untrusted origins.

def test_google_account_linking_reports_missing_credentials_and_requires_reauthentication(monkeypatch):
    monkeypatch.delenv('GOOGLE_CLIENT_ID',raising=False);monkeypatch.delenv('GOOGLE_CLIENT_SECRET',raising=False);monkeypatch.delenv('GOOGLE_REDIRECT_URI',raising=False)
    with TestClient(app) as client:
        register(client)
        csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        assert client.get('/api/v1/auth/google/status').json()=={"available":False,"linked":False,"email":None}
        unavailable=client.post('/api/v1/auth/google/link/start',headers=headers,json={"password":"safe-password-987"})
        assert unavailable.status_code==503
        monkeypatch.setenv('GOOGLE_CLIENT_ID','test-client.apps.googleusercontent.com');monkeypatch.setenv('GOOGLE_CLIENT_SECRET','test-secret');monkeypatch.setenv('GOOGLE_REDIRECT_URI','http://127.0.0.1:8000/api/v1/auth/google/callback')
        bad=client.post('/api/v1/auth/google/link/start',headers=headers,json={"password":"wrong-password"})
        assert bad.status_code==401

def test_google_account_linking_uses_pkce_verified_subject_and_single_use_state(monkeypatch):
    from urllib.parse import urlparse,parse_qs
    monkeypatch.setenv('GOOGLE_CLIENT_ID','test-client.apps.googleusercontent.com');monkeypatch.setenv('GOOGLE_CLIENT_SECRET','test-secret');monkeypatch.setenv('GOOGLE_REDIRECT_URI','http://127.0.0.1:8000/api/v1/auth/google/callback')
    token_payload={"id_token":"mock-signed-token"};calls=[]
    class FakeResponse:
        def raise_for_status(self):pass
        def json(self):return token_payload
    def fake_post(url,**kwargs):calls.append((url,kwargs));return FakeResponse()
    monkeypatch.setattr(main.httpx,'post',fake_post)
    with TestClient(app) as client:
        register(client)
        headers={"origin":"http://localhost:5173","x-csrf-token":client.cookies['lf_csrf']}
        started=client.post('/api/v1/auth/google/link/start',headers=headers,json={"password":"safe-password-987"})
        assert started.status_code==200
        params=parse_qs(urlparse(started.json()['authorization_url']).query)
        assert params['code_challenge_method']==['S256'] and params['scope']==['openid email profile']
        monkeypatch.setattr(main,'verify_google_id_token',lambda raw,audience:{"sub":"google-sub-123","email":"different-address@example.com","email_verified":True,"nonce":params['nonce'][0]})
        callback=client.get('/api/v1/auth/google/callback',params={"state":params['state'][0],"code":"oauth-code"},follow_redirects=False)
        assert callback.status_code==303 and callback.headers['location'].endswith('/settings/accounts?google=linked')
        assert calls[0][1]['data']['code_verifier']
        assert client.get('/api/v1/auth/google/status').json()=={"available":True,"linked":True,"email":"different-address@example.com"}
        replay=client.get('/api/v1/auth/google/callback',params={"state":params['state'][0],"code":"another-code"},follow_redirects=False)
        assert replay.headers['location'].endswith('?google=invalid') and len(calls)==1
        wrong_password=client.post('/api/v1/auth/google/unlink',headers=headers,json={"password":"wrong-password"})
        assert wrong_password.status_code==401
        unlinked=client.post('/api/v1/auth/google/unlink',headers=headers,json={"password":"safe-password-987"})
        assert unlinked.status_code==200 and client.get('/api/v1/auth/google/status').json()['linked'] is False

def test_google_link_never_merges_accounts_by_matching_email(monkeypatch):
    from urllib.parse import urlparse,parse_qs
    monkeypatch.setenv('GOOGLE_CLIENT_ID','test-client.apps.googleusercontent.com');monkeypatch.setenv('GOOGLE_CLIENT_SECRET','test-secret');monkeypatch.setenv('GOOGLE_REDIRECT_URI','http://127.0.0.1:8000/api/v1/auth/google/callback')
    class FakeResponse:
        def raise_for_status(self):pass
        def json(self):return {"id_token":"mock-signed-token"}
    monkeypatch.setattr(main.httpx,'post',lambda *a,**kw:FakeResponse())
    with TestClient(app) as client:
        owner=register(client)
        with TestClient(app) as other:
            register(other);email=other.get('/api/v1/auth/me').json()['email']
        headers={"origin":"http://localhost:5173","x-csrf-token":client.cookies['lf_csrf']}
        params=parse_qs(urlparse(client.post('/api/v1/auth/google/link/start',headers=headers,json={"password":"safe-password-987"}).json()['authorization_url']).query)
        monkeypatch.setattr(main,'verify_google_id_token',lambda raw,audience:{"sub":"separate-google-sub","email":email,"email_verified":True,"nonce":params['nonce'][0]})
        response=client.get('/api/v1/auth/google/callback',params={"state":params['state'][0],"code":"oauth-code"},follow_redirects=False)
        assert response.headers['location'].endswith('?google=linked')
        assert client.get('/api/v1/auth/me').json()['email']!=email
        assert client.get('/api/v1/auth/google/status').json()['email']==email
        with main.SessionLocal() as session:
            linked=session.scalar(main.select(main.GoogleAccount).where(main.GoogleAccount.provider_subject=='separate-google-sub'))
            assert linked and linked.user_id==owner['id']

def test_assistant_water_action_requires_preview_and_confirmation_and_is_idempotent():
    with TestClient(app) as client:
        register(client);headers={"origin":"http://localhost:5173","x-csrf-token":client.cookies['lf_csrf']}
        conversation=client.post('/api/v1/assistant/conversations',headers=headers).json()
        payload={"conversation_id":conversation['id'],"action":"log_water","water_ml":350,"idempotency_key":uuid4().hex}
        preview=client.post('/api/v1/assistant/actions/preview',headers=headers,json=payload)
        assert preview.status_code==201
        action=preview.json();assert action['status']=='pending' and action['preview']['today_total_after_ml']==350
        assert client.get('/api/v1/analytics/daily').json()['water_ml']==0
        repeated=client.post('/api/v1/assistant/actions/preview',headers=headers,json=payload)
        assert repeated.status_code==200 and repeated.json()['id']==action['id']
        mismatch={**payload,"water_ml":500}
        assert client.post('/api/v1/assistant/actions/preview',headers=headers,json=mismatch).status_code==409
        confirmed=client.post(f"/api/v1/assistant/actions/{action['id']}/confirm",headers=headers)
        assert confirmed.status_code==200 and confirmed.json()['status']=='confirmed'
        assert confirmed.json()['result']['water_ml']==350
        again=client.post(f"/api/v1/assistant/actions/{action['id']}/confirm",headers=headers)
        assert again.json()['result']['water_entry_id']==confirmed.json()['result']['water_entry_id']
        assert client.get('/api/v1/analytics/daily').json()['water_ml']==350

def test_assistant_meal_action_previews_catalogue_snapshot_then_commits_once():
    with TestClient(app) as owner,TestClient(app) as other:
        user=register(owner);headers={"origin":"http://localhost:5173","x-csrf-token":owner.cookies['lf_csrf']}
        food=owner.post('/api/v1/foods',headers=headers,json={"name":"Assistant action test oats","state":"cooked","kcal":120,"protein":4,"carbs":22,"fat":2}).json()
        conversation=owner.post('/api/v1/assistant/conversations',headers=headers).json()
        body={"conversation_id":conversation['id'],"action":"log_meal","idempotency_key":uuid4().hex,"meal":{"name":"Assistant oatmeal","meal_type":"breakfast","items":[{"food_id":food['id'],"grams":150}]}}
        preview=owner.post('/api/v1/assistant/actions/preview',headers=headers,json=body)
        assert preview.status_code==201 and preview.json()['preview']['totals']['kcal']==180
        assert owner.get('/api/v1/meals').json()==[]
        item=preview.json()['preview']['items'][0]
        assert item['state']=='cooked' and item['verification']=='user_provided'
        confirmed=owner.post(f"/api/v1/assistant/actions/{preview.json()['id']}/confirm",headers=headers)
        assert confirmed.status_code==200 and confirmed.json()['result']['kcal']==180
        meal_id=confirmed.json()['result']['meal_id']
        again=owner.post(f"/api/v1/assistant/actions/{preview.json()['id']}/confirm",headers=headers)
        assert again.json()['result']['meal_id']==meal_id
        assert len(owner.get('/api/v1/meals').json())==1
        deleted_food=owner.post('/api/v1/foods',headers=headers,json={"name":"Food removed during assistant preview","kcal":90}).json()
        second_body={**body,"idempotency_key":uuid4().hex,"meal":{"name":"Preview to invalidate","meal_type":"snack","items":[{"food_id":deleted_food['id'],"grams":100}]}}
        second=owner.post('/api/v1/assistant/actions/preview',headers=headers,json=second_body).json()
        assert owner.delete(f"/api/v1/foods/{deleted_food['id']}",headers=headers).status_code==204
        assert owner.post(f"/api/v1/assistant/actions/{second['id']}/confirm",headers=headers).status_code==409
        assert len(owner.get('/api/v1/meals').json())==1
        other_user=register(other);other_headers={"origin":"http://localhost:5173","x-csrf-token":other.cookies['lf_csrf']}
        other_conversation=other.post('/api/v1/assistant/conversations',headers=other_headers).json()
        forbidden={**body,"conversation_id":other_conversation['id'],"idempotency_key":uuid4().hex}
        assert other.post('/api/v1/assistant/actions/preview',headers=other_headers,json=forbidden).status_code==422
        assert other.post(f"/api/v1/assistant/actions/{preview.json()['id']}/confirm",headers=other_headers).status_code==404

def test_remaining_auth_scanner_and_assistant_rate_limits_are_enforced(monkeypatch):
    monkeypatch.setattr(main,'request_ip',lambda request:'dedicated-rate-limit-regression-client')
    monkeypatch.setenv('GOOGLE_CLIENT_ID','test-client.apps.googleusercontent.com');monkeypatch.setenv('GOOGLE_CLIENT_SECRET','test-secret');monkeypatch.setenv('GOOGLE_REDIRECT_URI','http://127.0.0.1:3001/api/v1/auth/google/callback')
    with TestClient(app) as client:
        user=register(client);headers={"origin":"http://localhost:5173","x-csrf-token":client.cookies['lf_csrf']}
        def protected_post(path,**kwargs):
            headers['x-csrf-token']=client.cookies['lf_csrf']
            return client.post(path,headers=headers,**kwargs)
        body={"name":"Rate Limit User","email":user['email'],"password":"safe-password-987"}
        registration=[client.post('/api/v1/auth/register',json=body).status_code for _ in range(100)]
        assert registration==[409]*99+[429]
        refresh=[protected_post('/api/v1/auth/refresh').status_code for _ in range(121)]
        assert refresh==[200]*120+[429]
        invalid_scan_body={"name":"Scan","meal_type":"lunch","items":[],"removed_candidate_ids":[]}
        scan_confirms=[protected_post('/api/v1/scans/987654321/confirm',json=invalid_scan_body).status_code for _ in range(21)]
        assert scan_confirms==[404]*20+[429]
        conversation=protected_post('/api/v1/assistant/conversations').json()
        preview_body={"conversation_id":conversation['id'],"action":"log_water","water_ml":100,"idempotency_key":None}
        preview_statuses=[]
        for _ in range(21):
            preview_body['idempotency_key']=uuid4().hex
            preview_statuses.append(protected_post('/api/v1/assistant/actions/preview',json=preview_body).status_code)
        assert preview_statuses==[201]*20+[429]
        confirm_statuses=[protected_post(f"/api/v1/assistant/actions/{'f'*32}/confirm").status_code for _ in range(31)]
        assert confirm_statuses==[404]*30+[429]
        google_statuses=[protected_post('/api/v1/auth/google/link/start',json={"password":"safe-password-987"}).status_code for _ in range(6)]
        assert google_statuses==[200]*5+[429]

def test_assistant_action_preview_is_private_cancelable_and_rechecked_before_write():
    with TestClient(app) as owner,TestClient(app) as other:
        register(owner);owner_headers={"origin":"http://localhost:5173","x-csrf-token":owner.cookies['lf_csrf']}
        conversation=owner.post('/api/v1/assistant/conversations',headers=owner_headers).json()
        base={"conversation_id":conversation['id'],"action":"log_water","water_ml":250}
        canceled=owner.post('/api/v1/assistant/actions/preview',headers=owner_headers,json={**base,"idempotency_key":uuid4().hex}).json()
        assert owner.post(f"/api/v1/assistant/actions/{canceled['id']}/cancel",headers=owner_headers).status_code==204
        assert owner.post(f"/api/v1/assistant/actions/{canceled['id']}/confirm",headers=owner_headers).status_code==409
        stale=owner.post('/api/v1/assistant/actions/preview',headers=owner_headers,json={**base,"idempotency_key":uuid4().hex}).json()
        assert owner.post('/api/v1/water?ml=100',headers=owner_headers).status_code==201
        response=owner.post(f"/api/v1/assistant/actions/{stale['id']}/confirm",headers=owner_headers)
        assert response.status_code==409 and owner.get('/api/v1/analytics/daily').json()['water_ml']==100
        expired=owner.post('/api/v1/assistant/actions/preview',headers=owner_headers,json={**base,"idempotency_key":uuid4().hex}).json()
        with main.SessionLocal() as session:
            pending=session.get(main.AssistantAction,expired['id']);pending.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);session.commit()
        assert owner.post(f"/api/v1/assistant/actions/{expired['id']}/confirm",headers=owner_headers).status_code==410
        assert owner.get('/api/v1/analytics/daily').json()['water_ml']==100
        register(other);other_headers={"origin":"http://localhost:5173","x-csrf-token":other.cookies['lf_csrf']}
        assert other.post(f"/api/v1/assistant/actions/{stale['id']}/confirm",headers=other_headers).status_code==404
        foreign={**base,"conversation_id":conversation['id'],"idempotency_key":uuid4().hex}
        assert other.post('/api/v1/assistant/actions/preview',headers=other_headers,json=foreign).status_code==404
        invalid=owner.post('/api/v1/assistant/actions/preview',headers=owner_headers,json={**base,"water_ml":49,"idempotency_key":uuid4().hex})
        assert invalid.status_code==422

def test_user_cannot_read_another_users_meal():
    with TestClient(app) as owner, TestClient(app) as other:
        register(owner)
        csrf=owner.cookies['lf_csrf']
        response=owner.post('/api/v1/meals',headers={"origin":"http://localhost:5173","x-csrf-token":csrf},json={"name":"Private lunch","meal_type":"lunch","items":[]})
        meal_id=response.json()['id']
        register(other)
        assert other.get(f'/api/v1/meals/{meal_id}').status_code==404

def test_custom_food_is_private_and_keeps_missing_nutrients_null():
    with TestClient(app) as owner, TestClient(app) as other:
        register(owner)
        csrf=owner.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        created=owner.post('/api/v1/foods',headers=headers,json={"name":"Homemade test soup","state":"cooked","kcal":55,"protein":None})
        assert created.status_code==201
        foods=owner.get('/api/v1/foods?q=test%20soup').json()
        assert foods[0]['verification']=='user_provided' and foods[0]['protein'] is None
        register(other)
        assert other.get('/api/v1/foods?q=test%20soup').json()==[]

def test_favorites_and_recent_foods_are_private_idempotent_and_cleanup_with_food():
    with TestClient(app) as owner,TestClient(app) as other:
        register(owner);owner_headers={"origin":"http://localhost:5173","x-csrf-token":owner.cookies['lf_csrf']}
        custom=owner.post('/api/v1/foods',headers=owner_headers,json={"name":"Favorite private lentil bowl","kcal":130}).json()
        assert owner.put(f"/api/v1/foods/{custom['id']}/favorite",headers=owner_headers).status_code==204
        assert owner.put(f"/api/v1/foods/{custom['id']}/favorite",headers=owner_headers).status_code==204
        assert owner.put(f"/api/v1/foods/{custom['id']}/recent",headers=owner_headers).status_code==204
        assert [f['id'] for f in owner.get('/api/v1/foods/favorites').json()]==[custom['id']]
        assert [f['id'] for f in owner.get('/api/v1/foods/recent').json()]==[custom['id']]
        register(other);other_headers={"origin":"http://localhost:5173","x-csrf-token":other.cookies['lf_csrf']}
        assert other.put(f"/api/v1/foods/{custom['id']}/favorite",headers=other_headers).status_code==404
        assert other.put(f"/api/v1/foods/{custom['id']}/recent",headers=other_headers).status_code==404
        assert other.get('/api/v1/foods/favorites').json()==[] and other.get('/api/v1/foods/recent').json()==[]
        assert owner.delete(f"/api/v1/foods/{custom['id']}",headers=owner_headers).status_code==204
        assert owner.get('/api/v1/foods/favorites').json()==[] and owner.get('/api/v1/foods/recent').json()==[]

def test_private_file_cleanup_failure_is_retained_for_retry(monkeypatch,tmp_path):
    monkeypatch.setenv('PRIVATE_UPLOAD_DIR',str(tmp_path))
    directory=tmp_path/'temporarily-not-a-file';directory.mkdir()
    with main.SessionLocal() as db:
        db.add(main.PrivateFileCleanup(private_path=str(directory)));db.commit()
        first=main.drain_private_file_cleanup(db)
        assert first=={"removed":0,"failed":1,"remaining":1}
        directory.rmdir()
        second=main.drain_private_file_cleanup(db)
        assert second=={"removed":1,"failed":0,"remaining":0}

def test_deletion_ledger_export_is_signed_and_tampering_is_rejected():
    secret='stable-test-ledger-secret'
    original=[main.hmac.new(secret.encode(),b"deleted@example.com",main.hashlib.sha256).hexdigest()]
    document=export_ledger(original,secret)
    assert verify_ledger(document,secret)==original
    tampered={**document,"digests":["0"*64]}
    try:
        verify_ledger(tampered,secret)
        assert False,"tampered ledger must not validate"
    except ValueError as error:
        assert 'signature' in str(error)

def test_restore_ledger_replay_dry_run_then_removes_deleted_account(tmp_path,monkeypatch):
    secret='stable-replay-test-secret';monkeypatch.setenv('DELETION_LEDGER_SECRET',secret);monkeypatch.setenv('PRIVATE_UPLOAD_DIR',str(tmp_path))
    private=tmp_path/'restored-user'/'scan.jpg';private.parent.mkdir();private.write_bytes(b'private')
    with TestClient(app) as client:
        user=register(client);food=client.post('/api/v1/foods',headers={"origin":"http://localhost:5173","x-csrf-token":client.cookies['lf_csrf']},json={"name":"Restore test private oats","kcal":90}).json()
        with main.SessionLocal() as db:
            db.add(main.ScanSession(owner_id=user['id'],private_path=str(private),candidates=[],status='needs_review'));db.commit()
        digest=main.hmac.new(secret.encode(),user['email'].lower().encode(),main.hashlib.sha256).hexdigest()
        ledger=tmp_path/'ledger.json';ledger.write_text(json.dumps(export_ledger([digest],secret)),encoding='utf-8')
        env=os.environ.copy();env['DELETION_LEDGER_SECRET']=secret;env['PRIVATE_UPLOAD_DIR']=str(tmp_path)
        command=[sys.executable,'scripts/replay-deletion-ledger.py','--ledger-file',str(ledger)]
        dry=subprocess.run(command,capture_output=True,text=True,env=env,check=True)
        assert '1 restored accounts match' in dry.stdout and private.exists()
        applied=subprocess.run(command+['--apply'],capture_output=True,text=True,env=env,check=True)
        assert 'Replay applied. 1 accounts removed' in applied.stdout and str(private) not in applied.stdout
        with main.SessionLocal() as db:
            assert db.get(main.User,user['id']) is None and db.get(main.Food,food['id']) is None
            assert db.scalar(main.select(main.AccountDeletionLedger.id).where(main.AccountDeletionLedger.email_digest==digest)) is not None
        assert not private.exists()

def test_login_and_password_reset_rate_limits_are_persistent():
    with TestClient(app) as client:
        login_statuses=[client.post('/api/v1/auth/login',json={"email":"unknown@example.com","password":"wrong-password"}).status_code for _ in range(16)]
        reset_statuses=[client.post('/api/v1/auth/forgot-password',json={"email":"unknown@example.com"}).status_code for _ in range(11)]
        assert login_statuses==[401]*15+[429]
        assert reset_statuses==[200]*10+[429]
        with main.SessionLocal() as db:
            rows=list(db.scalars(main.select(main.RateLimitBucket).where(main.RateLimitBucket.scope.in_(['login_ip','reset_request_ip']))))
            assert {row.scope:row.count for row in rows}=={'login_ip':16,'reset_request_ip':11}
            db.execute(main.delete(main.RateLimitBucket).where(main.RateLimitBucket.scope.in_(['login_ip','reset_request_ip'])));db.commit()

def test_assistant_rate_limit_applies_during_provider_outage_without_saving(monkeypatch):
    monkeypatch.delenv('AI_BASE_URL',raising=False);monkeypatch.delenv('AI_API_KEY',raising=False);monkeypatch.delenv('AI_MODEL',raising=False)
    with TestClient(app) as client:
        register(client);conversation=client.post('/api/v1/assistant/conversations',headers={"origin":"http://localhost:5173","x-csrf-token":client.cookies['lf_csrf']}).json()
        statuses=[client.post('/api/v1/assistant',json={"conversation_id":conversation['id'],"message":f"question {i}","idempotency_key":uuid4().hex}).status_code for i in range(16)]
        assert statuses==[503]*15+[429]
        assert client.get(f"/api/v1/assistant/conversations/{conversation['id']}").json()['messages']==[]
        with main.SessionLocal() as db:
            row=db.scalar(main.select(main.RateLimitBucket).where(main.RateLimitBucket.scope=='assistant_user'))
            assert row is not None and row.count==16

def test_profile_goal_updates_are_persisted_per_user():
    with TestClient(app) as client:
        register(client)
        csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        response=client.put('/api/v1/users/me',headers=headers,json={"name":"Updated Name","goals":{"calories":2000,"protein":125}})
        assert response.status_code==200
        assert response.json()['name']=='Updated Name'
        assert client.get('/api/v1/analytics/daily').json()['goals']['protein']==125

def test_diet_allergy_units_and_timezone_preferences_are_validated_and_private():
    with TestClient(app) as owner,TestClient(app) as other:
        register(owner);headers={"origin":"http://localhost:5173","x-csrf-token":owner.cookies['lf_csrf']}
        saved=owner.put('/api/v1/users/preferences',headers=headers,json={"diet":"vegan","allergies":["peanuts"," tree nuts ","PEANUTS"],"timezone":"America/Los_Angeles","units":"imperial"})
        assert saved.status_code==200
        assert saved.json()['preferences']=={"diet":"vegan","allergies":["peanuts","tree nuts"],"timezone":"America/Los_Angeles","units":"imperial"}
        assert owner.get('/api/v1/auth/me').json()['preferences']==saved.json()['preferences']
        assert owner.put('/api/v1/users/preferences',headers=headers,json={"diet":"vegan","allergies":[],"timezone":"Not/A_Timezone","units":"metric"}).status_code==422
        register(other)
        assert other.get('/api/v1/auth/me').json()['preferences']=={}

def test_unknown_macros_remain_unknown_in_meal_and_summary():
    with TestClient(app) as client:
        register(client);csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        meal=client.post('/api/v1/meals',headers=headers,json={"name":"Meal with partial data","meal_type":"snack","items":[{"name":"Food","grams":100,"per100":{"kcal":80,"protein":None,"carbs":None,"fat":None}}]})
        assert meal.status_code==201 and meal.json()['kcal']==80
        assert meal.json()['protein'] is None and meal.json()['carbs'] is None
        assert client.get('/api/v1/analytics/daily').json()['totals']['protein'] is None
        assert client.get('/api/v1/privacy/export.json').json()['meals'][0]['nutrition']['protein_g'] is None

def test_meal_update_and_delete_are_owner_scoped():
    with TestClient(app) as owner, TestClient(app) as other:
        register(owner);csrf=owner.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        meal=owner.post('/api/v1/meals',headers=headers,json={"name":"Meal","meal_type":"lunch","items":[]}).json()
        updated=owner.put(f"/api/v1/meals/{meal['id']}",headers=headers,json={"name":"Updated","meal_type":"dinner","items":[]})
        assert updated.status_code==200 and owner.get(f"/api/v1/meals/{meal['id']}").json()['name']=='Updated'
        register(other);their_csrf=other.cookies['lf_csrf'];their_headers={"origin":"http://localhost:5173","x-csrf-token":their_csrf}
        assert other.delete(f"/api/v1/meals/{meal['id']}",headers=their_headers).status_code==404
        assert owner.delete(f"/api/v1/meals/{meal['id']}",headers=headers).status_code==204

def test_conversation_history_is_private_and_deletable():
    with TestClient(app) as owner, TestClient(app) as other:
        register(owner);csrf=owner.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf};created=owner.post('/api/v1/assistant/conversations',headers=headers)
        conversation_id=created.json()['id']
        assert owner.get(f'/api/v1/assistant/conversations/{conversation_id}').json()['messages']==[]
        register(other)
        assert other.get(f'/api/v1/assistant/conversations/{conversation_id}').status_code==404
        assert owner.delete(f'/api/v1/assistant/conversations/{conversation_id}',headers=headers).status_code==204
        assert owner.get(f'/api/v1/assistant/conversations/{conversation_id}').status_code==404

def test_clear_all_conversations_only_clears_current_account():
    with TestClient(app) as owner, TestClient(app) as other:
        register(owner);register(other)
        h1={"origin":"http://localhost:5173","x-csrf-token":owner.cookies['lf_csrf']}
        h2={"origin":"http://localhost:5173","x-csrf-token":other.cookies['lf_csrf']}
        owner.post('/api/v1/assistant/conversations',headers=h1);other.post('/api/v1/assistant/conversations',headers=h2)
        assert owner.delete('/api/v1/assistant/conversations',headers=h1).status_code==204
        assert owner.get('/api/v1/assistant/conversations').json()==[]
        assert len(other.get('/api/v1/assistant/conversations').json())==1

def test_assistant_uses_actual_user_context_and_persists_reply(monkeypatch):
    captured={"calls":0}
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"choices":[{"message":{"content":"You logged 195 kcal today."}}]}
    class FakeClient:
        def __init__(self,timeout): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,url,headers,json): captured['payload']=json;captured['calls']+=1;return FakeResponse()
    monkeypatch.setattr(main.httpx,'Client',FakeClient)
    monkeypatch.setenv('AI_BASE_URL','https://provider.invalid/v1');monkeypatch.setenv('AI_API_KEY','test-only-key');monkeypatch.setenv('AI_MODEL','test-model')
    with TestClient(app) as client:
        register(client);csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        c=client.post('/api/v1/assistant/conversations',headers=headers).json()
        client.post('/api/v1/meals',headers=headers,json={"name":"Lunch","meal_type":"lunch","items":[{"name":"rice","grams":150,"per100":{"kcal":130,"protein":None,"carbs":None,"fat":None}}]})
        client.put('/api/v1/users/preferences',headers=headers,json={"diet":"vegetarian","allergies":["peanuts"],"timezone":"UTC","units":"metric"})
        request={"conversation_id":c['id'],"message":"How much did I eat?","idempotency_key":uuid4().hex}
        answer=client.post('/api/v1/assistant',headers=headers,json=request)
        assert answer.status_code==200 and answer.json()['message']=="You logged 195 kcal today."
        assert '195.0' in captured['payload']['messages'][0]['content']
        assert 'vegetarian' in captured['payload']['messages'][0]['content'] and 'peanuts' in captured['payload']['messages'][0]['content']
        replay=client.post('/api/v1/assistant',headers=headers,json=request)
        assert replay.status_code==200 and replay.json()['already_processed'] is True
        assert replay.json()['message']==answer.json()['message'] and captured['calls']==1
        conflict=client.post('/api/v1/assistant',headers=headers,json={**request,"message":"A different prompt"})
        assert conflict.status_code==409
        assert len(client.get(f"/api/v1/assistant/conversations/{c['id']}").json()['messages'])==2

def test_assistant_daily_context_uses_profile_timezone(monkeypatch):
    captured={}
    class FakeResponse:
        def raise_for_status(self):pass
        def json(self):return {"choices":[{"message":{"content":"Your day is ready."}}]}
    class FakeClient:
        def __init__(self,timeout):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,headers,json):captured['system']=json['messages'][0]['content'];return FakeResponse()
    monkeypatch.setattr(main.httpx,'Client',FakeClient)
    monkeypatch.setenv('AI_BASE_URL','https://provider.invalid/v1');monkeypatch.setenv('AI_API_KEY','test-only-key');monkeypatch.setenv('AI_MODEL','test-model')
    timezone_name='Asia/Kolkata';local_today=datetime.now(ZoneInfo(timezone_name)).date()
    start,end=main.local_date_bounds(local_today,local_today,type('Owner',(),{'preferences':{'timezone':timezone_name}})())
    with TestClient(app) as client:
        register(client);headers={"origin":"http://localhost:5173","x-csrf-token":client.cookies['lf_csrf']}
        client.put('/api/v1/users/preferences',headers=headers,json={"diet":"no_restrictions","allergies":[],"timezone":timezone_name,"units":"metric"})
        previous=(start-timedelta(microseconds=1)).isoformat()
        current=(start+timedelta(minutes=1)).isoformat()
        for name,eaten_at,kcal in [('Yesterday meal',previous,12),('Today meal',current,34)]:
            response=client.post('/api/v1/meals',headers=headers,json={"name":name,"meal_type":"snack","eaten_at":eaten_at,"items":[{"name":"Test food","grams":100,"per100":{"kcal":kcal}}]})
            assert response.status_code==201
        conversation=client.post('/api/v1/assistant/conversations',headers=headers).json()
        answer=client.post('/api/v1/assistant',json={"conversation_id":conversation['id'],"message":"What have I eaten today?","idempotency_key":uuid4().hex})
        assert answer.status_code==200
        assert 'Today meal' in captured['system'] and 'Yesterday meal' not in captured['system']
        assert '34.0' in captured['system']

def test_onboarding_calculates_targets_and_persists_weight_history():
    with TestClient(app) as client:
        register(client);csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        response=client.post('/api/v1/users/onboarding',headers=headers,json={"age":30,"sex":"female","height_cm":165,"weight_kg":70,"goal":"weight_loss","activity":"moderate","diet":"vegetarian","allergies":["peanuts"],"timezone":"Asia/Kolkata","units":"metric"})
        assert response.status_code==200
        assert 1400<=response.json()['goals']['calories']<=4500
        assert response.json()['profile']['weight_kg']==70
        me=client.get('/api/v1/auth/me').json()
        assert me['preferences']['allergies']==['peanuts']
        assert len(client.get('/api/v1/weight').json())==1

def test_weight_history_is_user_scoped_and_onboarding_validates_timezone():
    with TestClient(app) as owner, TestClient(app) as other:
        register(owner);csrf=owner.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        payload={"age":28,"sex":"other","height_cm":172,"weight_kg":68,"goal":"balanced","activity":"light","timezone":"Not/AZone"}
        assert owner.post('/api/v1/users/onboarding',headers=headers,json=payload).status_code==422
        payload['timezone']='UTC'
        assert owner.post('/api/v1/users/onboarding',headers=headers,json=payload).status_code==200
        register(other)
        assert other.get('/api/v1/weight').json()==[]

def test_password_reset_uses_expiring_single_use_token(monkeypatch):
    sent={}
    monkeypatch.setenv('SMTP_HOST','mail.example.test');monkeypatch.setenv('SMTP_FROM','support@lossfit.test')
    monkeypatch.setattr(main,'send_password_reset_email',lambda email,url:sent.update(email=email,url=url))
    with TestClient(app) as client:
        user=register(client)
        csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        response=client.post('/api/v1/auth/forgot-password',headers=headers,json={"email":user['email']})
        assert response.status_code==200
        # The sent link is only captured by the deterministic email test double; the API response stays generic.
        assert 'token' not in response.text and sent['email']==user['email']
        token=sent['url'].split('token=')[1]
        reset=client.post('/api/v1/auth/reset-password',headers=headers,json={"token":token,"password":"different-secure-password"})
        assert reset.status_code==200
        assert client.post('/api/v1/auth/reset-password',headers=headers,json={"token":token,"password":"another-secure-password"}).status_code==400
        assert client.get('/api/v1/auth/me').status_code==401
        login=client.post('/api/v1/auth/login',json={"email":sent['email'],"password":"different-secure-password"})
        assert login.status_code==200
        client.headers.update({"Authorization":f"Bearer {login.json()['access_token']}"})
        assert client.get('/api/v1/auth/me').status_code==200

def test_refresh_rotates_tokens_and_logout_revokes_current_session():
    with TestClient(app) as client:
        register(client);old_access=client.headers['Authorization'];old_refresh=client.cookies.get('lf_refresh');csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        rotated=client.post('/api/v1/auth/refresh',headers=headers)
        assert rotated.status_code==200 and rotated.json()['access_token']!=old_access.removeprefix('Bearer ')
        new_refresh=client.cookies.get('lf_refresh');new_csrf=client.cookies['lf_csrf'];assert new_refresh!=old_refresh
        client.headers.update({"Authorization":f"Bearer {rotated.json()['access_token']}"})
        assert client.get('/api/v1/auth/me').status_code==200
        client.cookies.set('lf_refresh',old_refresh,path='/api/v1/auth')
        reused=client.post('/api/v1/auth/refresh',headers={"origin":"http://localhost:5173","x-csrf-token":new_csrf})
        assert reused.status_code==401
        client.cookies.set('lf_refresh',new_refresh,path='/api/v1/auth')
        logout=client.post('/api/v1/auth/logout',headers={"origin":"http://localhost:5173","x-csrf-token":new_csrf})
        assert logout.status_code==204
        assert client.get('/api/v1/auth/me').status_code==401
        client.cookies.set('lf_refresh',new_refresh,path='/api/v1/auth')
        client.cookies.set('lf_csrf',new_csrf,path='/')
        assert client.post('/api/v1/auth/refresh',headers={"origin":"http://localhost:5173","x-csrf-token":new_csrf}).status_code==401

def test_learning_lessons_are_sourced_and_progress_is_private_and_persisted():
    with TestClient(app) as learner, TestClient(app) as other:
        register(learner)
        lessons=learner.get('/api/v1/learning').json()
        assert len(lessons)>=3 and all(item['sources'] for item in lessons)
        lesson=learner.get('/api/v1/learning/read-a-food-label').json()
        assert 'answer' not in lesson['quiz']
        assert learner.get('/api/v1/learning/read-a-food-label?detailed=true').json()['content']!=lesson['content']
        csrf=learner.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        result=learner.post('/api/v1/learning/read-a-food-label/complete',headers=headers,json={"answers":[1]})
        assert result.status_code==200 and result.json()['correct'] is True
        progress=next(item['progress'] for item in learner.get('/api/v1/learning').json() if item['slug']=='read-a-food-label')
        assert progress['score']==1 and progress['version']==1
        register(other)
        assert all(item['progress'] is None for item in other.get('/api/v1/learning').json())

def test_knowledge_retrieval_cites_latest_reviewed_source_version():
    with main.SessionLocal() as session:
        older=main.KnowledgeSource(source_key='test-label-guide',version=1,title='Older label guide',organization='Test agency',url='https://example.test/old',content_hash='1'*64)
        newer=main.KnowledgeSource(source_key='test-label-guide',version=2,title='Current label guide',organization='Test agency',url='https://example.test/current',content_hash='2'*64)
        unrelated=main.KnowledgeSource(source_key='test-hydration-guide',version=1,title='Water guide',organization='Test agency',url='https://example.test/water',content_hash='3'*64)
        session.add_all([older,newer,unrelated]);session.flush()
        session.add_all([
            main.KnowledgeChunk(source_id=older.id,chunk_index=0,content='FDA Nutrition Facts label serving size information.',embedding=None),
            main.KnowledgeChunk(source_id=newer.id,chunk_index=0,content='FDA Nutrition Facts label serving size and percent Daily Value details.',embedding=None),
            main.KnowledgeChunk(source_id=unrelated.id,chunk_index=0,content='Water intake changes with activity and hot weather.',embedding=None),
        ]);session.commit()
        matches=main.retrieve_knowledge(session,'FDA nutrition facts serving size percent daily value')
        assert matches[0]['source']['title']=='Current label guide'
        assert matches[0]['source']['version']==2 and matches[0]['ref']=='K1'
        assert main.retrieve_knowledge(session,'information about astronomy galaxies')==[]

def test_assistant_includes_retrieved_evidence_and_persists_citations(monkeypatch):
    captured={}
    evidence=[{"ref":"K1","text":"Serving size on a nutrition label is not a recommendation of how much to eat.","source":{"title":"FDA label guide","organization":"U.S. Food and Drug Administration","url":"https://www.fda.gov/food/nutrition-facts-label/how-understand-and-use-nutrition-facts-label","version":1}}]
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"choices":[{"message":{"content":"A label serving is a reference amount, not a suggested portion [K1]."}}]}
    class FakeClient:
        def __init__(self,timeout): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,url,headers,json): captured['messages']=json['messages'];return FakeResponse()
    monkeypatch.setattr(main.httpx,'Client',FakeClient)
    monkeypatch.setattr(main,'retrieve_knowledge',lambda session,query:evidence)
    monkeypatch.setenv('AI_BASE_URL','https://provider.invalid/v1');monkeypatch.setenv('AI_API_KEY','test-only-key');monkeypatch.setenv('AI_MODEL','test-model')
    with TestClient(app) as client:
        register(client);csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        conversation=client.post('/api/v1/assistant/conversations',headers=headers).json()
        response=client.post('/api/v1/assistant',headers=headers,json={"conversation_id":conversation['id'],"message":"What does serving size mean?","idempotency_key":uuid4().hex})
        assert response.status_code==200 and response.json()['sources'][0]['ref']=='K1'
        assert 'Serving size on a nutrition label' in captured['messages'][0]['content']
        persisted=client.get(f"/api/v1/assistant/conversations/{conversation['id']}").json()['messages'][-1]
        assert persisted['citations'][0]['url']==evidence[0]['source']['url']

def test_embedding_adapter_validates_dimensions_and_sorts_provider_results(monkeypatch):
    monkeypatch.setenv('AI_BASE_URL','https://embedding.provider.test/v1');monkeypatch.setenv('AI_API_KEY','test-only-key');monkeypatch.setenv('EMBEDDING_MODEL','test-embedding-model')
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"data":[{"index":1,"embedding":[0.0,1.0]},{"index":0,"embedding":[1.0,0.0]}]}
    class FakeClient:
        def __init__(self,timeout): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,*args,**kwargs): return FakeResponse()
    monkeypatch.setattr(main.httpx,'Client',FakeClient)
    vectors,model=main.request_embeddings(['first','second'])
    assert model=='test-embedding-model' and vectors==[[1.0,0.0],[0.0,1.0]]
    assert cosine([1.0,0.0],[1.0,0.0])==1.0 and cosine([1.0],[0.0,1.0])==0.0

def test_food_import_keeps_missing_nutrients_null_preserves_zero_and_explains_exclusions():
    base={"fdcId":123,"description":"Chicken breast, raw","foodCategory":{"description":"Poultry"},"foodPortions":[{"amount":1,"measureUnit":{"name":"piece"},"gramWeight":120}],"foodNutrients":[
        {"nutrient":{"id":1008,"name":"Energy"},"amount":0,"foodNutrientDerivation":{"code":"A","description":"Analytical","foodNutrientSource":{"description":"Analytical"}}},
        {"nutrient":{"id":1003,"name":"Protein"},"amount":20,"foodNutrientDerivation":{"code":"NC","description":"Calculated","foodNutrientSource":{"description":"Calculated"}}},
        {"nutrient":{"id":1005,"name":"Carbohydrate, by difference"},"amount":-0.2,"foodNutrientDerivation":{"code":"NC","description":"Calculated","foodNutrientSource":{"description":"Calculated"}}},
    ]}
    imported=normalize_foundation_food(base)
    assert imported['state']=='raw' and imported['kcal']==0 and imported['fat'] is None
    assert imported['nutrition_provenance']['kcal']['status']=='verified'
    assert imported['nutrition_provenance']['protein']['status']=='reviewed'
    assert imported['carbs'] is None and imported['nutrition_provenance']['carbs']['status']=='unavailable'
    assert imported['data_notes'] and imported['servings']==[{"label":"1 piece","grams":120.0}]

def test_catalogue_search_finds_late_matches_and_exposes_source_provenance():
    source_id=f"test-{uuid4().hex}"
    with main.SessionLocal() as db:
        rows=[Food(owner_id=None,name=f"A catalogue filler {i:03d}",state="prepared",aliases=[],verification="reviewed",source="test",nutrition_basis="per_100g",nutrition_provenance={}) for i in range(75)]
        target=Food(owner_id=None,name="Rarely listed cooked lentils",state="cooked",aliases=["lentils"],verification="reviewed",source="USDA FoodData Central FNDDS test",source_record_id=source_id,source_url="https://fdc.nal.usda.gov/food-details/123/nutrients",nutrition_basis="per_100g",nutrition_provenance={"kcal":{"status":"reviewed","source":"Survey"}},kcal=116,protein=9,carbs=20,fat=0.4)
        db.add_all(rows+[target]);db.flush();db.add(FoodServing(food_id=target.id,label="1 cup",grams=198,source="USDA"));target_id=target.id;db.commit()
    with TestClient(app) as client:
        register(client)
        results=client.get('/api/v1/foods?q=rarely%20listed').json()
        assert len(results)==1 and results[0]['id']==target_id
        detail=client.get(f"/api/v1/foods/{target_id}").json()
        assert detail['source_record_id']==source_id and detail['source_url'].startswith('https://fdc.nal.usda.gov/')
        assert detail['nutrition_provenance']['kcal']['status']=='reviewed'
        assert detail['kcal']==116 and detail['servings'][0]['source']=='USDA'
    with main.SessionLocal() as db:
        db.query(FoodServing).filter(FoodServing.food_id==target_id).delete()
        db.query(Food).filter(Food.id==target_id).delete()
        db.query(Food).filter(Food.name.like('A catalogue filler %')).delete(synchronize_session=False)
        db.commit()

def test_forgot_password_response_does_not_reveal_account_existence():
    with TestClient(app) as client:
        unknown=client.post('/api/v1/auth/forgot-password',json={"email":"nobody@example.com"})
        assert unknown.status_code==200
        assert 'If an account exists' in unknown.json()['message']

def test_account_deletion_requires_password_and_confirmation_then_cleans_user_data(monkeypatch,tmp_path):
    with TestClient(app) as client:
        user=register(client);csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        monkeypatch.setenv('PRIVATE_UPLOAD_DIR',str(tmp_path));private_file=tmp_path/str(user['id'])/'scan.jpg';private_file.parent.mkdir();private_file.write_bytes(b'private')
        with main.SessionLocal() as db:db.add(main.ScanSession(owner_id=user['id'],private_path=str(private_file),candidates=[],status='needs_review'));db.commit()
        client.post('/api/v1/foods',headers=headers,json={"name":"Private oats","kcal":80})
        meal=client.post('/api/v1/meals',headers=headers,json={"name":"Breakfast","meal_type":"breakfast","items":[]})
        conversation=client.post('/api/v1/assistant/conversations',headers=headers).json()
        wrong=client.request('DELETE','/api/v1/account',headers=headers,json={"password":"wrong-password","confirmation":"DELETE MY ACCOUNT"})
        assert wrong.status_code==403
        deleted=client.request('DELETE','/api/v1/account',headers=headers,json={"password":"safe-password-987","confirmation":"DELETE MY ACCOUNT"})
        assert deleted.status_code==204
        assert not private_file.exists()
        assert client.get('/api/v1/auth/me').status_code==401
        assert client.get(f"/api/v1/meals/{meal.json()['id']}").status_code==401
        with main.SessionLocal() as db:
            assert db.scalar(main.select(main.User).where(main.User.id==user['id'])) is None
            assert db.scalar(main.select(main.Food).where(main.Food.name=='Private oats')) is None
            assert db.scalar(main.select(main.Conversation).where(main.Conversation.id==conversation['id'])) is None
            assert db.scalar(main.select(main.AccountDeletionLedger)) is not None

def test_catalogue_food_drives_server_nutrition_and_meal_snapshot_survives_catalogue_edits():
    with TestClient(app) as client:
        register(client);csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        food=client.post('/api/v1/foods',headers=headers,json={"name":"Rice","state":"cooked","aliases":["steamed rice"],"kcal":130,"protein":2.7,"carbs":28,"fat":0.3,"serving_label":"1 cup","serving_grams":158})
        assert food.status_code==201 and food.json()['servings'][-1]['grams']==158
        assert client.get('/api/v1/foods?q=steamed%20rice').json()[0]['id']==food.json()['id']
        meal=client.post('/api/v1/meals',headers=headers,json={"name":"Lunch","meal_type":"lunch","items":[{"food_id":food.json()['id'],"name":"tampered name","grams":150,"per100":{"kcal":999,"protein":999,"carbs":999,"fat":999}}]})
        assert meal.status_code==201 and meal.json()['kcal']==195
        item=meal.json()['items'][0]
        assert item['name']=='Rice' and item['per100']['kcal']==130 and item['verification']=='user_provided'
        changed=client.put(f"/api/v1/foods/{food.json()['id']}",headers=headers,json={"name":"Rice cooked","state":"cooked","kcal":200,"protein":3,"carbs":40,"fat":1})
        assert changed.status_code==200
        historical=client.get(f"/api/v1/meals/{meal.json()['id']}").json()
        assert historical['items'][0]['name']=='Rice' and historical['items'][0]['per100']['kcal']==130 and historical['kcal']==195
        edited=client.put(f"/api/v1/meals/{meal.json()['id']}",headers=headers,json={"name":"Lunch","meal_type":"lunch","items":[{"snapshot_id":item['snapshot_id'],"food_id":food.json()['id'],"name":"tampered again","grams":200,"per100":{"kcal":1,"protein":1,"carbs":1,"fat":1}}]})
        assert edited.status_code==200 and edited.json()['kcal']==260
        assert edited.json()['items'][0]['per100']['kcal']==130
        assert client.delete(f"/api/v1/foods/{food.json()['id']}",headers=headers).status_code==204
        retained=client.get(f"/api/v1/meals/{meal.json()['id']}").json()
        assert retained['items'][0]['name']=='Rice' and retained['kcal']==260

def test_food_servings_and_food_edits_are_owner_scoped_and_nutrients_validated():
    with TestClient(app) as owner, TestClient(app) as other:
        register(owner);csrf=owner.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        food=owner.post('/api/v1/foods',headers=headers,json={"name":"Pear","kcal":57})
        serving=food.json()['servings'][0]
        assert owner.delete(f"/api/v1/foods/{food.json()['id']}/servings/{serving['id']}",headers=headers).status_code==400
        register(other)
        assert other.get(f"/api/v1/foods/{food.json()['id']}").status_code==404
        other_headers={"origin":"http://localhost:5173","x-csrf-token":other.cookies['lf_csrf']}
        assert other.put(f"/api/v1/foods/{food.json()['id']}",headers=other_headers,json={"name":"Hijack","kcal":0}).status_code==404
        assert other.delete(f"/api/v1/foods/{food.json()['id']}/servings/{serving['id']}",headers=other_headers).status_code==404
        assert owner.post('/api/v1/foods',headers=headers,json={"name":"Bad nutrition","kcal":-1}).status_code==422
        assert owner.post(f"/api/v1/foods/{food.json()['id']}/servings",headers=headers,json={"label":"Huge","grams":10001}).status_code==422

def test_meal_history_analytics_and_exports_use_user_local_dates():
    with TestClient(app) as client:
        register(client);csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        onboarding={"age":30,"sex":"other","height_cm":170,"weight_kg":70,"goal":"balanced","activity":"light","timezone":"Asia/Kolkata","units":"metric"}
        assert client.post('/api/v1/users/onboarding',headers=headers,json=onboarding).status_code==200
        local_today=datetime.now(ZoneInfo('Asia/Kolkata')).date()
        local_start=datetime.combine(local_today,datetime.min.time(),ZoneInfo('Asia/Kolkata'))
        start_utc=local_start.astimezone(timezone.utc)
        first=client.post('/api/v1/meals',headers=headers,json={"name":"Before midnight UTC","meal_type":"dinner","eaten_at":(start_utc+timedelta(minutes=5)).isoformat(),"items":[{"name":"Partial meal","grams":100,"per100":{"kcal":100,"protein":None}}]})
        next_day=client.post('/api/v1/meals',headers=headers,json={"name":"Next local date","meal_type":"snack","eaten_at":(start_utc+timedelta(days=1,minutes=5)).isoformat(),"items":[]})
        assert first.status_code==201 and next_day.status_code==201
        history=client.get(f"/api/v1/meals?date={local_today.isoformat()}").json()
        assert [m['name'] for m in history]==['Before midnight UTC']
        trends=client.get('/api/v1/analytics/range?days=7').json()
        bucket=next(d for d in trends['daily'] if d['date']==local_today.isoformat())
        assert bucket['totals']['kcal']==100 and bucket['totals']['protein'] is None
        export=client.get(f"/api/v1/privacy/export.json?start_date={local_today}&end_date={local_today}").json()
        assert len(export['meals'])==1 and export['meals'][0]['name']=='Before midnight UTC'
        assert client.get(f"/api/v1/privacy/export.csv?start_date={local_today}&end_date={local_today}").status_code==200
        assert client.get('/api/v1/analytics/range?days=6').status_code==422

def test_scanner_validates_private_image_resolves_candidates_and_confirms_once(monkeypatch,tmp_path):
    image=io.BytesIO();Image.new('RGB',(320,240),(30,140,70)).save(image,format='PNG');image_bytes=image.getvalue()
    monkeypatch.setenv('PRIVATE_UPLOAD_DIR',str(tmp_path));monkeypatch.setenv('AI_BASE_URL','https://vision.invalid/v1');monkeypatch.setenv('AI_API_KEY','secret-test-key');monkeypatch.setenv('VISION_MODEL','test-vision')
    captured={}
    class Response:
        def raise_for_status(self):pass
        def json(self):return {"choices":[{"message":{"content":'{"items":[{"name":"banana","grams":118}]}'}}]}
    class FakeClient:
        def __init__(self,timeout):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,headers,json):captured['request']=json;return Response()
    monkeypatch.setattr(main.httpx,'Client',FakeClient)
    with TestClient(app) as owner,TestClient(app) as other:
        register(owner);csrf=owner.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        food=owner.post('/api/v1/foods',headers=headers,json={"name":"Banana","kcal":89,"carbs":22.8,"protein":1.1,"fat":0.3}).json()
        scan=owner.post('/api/v1/scans',headers=headers,files={"image":("photo.png",image_bytes,"image/png")})
        assert scan.status_code==201 and scan.json()['candidates'][0]['name']=='banana'
        assert set(scan.json()['candidates'][0]).issuperset({'id','name','grams','matches'})
        assert 'per100' not in scan.json()['candidates'][0] and 'kcal' not in scan.json()['candidates'][0]
        scan_id=scan.json()['id'];path=next(tmp_path.rglob('*.jpg'))
        with Image.open(path) as sanitized:assert sanitized.format=='JPEG' and sanitized.getexif()=={}
        assert owner.get(f'/api/v1/scans/{scan_id}/image').status_code==200
        register(other)
        assert other.get(f'/api/v1/scans/{scan_id}').status_code==404
        assert other.get(f'/api/v1/scans/{scan_id}/image').status_code==404
        other_headers={"origin":"http://localhost:5173","x-csrf-token":other.cookies['lf_csrf']}
        assert other.delete(f'/api/v1/scans/{scan_id}',headers=other_headers).status_code==404
        incomplete=owner.post(f'/api/v1/scans/{scan_id}/confirm',headers=headers,json={"name":"Lunch","meal_type":"lunch","items":[],"removed_candidate_ids":[]})
        assert incomplete.status_code==422
        confirmed=owner.post(f'/api/v1/scans/{scan_id}/confirm',headers=headers,json={"name":"Lunch","meal_type":"lunch","items":[{"candidate_id":"0","food_id":food['id'],"grams":118}],"removed_candidate_ids":[]})
        assert confirmed.status_code==200 and confirmed.json()['meal']['kcal']==105.02
        assert len(owner.get('/api/v1/privacy/export.json').json()['meals'])==1
        assert other.get('/api/v1/privacy/export.json').json()['meals']==[]
        assert 'Lunch' not in other.get('/api/v1/privacy/export.csv').text
        repeat=owner.post(f'/api/v1/scans/{scan_id}/confirm',headers=headers,json={"name":"Lunch duplicate","meal_type":"lunch","items":[{"candidate_id":"0","food_id":food['id'],"grams":118}],"removed_candidate_ids":[]})
        assert repeat.status_code==200 and repeat.json()['already_confirmed'] is True
        assert repeat.json()['meal']['id']==confirmed.json()['meal']['id']
        assert owner.delete(f'/api/v1/scans/{scan_id}',headers=headers).status_code==204
        assert not path.exists()

def test_scanner_reports_provider_outage_and_rejects_small_or_invalid_images(monkeypatch,tmp_path):
    image=io.BytesIO();Image.new('RGB',(64,64),'red').save(image,format='PNG');valid=image.getvalue()
    tiny=io.BytesIO();Image.new('RGB',(10,10),'red').save(tiny,format='PNG')
    monkeypatch.setenv('PRIVATE_UPLOAD_DIR',str(tmp_path));monkeypatch.delenv('AI_BASE_URL',raising=False);monkeypatch.delenv('AI_API_KEY',raising=False);monkeypatch.delenv('AI_MODEL',raising=False);monkeypatch.delenv('VISION_MODEL',raising=False)
    with TestClient(app) as client:
        register(client);csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        assert client.get('/api/v1/scan/status').json()['available'] is False
        assert client.post('/api/v1/scans',headers=headers,files={"image":("tiny.png",tiny.getvalue(),"image/png")}).status_code==422
        assert client.post('/api/v1/scans',headers=headers,files={"image":("bad.jpg",b"not an image","image/jpeg")}).status_code==415
        outage=client.post('/api/v1/scans',headers=headers,files={"image":("food.png",valid,"image/png")})
        assert outage.status_code==503 and 'manually' in outage.json()['detail']
        assert list(tmp_path.rglob('*.jpg'))==[]

def test_scanner_upload_rate_limit_persists_across_requests(monkeypatch):
    image=io.BytesIO();Image.new('RGB',(64,64),'blue').save(image,format='PNG');valid=image.getvalue()
    monkeypatch.delenv('AI_BASE_URL',raising=False);monkeypatch.delenv('AI_API_KEY',raising=False);monkeypatch.delenv('AI_MODEL',raising=False);monkeypatch.delenv('VISION_MODEL',raising=False)
    with TestClient(app) as client:
        register(client);csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        statuses=[client.post('/api/v1/scans',headers=headers,files={"image":("food.png",valid,"image/png")}).status_code for _ in range(4)]
        assert statuses==[503,503,503,429]
        with main.SessionLocal() as db:
            digest=main.hmac.new(main.JWT_SECRET.encode(),(f"scan_upload_user:{client.get('/api/v1/auth/me').json()['id']}").encode(),main.hashlib.sha256).hexdigest()
            row=db.scalar(main.select(main.RateLimitBucket).where(main.RateLimitBucket.scope=='scan_upload_user',main.RateLimitBucket.subject_digest==digest))
            assert row is not None and row.count==4
