# Il Supervisor inietterà l'immagine corretta (es. ghcr.io/home-assistant/aarch64-addon-base)
ARG BUILD_FROM
FROM $BUILD_FROM

# Pacchetti utili (bashio e s6 sono già inclusi nell'addon-base)
RUN apk add --no-cache \
    python3 py3-pip jq bash curl nano htop mosquitto-clients \
    build-base python3-dev libffi-dev openssl-dev libgpiod libgpiod-dev

# Venv per rispettare PEP 668
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV GPIOZERO_PIN_FACTORY=lgpio

# --- COPIE CORRETTE ---
# Porta la tua app (dove c'è main.py) in /app/app
COPY rootfs/app /app/app
# (se ti serve la parte WEB)
COPY rootfs/WEB /app/WEB
# Copia lo script di avvio (è nella stessa cartella del Dockerfile)
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

# Dipendenze Python (aggiungi qui se usi un requirements.txt)
RUN pip install --no-cache-dir \
    janus asyncserial asyncio-mqtt tinydb gmqtt uvloop tornado \
    paho-mqtt debugpy

# Lavoriamo nella cartella che contiene main.py
WORKDIR /app/app

# Avvio (usa bashio e s6-overlay)
CMD ["/app/run.sh"]
