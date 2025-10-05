ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base-python:latest
FROM $BUILD_FROM

ENV LANG=C.UTF-8

# Installa solo tool extra necessari
RUN apk add --no-cache \
    mosquitto-clients \
    bash

# Copia i file dell'applicazione
COPY rootfs /

# Installa dipendenze Python (immagine base-python gestisce pip correttamente)
WORKDIR /app
RUN pip3 install --no-cache-dir \
    janus \
    asyncserial \
    asyncio-mqtt \
    tinydb \
    gmqtt \
    uvloop \
    tornado \
    paho-mqtt \
    debugpy

# Script di avvio
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]