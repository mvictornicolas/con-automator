@echo off
cd /d C:\con-automator\backend
"C:\Users\USER\AppData\Local\Python\pythoncore-3.11-64\python.exe" -m uvicorn api.main:app --host 0.0.0.0 --port 8000 > C:\con-automator\backend\uvicorn_log.txt 2>&1
