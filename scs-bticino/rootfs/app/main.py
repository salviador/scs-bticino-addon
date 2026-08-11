import asyncio
import time
import os
import janus
import subprocess
import json
import SCS
import mqtt2
from serialhandler import SerialHandler
import databaseAttuatori
import nodered
import logging
import sys
import os, time, atexit
import tornado
import tornado.web
import tornado.ioloop
import tornado.httpserver
import uvloop

# Docker copia le due directory affiancate in /app/app e /app/WEB.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.abspath(os.path.join(APP_DIR, os.pardir, 'WEB'))
if WEB_DIR not in sys.path:
    sys.path.insert(0, WEB_DIR)

import webapp


# Configurazione logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
DEBUG_MODE = str(os.getenv('DEBUG_MODE', 'false')).lower() in ('1','true','yes','on')

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Leggi porta seriale da variabile d'ambiente PRIMA di usarla nei log
nameSerial = os.getenv('SERIAL_PORT', '/dev/serial0')

# Debug remoto se abilitato
if DEBUG_MODE:
    try:
        import debugpy
        debugpy.listen(("0.0.0.0", 5678))
        logger.warning("⏳ Debugger listening on port 5678")
        logger.warning("⏳ Waiting for debugger to attach...")
        debugpy.wait_for_client()
        logger.info("✅ Debugger attached!")
    except Exception as e:
        logger.error(f"Failed to start debugger: {e}")

logger.info("="*50)
logger.info("SCS BTicino Bridge - Application Starting")
logger.info(f"Serial Port: {nameSerial}")
logger.info(f"Debug Mode: {DEBUG_MODE}")
logger.info(f"Log Level: {LOG_LEVEL}")
logger.info("="*50)


import logging
import sys

# ... existing imports ...

logger = logging.getLogger(__name__)

# =============================================================================
# GPIO CONFIGURATION (Raspberry Pi 5)
# =============================================================================
import gpiod
import atexit

GPIO_PIN = 12
gpio_chip = None
gpio_line = None
gpio_available = False

def gpio12_init():
    """Inizializza GPIO12 usando libgpiod per RPi 5"""
    global gpio_chip, gpio_line, gpio_available
    
    # Prova tutti i chip disponibili
    for chip_name in ['gpiochip4', 'gpiochip0', 'gpiochip10', 'gpiochip11', 
                      'gpiochip12', 'gpiochip13', 'gpiochip1', 'gpiochip2']:
        try:
            logger.info(f"Trying {chip_name}...")
            gpio_chip = gpiod.Chip(chip_name)
            
            # Info dettagliate
            num_lines = gpio_chip.num_lines()
            logger.info(f"  {chip_name}: {num_lines} lines, name={gpio_chip.name()}, label={gpio_chip.label()}")
            
            # Verifica linee disponibili
            if num_lines <= GPIO_PIN:
                logger.debug(f"  {chip_name} only has {num_lines} lines (need {GPIO_PIN})")
                gpio_chip.close()
                continue
            
            # Prova ad acquisire GPIO12
            test_line = gpio_chip.get_line(GPIO_PIN)
            
            if test_line.is_used():
                logger.warning(f"  Line {GPIO_PIN} already used by '{test_line.consumer()}'")
                gpio_chip.close()
                continue
            
            gpio_line = test_line
            gpio_line.request(
                consumer='scs_bticino',
                type=gpiod.LINE_REQ_DIR_OUT,
                default_vals=[1]
            )
            logger.info(f"✓ GPIO12 activated on {chip_name}")
            gpio_available = True
            return True
            
        except PermissionError as e:
            logger.warning(f"  {chip_name}: Permission denied")
        except OSError as e:
            logger.warning(f"  {chip_name}: {e}")
        except Exception as e:
            logger.debug(f"  {chip_name}: {type(e).__name__}: {e}")
        finally:
            if gpio_chip and not gpio_available:
                try:
                    gpio_chip.close()
                except:
                    pass
                gpio_chip = None
    
    # Fallback: prova metodo host
    logger.warning("libgpiod failed, trying sysfs method...")
    return gpio12_init_sysfs()

def gpio12_init_sysfs():
    """Fallback usando /sys/class/gpio"""
    global gpio_available
    try:
        # Export GPIO12
        with open('/sys/class/gpio/export', 'w') as f:
            f.write(str(GPIO_PIN))
        time.sleep(0.1)
        
        # Set direction OUT
        with open(f'/sys/class/gpio/gpio{GPIO_PIN}/direction', 'w') as f:
            f.write('out')
        
        # Set HIGH
        with open(f'/sys/class/gpio/gpio{GPIO_PIN}/value', 'w') as f:
            f.write('1')
        
        logger.info(f"✓ GPIO12 activated via sysfs")
        gpio_available = True
        return True
    except Exception as e:
        logger.error(f"sysfs GPIO init failed: {e}")
        return False

