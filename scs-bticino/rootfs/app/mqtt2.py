import asyncio
import os
import signal
import time
import json
from gmqtt import Client as MQTTClient
from datetime import datetime

# gmqtt compatibility with uvloop  
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class SCSMQTT2(object):
    def __init__(self, stop):
        self.STOP = stop
        # Leggi configurazione da variabili d'ambiente
        self.mqtt_host = os.getenv('MQTT_HOST', 'localhost')
        self.mqtt_port = int(os.getenv('MQTT_PORT', 1883))
        self.mqtt_user = os.getenv('MQTT_USER', '')
        self.mqtt_password = os.getenv('MQTT_PASSWORD', '')

    def on_connect(self, client, flags, rc, properties):
        print('MQTT connected')
        self.client.subscribe('/scsshield/#', qos=0)

    async def on_message(self, client, topic, payload, qos, properties):
        message = dict()
        message["topic"] = topic
        message["payload"] = payload
        await self.queue.put(message)

    def on_disconnect(self, client, packet, exc=None):
        print('MQTT Disconnected')

    def on_subscribe(self, client, mid, qos, properties):
        print('MQTT Subscribed')

    def ask_exit(*args):
        pass

    def post_to_topicsync(self, topic, message):
        try:
            if self.client.is_connected:
                self.client.publish(topic, message, qos=1)
        except Exception as e:
            print("MQTT ERROR - PUBLISH:", e)

    async def post_to_MQTT(self, topic, message):
        try:
            if self.client.is_connected:
                self.client.publish(topic, message, qos=1, retain=True)            
        except Exception as e:
            print("MQTT ERROR - post_to_MQTT:", e)

    async def post_to_MQTT_retain_reset(self, topic):
        try:
            if self.client.is_connected:
                self.client.publish(topic, None, qos=1, retain=True)
        except Exception as e:
            print("MQTT ERROR - post_to_MQTT_retain_reset:", e)

    async def publish_discovery(self, device_name, device_type, device_config):
        """Pubblica configurazione device per Home Assistant MQTT Discovery"""
        if device_type == "switch":
            discovery_topic = f"homeassistant/switch/scs_{device_name}/config"
            config = {
                "name": device_name,
                "command_topic": f"/scsshield/device/{device_name}/switch",
                "state_topic": f"/scsshield/device/{device_name}/status",
                "unique_id": f"scs_{device_name}",
                "device": {
                    "identifiers": [f"scs_bticino_{device_name}"],
                    "name": device_name,
                    "model": "SCS BTicino",
                    "manufacturer": "BTicino"
                }
            }
        elif device_type == "cover":
            discovery_topic = f"homeassistant/cover/scs_{device_name}/config"
            config = {
                "name": device_name,
                "command_topic": f"/scsshield/device/{device_name}/percentuale",
                "position_topic": f"/scsshield/device/{device_name}/status",
                "set_position_topic": f"/scsshield/device/{device_name}/percentuale",
                "unique_id": f"scs_{device_name}",
                "device": {
                    "identifiers": [f"scs_bticino_{device_name}"],
                    "name": device_name,
                    "model": "SCS BTicino Shutter",
                    "manufacturer": "BTicino"
                }
            }

        await self.client.publish(discovery_topic, json.dumps(config), qos=1, retain=True)

    async def main(self, queue):
        self.queue = queue
        try:
            self.client = MQTTClient("scs-bticino-bridge")
            
            # Imposta autenticazione PRIMA di connettersi
            if self.mqtt_user and self.mqtt_password:
                print(f"MQTT: Using authentication for user '{self.mqtt_user}'")
                self.client.set_auth_credentials(self.mqtt_user, self.mqtt_password)
            else:
                print("MQTT: Connecting without authentication")
            
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            self.client.on_disconnect = self.on_disconnect
            self.client.on_subscribe = self.on_subscribe

            await self.client.connect(self.mqtt_host, port=self.mqtt_port, keepalive=65535)
            await self.STOP.wait()
            await self.client.disconnect()

        except Exception as e:
            print("MQTT ERROR:", e)