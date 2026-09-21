import os
import requests
import json

# ==========================================
# CONFIGURACOES DO DESENVOLVEDOR
# ==========================================
GITHUB_USER = "mvictornicolas"
GITHUB_REPO = "con-automator-releases" # ex: con-automator-releases
GITHUB_PAT = "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"

EXE_PATH = r"backend\dist\ConsignetRobo.exe"

def main():
    print("=== DEPLOY DE NOVA ATUALIZACAO ===")
    version = input("Digite a nova versao (ex: v1.0.1): ").strip()
    notes = input("Digite o que ha de novo nessa versao: ").strip()
    
    if not os.path.exists(EXE_PATH):
        print(f"ERRO: O arquivo {EXE_PATH} nao foi encontrado! Compile primeiro.")
        return
        
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 1. Criar a Release no GitHub
    print("\n1. Criando release no GitHub...")
    release_data = {
        "tag_name": version,
        "target_commitish": "main",
        "name": f"Atualizacao {version}",
        "body": notes,
        "draft": False,
        "prerelease": False
    }
    
    repo_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases"
    resp = requests.post(repo_url, headers=headers, json=release_data)
    
    if resp.status_code != 201:
        print(f"ERRO ao criar release: {resp.status_code} - {resp.text}")
        return
        
    release_info = resp.json()
    upload_url = release_info["upload_url"].split("{")[0] # limpa parametros templated da URL
    
    # 2. Fazer Upload do .exe
    print("2. Fazendo upload do executavel (isso pode demorar um pouco)...")
    with open(EXE_PATH, "rb") as f:
        exe_data = f.read()
        
    headers_upload = {
        "Authorization": f"token {GITHUB_PAT}",
        "Content-Type": "application/octet-stream",
        "Accept": "application/vnd.github.v3+json"
    }
    
    upload_resp = requests.post(
        f"{upload_url}?name=ConsignetRobo.exe",
        headers=headers_upload,
        data=exe_data
    )
    
    if upload_resp.status_code == 201:
        print("\nSUCESSO! Atualizacao enviada e pronta para os clientes baixarem.")
    else:
        print(f"\nERRO ao fazer upload do arquivo: {upload_resp.status_code} - {upload_resp.text}")

if __name__ == "__main__":
    main()
