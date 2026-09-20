@echo off
echo ===================================================
echo   Reiniciando o Servidor ConAutomator Silencioso
echo ===================================================
echo.
echo Encerrando processos antigos...
wmic process where "commandline like '%%run_server.py%%'" call terminate >nul 2>&1
wmic process where "commandline like '%%uvicorn api.main:app%%'" call terminate >nul 2>&1
timeout /t 2 /nobreak >nul

echo.
echo Iniciando servidor em background...
start "" "C:\Users\USER\AppData\Local\Python\pythoncore-3.11-64\pythonw.exe" "C:\con-automator\backend\run_server.py"

echo.
echo Pronto! Servidor reiniciado.
echo Pode fechar esta janela.
timeout /t 5 >nul
