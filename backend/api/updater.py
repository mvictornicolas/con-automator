import os
import sys
import subprocess
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

update_router = APIRouter()

# Coloque o nome do repositorio aqui (formato: usuario/repositorio)
GITHUB_REPO = "mvictornicolas/con-automator-releases"
DEFAULT_GITHUB_PAT = "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"

from typing import Optional

class UpdateCheckRequest(BaseModel):
    update_token: Optional[str] = None

@update_router.post("/api/update/check")
def check_update(data: UpdateCheckRequest):
    """Verifica se ha uma nova versao no GitHub."""
    token_to_use = data.update_token if data.update_token else DEFAULT_GITHUB_PAT
    headers = {
        "Authorization": f"token {token_to_use}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Busca a ultima release
    response = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", headers=headers)
    
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Nenhuma atualização encontrada ou token inválido.")
    elif response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"Erro ao acessar GitHub: {response.text}")
        
    release = response.json()
    version = release.get("tag_name", "v1.0.0")
    
    # Encontra o asset do executavel
    asset_url = None
    for asset in release.get("assets", []):
        if asset["name"].endswith(".exe"):
            asset_url = asset["url"]
            break
            
    if not asset_url:
        raise HTTPException(status_code=404, detail="Executável não encontrado na versão mais recente.")
        
    return {
        "status": "success",
        "latest_version": version,
        "asset_url": asset_url
    }

class ApplyUpdateRequest(BaseModel):
    update_token: Optional[str] = None
    asset_url: str

@update_router.post("/api/update/apply")
def apply_update(data: ApplyUpdateRequest):
    """Baixa o executavel e inicia o processo de substituicao."""
    token_to_use = data.update_token if data.update_token else DEFAULT_GITHUB_PAT
    headers = {
        "Authorization": f"token {token_to_use}",
        "Accept": "application/octet-stream" # Aceite binario para baixar o asset
    }
    
    exe_name = "ConsignetRobo.exe"
    new_exe_name = "ConsignetRobo_New.exe"
    
    # 1. Baixar o arquivo
    response = requests.get(data.asset_url, headers=headers, stream=True)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Erro ao baixar atualização.")
        
    try:
        with open(new_exe_name, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo: {str(e)}")
        
    # 2. Criar script de atualizacao (updater.bat)
    bat_content = f"""@echo off
echo Atualizando o sistema, por favor aguarde...
timeout /t 3 /nobreak > NUL
del /f /q {exe_name}
ren {new_exe_name} {exe_name}
start {exe_name}
del "%~f0"
"""
    with open("updater.bat", "w") as f:
        f.write(bat_content)
        
    # 3. Executar o updater.bat em uma nova janela de forma independente
    subprocess.Popen("updater.bat", creationflags=subprocess.CREATE_NEW_CONSOLE)
    
    # 4. Finalizar este processo para liberar o lock do arquivo
    os._exit(0)
