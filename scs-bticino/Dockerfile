# Usa il base image fornito dal Supervisor di Home Assistant
ARG BUILD_FROM
FROM $BUILD_FROM

# Installa i pacchetti di sistema necessari
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-rpi.gpio \
    jq \
    bash \
    curl \
    nano \
    htop \
    mosquitto-clients \
    build-base \
    python3-dev \
    libffi-dev \
    openssl-dev

# ✅ Crea un virtual environment per evitare il problema PEP 668
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Imposta directory di lavoro
WORKDIR /app

# Copia requirements.txt (se lo usi)
# COPY requirements.txt /app/requirements.txt
# RUN pip install --no-cache-dir -r /app/requirements.txt

# ✅ Installa tutte le librerie necessarie (incluso gpiozero e RPi.GPIO)
RUN pip install --no-cache-dir \
    janus \
    asyncserial \
    asyncio-mqtt \
    tinydb \
    gmqtt \
    uvloop \
    tornado \
    paho-mqtt \
    debugpy \
    gpiozero \
    RPi.GPIO

# Copia tutti i file dell’add-on dentro il container
COPY . /app

# Rendi eseguibile lo script di avvio
RUN chmod +x /app/run.sh

# Comando di avvio del container
CMD ["/app/run.sh"]
