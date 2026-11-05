"""Fail-closed checks for production-only configuration."""
from urllib.parse import urlsplit

def validate_production_environment(env):
    if env.get('ENVIRONMENT')!='production':return
    for name in ('JWT_SECRET','DELETION_LEDGER_SECRET'):
        value=env.get(name,'')
        if len(value)<32 or value.lower().startswith(('replace','local-only','local-e2e','change-me')):
            raise RuntimeError(f'Production requires a non-placeholder {name} of at least 32 characters')
    origins=env.get('CORS_ORIGINS','').split(',')
    for name,values in [('CORS_ORIGINS',origins),('APP_BASE_URL',[env.get('APP_BASE_URL','')])]:
        for value in values:
            parsed=urlsplit(value)
            if parsed.scheme!='https' or not parsed.hostname or '*' in value or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
                raise RuntimeError(f'Production {name} must contain explicit HTTPS origins')
