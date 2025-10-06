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

import sys
#sys.path.append('/home/pi/SCS/APP')
#import databaseAttuatori
#import nodered

import importlib.machinery
#sys.path.append('/home/pi/SCS/WEB')
#import webapp

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



dbm = databaseAttuatori.configurazione_database()


cl = []     #websocket connessioni


q = None
q_nodered = None











# webapp.py (in alto, dove hai già letto le env)
import os, json, tornado.web

MQTT_HOST = os.getenv("MQTT_HOST", "core-mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_WS_PORT = int(os.getenv("MQTT_WS_PORT", "1884"))  # <— aggiungi questa env per WS
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_WS_PATH = os.getenv("MQTT_WS_PATH", "")  # di solito vuoto con Mosquitto addon

class MQTTConfigHandler(tornado.web.RequestHandler):
    def get(self):
        # NB: per il browser useremo window.location.hostname, non l’host del container
        cfg = {
            "use_tls": False,               # metti True se usi wss
            "ws_port": MQTT_WS_PORT,        # es. 1884 (websockets)
            "path": MQTT_WS_PATH,           # es. "/mqtt" se lo hai configurato
            "username": MQTT_USER or None,
            "password": MQTT_PASSWORD or None
        }
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(cfg))









# --- MQTT Discovery helpers ---------------------------------------------------
import re
import json as _json
import paho.mqtt.publish as _publish

def _slugify(value: str) -> str:
    s = re.sub(r"\s+", "_", value.strip())
    s = re.sub(r"[^a-zA-Z0-9_]", "", s)
    return s.lower()

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
    # "termostati": "climate",  # lo aggiungeremo quando prepari i topic completi
}

def _build_topics(object_id: str):
    base = f"/scsshield/device/{object_id}"
    return {
        "state": f"{base}/status",
        "switch_cmd": f"{base}/switch",
        "dimmer_cmd": f"{base}/dimmer",
        "dimmer_state": f"{base}/status/percentuale",
        "cover_setpos": f"{base}/percentuale",
        "cover_position": f"{base}/percentuale",  # se in futuro pubblichi lo stato
        "attrs": f"{base}/attrs",
    }

def _build_discovery_payload(nome_attuatore: str, tipo_attuatore: str):
    object_id = _slugify(nome_attuatore)
    unique_id = f"scs_{object_id}"
    t = (tipo_attuatore or "").lower()
    domain = DOMAIN_MAP.get(t, "switch")

    topics = _build_topics(object_id)

    device = {
        "identifiers": ["scs_bticino_bridge"],
        "name": "SCS BTicino Bridge",
        "manufacturer": "YourName",
        "model": "SCS ↔ MQTT",
    }

    # Default payload comune
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
        # per dimmer: comandi numerici 0..100 sullo stesso topic
        payload.update({
            "state_topic": topics["state"],
            "command_topic": topics["dimmer_cmd"],             # "on"/"off"/numero 0..100
            "brightness_command_topic": topics["dimmer_cmd"],  # numero 0..100
            "brightness_state_topic": topics["dimmer_state"],  # percentuale da /status/percentuale
            "brightness_scale": 100,
            "state_on": "on",
            "state_off": "off",
            "payload_on": "on",
            "payload_off": "off",
        })

    elif domain == "cover":
        # al momento non pubblichi la posizione -> optimistic
        payload.update({
            "set_position_topic": topics["cover_setpos"],   # invii 0..100
            "optimistic": True
            # Se in futuro pubblichi lo stato posizione:
            # "position_topic": topics["cover_position"],
            # "position_open": 100,
            # "position_closed": 0,
        })

    elif domain == "binary_sensor":
        # es. campanello: dovrai pubblicare "on"/"off" su topics["state"]
        payload.update({
            "state_topic": topics["state"],
            "payload_on": "on",
            "payload_off": "off",
            "device_class": "occupancy"  # o "motion", "doorbell" non esiste; scegli tu
        })

    elif domain == "sensor":
        # sensori temperatura: pubblichi il valore in chiaro su /status
        payload.update({
            "state_topic": topics["state"],
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        })

    elif domain == "lock":
        # se/quando implementi sblocco/chiusura su topic dedicati
        return None  # per ora non pubblichiamo discovery lock

    else:
        return None

    return domain, object_id, payload

