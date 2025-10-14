#!/usr/bin/env python3

import tornado.ioloop
import tornado.web
from tornado import websocket
import json
import os
import shutil
import paho.mqtt.client as mqtt
import re
import janus
import asyncio
import paho.mqtt.publish as publish
import logging
import time
import sys
import importlib.machinery

logger = logging.getLogger(__name__)


DEBUG_MODE = str(os.getenv('DEBUG_MODE', 'false')).lower() in ('1','true','yes','on')


# ============================================================================
# PATH E CONFIGURAZIONE
# ============================================================================
dir_path = os.path.dirname(os.path.realpath(__file__))
dir_path_weblist = dir_path.split('/')
s = ''
for i, _ in enumerate(dir_path_weblist):
    if((len(dir_path_weblist)-1) != i):
        s = s + _ + '/'
dir_path_app = s + 'app/'

databaseAttuatori = importlib.machinery.SourceFileLoader('databaseAttuatori', dir_path_app + 'databaseAttuatori.py').load_module()
nodered = importlib.machinery.SourceFileLoader('nodered', dir_path_app + 'nodered.py').load_module()
noderedAWS = importlib.machinery.SourceFileLoader('noderedAWS', dir_path_app + 'noderedAWS.py').load_module()

mqtt_host = os.getenv('MQTT_HOST', 'localhost')
mqtt_port = int(os.getenv('MQTT_PORT', 1883))
mqtt_user = os.getenv('MQTT_USER', '')
mqtt_password = os.getenv('MQTT_PASSWORD', '')
MQTT_WS_PORT = int(os.getenv("MQTT_WS_PORT", "1884"))
MQTT_WS_PATH = os.getenv("MQTT_WS_PATH", "")

dbm = databaseAttuatori.configurazione_database()
cl = []  # websocket connections
q = None
q_nodered = None

# ============================================================================
# MQTT DISCOVERY HELPERS
# ============================================================================

def _slugify(value: str) -> str:
    """Converte nome dispositivo in slug valido (USATO OVUNQUE)"""
    s = re.sub(r"\s+", "_", value.strip())
    s = re.sub(r"[^a-zA-Z0-9_]", "", s)
    return s.lower()

# ✅ ESPORTA la funzione per usarla in altri moduli
def get_device_slug(nome_attuatore: str) -> str:
    """Ritorna lo slug del dispositivo (da usare nei topic MQTT)"""
    return _slugify(nome_attuatore.lower())

# ============================================================================
# MQTT DISCOVERY HELPERS
# ============================================================================

DOMAIN_MAP = {
    "on_off": "switch",
    "switch": "switch",
    "luce": "light",
    "light": "light",
    "dimmer": "light",
    "serrande_tapparelle": "cover",
    "tapparella": "cover",
    "tenda": "cover",
    "serranda": "cover",
    "sensori_temperatura": "sensor",
    "temperatura": "sensor",
    "umidita": "sensor",
    "campanello_porta": "binary_sensor",
    "serrature": "lock",
    "termostati": "climate",
}

def _build_topics(object_id: str):
    """Costruisce i topic MQTT per un dispositivo"""
    base = f"/scsshield/device/{object_id}"
    return {
        "state": f"{base}/status",
        "switch_cmd": f"{base}/switch",
        "dimmer_cmd": f"{base}/dimmer",
        "dimmer_state": f"{base}/status/percentuale",
        "cover_setpos": f"{base}/percentuale",
        "attrs": f"{base}/attrs",
    }

