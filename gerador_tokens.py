import json
import base64
import rsa
import os
from datetime import datetime, timedelta

def load_private_key():
    # Carrega a chave privada do arquivo
    with open("private_key.pem", "rb") as f:
        return rsa.PrivateKey.load_pkcs1(f.read())

PRIVATE_KEY = load_private_key()

def generate_token(hwid: str, days_valid: int):
    # Calcula data de expiracao
    exp_date = datetime.now() + timedelta(days=days_valid)
    
    # Cria o payload em JSON
    payload = {
        "hwid": hwid.strip(),
        "exp": exp_date.isoformat()
    }
    payload_json = json.dumps(payload)
    
    # Codifica Payload em Base64
    b64_payload = base64.b64encode(payload_json.encode('utf-8')).decode('utf-8')
    
    # Gera a assinatura digital RSA
    signature = rsa.sign(b64_payload.encode('utf-8'), PRIVATE_KEY, 'SHA-256')
    signature_b64 = base64.b64encode(signature).decode('utf-8')
    
    # O token final
    token = f"{b64_payload}.{signature_b64}"
    return token, exp_date

if __name__ == "__main__":
    print("=========================================")
    print("       GERADOR DE LICENCAS (RPA)         ")
    print("=========================================")
    print("NUNCA ENVIE ESTE ARQUIVO PARA O CLIENTE!\n")
    
    hwid = input("Digite o Hardware ID (HWID) do cliente: ")
    days = input("Quantos dias de validade o token tera? (ex: 30): ")
    
    try:
        days = int(days)
        token, exp = generate_token(hwid, days)
        print("\n--- TOKEN GERADO COM SUCESSO ---")
        print(f"Valido ate: {exp.strftime('%d/%m/%Y %H:%M')}")
        print(f"HWID Vinculado: {hwid}")
        print("\nCopie a linha abaixo e envie para o cliente:")
        print("--------------------------------------------------------------------------------")
        print(token)
        print("--------------------------------------------------------------------------------")
        print("\n")
    except ValueError:
        print("Erro: O numero de dias deve ser um numero inteiro.")
    
    input("Pressione Enter para sair...")
