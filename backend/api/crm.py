from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Optional
import pandas as pd
import io
import os
import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, cast, Float

from core.database import get_db
from core.models import Cliente, TaskHistory

router = APIRouter()

def clean_cpf(cpf: str) -> str:
    """Limpa o CPF deixando apenas os numeros e com 11 digitos."""
    if pd.isna(cpf): return ""
    cpf_str = str(cpf).replace(".","").replace("-","").replace(" ", "")
    # Extrai so digitos
    cpf_str = ''.join(filter(str.isdigit, cpf_str))
    if not cpf_str: return ""
    return cpf_str.zfill(11)

@router.post("/import")
async def import_spreadsheets(
    convenio: str = Form(...),
    force: str = Form("false"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    total_imported = 0
    errors = []

    for file in files:
        contents = await file.read()
        try:
            if file.filename.endswith('.csv'):
                try:
                    df = pd.read_csv(io.BytesIO(contents), sep=";")
                except:
                    df = pd.read_csv(io.BytesIO(contents), sep=",")
            elif file.filename.endswith('.xlsx'):
                df = pd.read_excel(io.BytesIO(contents))
            else:
                errors.append(f"{file.filename}: Formato não suportado.")
                continue
            
            # Normalizar colunas para maiusculo para facilitar busca do CPF/NOME
            df.columns = [str(c).strip().upper() for c in df.columns]
            
            if force.lower() != "true":
                conv_col = None
                for c in df.columns:
                    if c in ["CONVENIO", "CONVÊNIO", "ORGAO", "ÓRGÃO", "ENTIDADE"]:
                        conv_col = c
                        break
                
                if conv_col:
                    val_counts = df[conv_col].dropna().value_counts()
                    if not val_counts.empty:
                        detected_conv = str(val_counts.idxmax()).strip()
                        # Se não for idêntico (case-insensitive)
                        if detected_conv.lower() != convenio.strip().lower():
                            from fastapi.responses import JSONResponse
                            return JSONResponse(status_code=409, content={
                                "detected": detected_conv,
                                "message": f"Identificamos o convênio '{detected_conv}' na planilha, mas você informou '{convenio}'."
                            })
            
            # Descobrir qual coluna é o CPF
            cpf_col = None
            if "CPF" in df.columns: cpf_col = "CPF"
            elif "DOCUMENTO" in df.columns: cpf_col = "DOCUMENTO"
            
            if not cpf_col:
                errors.append(f"{file.filename}: Coluna 'CPF' não encontrada.")
                continue
                
            # Descobrir Nome
            nome_col = None
            if "NOME" in df.columns: nome_col = "NOME"
            elif "CLIENTE" in df.columns: nome_col = "CLIENTE"
            
            for _, row in df.iterrows():
                raw_cpf = row[cpf_col]
                cpf_limpo = clean_cpf(raw_cpf)
                
                if not cpf_limpo:
                    continue
                    
                nome = str(row[nome_col]) if nome_col and not pd.isna(row[nome_col]) else ""
                
                # Montar o dict de extras iterando por todas as colunas
                extras = {}
                for col in df.columns:
                    if col not in [cpf_col, nome_col]:
                        val = row[col]
                        # Substituir NaN por None
                        if pd.isna(val):
                            extras[col] = None
                        else:
                            extras[col] = str(val)
                            
                # Upsert no banco de dados
                cliente = db.query(Cliente).filter(Cliente.cpf == cpf_limpo).first()
                if not cliente:
                    cliente = Cliente(cpf=cpf_limpo)
                    db.add(cliente)
                    db.flush()
                    
                cliente.nome = nome
                cliente.convenio = convenio
                
                # Fazer merge dos dados_extras caso o cliente ja exista
                existing_extras = cliente.dados_extras or {}
                existing_extras.update(extras)
                cliente.dados_extras = existing_extras
                
                total_imported += 1
                
        except Exception as e:
            errors.append(f"{file.filename}: Erro ao processar ({str(e)})")

    db.commit()
    return {"message": "Importação concluída.", "total_imported": total_imported, "errors": errors}

@router.post("/import_from_task/{task_id}")
def import_from_task(task_id: int, convenio: str = Form("Importado do Histórico"), db: Session = Depends(get_db)):
    task = db.query(TaskHistory).filter(TaskHistory.id == task_id).first()
    if not task or not task.file_path_output:
        raise HTTPException(404, "Tarefa não encontrada ou não possui resultado final.")
        
    # O file_path_output vem como /outputs/resultado_XXX.csv
    filename = task.file_path_output.split("/")[-1]
    real_path = os.path.join("../data/outputs", filename)
    
    if not os.path.exists(real_path):
        raise HTTPException(404, "Arquivo CSV não encontrado no disco.")
        
    total_imported = 0
    try:
        try:
            df = pd.read_csv(real_path, sep=";")
        except:
            df = pd.read_csv(real_path, sep=",")
            
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        cpf_col = None
        for col in ["CPF", "DOCUMENTO"]:
            if col in df.columns:
                cpf_col = col
                break
                
        if not cpf_col:
            raise HTTPException(400, "Arquivo da tarefa não possui coluna de CPF.")
            
        for _, row in df.iterrows():
            raw_cpf = row.get("CPF_REAL_COLETADO")
            if pd.isna(raw_cpf) or not raw_cpf or "*" in str(raw_cpf):
                raw_cpf = row[cpf_col]
                
            cpf_limpo = clean_cpf(raw_cpf)
            if not cpf_limpo: continue
            
            extras = {}
            for col in df.columns:
                if col != cpf_col:
                    val = row[col]
                    extras[col] = None if pd.isna(val) else str(val)
                    
            cli = db.query(Cliente).filter(Cliente.cpf == cpf_limpo).first()
            if not cli:
                cli = Cliente(cpf=cpf_limpo, convenio=convenio)
                db.add(cli)
                db.flush()
            
            # Se a tarefa gerou Margem, atualiza no CRM
            margem = extras.get("MARGEM") or extras.get("MARGEM_CALCULADA")
            if margem:
                cli.margem_calculada = str(margem)
                
            nome = extras.get("NOME") or extras.get("CLIENTE")
            if nome and not cli.nome:
                cli.nome = nome

            # Extração heurística de telefone e email
            for k, v in extras.items():
                ku = k.upper()
                if v and str(v).strip():
                    if not cli.telefone and any(t in ku for t in ["TELEFONE", "CELULAR", "WHATSAPP", "FONE"]):
                        cli.telefone = str(v).strip()
                    if not cli.email and any(e in ku for e in ["EMAIL", "E-MAIL", "CORREIO"]):
                        cli.email = str(v).strip()
                
            existing_extras = cli.dados_extras or {}
            existing_extras.update(extras)
            cli.dados_extras = existing_extras
            
            total_imported += 1
            
        db.commit()
    except Exception as e:
        raise HTTPException(500, f"Erro ao processar arquivo: {str(e)}")
        
    return {"message": "Salvo no CRM com sucesso!", "total_imported": total_imported}

@router.get("/convenios")
def list_convenios(db: Session = Depends(get_db)):
    convenios = db.query(Cliente.convenio).filter(Cliente.convenio != None).distinct().all()
    result = [c[0] for c in convenios if c[0]]
    return {"convenios": sorted(result)}

@router.get("/clients")
def list_clients(
    skip: int = 0, 
    limit: int = 50, 
    convenios: List[str] = Query(None), 
    statuses: List[str] = Query(None), 
    contato_ok: str = None, 
    tem_margem: str = None, 
    margem_min: float = None, 
    order_by: str = "updated_at", 
    db: Session = Depends(get_db)
):
    query = db.query(Cliente)
    
    if convenios:
        query = query.filter(Cliente.convenio.in_(convenios))
    if statuses:
        query = query.filter(Cliente.status_crm.in_(statuses))
        
    if contato_ok == "sim":
        query = query.filter(Cliente.contato_atualizado == True)
    elif contato_ok == "nao":
        query = query.filter((Cliente.contato_atualizado == False) | (Cliente.contato_atualizado == None))
        
    margem_clean = func.replace(func.replace(func.replace(Cliente.margem_calculada, 'R$ ', ''), '.', ''), ',', '.')
    
    if tem_margem == "sim":
        query = query.filter(Cliente.margem_calculada.like('%R$%'))
    elif tem_margem == "nao":
        query = query.filter(
            Cliente.margem_calculada != None,
            Cliente.margem_calculada != "",
            ~Cliente.margem_calculada.like('%R$%')
        )
        
    if margem_min is not None:
        query = query.filter(cast(margem_clean, Float) >= margem_min)
        
    if order_by == "margem":
        query = query.order_by(desc(cast(margem_clean, Float)))
    else:
        query = query.order_by(desc(Cliente.updated_at))
        
    total = query.count()
    clientes = query.offset(skip).limit(limit).all()
    
    # Serializar
    result = []
    for c in clientes:
        result.append({
            "cpf": c.cpf,
            "nome": c.nome,
            "convenio": c.convenio,
            "margem_calculada": c.margem_calculada,
            "status_crm": c.status_crm,
            "data_lembrete": c.data_lembrete.isoformat() if c.data_lembrete else None,
            "telefone": c.telefone,
            "email": c.email,
            "contato_atualizado": c.contato_atualizado,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "dados_extras": c.dados_extras
        })
        
    return {"total": total, "clientes": result}

from pydantic import BaseModel
class UpdateClientSchema(BaseModel):
    status_crm: Optional[str] = None
    data_lembrete: Optional[str] = None
    margem_calculada: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    contato_atualizado: Optional[bool] = None

@router.put("/clients/{cpf}")
def update_client(cpf: str, data: UpdateClientSchema, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.cpf == cpf).first()
    if not cliente:
        raise HTTPException(404, "Cliente não encontrado")
        
    if data.status_crm is not None:
        cliente.status_crm = data.status_crm
    if data.data_lembrete is not None:
        if data.data_lembrete == "":
            cliente.data_lembrete = None
        else:
            cliente.data_lembrete = datetime.fromisoformat(data.data_lembrete.replace('Z', '+00:00'))
    if data.margem_calculada is not None:
        cliente.margem_calculada = data.margem_calculada
    if data.telefone is not None:
        cliente.telefone = data.telefone
    if data.email is not None:
        cliente.email = data.email
    if data.contato_atualizado is not None:
        cliente.contato_atualizado = data.contato_atualizado
        
    db.commit()
    return {"message": "Atualizado com sucesso"}

class BatchActionSchema(BaseModel):
    cpfs: List[str]
    plugin: str
    convenio: Optional[str] = None

@router.post("/query_batch")
def query_batch(data: BatchActionSchema, db: Session = Depends(get_db)):
    if not data.cpfs:
        raise HTTPException(400, "Nenhum CPF fornecido.")
        
    # Atualiza o config global do plugin
    from core.models import SiteConfig
    config = db.query(SiteConfig).filter(SiteConfig.plugin_name == data.plugin).first()
    if config:
        cfg = dict(config.config_data) if config.config_data else {}
        if data.convenio:
            cfg["convenio"] = data.convenio
        cfg["tipo_dado"] = "cpf" # CRM sempre envia CPFs
        config.config_data = cfg
    else:
        cfg = {"tipo_dado": "cpf"}
        if data.convenio:
            cfg["convenio"] = data.convenio
        db.add(SiteConfig(plugin_name=data.plugin, config_data=cfg))
    db.commit()

    # Gera um CSV temporario
    task_input_path = f"../data/uploads/batch_{datetime.now().strftime('%Y%md%H%M%S')}.csv"
    import csv
    with open(task_input_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["CPF"])
        for cpf in data.cpfs:
            writer.writerow([cpf])
            
    # Cria a tarefa no banco
    task = TaskHistory(
        plugin_name=data.plugin,
        status="pending",
        file_path_input=task_input_path,
        total_cpfs=len(data.cpfs),
        processed_cpfs=0,
        convenio=data.convenio or "CRM em Lote",
        tipo_dado="cpf"
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return {"message": "Tarefa de consulta em lote iniciada!", "task_id": task.id}

@router.post("/export")
def export_clients(data: dict, db: Session = Depends(get_db)):
    # data: {"cpfs": [...], "columns": ["CPF", "NOME", "DDDFONECEL1"]}
    cpfs = data.get("cpfs", [])
    columns = data.get("columns", ["CPF", "NOME"])
    
    if not cpfs:
        raise HTTPException(400, "Nenhum CPF selecionado para exportacao")
        
    clientes = db.query(Cliente).filter(Cliente.cpf.in_(cpfs)).all()
    
    output_path = f"../data/outputs/export_{datetime.now().strftime('%Y%md%H%M%S')}.csv"
    import csv
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(columns)
        
        for c in clientes:
            row = []
            for col in columns:
                if col.upper() == "CPF": row.append(c.cpf)
                elif col.upper() == "NOME": row.append(c.nome)
                elif col.upper() == "CONVENIO": row.append(c.convenio)
                elif col.upper() == "MARGEM_CALCULADA": row.append(c.margem_calculada)
                elif col.upper() == "STATUS_CRM": row.append(c.status_crm)
                else:
                    # Tenta pegar dos extras
                    val = (c.dados_extras or {}).get(col.upper(), "")
                    row.append(val)
            writer.writerow(row)
            
    filename = os.path.basename(output_path)
    return {"url": f"/outputs/{filename}"}

