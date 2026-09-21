from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime
import os
import time

from core.plugin_manager import manager
from core.database import engine, Base, get_db, SessionLocal
from core.models import TaskHistory, SiteConfig, GlobalSettings, QueryLog
from services.data_engine import DataEngine
from fastapi.responses import JSONResponse
import api.license as license_manager
from api.crm import router as crm_router
from api.updater import update_router

# Cria tabelas se nÃ£o existirem
Base.metadata.create_all(bind=engine)

app = FastAPI(title="RPA Automator API")

app.include_router(crm_router, prefix="/api/crm", tags=["CRM"])
app.include_router(update_router)

@app.middleware("http")
async def check_license_middleware(request: Request, call_next):
    # Proteger rotas da API (exceto endpoints de licenca e a propria UI no "/")
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/license"):
        if not license_manager.is_license_valid():
            return JSONResponse(status_code=403, content={"detail": "Licenca invalida ou expirada."})
    response = await call_next(request)
    return response

@app.on_event("startup")
def startup_event():
    # Cleanup zombie tasks from previous crashes
    db = SessionLocal()
    try:
        zombies = db.query(TaskHistory).filter(
            TaskHistory.status.in_(["pending", "processing_data", "running_rpa", "aguardando_login", "aguardando_limite"])
        ).all()
        for z in zombies:
            z.status = "error"
            z.error_message = "Automacao interrompida (Servidor reiniciado)."
        db.commit()
    finally:
        db.close()

# Habilitar CORS para o Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("../data/uploads", exist_ok=True)
os.makedirs("../data/outputs", exist_ok=True)

app.mount("/outputs", StaticFiles(directory="../data/outputs"), name="outputs")

@app.get("/", response_class=HTMLResponse)
def read_root():
    import sys
    # Handle PyInstaller _MEIPASS
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    # If not running from PyInstaller, it will be the api/ directory, so we go up one level
    if not hasattr(sys, '_MEIPASS'):
        base_dir = os.path.dirname(base_dir)
        
    template_path = os.path.join(base_dir, "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/license/status")
def get_license_status():
    hwid = license_manager.get_hwid()
    token = license_manager.load_saved_token()
    valid, payload_or_msg = license_manager.verify_token(token)
    
    if valid:
        return {"status": "valid", "hwid": hwid, "expiration": payload_or_msg["exp"], "tier": payload_or_msg.get("tier", "ultimate")}
    else:
        return {"status": "invalid", "hwid": hwid, "message": payload_or_msg}

from pydantic import BaseModel
class LicenseInput(BaseModel):
    token: str

@app.post("/api/license/activate")
def activate_license(data: LicenseInput):
    valid, msg = license_manager.verify_token(data.token)
    if valid:
        # Salva o token valido no arquivo
        with open(license_manager.LICENSE_FILE, "w") as f:
            f.write(data.token)
            
        exp_date = datetime.fromisoformat(msg["exp"])
        days_left = (exp_date - datetime.now()).days
        return {"status": "success", "message": f"Licença ativada com sucesso! Restam {days_left} dias de assinatura.", "expiration": msg["exp"], "days_left": days_left, "tier": msg.get("tier", "ultimate")}
    else:
        raise HTTPException(status_code=400, detail=msg)

@app.get("/api/plugins")
def list_plugins():
    """Retorna os sites disponÃ­veis e suas configuraÃ§Ãµes requeridas para a UI montar o form dinÃ¢mico"""
    return manager.get_all_plugins_info()

@app.post("/api/config/{plugin_name}")
def save_config(plugin_name: str, config_data: dict, db: Session = Depends(get_db)):
    """Salva a configuraÃ§Ã£o do site (credenciais)"""
    config = db.query(SiteConfig).filter(SiteConfig.plugin_name == plugin_name).first()
    if config:
        config.config_data = config_data
    else:
        config = SiteConfig(plugin_name=plugin_name, config_data=config_data)
        db.add(config)
    db.commit()
    return {"status": "success", "message": "ConfiguraÃ§Ãµes salvas"}

@app.get("/api/config/{plugin_name}")
def get_config(plugin_name: str, db: Session = Depends(get_db)):
    """Busca as configuraÃ§Ãµes salvas de um site (nÃ£o traz as senhas em plain text na prod, mas para dev ok)"""
    config = db.query(SiteConfig).filter(SiteConfig.plugin_name == plugin_name).first()
    return config.config_data if config else {}

