FROM python:3.11-slim

# Instalar dependências de sistema para VNC, Xvfb, e Navegador
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    chromium \
    chromium-driver \
    fluxbox \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Diretório de trabalho
WORKDIR /app

# Copiar dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar script de entrypoint e dar permissão de execução
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copiar o resto do código
COPY . .

# Portas
EXPOSE 8000
EXPOSE 7900

CMD ["/entrypoint.sh"]