def gpio12_set(value: int):
    """Imposta GPIO12"""
    global gpio_line, gpio_available
    
    if not gpio_available:
        return False
    
    # Prova libgpiod
    if gpio_line:
        try:
            gpio_line.set_value(1 if value else 0)
            logger.debug(f"GPIO12 = {'HIGH' if value else 'LOW'}")
            return True
        except Exception as e:
            logger.debug(f"gpiod set failed: {e}")
    
    # Fallback sysfs
    try:
        with open(f'/sys/class/gpio/gpio{GPIO_PIN}/value', 'w') as f:
            f.write('1' if value else '0')
        return True
    except Exception as e:
        logger.debug(f"sysfs set failed: {e}")
        return False

def gpio12_cleanup():
    """Cleanup GPIO"""
    global gpio_chip, gpio_line, gpio_available
    try:
        if gpio_line:
            gpio_line.set_value(0)
            gpio_line.release()
        if gpio_chip:
            gpio_chip.close()
        
        # Cleanup sysfs
        try:
            with open('/sys/class/gpio/unexport', 'w') as f:
                f.write(str(GPIO_PIN))
        except:
            pass
        
        logger.info("✓ GPIO cleanup completed")
    except Exception as e:
        logger.debug(f"GPIO cleanup: {e}")

# Inizializza GPIO
logger.info("Initializing GPIO for Raspberry Pi 5...")
gpio12_init()
atexit.register(gpio12_cleanup)


# Test GPIO se disponibile
if gpio_available:
    logger.info("✓ GPIO12 enabled - testing...")
    gpio12_set(1)
    logger.info("✓ GPIO test completed")
else:
    logger.warning("⚠ Running without GPIO - SCS opto may not work")





# Debug info
logger.info("=== GPIO DEBUG ===")
try:
    gpio_devs = [d for d in os.listdir('/dev') if 'gpio' in d.lower()]
    logger.info(f"GPIO devices: {gpio_devs}")
except Exception as e:
    logger.error(f"Cannot list /dev: {e}")

logger.info(f"/sys/class/gpio exists: {os.path.exists('/sys/class/gpio')}")
logger.info("==================")

# =============================================================================
# DATABASE E EVENT LOOP
# =============================================================================
if gpio_available:
    logger.info("✓ GPIO12 enabled (opto active)")
else:
    logger.warning("⚠ Running without GPIO control - some features may be limited")

dbm = databaseAttuatori.configurazione_database()
loop = uvloop.new_event_loop()
asyncio.set_event_loop(loop)
lock_uartTX = asyncio.Lock()
lock_refresh_Database = asyncio.Lock()

ENERGY_TOTALS_PATH = '/data/scs_energy_totals.json'