# FunÃ§Ã£o para executar a tarefa em background
def execute_rpa_task(task_id: int, plugin_name: str, file_content: bytes, filename: str):
    # Nota: Em um ambiente de produÃ§Ã£o real (celery), inicializarÃ­amos uma nova sessÃ£o de BD aqui
    db = next(get_db())
    task = db.query(TaskHistory).filter(TaskHistory.id == task_id).first()
    
    try:
        task.status = "processing_data"
        db.commit()
        
        site_config = db.query(SiteConfig).filter(SiteConfig.plugin_name == plugin_name).first()
        config_data = site_config.config_data if site_config else {}
        
        # Sobrescreve com as propriedades originais da tarefa, se existirem
        if task.convenio:
            config_data["convenio"] = task.convenio
        if getattr(task, "tipo_dado", None):
            config_data["tipo_dado"] = task.tipo_dado
            
        preferred_col = config_data.get("tipo_dado")
        
        # 1. Usar o Data Engine para processar o input
        df, cpf_col = DataEngine.process_file_input(file_content, filename, preferred_col)
        cpfs_to_process = df[cpf_col].dropna().tolist()
        
        task.total_cpfs = len(cpfs_to_process)
        task.status = "running_rpa"
        db.commit()
        
        # 2. Obter plugin e config
        plugin = manager.get_plugin(plugin_name)
        
        def progress_cb(current, total, msg, task_status=None):
            print(f"[Tarefa {task_id}] Progresso: {current}/{total} - {msg}")
            task.processed_cpfs = current
            task.total_cpfs = total
            task.current_item = msg
            
            if task_status and task_status != task.status:
                now = datetime.utcnow()
                if task_status == "aguardando_login":
                    task.last_login_wait_start = now
                elif task.status == "aguardando_login" and task.last_login_wait_start:
                    diff = (now - task.last_login_wait_start).total_seconds()
                    task.total_login_wait_seconds = (task.total_login_wait_seconds or 0) + int(diff)
                    task.last_login_wait_start = None
                task.status = task_status
                
            db.commit()
            
        def get_speed_cb():
            # Abre uma sessÃ£o nova rÃ¡pida apenas para ler o estado atual
            db_session = SessionLocal()
            t = db_session.query(TaskHistory).filter(TaskHistory.id == task_id).first()
            if t and t.status == "canceled":
                db_session.close()
                raise Exception("CANCELADO_PELO_USUARIO")
            if t and t.status == "paused":
                db_session.close()
                while True:
                    time.sleep(1.0)
                    db2 = SessionLocal()
                    t2 = db2.query(TaskHistory).filter(TaskHistory.id == task_id).first()
                    current_status = t2.status if t2 else "canceled"
                    db2.close()
                    if current_status == "canceled":
                        raise Exception("CANCELADO_PELO_USUARIO")
                    if current_status != "paused":
                        break
                db_session = SessionLocal()
                t = db_session.query(TaskHistory).filter(TaskHistory.id == task_id).first()
                
            speed_val = t.speed_multiplier if t and t.speed_multiplier else 1.0
            db_session.close()
            return speed_val
            
        def check_rate_limit_cb():
            db_session = SessionLocal()
            
            # Limite do usuario
            settings = db_session.query(GlobalSettings).first()
            user_limit = settings.limit_cpfs if settings and settings.limit_cpfs > 0 else 0
            user_hours = settings.limit_hours if settings and settings.limit_hours > 0 else 1
            
            # Limite da licenca (24h)
            token = license_manager.load_saved_token()
            valid, payload = license_manager.verify_token(token)
            tier = payload.get("tier", "ultimate") if (valid and isinstance(payload, dict)) else "basic"
            
            tier_limit = 0
            if tier == "basic":
                tier_limit = 400
            elif tier == "medium":
                tier_limit = 800
                
            from datetime import timedelta
            
            # Limpar logs antigos (mais de 24h, para garantir que o tier limit funcione)
            db_session.query(QueryLog).filter(QueryLog.timestamp < datetime.utcnow() - timedelta(hours=24)).delete()
            db_session.commit()
            
            wait_user = 0
            wait_tier = 0
            
            # Verifica limite do usuario
            if user_limit > 0:
                limit_time_user = datetime.utcnow() - timedelta(hours=user_hours)
                count_user = db_session.query(QueryLog).filter(QueryLog.timestamp >= limit_time_user).count()
                if count_user >= user_limit:
                    oldest = db_session.query(QueryLog).filter(QueryLog.timestamp >= limit_time_user).order_by(QueryLog.timestamp.asc()).first()
                    if oldest:
                        target = oldest.timestamp + timedelta(hours=user_hours)
                        wait_user = max(1, int((target - datetime.utcnow()).total_seconds()))
                        
            # Verifica limite da licenca
            if tier_limit > 0:
                limit_time_tier = datetime.utcnow() - timedelta(hours=24)
                count_tier = db_session.query(QueryLog).filter(QueryLog.timestamp >= limit_time_tier).count()
                if count_tier >= tier_limit:
                    oldest = db_session.query(QueryLog).filter(QueryLog.timestamp >= limit_time_tier).order_by(QueryLog.timestamp.asc()).first()
                    if oldest:
                        target = oldest.timestamp + timedelta(hours=24)
                        wait_tier = max(1, int((target - datetime.utcnow()).total_seconds()))

            db_session.close()
            return max(wait_user, wait_tier)
            
        def register_query_cb():
            db_session = SessionLocal()
            db_session.add(QueryLog())
            db_session.commit()
            db_session.close()

        safe_conv = "".join([c if c.isalnum() else "_" for c in str(task.convenio)]) if task.convenio else task.plugin_name
        output_filename = f"resultado_{safe_conv}_{task_id}_{int(time.time())}.csv"
        output_path = os.path.join("../data/outputs", output_filename)
        
        # Define output path early so UI can download partials
        task.file_path_output = f"/outputs/{output_filename}"
        db.commit()
        
        # Salva o arquivo em disco IMEDIATAMENTE (vazio/com as colunas originais)
        # Isso garante que se o usuario clicar em "Baixar Restantes" antes do primeiro CPF, o arquivo exista.
        DataEngine.merge_results_and_save(df, cpf_col, [], output_path)
        
        def partial_save_cb(current_results):
            DataEngine.merge_results_and_save(df, cpf_col, current_results, output_path)
            # Sincroniza com a Base de Clientes (CRM) se o CPF existir lá
            db_session = SessionLocal()
            try:
                from core.models import Cliente
                for res in current_results:
                    c_cpf = res.get("cpf_real_coletado") or res.get("cpf") or res.get("CPF")
                    c_margem = res.get("Margem") or res.get("margem") or res.get("margem_calculada") or res.get("Erro") or res.get("erro")
                    if c_cpf and c_cpf != "Nao encontrado" and "*" not in c_cpf:
                        # Limpa CPF
                        cpf_limpo = ''.join(filter(str.isdigit, str(c_cpf))).zfill(11)
                        cli = db_session.query(Cliente).filter(Cliente.cpf == cpf_limpo).first()
                        if cli:
                            cli.margem_calculada = str(c_margem)
                db_session.commit()
            except Exception as e:
                print("Erro ao atualizar CRM:", e)
            finally:
                db_session.close()

        results = plugin.execute(cpfs_to_process, config_data, progress_callback=progress_cb, get_speed_callback=get_speed_cb, check_rate_limit_callback=check_rate_limit_cb, register_query_callback=register_query_cb, partial_save_callback=partial_save_cb)
        
        is_error = False
        if results is None:
            results = []
            
        # Final save just in case
        DataEngine.merge_results_and_save(df, cpf_col, results, output_path)
        
        if not is_error:
            task.status = "completed"
            
        task.processed_cpfs = len(results)
        task.completed_at = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        import traceback
        task.status = "error"
        task.error_message = traceback.format_exc()
        print(f"Erro na tarefa {task_id}:\n{task.error_message}")
        db.commit()

