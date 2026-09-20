#!/bin/bash

# Iniciar X virtual framebuffer (display invisível para simular monitor)
Xvfb :99 -screen 0 1280x1024x24 &
sleep 2

# Iniciar um gerenciador de janelas leve (opcional, mas ajuda com algumas popups do Chrome)
fluxbox -display :99 &

# Iniciar servidor VNC para o Xvfb (sem senha para facilidade de dev local)
x11vnc -display :99 -nopw -listen localhost -xkb -ncache 10 -ncache_cr -forever &

# Iniciar NoVNC proxy para converter VNC em WebSockets para o Iframe
/usr/share/novnc/utils/launch.sh --vnc localhost:5900 --listen 7900 &

# Iniciar o servidor FastAPI
echo "Iniciando FastAPI..."
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
