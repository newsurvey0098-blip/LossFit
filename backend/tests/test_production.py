import pytest
from backend.app.production import validate_production_environment

def valid():return {'ENVIRONMENT':'production','JWT_SECRET':'a'*48,'DELETION_LEDGER_SECRET':'b'*48,'CORS_ORIGINS':'https://lossfit.example','APP_BASE_URL':'https://lossfit.example'}

@pytest.mark.parametrize('name,value', [('JWT_SECRET','replace-with-a-random-secret-of-at-least-32-characters'),('DELETION_LEDGER_SECRET','short'),('CORS_ORIGINS','*'),('CORS_ORIGINS','http://localhost:5173'),('APP_BASE_URL','https://user:secret@example.com'),('CORS_ORIGINS','https://example.com/private'),('APP_BASE_URL','')])
def test_production_rejects_unsafe_configuration(name,value):
    env=valid();env[name]=value
    with pytest.raises(RuntimeError):validate_production_environment(env)

def test_production_accepts_explicit_https_origins_and_development_remains_local():
    validate_production_environment(valid())
    validate_production_environment({'ENVIRONMENT':'development'})