@app.post("/api/execute")
async def execute_task(
    background_tasks: BackgroundTasks,
    plugin_name: str = Form(...),
    file: UploadFile = File(...),
    speed: float = Form(1.0),
    db: Session = Depends(get_db)
):
    """Endpoint principal: Inicia uma execuÃ§Ã£o RPA"""
    
    # ValidaÃ§Ãµes bÃ¡sicas
    plugin = manager.get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(status_code=400, detail="Plugin nao encontrado")
    
    # Bloqueia se ja existe uma tarefa rodando
    running = db.query(TaskHistory).filter(TaskHistory.status.in_(["pending", "processing_data", "running_rpa", "aguardando_login", "aguardando_limite"])).first()
    if running:
        raise HTTPException(status_code=409, detail="Ja existe uma automacao em andamento. Aguarde ou cancele antes de iniciar outra.")
        
    site_config = db.query(SiteConfig).filter(SiteConfig.plugin_name == plugin_name).first()
    if not site_config or not site_config.config_data:
        raise HTTPException(status_code=400, detail="Configure o site antes de executar")
    
    # LÃª o conteÃºdo do arquivo
    content = await file.read()
    
    # Cap de velocidade pela licenca
    token = license_manager.load_saved_token()
    valid, payload = license_manager.verify_token(token)
    tier = payload.get("tier", "ultimate") if (valid and isinstance(payload, dict)) else "basic"
    if tier == "basic":
        speed = max(speed, 1.0)
    elif tier == "medium":
        speed = max(speed, 0.33)
        
    # Salva o arquivo de input (opcional para histÃ³rico)
    input_path = os.path.join("../data/uploads", f"input_{int(time.time())}_{file.filename}")
    with open(input_path, "wb") as f:
        f.write(content)
        
    # Cria o registro da tarefa
    convenio_str = site_config.config_data.get("convenio", "") if site_config.config_data else ""
    tipo_dado_str = site_config.config_data.get("tipo_dado", "cpf") if site_config.config_data else "cpf"
    task = TaskHistory(
        plugin_name=plugin_name,
        status="pending",
        file_path_input=input_path,
        speed_multiplier=speed,
        convenio=convenio_str,
        tipo_dado=tipo_dado_str
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # Envia para processamento em background
    background_tasks.add_task(execute_rpa_task, task.id, plugin_name, content, file.filename)
    
    return {"status": "success", "message": "Tarefa iniciada em background", "task_id": task.id}

from pydantic import BaseModel
class SpeedUpdate(BaseModel):
    speed_multiplier: float

@app.put("/api/tasks/{task_id}/speed")
def update_task_speed(task_id: int, speed_data: SpeedUpdate, db: Session = Depends(get_db)):
    task = db.query(TaskHistory).filter(TaskHistory.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        
    speed = speed_data.speed_multiplier
    token = license_manager.load_saved_token()
    valid, payload = license_manager.verify_token(token)
    tier = payload.get("tier", "ultimate") if (valid and isinstance(payload, dict)) else "basic"
    
    if tier == "basic":
        speed = max(speed, 1.0)
    elif tier == "medium":
        speed = max(speed, 0.33)
        
    task.speed_multiplier = speed
    db.commit()
    return {"status": "success", "speed": task.speed_multiplier}

from fastapi.responses import StreamingResponse
import io
import pandas as pd

@app.get("/api/tasks/{task_id}/download_unprocessed")
def download_unprocessed(task_id: int, db: Session = Depends(get_db)):
    task = db.query(TaskHistory).filter(TaskHistory.id == task_id).first()
    if not task or not task.file_path_output:
        raise HTTPException(status_code=404, detail="Arquivo nÃ£o encontrado")
        
    filename = task.file_path_output.split('/')[-1]
    filepath = os.path.join("../data/outputs", filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Arquivo fÃ­sico nÃ£o encontrado")
        
    df = pd.read_csv(filepath, sep=';', encoding='utf-8-sig')
    
    # Filtra as linhas onde o robÃ´ nÃ£o chegou a colocar a margem
    unprocessed_df = df[df['margem_calculada'].isna() | (df['margem_calculada'] == '')]
    
    # Remove as colunas geradas pelo robÃ´, voltando a planilha ao formato exato original
    unprocessed_df = unprocessed_df.drop(columns=['margem_calculada', 'cpf_real_coletado'], errors='ignore')
    
    # Exporta direto para a memÃ³ria para envio
    stream = io.BytesIO()
    unprocessed_df.to_csv(stream, index=False, sep=';', encoding='utf-8-sig')
    stream.seek(0)
    
    return StreamingResponse(
        stream, 
        media_type="text/csv", 
        headers={"Content-Disposition": f"attachment; filename=restantes_{filename}"}
    )

@app.get("/api/tasks")
def list_tasks(archived: bool = False, db: Session = Depends(get_db)):
    """Lista o histÃ³rico de tarefas"""
    return db.query(TaskHistory).filter(TaskHistory.is_archived == archived).order_by(TaskHistory.id.desc()).limit(50).all()

@app.put("/api/tasks/archive_all")
def archive_all_tasks(db: Session = Depends(get_db)):
    db.query(TaskHistory).filter(TaskHistory.is_archived == False).update({"is_archived": True})
    db.commit()
    return {"status": "success"}

@app.put("/api/tasks/{task_id}/archive")
def archive_task(task_id: int, archive: bool, db: Session = Depends(get_db)):
    task = db.query(TaskHistory).filter(TaskHistory.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa nÃ£o encontrada")
    task.is_archived = archive
    db.commit()
    return {"status": "success"}

@app.put('/api/tasks/{task_id}/cancel')
def cancel_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(TaskHistory).filter(TaskHistory.id == task_id).first()
    if not task: raise HTTPException(404)
    if task.status in ['running_rpa', 'aguardando_login', 'pending', 'paused']:
        task.status = 'canceled'
        db.commit()
    return {'status': 'success'}

@app.put('/api/tasks/{task_id}/pause')
def pause_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(TaskHistory).filter(TaskHistory.id == task_id).first()
    if not task: raise HTTPException(404)
    if task.status in ['running_rpa', 'aguardando_login', 'pending']:
        task.status = 'paused'
        db.commit()
    return {'status': 'success'}

@app.put('/api/tasks/{task_id}/unpause')
def unpause_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(TaskHistory).filter(TaskHistory.id == task_id).first()
    if not task: raise HTTPException(404)
    if task.status == 'paused':
        task.status = 'running_rpa'
        db.commit()
    return {'status': 'success'}

@app.post('/api/tasks/{task_id}/resume')
def resume_task(task_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.query(TaskHistory).filter(TaskHistory.id == task_id).first()
    if not task or not task.file_path_input: raise HTTPException(404, 'Arquivo base não encontrado')
    
    import pandas as pd
    try:
        df = pd.read_csv(task.file_path_input, sep=';', dtype=str)
    except Exception:
        raise HTTPException(500, 'Erro ao ler arquivo original')
        
    if task.file_path_output and os.path.exists(os.path.join('../data/outputs', task.file_path_output.split('/')[-1])):
        try:
            done_df = pd.read_csv(os.path.join('../data/outputs', task.file_path_output.split('/')[-1]), sep=';', dtype=str)
            done_cpfs = done_df['cpf'].dropna().unique().tolist()
            df = df[~df.iloc[:,0].astype(str).isin(done_cpfs)]
        except: pass
        
    if df.empty: raise HTTPException(400, 'Não há mais registros para processar.')
    
    filename = 'resume_' + str(int(time.time())) + '.csv'
    filepath = os.path.join('../data/uploads', filename)
    df.to_csv(filepath, sep=';', index=False, encoding='utf-8-sig')
    
    with open(filepath, 'rb') as f:
        file_content = f.read()
    
    new_task = TaskHistory(
        plugin_name=task.plugin_name,
        status='pending',
        file_path_input=filepath,
        total_cpfs=len(df),
        speed_multiplier=task.speed_multiplier,
        convenio=task.convenio,
        tipo_dado=getattr(task, "tipo_dado", "cpf")
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    
    background_tasks.add_task(execute_rpa_task, new_task.id, task.plugin_name, file_content, filename)
    
    if task.status in ['running_rpa', 'aguardando_login']:
        task.status = 'canceled'
        db.commit()
        
    return {'status': 'success', 'new_task_id': new_task.id}

@app.get('/api/tasks/{task_id}/results')
def get_task_results(task_id: int, db: Session = Depends(get_db)):
    task = db.query(TaskHistory).filter(TaskHistory.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    if not task.file_path_output:
        return {"data": []}
        
    filename = task.file_path_output.split("/")[-1]
    real_path = os.path.join("../data/outputs", filename)
    
    if not os.path.exists(real_path):
        return {"data": []}
        
    import pandas as pd
    try:
        try:
            df = pd.read_csv(real_path, sep=";")
        except:
            df = pd.read_csv(real_path, sep=",")
            
        df = df.fillna("")
        return {"data": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from pydantic import BaseModel
class RateLimitUpdate(BaseModel):
    limit_cpfs: int
    limit_hours: float

@app.get('/api/settings/rate_limit')
def get_rate_limit(db: Session = Depends(get_db)):
    settings = db.query(GlobalSettings).first()
    if not settings:
        settings = GlobalSettings(limit_cpfs=0, limit_hours=1.0)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    from datetime import timedelta
    limit_time = datetime.utcnow() - timedelta(hours=settings.limit_hours)
    current_count = db.query(QueryLog).filter(QueryLog.timestamp >= limit_time).count()
    
    return {
        'limit_cpfs': settings.limit_cpfs,
        'limit_hours': settings.limit_hours,
        'current_count': current_count
    }

@app.put('/api/settings/rate_limit')
def update_rate_limit(data: RateLimitUpdate, db: Session = Depends(get_db)):
    settings = db.query(GlobalSettings).first()
    if not settings:
        settings = GlobalSettings()
        db.add(settings)
    settings.limit_cpfs = data.limit_cpfs
    settings.limit_hours = data.limit_hours
    db.commit()
    return {'status': 'success'}