def _build_discovery_payload(nome_attuatore: str, tipo_attuatore: str):
    """Costruisce il payload discovery per Home Assistant"""
    object_id = _slugify(nome_attuatore)
    unique_id = f"scs_{object_id}"
    t = (tipo_attuatore or "").lower()
    domain = DOMAIN_MAP.get(t, "switch")

    topics = _build_topics(object_id)

    device = {
        "identifiers": ["scs_bticino_bridge"],
        "name": "SCS BTicino Bridge",
        "manufacturer": "Custom",
        "model": "SCS → MQTT Bridge",
    }

    payload = {
        "name": nome_attuatore,
        "unique_id": unique_id,
        "json_attributes_topic": topics["attrs"],
        "device": device,
    }

    if domain == "switch":
        payload.update({
            "state_topic": topics["state"],
            "command_topic": topics["switch_cmd"],
            "state_on": "on",
            "state_off": "off",
            "payload_on": "on",
            "payload_off": "off",
        })

    elif domain == "light":
        payload.update({
            "state_topic": topics["state"],
            "command_topic": topics["dimmer_cmd"],
            "brightness_command_topic": topics["dimmer_cmd"],
            "brightness_state_topic": topics["dimmer_state"],
            "brightness_scale": 100,
            "on_command_type": "first",
            "state_value_template": "{{ 'ON' if value == 'on' else 'OFF' }}",
            "brightness_value_template": "{{ value | int }}",
        })

    elif domain == "cover":
        payload.update({
            "command_topic": topics["cover_setpos"],
            "position_topic": topics["state"],
            "set_position_topic": topics["cover_setpos"],
            "position_open": 100,
            "position_closed": 0,
            "payload_open": "100",
            "payload_close": "0",
        })

    elif domain == "binary_sensor":
        payload.update({
            "state_topic": topics["state"],
            "payload_on": "1",
            "payload_off": "0",
            "device_class": "motion",
            "off_delay": 3,
        })

    elif domain == "sensor":
        payload.update({
            "state_topic": topics["state"],
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
            "value_template": "{{ value | float | round(1) }}",
        })

    elif domain == "climate":
        payload.update({
            "current_temperature_topic": topics["state"],
            "temperature_state_topic": f"/scsshield/device/{object_id}/temperatura_termostato_impostata",
            "temperature_command_topic": f"/scsshield/device/{object_id}/set_temp_termostato",
            "mode_state_topic": f"/scsshield/device/{object_id}/modalita_termostato_impostata",
            "mode_command_topic": f"/scsshield/device/{object_id}/set_modalita_termostato",
            "modes": ["off", "heat", "cool"],
            "min_temp": 3,
            "max_temp": 35,
            "temp_step": 0.5,
            "temperature_unit": "C",
            #"mode_state_template": "{% if value == 'OFF' %}off{% elif value == 'INVERNO' %}heat{% elif value == 'ESTATE' %}cool{% else %}off{% endif %}",
            #"mode_command_template": "{% if value == 'off' %}OFF{% elif value == 'heat' %}INVERNO{% elif value == 'cool' %}ESTATE{% endif %}",
            "mode_state_template": "{% if value == 'OFF' %}off{% elif value == 'INVERNO' %}cool{% elif value == 'ESTATE' %}heat{% else %}off{% endif %}",
            "mode_command_template": "{% if value == 'off' %}OFF{% elif value == 'heat' %}ESTATE{% elif value == 'cool' %}INVERNO{% endif %}",

        })
        
        #payload.update({
        #    "current_temperature_topic": topics["state"],
        #    "temperature_state_topic": f"/scsshield/device/{object_id}/temperatura_termostato_impostata",
        #    "temperature_command_topic": f"/scsshield/device/{object_id}/set_temp_termostato",
        #    "mode_state_topic": f"/scsshield/device/{object_id}/modalita_termostato_impostata",
        #    "mode_command_topic": f"/scsshield/device/{object_id}/set_modalita_termostato",
        #    "modes": ["off", "heat", "cool"],
        #    "min_temp": 3,
        #    "max_temp": 35,
        #    "temp_step": 0.5,
        #    "temperature_unit": "C",
        #    # ✅ INVERSIONE: quando bus dice INVERNO → HA mostra COOL, quando bus dice ESTATE → HA mostra HEAT
        #    "mode_state_template": "{% if value == 'OFF' %}off{% elif value == 'INVERNO' %}cool{% elif value == 'ESTATE' %}heat{% else %}off{% endif %}",
        #    "mode_command_template": "{% if value == 'off' %}OFF{% elif value == 'heat' %}ESTATE{% elif value == 'cool' %}INVERNO{% endif %}",
        #})        
        
        
        
        
        
        
        
        
        
    elif domain == "lock":
        domain = "button"
        payload.update({
            "command_topic": f"/scsshield/device/{object_id}/sblocca",
            "payload_press": "sblocca",
            "device_class": "restart",
            "retain": False,
        })
        payload["unique_id"] = f"scs_{object_id}_unlock_btn"




    else:
        return None

    return domain, object_id, payload

            
