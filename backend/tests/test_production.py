from pathlib import Path

import pytest
from backend.app.production import validate_production_environment

def valid():return {'ENVIRONMENT':'production','JWT_SECRET':'a'*48,'DELETION_LEDGER_SECRET':'b'*48,'CORS_ORIGINS':'https://lossfit.example','APP_BASE_URL':'https://lossfit.example','PRIVATE_UPLOAD_DIR':str(Path.cwd()/'private-uploads')}

@pytest.mark.parametrize('name,value', [('JWT_SECRET','replace-with-a-random-secret-of-at-least-32-characters'),('DELETION_LEDGER_SECRET','short'),('CORS_ORIGINS','*'),('CORS_ORIGINS','http://localhost:5173'),('APP_BASE_URL','https://user:secret@example.com'),('CORS_ORIGINS','https://example.com/private'),('APP_BASE_URL','')])
def test_production_rejects_unsafe_configuration(name,value):
    env=valid();env[name]=value
    with pytest.raises(RuntimeError):validate_production_environment(env)

def test_production_accepts_explicit_https_origins_and_development_remains_local():
    validate_production_environment(valid())
    validate_production_environment({'ENVIRONMENT':'development'})

def test_production_requires_durable_private_file_storage():
    env=valid();env.pop('PRIVATE_UPLOAD_DIR')
    with pytest.raises(RuntimeError,match='private Blob storage'):
        validate_production_environment(env)
    env=valid();env['BLOB_STORE_ID']='store_lossfit'
    validate_production_environment(env)

def test_production_rejects_relative_private_upload_directory():
    env=valid();env['PRIVATE_UPLOAD_DIR']='uploads'
    with pytest.raises(RuntimeError,match='absolute persistent directory'):
        validate_production_environment(env)
