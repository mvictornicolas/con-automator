import os
import json
import base64
import rsa
import subprocess
from datetime import datetime

# A CHAVE PÚBLICA fica no software do cliente.
# Ela APENAS consegue "verificar" se o token é válido.
# É matematicamente impossível usá-la para "criar" um novo token falso!
PUBLIC_KEY_PEM = b"""-----BEGIN RSA PUBLIC KEY-----
MIGJAoGBAOfCu7xCGTHNrAO28W1rQMp2bKVS/qhTWxgIFPgfwnTkOA0Edr3WlSbS
ztNxFHjsDxda5lciXr+7xpml66H5HbjNdttFV1MZuD308RApFWoezzA0//KaIkup
SF8l5OtDXVzCHdnFvJtjUfFX8pgwdXHCkMN19eY3qYXt9MgBtYj7AgMBAAE=
-----END RSA PUBLIC KEY-----"""

PUBLIC_KEY = rsa.PublicKey.load_pkcs1(PUBLIC_KEY_PEM)
LICENSE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "license.key")

def get_hwid():
    """Obtem o UUID unico da placa mae/sistema do Windows."""
    try:
        output = subprocess.check_output('wmic csproduct get uuid', shell=True).decode()
        hwid = output.split('\n')[1].strip()
        if hwid and hwid != "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF":
            return hwid
    except Exception:
        pass
    return "UNKNOWN_HWID_FALLBACK"

def load_saved_token():
    if os.path.exists(LICENSE_FILE):
        with open(LICENSE_FILE, "r") as f:
            return f.read().strip()
    return None

def verify_token(token: str):
    """
    Verifica se o token eh valido usando a Chave Publica RSA.
    """
    if not token or "." not in token:
        return False, "Nenhuma licença encontrada ou formato inválido."
        
    try:
        b64_payload, signature_b64 = token.split('.', 1)
        
        # 1. Decodificar a assinatura em B64
        signature = base64.b64decode(signature_b64)
        
        # 2. Verificar Assinatura usando RSA e Chave Publica
        try:
            rsa.verify(b64_payload.encode('utf-8'), signature, PUBLIC_KEY)
        except rsa.VerificationError:
            return False, "Licença inválida (Assinatura incorreta ou adulterada)."
            
        # 3. Decodificar Payload
        payload_json = base64.b64decode(b64_payload).decode('utf-8')
        payload = json.loads(payload_json)
        
        # 3. Verificar Hardware ID (Impede copia pra outro PC)
        current_hwid = get_hwid()
        if payload.get("hwid") != current_hwid:
            return False, f"Licença registrada para outra máquina. (Sua máquina: {current_hwid})"
            
        # 4. Verificar Expiracao
        exp_date = datetime.fromisoformat(payload.get("exp"))
        if datetime.now() > exp_date:
            return False, f"Sua licença expirou em {exp_date.strftime('%d/%m/%Y %H:%M')}."
            
        return True, payload
        
    except Exception as e:
        return False, f"Erro ao processar licença: {str(e)}"

def is_license_valid():
    token = load_saved_token()
    valid, _ = verify_token(token)
    return valid