def publish_discovery(nome_attuatore: str, tipo_attuatore: str, retain=True):
    """Pubblica discovery MQTT per Home Assistant"""
    res = _build_discovery_payload(nome_attuatore, tipo_attuatore)
    if not res:
        logger.warning(f"Discovery not available for {nome_attuatore} ({tipo_attuatore})")
        return None
    
    domain, object_id, payload = res
    topic = f"homeassistant/{domain}/{object_id}/config"
    
    auth_dict = None
    if mqtt_user and mqtt_password:
        auth_dict = {"username": mqtt_user, "password": mqtt_password}
    
    try:
        publish.single(
            topic,
            payload=json.dumps(payload),
            hostname=mqtt_host,
            port=mqtt_port,
            auth=auth_dict,
            retain=retain,
        )
        logger.info(f"✓ Published discovery: {topic}")
        return topic
    except Exception as e:
        logger.error(f"✗ Discovery publish failed for {nome_attuatore}: {e}")
        return None


def unpublish_discovery(nome_attuatore: str, tipo_attuatore: str):
    """Rimuove discovery MQTT da Home Assistant"""
    res = _build_discovery_payload(nome_attuatore, tipo_attuatore)
    if not res:
        return None
    
    domain, object_id, _ = res
    topic = f"homeassistant/{domain}/{object_id}/config"
    
    auth_dict = None
    if mqtt_user and mqtt_password:
        auth_dict = {"username": mqtt_user, "password": mqtt_password}
    
    try:
        publish.single(
            topic,
            payload="",
            hostname=mqtt_host,
            port=mqtt_port,
            auth=auth_dict,
            retain=True,
        )
        logger.info(f"✓ Unpublished discovery: {topic}")
        return topic
    except Exception as e:
        logger.error(f"✗ Discovery unpublish failed for {nome_attuatore}: {e}")
        return None


# ============================================================================
# WEBSOCKET HANDLER
# ============================================================================