def publish_discovery(nome_attuatore: str, tipo_attuatore: str, retain=True):
    res = _build_discovery_payload(nome_attuatore, tipo_attuatore)
    if not res:
        return
    domain, object_id, payload = res
    topic = f"homeassistant/{domain}/{object_id}/config"
    _publish.single(
        topic,
        payload=_json.dumps(payload),
        hostname=mqtt_host,
        port=mqtt_port,
        auth={"username": mqtt_user, "password": mqtt_password} if mqtt_user else None,
        retain=retain,
    )
    return topic

def unpublish_discovery(nome_attuatore: str, tipo_attuatore: str):
    res = _build_discovery_payload(nome_attuatore, tipo_attuatore)
    if not res:
        return
    domain, object_id, _ = res
    topic = f"homeassistant/{domain}/{object_id}/config"
    _publish.single(
        topic,
        payload="",    # payload vuoto = rimuovi entità
        hostname=mqtt_host,
        port=mqtt_port,
        auth={"username": mqtt_user, "password": mqtt_password} if mqtt_user else None,
        retain=True,
    )
    return topic
# ------------------------------------------------------------------------------ 

# ------------------------------------------------------------------------------ 


#        for c in cl:
#           c.write_message(data)

class SocketHandler(websocket.WebSocketHandler):
    nodolast_temp = None

    def check_origin(self, origin):
        return True

    def open(self):
        if self not in cl:
            cl.append(self)
        #self.write_message("HELLO WEBSOCKET")

    def on_close(self):
        if self in cl:
            cl.remove(self)

    def on_message(self, message):              
        #data = json.loads(message) 
        #print("sochet message: ", message)
        pass


#HOME
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        #self.render('site/main.html')
        self.render('site/build/index.html')
class HomeHandler(tornado.web.RequestHandler):
    def get(self):
        #self.render('site/main.html')
        self.render('site/build/index.html')


#PAGE
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



#REACT PAGE X TEST
class reactMain(tornado.web.RequestHandler):
    def get(self):
        self.render('site/build/test3.html')
"""        
class reactImagelamp_spenta(tornado.web.RequestHandler):
    def get(self):
        self.render('site/build/lamp_spenta.svg')
class reactImagelamp_accesa(tornado.web.RequestHandler):
    def get(self):
        self.render('site/build/lamp_accesa.svg')

"""







