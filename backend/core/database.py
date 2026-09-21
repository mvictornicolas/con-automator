from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

import sys

if getattr(sys, 'frozen', False):
    # Se estiver rodando como .exe (compilado)
    base_dir = os.path.dirname(sys.executable)
else:
    # Se estiver rodando via Python script
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

data_dir = os.path.join(base_dir, "data")
os.makedirs(data_dir, exist_ok=True)

db_path = os.path.join(data_dir, "rpa_database.db")
DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
