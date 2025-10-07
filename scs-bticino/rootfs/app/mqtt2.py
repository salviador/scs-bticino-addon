import asyncio
import os
import logging
from gmqtt import Client as MQTTClient
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
logger = logging.getLogger(__name__)

class SCSMQTT2(object):
    def __init__(self, stop):
        self.STOP = stop
        self.mqtt_host = os.getenv('MQTT_HOST', 'localhost')
        self.mqtt_port = int(os.getenv('MQTT_PORT', 1883))
        self.mqtt_user = os.getenv('MQTT_USER', '')
        self.mqtt_password = os.getenv('MQTT_PASSWORD', '')
        self.reconnect_interval = 5  # secondi
        self.is_connected = False

    def on_connect(self, client, flags, rc, properties):
        logger.info(f'✓ MQTT connected to {self.mqtt_host}:{self.mqtt_port}')
        self.is_connected = True
        self.client.subscribe('/scsshield/#', qos=0)

    async def on_message(self, client, topic, payload, qos, properties):
        message = dict()
        message["topic"] = topic
        message["payload"] = payload
        await self.queue.put(message)

    def on_disconnect(self, client, packet, exc=None):
        logger.warning(f'✗ MQTT Disconnected: {exc}')
        self.is_connected = False

    def on_subscribe(self, client, mid, qos, properties):
        logger.info('✓ MQTT Subscribed to /scsshield/#')

    async def post_to_MQTT(self, topic, message):
        """Pubblica su MQTT con retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.client and self.client.is_connected:
                    self.client.publish(topic, message, qos=1, retain=True)
                    return True
                else:
                    logger.warning(f"MQTT not connected, attempt {attempt+1}/{max_retries}")
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"MQTT publish error (attempt {attempt+1}/{max_retries}): {e}")
                await asyncio.sleep(1)
        
        logger.error(f"Failed to publish to {topic} after {max_retries} attempts")
        return False

    async def post_to_MQTT_retain_reset(self, topic):
        """Rimuovi messaggio retained"""
        try:
            if self.client and self.client.is_connected:
                self.client.publish(topic, None, qos=1, retain=True)
        except Exception as e:
            logger.error(f"MQTT retain reset error: {e}")

    async def main(self, queue):
        self.queue = queue
        
        while not self.STOP.is_set():
            try:
                logger.info(f"Connecting to MQTT broker {self.mqtt_host}:{self.mqtt_port}...")
                self.client = MQTTClient("scs-bticino-bridge")
                
                if self.mqtt_user and self.mqtt_password:
                    logger.info(f"Using MQTT authentication for user '{self.mqtt_user}'")
                    self.client.set_auth_credentials(self.mqtt_user, self.mqtt_password)
                
                self.client.on_connect = self.on_connect
                self.client.on_message = self.on_message
                self.client.on_disconnect = self.on_disconnect
                self.client.on_subscribe = self.on_subscribe

                await self.client.connect(self.mqtt_host, port=self.mqtt_port, keepalive=60)
                
                # Loop finché connesso o fino a STOP
                while not self.STOP.is_set() and self.is_connected:
                    await asyncio.sleep(1)
                
                await self.client.disconnect()
                
            except Exception as e:
                logger.error(f"MQTT connection error: {e}")
                await asyncio.sleep(self.reconnect_interval)
                logger.info(f"Retrying MQTT connection in {self.reconnect_interval}s...")
        
        logger.info("MQTT client stopped")