class SocketHandler(websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        if self not in cl:
            cl.append(self)

    def on_close(self):
        if self in cl:
            cl.remove(self)

    def on_message(self, message):
        pass


# ============================================================================
# PAGE HANDLERS
# ============================================================================

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('site/build/index.html')

class HomeHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('site/build/index.html')

class ConfigurazioneHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('site/build/index.html')

class Testandler(tornado.web.RequestHandler):
    def get(self):
        self.render('site/build/index.html')

class noderedAlexaandler(tornado.web.RequestHandler):
    def get(self):
        self.render('site/build/index.html')

class noderedHomeHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('site/build/index.html')

class NoderedAlexaAWSHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('site/build/index.html')

class reactMain(tornado.web.RequestHandler):
    def get(self):
        self.render('site/build/test3.html')


# ============================================================================
# API JSON HANDLERS
# ============================================================================

class GetConfigurazione_JSON(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        lista_attuatori = {}
        all = dbm.RICHIESTA_TUTTI_ATTUATORI()
        for item in all:
            s = item['nome_attuatore']
            smod = s
            if (("timer_salita" in item) and ("timer_discesa" in item)):
                lista_attuatori[smod] = {
                    'nome_attuatore': s,
                    'tipo_attuatore': item['tipo_attuatore'],
                    'indirizzo_Ambiente': item['indirizzo_Ambiente'],
                    'indirizzo_PL': item['indirizzo_PL'],
                    'timer_salita': item['timer_salita'],
                    'timer_discesa': item['timer_discesa']
                }
            else:
                lista_attuatori[smod] = {
                    'nome_attuatore': s,
                    'tipo_attuatore': item['tipo_attuatore'],
                    'indirizzo_Ambiente': item['indirizzo_Ambiente'],
                    'indirizzo_PL': item['indirizzo_PL']
                }
        self.write(json.dumps(lista_attuatori))

class GetConfigurazione_JSONreact(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        lista_attuatori = []
        all = dbm.RICHIESTA_TUTTI_ATTUATORI()
        for item in all:
            s = item['nome_attuatore']
            temp = dict()
            temp['nome_attuatore'] = s
            temp['tipo_attuatore'] = item['tipo_attuatore']
            temp['indirizzo_Ambiente'] = item['indirizzo_Ambiente']
            temp['indirizzo_PL'] = item['indirizzo_PL']
            if (("timer_salita" in item) and ("timer_discesa" in item)):
                temp['timer_salita'] = item['timer_salita']
                temp['timer_discesa'] = item['timer_discesa']
            if ("nome_endpoint" in item):
                temp['nome_endpoint'] = item['nome_endpoint']
            lista_attuatori.append(temp)
        self.write(json.dumps(lista_attuatori))


# ============================================================================
# CRUD HANDLERS
# ============================================================================

class AGGIORNA_NOME_ATTUATORE_JOSN(tornado.web.RequestHandler):
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE, OPTIONS')
        self.set_status(204)
        self.finish()

    async def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        global q
        data = json.loads(self.request.body)
        if ("nome_attuatore" in data and "nuovo_nome" in data):
            old_attuatore = dbm.RICHIESTA_ATTUATORE(data['nome_attuatore'])
            dbm.AGGIORNA_ATTUATORE_xNome(data['nome_attuatore'], data['nuovo_nome'])
            await q.put(old_attuatore)

class AGGIORNA_INDIRIZZO_PL_JOSN(tornado.web.RequestHandler):
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE, OPTIONS')
        self.set_status(204)
        self.finish()

    async def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        global q
        data = json.loads(self.request.body)
        if ("nome_attuatore" in data and "indirizzo_PL" in data):
            dbm.AGGIORNA_ATTUATORE_xindirizzo_PL(data['nome_attuatore'], data['indirizzo_PL'])
            await q.put(1)

class AGGIORNA_INDIRIZZO_A_JOSN(tornado.web.RequestHandler):
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE, OPTIONS')
        self.set_status(204)
        self.finish()

    async def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        global q
        data = json.loads(self.request.body)
        if ("nome_attuatore" in data and "indirizzo_Ambiente" in data):
            dbm.AGGIORNA_ATTUATORE_xindirizzo_Ambiente(data['nome_attuatore'], data['indirizzo_Ambiente'])
            await q.put(1)

class AGGIORNA_TIPO_ATTUATORE_JOSN(tornado.web.RequestHandler):
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE, OPTIONS')
        self.set_status(204)
        self.finish()

    async def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        global q
        data = json.loads(self.request.body)
        if ("nome_attuatore" in data and "tipo_attuatore" in data):
            old_attuatore = dbm.RICHIESTA_ATTUATORE(data['nome_attuatore'])
            dbm.AGGIORNA_ATTUATORE_xTipo(data['nome_attuatore'], data['tipo_attuatore'].lower())
            # Unpublish vecchio domain
            unpublish_discovery(old_attuatore['nome_attuatore'], old_attuatore['tipo_attuatore'])
            # Publish nuovo domain
            publish_discovery(data['nome_attuatore'], data['tipo_attuatore'])
            await q.put(old_attuatore)

class RIMUOVI_ATTUATORE_JOSN(tornado.web.RequestHandler):
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE, OPTIONS')
        self.set_status(204)
        self.finish()

    async def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        global q
        data = json.loads(self.request.body)
        if ("nome_attuatore" in data):
            old_attuatore = dbm.RICHIESTA_ATTUATORE(data['nome_attuatore'])
            dbm.RIMUOVE_ATTUATORE(data['nome_attuatore'])
            unpublish_discovery(old_attuatore['nome_attuatore'], old_attuatore['tipo_attuatore'])
            await q.put(old_attuatore)

class AGGIUNGI_ATTUATORE_JOSN(tornado.web.RequestHandler):
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE, OPTIONS')
        self.set_status(204)
        self.finish()

    async def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        global q
        data = json.loads(self.request.body)
        if ("nome_attuatore" in data and "tipo_attuatore" in data and "indirizzo_Ambiente" in data and "indirizzo_PL" in data):
            dbm.AGGIUNGI_ATTUATORE(
                data['nome_attuatore'],
                data['tipo_attuatore'].lower(),
                data['indirizzo_Ambiente'],
                data['indirizzo_PL']
            )
            # Pubblica discovery
            publish_discovery(data['nome_attuatore'], data['tipo_attuatore'])
            if ("timer_salita" in data and "timer_discesa" in data):
                dbm.AGGIORNA_TIMER_SERRANDETAPPARELLE_UP(data['nome_attuatore'], data['timer_salita'])
                dbm.AGGIORNA_TIMER_SERRANDETAPPARELLE_DW(data['nome_attuatore'], data['timer_discesa'])
            await q.put(1)

class AGGIORNA_TIMER_SERRANDETAPPARELLE_JOSN(tornado.web.RequestHandler):
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE, OPTIONS')
        self.set_status(204)
        self.finish()

    async def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        global q
        data = json.loads(self.request.body)
        if ("nome_attuatore" in data and "timer_salita" in data):
            dbm.AGGIORNA_TIMER_SERRANDETAPPARELLE_UP(data['nome_attuatore'], data['timer_salita'])
            await q.put(1)
        if ("nome_attuatore" in data and "timer_discesa" in data):
            dbm.AGGIORNA_TIMER_SERRANDETAPPARELLE_DW(data['nome_attuatore'], data['timer_discesa'])
            await q.put(1)

class GetDeviceConfigurazione_JOSN(tornado.web.RequestHandler):
    def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        data = json.loads(self.request.body)
        dev_obj = dbm.RICHIESTA_ATTUATORE(data['nome_attuatore'])
        self.write(json.dumps(dev_obj))


# ============================================================================
# NODE-RED HANDLERS
# ============================================================================

class Send_to_NodeRed(tornado.web.RequestHandler):
    async def get(self):
        global q_nodered
        self.set_header("Access-Control-Allow-Origin", "*")
        await q_nodered.put(1)
        self.write(json.dumps({'status': 'ok'}))

class Get_NodeRed_manual_flow(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        n = nodered.nodered()
        js = n.gennera_NodeRed_database()
        self.write(js)

class Get_NodeRedAWS_manual_flow(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        n = noderedAWS.noderedAWS()
        js = n.gennera_NodeRed_database()
        self.write(js)


# ============================================================================
# AWS HANDLERS
# ============================================================================

class AWSCertificatiploadHandler(tornado.web.RequestHandler):
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE, OPTIONS')
        self.set_status(204)
        self.finish()

    def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        
        if not os.path.isdir('/home/pi/AWSConfig/'):
            try:
                os.mkdir('/home/pi/AWSConfig/')
            except Exception as e:
                pass

        if len(self.request.files) == 1:
            key = list(self.request.files)
            tipo = self.get_arguments('tipo')[0]
            
            if tipo == 'PRIVATE_KEY':
                file_name = self.request.files[key[0]][0]['filename']
                fname, file_extension = os.path.splitext(file_name)
                if file_extension.lower() == '.key':
                    with open('/home/pi/AWSConfig/awsiot.private.key', 'wb') as f:
                        f.write(self.request.files[key[0]][0]['body'])
                        
            elif tipo == 'CERT_PEM':
                file_name = self.request.files[key[0]][0]['filename']
                fname, file_extension = os.path.splitext(file_name)
                if file_extension.lower() == '.crt':
                    with open('/home/pi/AWSConfig/awsiot.cert.pem', 'wb') as f:
                        f.write(self.request.files[key[0]][0]['body'])
                        
            elif tipo == 'root-CA':
                file_name = self.request.files[key[0]][0]['filename']
                fname, file_extension = os.path.splitext(file_name)
                if file_extension.lower() == '.pem':
                    with open('/home/pi/AWSConfig/root-CA.crt', 'wb') as f:
                        f.write(self.request.files[key[0]][0]['body'])

        self.write(json.dumps({'status': 'ok'}))

class GetConfigurazionereactAWSHandler(tornado.web.RequestHandler):
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE, OPTIONS')
        self.set_status(204)
        self.finish()

    def get(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        
        EndPoint = ''
        if os.path.isfile('/home/pi/AWSConfig/EndPoint'):
            with open('/home/pi/AWSConfig/EndPoint') as fp:
                EndPoint = fp.readline()

        PRIVATE_KEY = 'awsiot.private.key' if os.path.isfile('/home/pi/AWSConfig/awsiot.private.key') else ''
        CERT_PEM = 'awsiot.cert.pem' if os.path.isfile('/home/pi/AWSConfig/awsiot.cert.pem') else ''
        CRT = 'root-CA.crt' if os.path.isfile('/home/pi/AWSConfig/root-CA.crt') else ''

        js = json.dumps({
            'EndPoint': EndPoint,
            'PRIVATE_KEY': PRIVATE_KEY,
            'CERT_PEM': CERT_PEM,
            'CRT': CRT
        })
        self.write(js)

    def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        data = json.loads(self.request.body)
        
        if not os.path.isdir('/home/pi/AWSConfig/'):
            try:
                os.mkdir('/home/pi/AWSConfig/')
            except Exception as e:
                pass
                
        with open('/home/pi/AWSConfig/EndPoint', 'w') as f:
            f.write(data['EndPoint'])
            
        self.write(json.dumps({'status': 'ok'}))

class SetDeviceEndPointAWS(tornado.web.RequestHandler):
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE, OPTIONS')
        self.set_status(204)
        self.finish()

    def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        data = json.loads(self.request.body)
        
        if "nome_attuatore" in data and "nome_endpoint" in data:
            dbm.AGGIORNA_ATTUATORE_x_AWS_ENDPOINT(data['nome_attuatore'], data['nome_endpoint'])
            
        self.write(json.dumps({'status': 'ok'}))


# ============================================================================
# MQTT CONFIG HANDLER
# ============================================================================

class MQTTConfigHandler(tornado.web.RequestHandler):
    def get(self):
        cfg = {
            "use_tls": False,
            "ws_port": MQTT_WS_PORT,
            "path": MQTT_WS_PATH,
            "username": mqtt_user or None,
            "password": mqtt_password or None
        }
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(cfg))


# ============================================================================
# HEALTH HANDLER
# ============================================================================

class HealthHandler(tornado.web.RequestHandler):
    """Endpoint di diagnostica per verificare stato del bridge"""
    def get(self):
        main_module = sys.modules.get('__main__')
        
        devices_count = 0
        mqtt_connected = False
        device_types = {}
        
        if main_module:
            try:
                shield = getattr(main_module, 'shield', None)
                scsmqtt = getattr(main_module, 'scsmqtt', None)
                
                if shield:
                    devices_count = len(shield.getDevices())
                    for device in shield.getDevices():
                        device_type = device.Get_Type().name
                        if device_type not in device_types:
                            device_types[device_type] = 0
                        device_types[device_type] += 1
                
                if scsmqtt:
                    mqtt_connected = hasattr(scsmqtt, 'client') and scsmqtt.client.is_connected
            except Exception as e:
                logger.error(f"Health check error: {e}")
        
        health_data = {
            "status": "ok",
            "timestamp": time.time(),
            "mqtt": {
                "connected": mqtt_connected,
                "host": os.getenv('MQTT_HOST'),
                "port": os.getenv('MQTT_PORT')
            },
            "serial": {
                "port": os.getenv('SERIAL_PORT', '/dev/serial0'),
                "configured": True
            },
            "devices": {
                "count": devices_count,
                "types": device_types
            },
            "system": {
                "debug_mode": os.getenv('DEBUG_MODE') == '1',
                "log_level": os.getenv('LOG_LEVEL')
            }
        }
        
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(health_data, indent=2))


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def rec_queque(jqueqe):
    """Riceve la queue per comunicare con main.py"""
    global q
    q = jqueqe

def rec_queque_NODERED(jqueqe):
    """Riceve la queue per Node-RED"""
    global q_nodered
    q_nodered = jqueqe


# ============================================================================
# APP FACTORY
# ============================================================================

def make_app():
    return tornado.web.Application([
        (r"/", HomeHandler),
        (r"/index.html", HomeHandler),
        (r"/test.html", Testandler),
        (r"/configurazione.html", ConfigurazioneHandler),
        (r"/noderedAlexa.html", noderedAlexaandler),
        (r"/noderedHome.html", noderedHomeHandler),
        (r"/NoderedAlexaAWS.html", NoderedAlexaAWSHandler),
        
        (r"/GetConfigurazionereact.json", GetConfigurazione_JSONreact),
        (r"/GetConfigurazione.json", GetConfigurazione_JSON),
        (r"/AGGIORNA_NOME_ATTUATORE.json", AGGIORNA_NOME_ATTUATORE_JOSN),
        (r"/AGGIORNA_INDIRIZZO_PL.json", AGGIORNA_INDIRIZZO_PL_JOSN),
        (r"/AGGIORNA_INDIRIZZO_A.json", AGGIORNA_INDIRIZZO_A_JOSN),
        (r"/AGGIORNA_TIPO_ATTUATORE.json", AGGIORNA_TIPO_ATTUATORE_JOSN),
        (r"/RIMUOVI_ATTUATORE.json", RIMUOVI_ATTUATORE_JOSN),
        (r"/AGGIUNGI_ATTUATORE.json", AGGIUNGI_ATTUATORE_JOSN),
        (r"/AGGIORNA_TIMER_SERRANDETAPPARELLE.json", AGGIORNA_TIMER_SERRANDETAPPARELLE_JOSN),
        (r"/GetDeviceConfigurazione.json", GetDeviceConfigurazione_JOSN),
        (r"/Send_to_NodeRed.json", Send_to_NodeRed),
        (r"/Get_NodeRed_manual_flow.json", Get_NodeRed_manual_flow),
        (r"/Get_NodeRedAWS_manual_flow.json", Get_NodeRedAWS_manual_flow),
        (r"/AWSCertificatiploadHandler.html", AWSCertificatiploadHandler),
        (r"/GetConfigurazionereactAWS.json", GetConfigurazionereactAWSHandler),
        (r"/SetDeviceEndPointAWS.json", SetDeviceEndPointAWS),
        
        (r'/ws', SocketHandler),
        (r'/site/image/(.*)', tornado.web.StaticFileHandler, {'path': dir_path + '/site/build'}),
        (r"/test3.html", reactMain),
        (r"/build(.*)", tornado.web.StaticFileHandler, {'path': dir_path + '/site/build/'}),
        (r'/static/css/(.*)', tornado.web.StaticFileHandler, {'path': dir_path + '/site/build/static/css/'}),
        (r'/static/js/(.*)', tornado.web.StaticFileHandler, {'path': dir_path + '/site/build/static/js/'}),
        
        (r"/mqtt_config.json", MQTTConfigHandler),
        (r"/health", HealthHandler),
    ], debug=True)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info("*****WEBAPP STARTED*****")
    logger.info(f"Tornado version: {tornado.version}")
    
    app = make_app()
    app.listen(80)
    tornado.ioloop.IOLoop.current().start()