ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8

# Installa dipendenze di sistema e debug tools
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-tornado \
    mosquitto-clients \
    bash \
    curl \
    nano \
    htop

# Copia i file dell'applicazione
COPY rootfs /

# Installa dipendenze Python incluso debugpy
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