class EnergyAccumulator:
    """Totalizza l'energia in kWh a partire dalla potenza istantanea in W."""

    def __init__(self, path):
        self.path = path
        self.data = {}
        self._load()

    def _load(self):
        self.data = {}
        if os.path.isfile(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as fp:
                    loaded = json.load(fp)
                if isinstance(loaded, dict):
                    self.data = loaded
            except Exception as e:
                logger.error(f"Failed to load energy totals: {e}")

        # Dopo un riavvio ripartiamo da "adesso" per non integrare il downtime.
        now_ts = time.time()
        for slug, entry in list(self.data.items()):
            if not isinstance(entry, dict):
                self.data[slug] = {
                    "energy_kwh": 0.0,
                    "power_w": 0.0,
                    "last_update_ts": None,
                }
                continue

            entry["energy_kwh"] = float(entry.get("energy_kwh", 0.0) or 0.0)
            entry["power_w"] = float(entry.get("power_w", 0.0) or 0.0)
            if entry.get("last_update_ts") is not None:
                entry["last_update_ts"] = now_ts

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as fp:
                json.dump(self.data, fp, indent=2, sort_keys=True)
        except Exception as e:
            logger.error(f"Failed to save energy totals: {e}")

    def ensure_device(self, slug):
        entry = self.data.get(slug)
        if not isinstance(entry, dict):
            entry = {
                "energy_kwh": 0.0,
                "power_w": 0.0,
                "last_update_ts": None,
            }
            self.data[slug] = entry

        entry["energy_kwh"] = float(entry.get("energy_kwh", 0.0) or 0.0)
        entry["power_w"] = float(entry.get("power_w", 0.0) or 0.0)
        return entry

    def register_device(self, slug):
        self.ensure_device(slug)

    def get_energy_kwh(self, slug):
        entry = self.ensure_device(slug)
        return float(entry.get("energy_kwh", 0.0) or 0.0)

    def _integrate_until(self, entry, now_ts):
        last_update_ts = entry.get("last_update_ts")
        power_w = max(float(entry.get("power_w", 0.0) or 0.0), 0.0)

        if last_update_ts is not None and now_ts > last_update_ts and power_w > 0:
            delta_kwh = power_w * (now_ts - last_update_ts) / 3600000.0
            entry["energy_kwh"] = float(entry.get("energy_kwh", 0.0) or 0.0) + delta_kwh

        entry["last_update_ts"] = now_ts

    def update_power(self, slug, power_w, now_ts=None):
        now_ts = now_ts or time.time()
        entry = self.ensure_device(slug)
        self._integrate_until(entry, now_ts)
        entry["power_w"] = max(float(power_w), 0.0)
        self._save()
        return self.get_energy_kwh(slug)

    def tick(self, now_ts=None):
        now_ts = now_ts or time.time()
        changed_slugs = []

        for slug, entry in self.data.items():
            energy_before = round(float(entry.get("energy_kwh", 0.0) or 0.0), 6)
            self._integrate_until(entry, now_ts)
            energy_after = round(float(entry.get("energy_kwh", 0.0) or 0.0), 6)
            if energy_after != energy_before:
                changed_slugs.append(slug)

        if changed_slugs:
            self._save()

        return changed_slugs


energy_accumulator = EnergyAccumulator(ENERGY_TOTALS_PATH)












# Serial Handler
ser = SerialHandler(
    port=nameSerial,
    baudrate=9600
)

STOP = asyncio.Event()

# Inizializza shield e mqtt
shield = SCS.SCSshield()
shield.SetUART(ser)
scsmqtt = mqtt2.SCSMQTT2(STOP)


async def Node_Red_flow(jqueqe):
    while(True):
        v = await jqueqe.get()
        n = nodered.nodered()
        n.main()



async def publish_all_discovery():
    """Pubblica MQTT Discovery per tutti i dispositivi al boot"""
    logger.info("Publishing MQTT Discovery for all devices...")
    
    # Aspetta che MQTT sia connesso
    max_retries = 30
    for i in range(max_retries):
        if hasattr(scsmqtt, 'client') and scsmqtt.client.is_connected:
            break
        await asyncio.sleep(1)
    else:
        logger.error("MQTT not connected after 30s, skipping discovery publish")
        return
    
    from webapp import publish_discovery
    all_devices = dbm.RICHIESTA_TUTTI_ATTUATORI()
    
    for device in all_devices:
        try:
            nome = device['nome_attuatore']
            tipo = device['tipo_attuatore']
            publish_discovery(nome, tipo)
            if tipo == 'sensori_consumo':
                device_slug = webapp.get_device_slug(nome)
                energy_accumulator.register_device(device_slug)
                await scsmqtt.post_to_MQTT(
                    f"/scsshield/device/{device_slug}/energy",
                    format(energy_accumulator.get_energy_kwh(device_slug), '.6f')
                )
            logger.info(f"✓ Published discovery for: {nome} ({tipo})")
            await asyncio.sleep(0.1)  # rate limiting
        except Exception as e:
            logger.error(f"Failed to publish discovery for {device}: {e}")
    
    logger.info("✓ Discovery publish completed")
    
    
    
    
def popula_device():
    """Legge il database e popola la lista device nella classe SCS.SCSshield"""
    shield.clearDevice()
    allDevice = dbm.RICHIESTA_TUTTI_ATTUATORI()

    for item in allDevice:
        if(((item['indirizzo_Ambiente']) == '') or ((item['indirizzo_PL']) == '')):
            return

        if (item['tipo_attuatore'] == "on_off"):
            on_off = SCS.Switch(shield)
            on_off.Set_Address(int(item['indirizzo_Ambiente']), int(item['indirizzo_PL']))
            on_off.Set_Nome_Attuatore(item['nome_attuatore'])
            shield.addDevice(on_off)

        elif (item['tipo_attuatore'] == "serrande_tapparelle"):
            serranda = SCS.Serranda(shield)
            serranda.Set_Address(int(item['indirizzo_Ambiente']), int(item['indirizzo_PL']))
            serranda.set_Timer(int(item['timer_salita']), int(item['timer_discesa']))
            serranda.Set_Nome_Attuatore(item['nome_attuatore'])
            serranda.register_MQTT_POST(scsmqtt, loop)
            shield.addDevice(serranda)

        elif (item['tipo_attuatore'] == "dimmer"):
            dimmer = SCS.Dimmer(shield)
            dimmer.Set_Address(int(item['indirizzo_Ambiente']), int(item['indirizzo_PL']))
            dimmer.Set_Nome_Attuatore(item['nome_attuatore'])
            shield.addDevice(dimmer)

        elif (item['tipo_attuatore'] == "sensori_temperatura"):
            sensore = SCS.Sensori_Temperatura(shield)
            new_add = hex(int(item['indirizzo_Ambiente']) * 10 + int(item['indirizzo_PL']))
            
            if(len(new_add)==3):
                new_add = new_add[0] + new_add[1] + '0' + new_add[2]
                logger.info(f'corretto {new_add}')

            sensore.Set_Address(int(new_add[2], 16), int(new_add[3], 16))
            sensore.Set_Nome_Attuatore(item['nome_attuatore'])
            shield.addDevice(sensore)
            loop.create_task(sensore.Forza_la_lettura_Temperatura(lock_uartTX))

        elif (item['tipo_attuatore'] == "termostati"):
            termostato = SCS.Termostati(shield)
            termostato.Set_obj_SensoreTemp(SCS.Sensori_Temperatura(shield))
            sensore = termostato.Get_obj_SensoreTemp()

            new_add = hex(int(item['indirizzo_Ambiente']) * 10 + int(item['indirizzo_PL']))
            if(len(new_add)==3):
                new_add = new_add[0] + new_add[1] + '0' + new_add[2]
            sensore.Set_Address(int(new_add[2], 16), int(new_add[3], 16))
            sensore.Set_Nome_Attuatore(item['nome_attuatore'])
            shield.addDevice(sensore)

            new_add = hex(int(item['indirizzo_Ambiente']) * 10 + int(item['indirizzo_PL']))
            if(len(new_add)==3):
                new_add = new_add[0] + new_add[1] + '0' + new_add[2]
            termostato.Set_Address(int(new_add[2], 16), int(new_add[3], 16))
            termostato.Set_Nome_Attuatore(item['nome_attuatore'])
            shield.addDevice(termostato)
            loop.create_task(sensore.Forza_la_lettura_Temperatura(lock_uartTX))

        elif (item['tipo_attuatore'] == "sensori_consumo"):
            sensore_consumo = SCS.Sensori_Consumo(shield)
            sensore_consumo.Set_Address(int(item['indirizzo_Ambiente']), int(item['indirizzo_PL']))
            sensore_consumo.Set_Nome_Attuatore(item['nome_attuatore'])
            shield.addDevice(sensore_consumo)
            energy_accumulator.register_device(webapp.get_device_slug(item['nome_attuatore']))

        elif (item['tipo_attuatore'] == "gruppi"):
            gruppi = SCS.Gruppi(shield)
            gruppi.Set_Address(int(item['indirizzo_Ambiente']), int(item['indirizzo_PL']))
            gruppi.Set_Nome_Attuatore(item['nome_attuatore'])
            shield.addDevice(gruppi)

        elif (item['tipo_attuatore'] == "serrature"):
            serrature = SCS.Serrature(shield)
            serrature.Set_Address(int(item['indirizzo_Ambiente']), 0)
            serrature.Set_Nome_Attuatore(item['nome_attuatore'])
            shield.addDevice(serrature)

        elif (item['tipo_attuatore'] == "campanello_porta"):
            campanello = SCS.Campanello(shield)
            campanello.Set_Address(0, int(item['indirizzo_PL']))
            campanello.Set_Nome_Attuatore(item['nome_attuatore'])
            campanello.register_MQTT_POST(scsmqtt, loop)
            shield.addDevice(campanello)


async def tsk_refresh_database(jqueqe):
    """Aggiorna il database e popola la lista device"""
    global shield
    while(True):
        try:
            v = await jqueqe.get()

            if(type(v) != int):
                try:
                    nomeAtt = v['nome_attuatore'].lower()
                    tipoAtt = v['tipo_attuatore']
                    
                    # ✅ USA SLUG per reset topic
                    device_slug = nomeAtt

                    if(tipoAtt == 'on_off'):
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/status")
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/switch")
                    elif(tipoAtt == 'dimmer'):
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/status")
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/dimmer")
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/status/percentuale")
                    elif(tipoAtt == 'serrande_tapparelle'):
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/status")
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/percentuale")
                    elif(tipoAtt == 'sensori_temperatura'):
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/request")
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/status")
                    elif(tipoAtt == 'sensori_consumo'):
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/status")
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/energy")
                    elif(tipoAtt == 'termostati'):
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/status")
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/temperatura_termostato_impostata")
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/modalita_termostato_impostata")
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/set_temp_termostato")
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/set_modalita_termostato")
                    elif(tipoAtt == 'gruppi'):
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/switch")
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/status")
                    elif(tipoAtt == 'campanello_porta'):
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/status")
                    elif(tipoAtt == 'serrature'):
                        await scsmqtt.post_to_MQTT_retain_reset(f"/scsshield/device/{device_slug}/sblocca")

                except KeyError:
                    pass
            
            popula_device()
        except Exception as e:
            logger.error("Error in tsk_refresh_database")
            logger.error(e)
            


async def mqtt_action(jqueqe):
    """Riceve messaggi da MQTT e invia comandi al BUS SCS"""
    while(True):
        try:
            v = await jqueqe.get()
            topic = v["topic"]
            payload = v["payload"]
            message = str(payload, 'utf-8')

            b = topic.split("/")
            mtopicbase = '/' + b[1] + '/' + b[2] + '/'
            
            if "/scsshield/device/#"[:-1] in mtopicbase:
                device_slug_from_topic = b[3].lower()
                
                
                devices = shield.getDevices()
                
                for device in devices:
                    ndevice = device.Get_Nome_Attuatore().lower()
                    

                    if ndevice == device_slug_from_topic:
                        tdevice = device.Get_Type()
                        
                        if tdevice.name == SCS.TYPE_INTERfACCIA.on_off.name:
                            action = b[4]
                            if action.lower() == "switch":
                                if message.lower() in ["on", "1"]:
                                    await device.On(lock_uartTX)
                                elif message.lower() in ["off", "0"]:
                                    await device.Off(lock_uartTX)
                                elif message.lower().startswith("t") or message.lower() == "2":
                                    await device.Toggle(lock_uartTX)
                                    
                        elif tdevice.name == SCS.TYPE_INTERfACCIA.dimmer.name:
                            action = b[4]
                            if action.lower() == "dimmer":
                                msg_lower = message.lower().strip()
        
                                # ✅ PRIMA gestisci comandi speciali, POI i numeri
                                if msg_lower in ["on", "1"]:
                                    await device.On(lock_uartTX)
                                elif msg_lower in ["off", "0"]:
                                    await device.Off(lock_uartTX)
                                elif msg_lower.startswith("t") or msg_lower == "2":
                                    await device.Toggle(lock_uartTX)
                                else:
                                    # Tutto il resto è una percentuale                
                                    try:
                                        brightness = int(message)
                                        await device.Set_Dimmer_percent(brightness, lock_uartTX)
                                    except ValueError:
                                        logger.warning(f"Dimmer {device_slug}: comando sconosciuto '{message}'")
                
                
                        elif tdevice.name == SCS.TYPE_INTERfACCIA.serrande_tapparelle.name:
                            action = b[4]
                            if action.lower() == "percentuale":
                                try:
                                    await device.Azione(int(message), lock_uartTX)
                                except Exception as e:
                                    logger.error("Error in serranda action")
                                    logger.error(e)

                        elif tdevice.name == SCS.TYPE_INTERfACCIA.sensori_temperatura.name:
                            action = b[4]
                            if action.lower() == "request":
                                await device.Forza_la_lettura_Temperatura(lock_uartTX)

                        elif tdevice.name == SCS.TYPE_INTERfACCIA.termostati.name:
                            action = b[4]
                            if action.lower() == "set_temp_termostato":
                                await device.set_temp_termostato(float(message), lock_uartTX)
                            elif action.lower() == "set_modalita_termostato":
                                await device.set_modalita_termostato(message, lock_uartTX)

                        elif tdevice.name == SCS.TYPE_INTERfACCIA.gruppi.name:
                            action = b[4]
                            if action.lower() == "switch":
                                if message.lower() in ["on", "1"]:
                                    await device.On(lock_uartTX)
                                elif message.lower() in ["off", "0"]:
                                    await device.Off(lock_uartTX)
                                elif message.lower().startswith("t") or message.lower() == "2":
                                    await device.Toggle(lock_uartTX)

                        elif tdevice.name == SCS.TYPE_INTERfACCIA.serrature.name:
                            action = b[4]
                            if action.lower() == "sblocca":
                                await device.Sblocca(lock_uartTX)

                                
                                
                                
                                

            elif topic == '/scsshield/SendtoBus':
                s1 = message.split(' ')
                s2 = message.split(',')
                sx = []
                
                if len(s1) in [7, 11]:
                    sx = s1
                elif len(s2) in [7, 11]:
                    sx = s2
                    
                if len(sx) > 0:
                    bytesRaw = []
                    for _ in sx:
                        v = _
                        if _[0].lower() == 'x':
                            v = _[1:]
                        elif _[1].lower() == 'x':
                            v = _[2:]
                        bytesRaw.append(bytes.fromhex(v))

                    async with lock_uartTX:
                        if len(bytesRaw) == 7:
                            await shield.interfaccia_send_COMANDO_7_RAW(bytesRaw)
                        elif len(bytesRaw) == 11:
                            await shield.interfaccia_send_COMANDO_11_RAW(bytesRaw)

        except Exception as e:
            logger.error("Error in mqtt_action")
            logger.error(e)

        await asyncio.sleep(0)


async def tsk_publish_energy_totals():
    """Aggiorna periodicamente l'energia cumulata per i sensori di consumo."""
    while True:
        try:
            await asyncio.sleep(60)
            for device_slug in energy_accumulator.tick():
                await scsmqtt.post_to_MQTT(
                    f"/scsshield/device/{device_slug}/energy",
                    format(energy_accumulator.get_energy_kwh(device_slug), '.6f')
                )
        except Exception as e:
            logger.error("Error in tsk_publish_energy_totals")
            logger.error(e)


# Intervallo (in secondi) del keep-alive della trasmissione continua dei toroidi F520.
# Il dispositivo si autodisattiva dopo un timeout se nessuno gli invia la trama di
# abilitazione (0xA8 0xD1 <ADDR> 0x02 0x32 0x00 0x02 0x1D 0xFF <CHK> 0xA3),
# quindi la rinviamo periodicamente. 60 s è un valore di sicurezza.
SENSORI_CONSUMO_KEEPALIVE_SEC = 60*5


async def tsk_keepalive_sensori_consumo():
    """
    Mantiene attiva la trasmissione continua della potenza per tutti i sensori
    di consumo F520 configurati. Se non ci sono sensori di consumo tra i device
    registrati, il task non invia alcuna trama sul bus.
    """
    # Piccolo ritardo iniziale per lasciare che popula_device() completi
    await asyncio.sleep(2)
    while True:
        try:
            devices = shield.getDevices()
            for device in devices:
                try:
                    if device.Get_Type().name == SCS.TYPE_INTERfACCIA.sensori_consumo.name:
                        await device.Attiva_Trasmissione_Continua(lock_uartTX)
                        # Piccolo gap tra toroidi diversi per non intasare il bus
                        await asyncio.sleep(0.2)
                except Exception as inner:
                    logger.error(f"keepalive sensore_consumo fallito: {inner}")
            await asyncio.sleep(SENSORI_CONSUMO_KEEPALIVE_SEC)
        except Exception as e:
            logger.error("Error in tsk_keepalive_sensori_consumo")
            logger.error(e)
            await asyncio.sleep(SENSORI_CONSUMO_KEEPALIVE_SEC)


async def deviceReceiver_from_SCSbus(jqueqe):
    """Riceve gli stati dei device dal BUS SCS e li invia a MQTT"""
    while True:
        trama = await jqueqe.get()

        try:
            devices = shield.getDevices()
            for device in devices:
                type = device.Get_Type()
                ndevice = device.Get_Nome_Attuatore().lower()
                
                
                device_slug = ndevice

                
                addA = device.Get_Address_A()
                addPL = device.Get_Address_PL()

                address = b'\x00'
                address = SCS.bitwise_and_bytes(bytes([addA]), b'\x0F')
                address = SCS.bitwise_shiftleft_bytes(address, b'\x04')
                address = SCS.bitwise_and_bytes(address, b'\xF0')
                address = SCS.bitwise_or_bytes(address, bytes([addPL]))
                
                BUS_address_attuatore = trama[2]

                if address == BUS_address_attuatore:
                    # SWITCH
                    if len(trama) == 7 and trama[1] == b'\xB8' and type.name == SCS.TYPE_INTERfACCIA.on_off.name:
                        statoDevice_in_Bus = int.from_bytes(trama[4], "big")
                        device.Set_Stato(statoDevice_in_Bus)
                        if statoDevice_in_Bus == 1:
                            # ✅ USA SLUG invece di ndevice
                            await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/status", "off")
                        else:
                            await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/status", "on")
                    
                    # DIMMER
                    elif len(trama) == 7 and trama[1] == b'\xB8' and type.name == SCS.TYPE_INTERfACCIA.dimmer.name:
                        statoDevice_in_Bus = int.from_bytes(trama[4], "big")
                        device.Set_Stato(statoDevice_in_Bus)
                        dimperc = device.Get_Dimmer_percent()
                        if statoDevice_in_Bus == 1:
                            await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/status", "off")
                        elif statoDevice_in_Bus == 0:
                            await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/status", "on")
                        else:
                            await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/status", "on")
                            await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/status/percentuale", dimperc)

                    # SERRANDE TAPPARELLE
                    elif len(trama) == 7 and trama[1] == b'\xB8' and type.name == SCS.TYPE_INTERfACCIA.serrande_tapparelle.name:
                        statoDevice_in_Bus = int.from_bytes(trama[4], "big")
                        device.Set_Stato(statoDevice_in_Bus)
                        
                        if trama[1] == b'\xB8' and trama[3] == b'\x12' and trama[4] == b'\x0A':
                            device.Ricalcolo_Percent_from_timerelaspe()
                            device.stop_timer()
                            
                            # ✅ AGGIUNGI pubblicazione posizione dopo STOP:
                            posizione = int(device.get_percentuale())
                            await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/status", str(posizione))
                            
                        elif trama[1] == b'\xB8' and trama[3] == b'\x12' and trama[4] == b'\x08':
                            device.RecTimer(1)
                            device.start_timer((device.timer_salita_/1000)+2)
                        elif trama[1] == b'\xB8' and trama[3] == b'\x12' and trama[4] == b'\x09':
                            device.RecTimer(-1)
                            device.start_timer((device.timer_discesa_/1000)+2)

                    # Sensori Temperature
                    elif len(trama) == 7 and trama[1] == b'\xB4' and type.name == SCS.TYPE_INTERfACCIA.sensori_temperatura.name:
                        rawtemp = int.from_bytes(trama[4], "big")
                        temp = rawtemp / 10
                        device.Set_Stato(temp)
                        await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/status", format(temp, '.1f'))

                    # Sensori Temperature > 25.5
                    elif len(trama) == 7 and trama[1] == b'\xB5' and type.name == SCS.TYPE_INTERfACCIA.sensori_temperatura.name:
                        rawtemp = int.from_bytes(trama[4], "big")
                        temp = rawtemp / 10 + 25.6
                        device.Set_Stato(temp)
                        await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/status", format(temp, '.1f'))

                    # Sensori Consumo F520 - trama estesa 11 byte
                    elif (
                        len(trama) == 11
                        and trama[1] == b'\xD2'
                        and trama[3] == b'\x02'
                        and trama[4] == b'\x34'
                        and trama[5] == b'\x00'
                        and trama[6] == b'\x1D'
                        and type.name == SCS.TYPE_INTERfACCIA.sensori_consumo.name
                    ):
                        potenza = (int.from_bytes(trama[7], "big") << 8) + int.from_bytes(trama[8], "big")
                        device.Set_Stato(potenza)
                        await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/status", str(potenza))
                        energy_accumulator.update_power(device_slug, potenza)
                        await scsmqtt.post_to_MQTT(
                            f"/scsshield/device/{device_slug}/energy",
                            format(energy_accumulator.get_energy_kwh(device_slug), '.6f')
                        )

                    # Campanello
                    elif len(trama) == 7 and trama[1] == b'\x91' and trama[3] == b'\x60' and trama[4] == b'\x08' and type.name == SCS.TYPE_INTERfACCIA.campanello_porta.name:
                        device.start_timer(2)

                    # Gruppi
                    elif len(trama) > 7 and trama[1] == b'\xEC' and type.name == SCS.TYPE_INTERfACCIA.gruppi.name:
                        pass

                    # TERMOSTATO - Temperatura setting
                    elif len(trama) > 7 and trama[1] == b'\xD2' and trama[3] == b'\x03' and trama[4] == b'\x04' and trama[5] == b'\xC0' and type.name == SCS.TYPE_INTERfACCIA.termostati.name:
                        rawtemp = int.from_bytes(trama[7], "big")
                        if rawtemp != 0:
                            temperature_di_Setting = ((rawtemp - 6) * 0.50) + 3
                            device.Set_Temperatura_Termostato(temperature_di_Setting)
                            await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/temperatura_termostato_impostata", temperature_di_Setting)

                    # TERMOSTATO - Temperatura e Modalità
                    elif len(trama) > 7 and trama[1] == b'\xD2' and trama[3] == b'\x03' and SCS.bitwise_and_bytes(trama[4], b'\x0F') == b'\x04' and trama[5] == b'\x12' and type.name == SCS.TYPE_INTERfACCIA.termostati.name:
                        msb = int.from_bytes(trama[7], "big")
                        lsb = int.from_bytes(trama[8], "big")
                        tempv = msb * 256 + lsb
                        temp = tempv / 10
                        device.Set_Temperatura_Termostato(temp)
                        await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/temperatura_termostato_impostata", temp)

                        bit1 = SCS.bitwise_and_bytes(trama[6], b'\x0F')
                        if bit1 in [b'\x02', b'\x00']:
                            device.Set_Modalita_Termostato(device.MODALITA.ESTATE)
                            await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/modalita_termostato_impostata", device.MODALITA.ESTATE.name)
                        elif bit1 in [b'\x03', b'\x01']:
                            device.Set_Modalita_Termostato(device.MODALITA.INVERNO)
                            await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/modalita_termostato_impostata", device.MODALITA.INVERNO.name)
                        elif trama[6] == b'\xFF':
                            device.Set_Modalita_Termostato(device.MODALITA.OFF)
                            await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/modalita_termostato_impostata", device.MODALITA.OFF.name)

                    # TERMOSTATO - Temperature di Setting
                    elif len(trama) > 7 and trama[1] == b'\xD2' and trama[3] == b'\x03' and trama[4] == b'\x04' and trama[5] == b'\x0E' and type.name == SCS.TYPE_INTERfACCIA.termostati.name:
                        rawtemp = int.from_bytes(trama[7], "big")
                        temp = rawtemp / 10
                        device.Set_Temperatura_Termostato(temp)
                        await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/temperatura_termostato_impostata", temp)

                # Gruppi (address diverso)
                elif len(trama) > 7 and address == trama[5] and trama[1] == b'\xEC' and type.name == SCS.TYPE_INTERfACCIA.gruppi.name:
                    statoDevice_in_Bus = int.from_bytes(trama[8], "big")
                    device.Set_Stato(statoDevice_in_Bus)
                    if statoDevice_in_Bus == 1:
                        await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/status", "off")
                    else:
                        await scsmqtt.post_to_MQTT(f"/scsshield/device/{device_slug}/status", "on")

            # Pubblica trama raw
            s = ""
            for _ in trama:
                h = '0x' + _.hex()
                s = s + h + ' '
            await scsmqtt.post_to_MQTT("/scsshield/ReceivefromBus", s)

            await asyncio.sleep(0)

        except Exception as e:
            logger.error("Error in deviceReceiver_from_SCSbus")
            logger.error(e)


async def start_tornado(jqueqe, jqueqeNodeRed):
    logger.info(f'{time.ctime()} WEB SERVER start')

    app = webapp.make_app()
    app.listen(80)

    webapp.rec_queque(jqueqe)
    webapp.rec_queque_NODERED(jqueqeNodeRed)
    
    #webapp.tornado.platform.asyncio.AsyncIOMainLoop().install()


async def TEST_PUB():
    while(True):
        await scsmqtt.post_to_MQTT("test", "onddddddddddddd")
        await scsmqtt.post_to_MQTT("test", "xxxxxxxxxxxx")
        await asyncio.sleep(5)






async def main():
    mjqueqe = janus.Queue()
    queqe_refresh_database = janus.Queue()

    queue_refreshdatabase = janus.Queue()
    queue_mqtt_action = janus.Queue()

    queue_node_red_action = janus.Queue()

    queue_UartRx = janus.Queue()
    shield.Rec_QuequeUartRx(queue_UartRx.async_q)

    queue_rx_trama_data_found = janus.Queue()



    tasks = []
    #Tornado START
    tasks.append(asyncio.create_task(start_tornado(queue_refreshdatabase.async_q, queue_node_red_action.async_q )))
    #Refresh Database
    tasks.append(loop.create_task( tsk_refresh_database(queue_refreshdatabase.async_q)           ))

    #Test	
    tasks.append(loop.create_task( shield.uart_rx(queue_rx_trama_data_found.async_q)           ))
    tasks.append(loop.create_task( deviceReceiver_from_SCSbus(queue_rx_trama_data_found.async_q)           ))

    tasks.append(asyncio.create_task( scsmqtt.main(queue_mqtt_action.async_q)        ))
    #tasks.append(loop.create_task( scsmqtt.main(queue_mqtt_action.async_q)        ))

    tasks.append(loop.create_task( mqtt_action(queue_mqtt_action.async_q)           ))
    tasks.append(loop.create_task( tsk_publish_energy_totals()                      ))
    tasks.append(loop.create_task( tsk_keepalive_sensori_consumo()                  ))

    #tasks.append(loop.create_task( Node_Red_flow(queue_node_red_action.async_q)           ))

    #tasks.append(loop.create_task( TEST_PUB()           ))


    await asyncio.gather(*tasks)  # ← AGGIUNGI 'await' qui!




# Rimuovi queste righe:
# os.popen("sudo systemctl stop mosquitto.service").read()
# os.popen("sudo rm /var/lib/mosquitto/mosquitto.db").read()
# os.popen("sudo systemctl start mosquitto.service").read()


popula_device()

# ✅ Pubblica discovery all'avvio
loop.create_task(publish_all_discovery())

loop.create_task(main())
loop.run_forever()
loop.close()

ser.close()