#GET_DATA
class GetConfigurazione_JSON(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Access-Control-Allow-Origin", "*")

        lista_attuatori = {}
        all = dbm.RICHIESTA_TUTTI_ATTUATORI()
        for item in all:
            s = item['nome_attuatore']
            #smod = re.sub("\s+", "_", s.strip())
            smod = s

            if (("timer_salita" in item) and ("timer_discesa" in item)):
                lista_attuatori[smod] = {'nome_attuatore' : s ,'tipo_attuatore': item['tipo_attuatore'], 'indirizzo_Ambiente' : item['indirizzo_Ambiente'] ,'indirizzo_PL': item['indirizzo_PL'], 'timer_salita': item['timer_salita'], 'timer_discesa': item['timer_discesa']}
            else:
                lista_attuatori[smod] = {'nome_attuatore' : s ,'tipo_attuatore': item['tipo_attuatore'], 'indirizzo_Ambiente' : item['indirizzo_Ambiente'] ,'indirizzo_PL': item['indirizzo_PL']}

        #print("*****" , lista_attuatori)
        self.write(json.dumps(lista_attuatori))
                
class GetConfigurazione_JSONreact(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Access-Control-Allow-Origin", "*")

        lista_attuatori = []
        all = dbm.RICHIESTA_TUTTI_ATTUATORI()
        for item in all:
            s = item['nome_attuatore']
            #smod = re.sub("\s+", "_", s.strip())
            smod = s

            temp = dict()

            temp['nome_attuatore'] = s
            temp['tipo_attuatore'] = item['tipo_attuatore']
            temp['indirizzo_Ambiente'] = item['indirizzo_Ambiente']
            temp['indirizzo_PL'] = item['indirizzo_PL']

            if (("timer_salita" in item) and ("timer_discesa" in item)):
                temp['timer_salita'] = item['timer_salita']
                temp['timer_discesa'] = item['timer_discesa']

            if ("nome_endpoint" in item) :
                temp['nome_endpoint'] = item['nome_endpoint']

            lista_attuatori.append(temp)
            """
            if (("timer_salita" in item) and ("timer_discesa" in item)):
                lista_attuatori.append({'nome_attuatore' : s ,'tipo_attuatore': item['tipo_attuatore'], 'indirizzo_Ambiente' : item['indirizzo_Ambiente'] ,'indirizzo_PL': item['indirizzo_PL'], 'timer_salita': item['timer_salita'], 'timer_discesa': item['timer_discesa']})
            else:
                lista_attuatori.append({'nome_attuatore' : s ,'tipo_attuatore': item['tipo_attuatore'], 'indirizzo_Ambiente' : item['indirizzo_Ambiente'] ,'indirizzo_PL': item['indirizzo_PL']})
            """

        #print("*****" , lista_attuatori)
        self.write(json.dumps(lista_attuatori))   


class AGGIORNA_NOME_ATTUATORE_JOSN(tornado.web.RequestHandler):
    global q
    #x react
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-   revalidate, max-age=0')
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
            dbm.AGGIORNA_ATTUATORE_xNome(data['nome_attuatore'],data['nuovo_nome'])           
            await q.put(old_attuatore)

class AGGIORNA_INDIRIZZO_PL_JOSN(tornado.web.RequestHandler):
    global q
    #x react
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-   revalidate, max-age=0')
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
            dbm.AGGIORNA_ATTUATORE_xindirizzo_PL(data['nome_attuatore'],data['indirizzo_PL'])
            await q.put(1)
class AGGIORNA_INDIRIZZO_A_JOSN(tornado.web.RequestHandler):
    global q
    #x react
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-   revalidate, max-age=0')
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
            dbm.AGGIORNA_ATTUATORE_xindirizzo_Ambiente(data['nome_attuatore'],data['indirizzo_Ambiente'])
            await q.put(1)
class AGGIORNA_TIPO_ATTUATORE_JOSN(tornado.web.RequestHandler):
    global q
    #x react
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-   revalidate, max-age=0')
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
            dbm.AGGIORNA_ATTUATORE_xTipo(data['nome_attuatore'],data['tipo_attuatore'].lower())
            # UNPUBLISH vecchio domain
            unpublish_discovery(old_attuatore['nome_attuatore'], old_attuatore['tipo_attuatore'])
            # PUBLISH nuovo domain
            publish_discovery(data['nome_attuatore'], data['tipo_attuatore'])			
            await q.put(old_attuatore)
class RIMUOVI_ATTUATORE_JOSN(tornado.web.RequestHandler):
    global q
    #x react
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-   revalidate, max-age=0')
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
    global q
    #x react
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-   revalidate, max-age=0')
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
            dbm.AGGIUNGI_ATTUATORE(data['nome_attuatore'],data['tipo_attuatore'].lower(),data['indirizzo_Ambiente'],data['indirizzo_PL'])
            # PUBBLICA DISCOVERY
            publish_discovery(data['nome_attuatore'], data['tipo_attuatore'])
            if ("timer_salita" in data and "timer_discesa" in data):
                dbm.AGGIORNA_TIMER_SERRANDETAPPARELLE_UP(data['nome_attuatore'],data['timer_salita'])
                dbm.AGGIORNA_TIMER_SERRANDETAPPARELLE_DW(data['nome_attuatore'],data['timer_discesa'])
            await q.put(1)


class AGGIORNA_TIMER_SERRANDETAPPARELLE_JOSN(tornado.web.RequestHandler):
    global q
    #x react
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-   revalidate, max-age=0')
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
            dbm.AGGIORNA_TIMER_SERRANDETAPPARELLE_UP(data['nome_attuatore'],data['timer_salita'])
            await q.put(1)
        if ("nome_attuatore" in data and "timer_discesa" in data):
            dbm.AGGIORNA_TIMER_SERRANDETAPPARELLE_DW(data['nome_attuatore'],data['timer_discesa'])
            await q.put(1)
class GetDeviceConfigurazione_JOSN(tornado.web.RequestHandler):
    def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        data = json.loads(self.request.body)
        dev_obj = dbm.RICHIESTA_ATTUATORE(data['nome_attuatore'])
        self.write(json.dumps(dev_obj))   






class Send_to_NodeRed(tornado.web.RequestHandler):
    global q_nodered
    async def get(self):
        global q_nodered
        self.set_header("Access-Control-Allow-Origin", "*")
        await q_nodered.put(1)
        self.write(json.dumps({'status':'ok'}))
def rec_queque_NODERED(jqueqe):
    global q_nodered
    q_nodered = jqueqe
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


# ******************** AWS **************************
# ******************** AWS **************************
# ******************** AWS **************************

# UPLOAD FILE CERTIFICATI
class AWSCertificatiploadHandler(tornado.web.RequestHandler):
    #x react
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-   revalidate, max-age=0')
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE, OPTIONS')        
        self.set_status(204)
        self.finish()

    def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        #print(self.get_arguments('tipo')[0])
        #print(self.request.files)

        if(os.path.isdir('/home/pi/AWSConfig/') == False):
            #Crea directory
            try:
                os.mkdir('/home/pi/AWSConfig/')
            except Exception as e:
                pass

        if len(self.request.files) == 1:
            key = list(self.request.files)
            if(self.get_arguments('tipo')[0] == 'PRIVATE_KEY'):
                file_name = self.request.files[key[0]][0]['filename']
                fname, file_extension = os.path.splitext(file_name)
                if(file_extension.lower() == '.key'):
                    #rename and save
                    with open('/home/pi/AWSConfig/awsiot.private.key', 'wb') as f:
                        f.write(self.request.files[key[0]][0]['body'])

            if(self.get_arguments('tipo')[0] == 'CERT_PEM'):
                file_name = self.request.files[key[0]][0]['filename']
                fname, file_extension = os.path.splitext(file_name)
                if(file_extension.lower() == '.crt'):
                    #rename and save
                    with open('/home/pi/AWSConfig/awsiot.cert.pem', 'wb') as f:
                        f.write(self.request.files[key[0]][0]['body'])

            if(self.get_arguments('tipo')[0] == 'root-CA'):
                file_name = self.request.files[key[0]][0]['filename']
                fname, file_extension = os.path.splitext(file_name)
                if(file_extension.lower() == '.pem'):
                    #rename and save
                    with open('/home/pi/AWSConfig/root-CA.crt', 'wb') as f:
                        f.write(self.request.files[key[0]][0]['body'])

        self.write(json.dumps({'status':'ok'}))

# GET CONFIGURAZIONE AWS
class GetConfigurazionereactAWSHandler(tornado.web.RequestHandler):
    #x react
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-   revalidate, max-age=0')
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE, OPTIONS')        
        self.set_status(204)
        self.finish()

    def get(self):
        self.set_header("Access-Control-Allow-Origin", "*")

        print("GetConfigurazionereactAWS.json -> GET")

        EndPoint = ''
        if(os.path.isfile('/home/pi/AWSConfig/EndPoint') == True):
            with open('/home/pi/AWSConfig/EndPoint') as fp:
                EndPoint = fp.readline()

        PRIVATE_KEY = ''
        if(os.path.isfile('/home/pi/AWSConfig/awsiot.private.key') == True):
            PRIVATE_KEY = 'awsiot.private.key'

        CERT_PEM = ''
        if(os.path.isfile('/home/pi/AWSConfig/awsiot.cert.pem') == True):
            CERT_PEM = 'awsiot.cert.pem'

        CRT = ''
        if(os.path.isfile('/home/pi/AWSConfig/root-CA.crt') == True):
            CRT = 'root-CA.crt'

        js = json.dumps({'EndPoint': EndPoint, 'PRIVATE_KEY': PRIVATE_KEY, 'CERT_PEM': CERT_PEM, 'CRT':CRT})
        self.write(js)

    def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")

        data = json.loads(self.request.body)

        if(os.path.isdir('/home/pi/AWSConfig/') == False):
            #Crea directory
            try:
                os.mkdir('/home/pi/AWSConfig/')
            except Exception as e:
                pass
        with open('/home/pi/AWSConfig/EndPoint', 'w') as f:
            f.write(data['EndPoint'])

        self.write(json.dumps({'status':'ok'}))

# SET DEVICE ENDPOINT in AWS
class SetDeviceEndPointAWS(tornado.web.RequestHandler):
    #x react
    def options(self):
        self.set_header('Cache-Control', 'no-store, no-cache, must-   revalidate, max-age=0')
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE, OPTIONS')        
        self.set_status(204)
        self.finish()

    def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")

        data = json.loads(self.request.body)
        if (("nome_attuatore" in data) and ("nome_endpoint" in data)):
            dbm.AGGIORNA_ATTUATORE_x_AWS_ENDPOINT(data['nome_attuatore'], data['nome_endpoint'])

        self.write(json.dumps({'status':'ok'}))






















def rec_queque(jqueqe):
    global q
    q = jqueqe
    #print(type(q))




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

        #Node red
        (r"/Send_to_NodeRed.json", Send_to_NodeRed),
        (r"/Get_NodeRed_manual_flow.json", Get_NodeRed_manual_flow),
        (r"/Get_NodeRedAWS_manual_flow.json", Get_NodeRedAWS_manual_flow),





        #AWS certificati Upload
        (r"/AWSCertificatiploadHandler.html", AWSCertificatiploadHandler),
        (r"/GetConfigurazionereactAWS.json", GetConfigurazionereactAWSHandler),
        (r"/SetDeviceEndPointAWS.json", SetDeviceEndPointAWS),



        #websocket
        (r'/ws', SocketHandler),

        #(r'/site/js/(.*)', tornado.web.StaticFileHandler, {'path': '/home/pi/SCS/WEB/site/js/'}),
        #(r'/site/css/(.*)', tornado.web.StaticFileHandler, {'path': '/home/pi/SCS/WEB/site/css/'}),
        (r'/site/image/(.*)', tornado.web.StaticFileHandler, {'path': dir_path + '/site/build'}),




        #(r"/test.html", Testandler),
        #(r"/configurazione.html", ConfigurazioneHandler),

        #React x pagina test
        (r"/test3.html", reactMain),
        (r"/build(.*)", tornado.web.StaticFileHandler, {'path': dir_path + '/site/build/'}),
        (r'/static/css/(.*)', tornado.web.StaticFileHandler, {'path': dir_path + '/site/build/static/css/'}),
        (r'/static/js/(.*)', tornado.web.StaticFileHandler, {'path': dir_path + '/site/build/static/js/'}),


        (r"/mqtt_config.json", MQTTConfigHandler)



    ], debug=True)



if __name__ == "__main__":    
    print("*****WEBAPP*****")
    print(tornado.version)
    
    app = make_app()
    app.listen(80)
    tornado.ioloop.IOLoop.current().start()



