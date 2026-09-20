from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime, Float
from datetime import datetime
from .database import Base

class SiteConfig(Base):
    """Armazena as configurações dinâmicas de cada site (ex: usuário, senha)"""
    __tablename__ = "site_configs"

    id = Column(Integer, primary_key=True, index=True)
    plugin_name = Column(String, unique=True, index=True)
    config_data = Column(JSON) # Armazena o JSON com as chaves configuradas

class TaskHistory(Base):
    """Armazena o histórico de execuções de RPA"""
    __tablename__ = "task_history"

    id = Column(Integer, primary_key=True, index=True)
    plugin_name = Column(String)
    status = Column(String) # pending, running, completed, error
    file_path_input = Column(String)
    file_path_output = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    total_cpfs = Column(Integer, default=0)
    processed_cpfs = Column(Integer, default=0)
    current_item = Column(String, nullable=True)
    convenio = Column(String, nullable=True)
    tipo_dado = Column(String, nullable=True, default="cpf")
    error_message = Column(String, nullable=True)
    speed_multiplier = Column(Float, default=1.0)
    total_login_wait_seconds = Column(Integer, default=0)
    last_login_wait_start = Column(DateTime, nullable=True)
    is_archived = Column(Boolean, default=False)

class GlobalSettings(Base):
    __tablename__ = "global_settings"
    id = Column(Integer, primary_key=True)
    limit_cpfs = Column(Integer, default=0)
    limit_hours = Column(Float, default=1.0)

class QueryLog(Base):
    __tablename__ = "query_logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Cliente(Base):
    """Armazena a base de clientes (CRM)"""
    __tablename__ = "clientes"

    cpf = Column(String, primary_key=True, index=True)
    nome = Column(String, nullable=True)
    convenio = Column(String, index=True, nullable=True)  # Rótulo de origem (ex: Itanhaem)
    margem_calculada = Column(String, nullable=True)
    status_crm = Column(String, default="Novo", index=True) # Novo, Contatado, Venda, Nao Incomodar
    data_lembrete = Column(DateTime, nullable=True)
    telefone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    contato_atualizado = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    dados_extras = Column(JSON, default={}) # Campos NoSQL dinâmicos
