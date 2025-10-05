ARG BUILD_FROM
FROM $BUILD_FROM

# Pacchetti di sistema (senza py3-rpi.gpio: NON esiste su Alpine base HA)
RUN apk add --no-cache \
    python3 \
    py3-pip \
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

# Virtualenv per evitare PEP 668
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dipendenze Python (includi gpiozero; NON installare RPi.GPIO via apk)
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
    gpiozero

COPY . /app
RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]
