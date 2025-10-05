#!/usr/bin/with-contenv bashio

# Abilita output dettagliato
set -e

CONFIG_PATH=/data/options.json

# Leggi configurazioni
MQTT_HOST=$(bashio::config 'mqtt_host')
MQTT_PORT=$(bashio::config 'mqtt_port')
MQTT_USER=$(bashio::config 'mqtt_user')
MQTT_PASSWORD=$(bashio::config 'mqtt_password')
SERIAL_PORT=$(bashio::config 'serial_port')
DEBUG_MODE=$(bashio::config 'debug_mode')
LOG_LEVEL=$(bashio::config 'log_level')

bashio::log.info "==================================="
bashio::log.info "SCS BTicino Bridge - Starting"
bashio::log.info "==================================="
bashio::log.info "MQTT Host: ${MQTT_HOST}"
bashio::log.info "MQTT Port: ${MQTT_PORT}"
bashio::log.info "Serial Port: ${SERIAL_PORT}"
bashio::log.info "Debug Mode: ${DEBUG_MODE}"
bashio::log.info "Log Level: ${LOG_LEVEL}"
bashio::log.info "==================================="

# Verifica porta seriale
if [ -e "${SERIAL_PORT}" ]; then
    bashio::log.info "✓ Serial port ${SERIAL_PORT} found"
    ls -la "${SERIAL_PORT}"
else
    bashio::log.error "✗ Serial port ${SERIAL_PORT} NOT found"
    bashio::log.info "Available serial devices:"
    ls -la /dev/tty* || true
    ls -la /dev/serial* || true
fi

# Verifica connessione MQTT
bashio::log.info "Testing MQTT connection..."
timeout 5 mosquitto_sub -h "${MQTT_HOST}" -p "${MQTT_PORT}" -t "test" -C 1 &>/dev/null && \
    bashio::log.info "✓ MQTT broker reachable" || \
    bashio::log.warning "✗ MQTT broker not reachable (might start later)"

# Esporta variabili d'ambiente
export MQTT_HOST="$MQTT_HOST"
export MQTT_PORT="$MQTT_PORT"
export MQTT_USER="$MQTT_USER"
export MQTT_PASSWORD="$MQTT_PASSWORD"
export SERIAL_PORT="$SERIAL_PORT"
export DEBUG_MODE="$DEBUG_MODE"
export LOG_LEVEL="$LOG_LEVEL"

bashio::log.info "Starting Python application..."

cd /app

# Se debug mode, avvia con logging dettagliato
if [ "$DEBUG_MODE" = "true" ]; then
    bashio::log.warning "⚠ DEBUG MODE ENABLED - Performance may be affected"
    python3 -u main.py 2>&1 | while read line; do
        bashio::log.debug "$line"
    done
else
    python3 -u main.py
fi