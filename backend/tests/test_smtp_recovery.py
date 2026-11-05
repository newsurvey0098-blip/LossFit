"""Real local SMTP-over-TLS delivery; no provider credentials or public email."""
import re
import ssl
import socketserver
import threading
from queue import Queue
from datetime import datetime,timedelta,timezone
from ipaddress import ip_address
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from email import policy
from email.parser import BytesParser
import pytest
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import backend.app.main as main

@pytest.fixture
def smtp_sink(tmp_path,monkeypatch):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')]);now=datetime.now(timezone.utc)
    cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip_address('127.0.0.1'))]),critical=False).sign(key,hashes.SHA256())
    cert_path=tmp_path/'smtp-cert.pem';key_path=tmp_path/'smtp-key.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM));key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    messages=Queue()
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.wfile.write(b'220 localhost test SMTP\r\n')
            while line:=self.rfile.readline():
                command=line.split(b' ',1)[0].strip().upper()
                if command in (b'EHLO',b'HELO'):self.wfile.write(b'250 localhost\r\n')
                elif command==b'DATA':
                    self.wfile.write(b'354 Send message\r\n');parts=[]
                    while (part:=self.rfile.readline()) not in (b'.\r\n',b''):
                        parts.append(part[1:] if part.startswith(b'..') else part)
                    messages.put(BytesParser(policy=policy.default).parsebytes(b''.join(parts)));self.wfile.write(b'250 Accepted\r\n')
                elif command==b'QUIT':self.wfile.write(b'221 Goodbye\r\n');return
                else:self.wfile.write(b'250 OK\r\n')
    class Server(socketserver.ThreadingTCPServer):
        daemon_threads=True
        def handle_error(self,*args):pass
    server=Server(('127.0.0.1',0),Handler)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert_path,key_path)
    server.socket=context.wrap_socket(server.socket,server_side=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    for name,value in {'SMTP_HOST':'127.0.0.1','SMTP_PORT':str(server.server_address[1]),'SMTP_SECURITY':'ssl','SMTP_FROM':'lossfit@example.com','SSL_CERT_FILE':str(cert_path),'APP_BASE_URL':'http://localhost:5173'}.items():monkeypatch.setenv(name,value)
    monkeypatch.delenv('SMTP_USERNAME',raising=False);monkeypatch.delenv('SMTP_PASSWORD',raising=False)
    try:yield messages
    finally:server.shutdown();server.server_close();thread.join(timeout=2)

def test_actual_tls_delivery_reset_replay_and_session_revocation(smtp_sink,monkeypatch):
    monkeypatch.setattr(main,'request_ip',lambda request:uuid4().hex)
    email=f'recovery-{uuid4().hex}@example.com';old='old-safe-password-987';new='new-safe-password-654'
    with TestClient(main.app) as client:
        registered=client.post('/api/v1/auth/register',json={'name':'Recovery user','email':email,'password':old}).json()
        client.headers['Authorization']='Bearer '+registered['access_token']
        headers={'origin':'http://localhost:5173','x-csrf-token':client.cookies['lf_csrf']}
        assert client.post('/api/v1/auth/forgot-password',headers=headers,json={'email':email}).status_code==200
        message=smtp_sink.get(timeout=2)
        assert str(message['To'])==email
        token=re.search(r'reset-password\?token=([A-Za-z0-9_-]+)',message.get_body().get_content()).group(1)
        def reset():
            with TestClient(main.app) as other:return other.post('/api/v1/auth/reset-password',json={'token':token,'password':new}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:reset(),range(2)))
        assert sorted(results)==[200,400]
        assert client.get('/api/v1/auth/me').status_code==401
        assert client.post('/api/v1/auth/login',json={'email':email,'password':old}).status_code==401
        assert client.post('/api/v1/auth/login',json={'email':email,'password':new}).status_code==200

def test_smtp_rejects_an_untrusted_certificate(smtp_sink,monkeypatch):
    monkeypatch.delenv('SSL_CERT_FILE')
    with pytest.raises(ssl.SSLCertVerificationError):main.send_password_reset_email('recipient@example.com','https://lossfit.example/reset-password?token=test')
    assert smtp_sink.empty()
