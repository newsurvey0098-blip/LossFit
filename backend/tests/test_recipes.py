from uuid import uuid4
from fastapi.testclient import TestClient
from backend.app.main import app

def user(client):
    r=client.post('/api/v1/auth/register',json={'name':'Recipe user','email':f'{uuid4().hex}@example.com','password':'safe-password-987'}).json()
    client.headers['Authorization']='Bearer '+r['access_token']
    return {'origin':'http://localhost:5173','x-csrf-token':client.cookies['lf_csrf']}

def test_recipe_yield_privacy_and_immutable_meal_snapshots():
    with TestClient(app) as owner,TestClient(app) as other:
        h=user(owner);oh=user(other)
        ingredient=owner.post('/api/v1/foods',headers=h,json={'name':'Dry oats','state':'raw','kcal':400,'protein':10}).json()
        data={'name':'Oat porridge','yield_grams':400,'ingredients':[{'food_id':ingredient['id'],'grams':100}]}
        response=owner.post('/api/v1/recipes',headers=h,json=data)
        assert response.status_code==201
        recipe=response.json();rid=recipe['id'];snap=recipe['recipe']['ingredients'][0]['snapshot_id']
        assert recipe['kcal']==100 and recipe['protein']==2.5 and recipe['carbs'] is None
        assert recipe['verification']=='estimated' and recipe['recipe']['ingredients'][0]['state']=='raw'
        meal=owner.post('/api/v1/meals',headers=h,json={'name':'Porridge breakfast','meal_type':'breakfast','items':[{'food_id':rid,'grams':200}]}).json()
        assert meal['kcal']==200 and meal['items'][0]['recipe']['yield_grams']==400
        assert other.get(f'/api/v1/foods/{rid}').status_code==404
        assert other.put(f'/api/v1/recipes/{rid}',headers=oh,json=data).status_code==404
        assert other.post('/api/v1/recipes',headers=oh,json=data).status_code==422
        owner.put(f"/api/v1/foods/{ingredient['id']}",headers=h,json={'name':'Updated oats','kcal':900})
        edited=owner.put(f'/api/v1/recipes/{rid}',headers=h,json={**data,'yield_grams':200,'ingredients':[{'food_id':ingredient['id'],'snapshot_id':snap,'grams':100}]}).json()
        assert edited['kcal']==200 and edited['recipe']['ingredients'][0]['name']=='Dry oats'
        assert owner.put(f'/api/v1/foods/{rid}',headers=h,json={'name':'Tampered','kcal':1}).status_code==409
        assert owner.put(f'/api/v1/recipes/{rid}',headers=h,json={**data,'ingredients':[{'food_id':rid,'grams':100}]}).status_code==422
        assert owner.post('/api/v1/recipes',headers=h,json={**data,'yield_grams':0}).status_code==422
        assert owner.post('/api/v1/recipes',headers=h,json={**data,'yield_grams':0.1}).status_code==422
        assert owner.delete(f'/api/v1/foods/{rid}',headers=h).status_code==204
        historical=owner.get(f"/api/v1/meals/{meal['id']}").json()
        assert historical['kcal']==200 and historical['items'][0]['recipe']['yield_grams']==400
