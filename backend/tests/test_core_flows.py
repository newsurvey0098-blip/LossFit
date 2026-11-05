from uuid import uuid4
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import io
from PIL import Image
from fastapi.testclient import TestClient
from backend.app.main import app
import backend.app.main as main

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

def test_profile_goal_updates_are_persisted_per_user():
    with TestClient(app) as client:
        register(client)
        csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        response=client.put('/api/v1/users/me',headers=headers,json={"name":"Updated Name","goals":{"calories":2000,"protein":125}})
        assert response.status_code==200
        assert response.json()['name']=='Updated Name'
        assert client.get('/api/v1/analytics/daily').json()['goals']['protein']==125

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
    captured={}
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"choices":[{"message":{"content":"You logged 195 kcal today."}}]}
    class FakeClient:
        def __init__(self,timeout): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,url,headers,json): captured['payload']=json;return FakeResponse()
    monkeypatch.setattr(main.httpx,'Client',FakeClient)
    monkeypatch.setenv('AI_BASE_URL','https://provider.invalid/v1');monkeypatch.setenv('AI_API_KEY','test-only-key');monkeypatch.setenv('AI_MODEL','test-model')
    with TestClient(app) as client:
        register(client);csrf=client.cookies['lf_csrf'];headers={"origin":"http://localhost:5173","x-csrf-token":csrf}
        c=client.post('/api/v1/assistant/conversations',headers=headers).json()
        client.post('/api/v1/meals',headers=headers,json={"name":"Lunch","meal_type":"lunch","items":[{"name":"rice","grams":150,"per100":{"kcal":130,"protein":None,"carbs":None,"fat":None}}]})
        answer=client.post('/api/v1/assistant',headers=headers,json={"conversation_id":c['id'],"message":"How much did I eat?"})
        assert answer.status_code==200 and answer.json()['message']=="You logged 195 kcal today."
        assert '195.0' in captured['payload']['messages'][0]['content']
        assert len(client.get(f"/api/v1/assistant/conversations/{c['id']}").json()['messages'])==2

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
        other_headers={"origin":"http://localhost:5173","x-csrf-token":other.cookies['lf_csrf']}
        assert other.delete(f'/api/v1/scans/{scan_id}',headers=other_headers).status_code==404
        incomplete=owner.post(f'/api/v1/scans/{scan_id}/confirm',headers=headers,json={"name":"Lunch","meal_type":"lunch","items":[],"removed_candidate_ids":[]})
        assert incomplete.status_code==422
        confirmed=owner.post(f'/api/v1/scans/{scan_id}/confirm',headers=headers,json={"name":"Lunch","meal_type":"lunch","items":[{"candidate_id":"0","food_id":food['id'],"grams":118}],"removed_candidate_ids":[]})
        assert confirmed.status_code==200 and confirmed.json()['meal']['kcal']==105.02
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
