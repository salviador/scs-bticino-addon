ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8

RUN apk add --no-cache \
    python3 \
    py3-pip \
    mosquitto-clients \
    bash

COPY rootfs /
COPY run.sh /

WORKDIR /app

RUN pip3 install --break-system-packages --no-cache-dir \
    janus \
    asyncserial \
    asyncio-mqtt \
    tinydb \
    gmqtt \
    uvloop \
    tornado \
    paho-mqtt \
    debugpy

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]