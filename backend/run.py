"""Production API entry point; a trusted HTTPS reverse proxy terminates TLS."""
import os
from dotenv import load_dotenv
import uvicorn

if __name__=='__main__':
    load_dotenv()
    if os.getenv('ENVIRONMENT')!='production':raise SystemExit('Set ENVIRONMENT=production before using this entry point')
    uvicorn.run('backend.app.main:app',host=os.getenv('BIND_HOST','127.0.0.1'),port=int(os.getenv('PORT','3001')),access_log=False,proxy_headers=True,forwarded_allow_ips=os.getenv('TRUSTED_PROXY_IPS','127.0.0.1'))
