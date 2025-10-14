import { useState, useEffect } from 'react';
import Dispositivi from './Dispositivi';
import mqtt from "mqtt";
import "./../App.css";

const ADDRESS_SERVER = "/";

function Test() {
  const [lista_dispositivi, setListaDispositivi] = useState([]);
  const [MqttClient, setMqttClient] = useState(null);
  const [MQTT_data, setMQTT_data] = useState("");
  const [DebugSCSbus, setDebugSCSbus] = useState("");

  useEffect(() => {
    let client = null;

    const loadDevices = async () => {
      const data = await fetch(ADDRESS_SERVER + "GetConfigurazionereact.json").then(r => r.json());
      console.log("✅ Dispositivi caricati:", data);
      setListaDispositivi(data);
      return data; // ✅ Ritorna i dati
    };

    const connectMqtt = async (devices) => {
      // 1) prendi config dal backend
      const cfg = await fetch("/mqtt_config.json").then(r => r.json());
      const host = window.location.hostname;
      const proto = cfg.use_tls ? "wss" : "ws";
      const url = `${proto}://${host}:${cfg.ws_port}${cfg.path || ""}`;

      const options = { reconnectPeriod: 2000, clean: true };
      if (cfg.username) options.username = cfg.username;
      if (cfg.password) options.password = cfg.password;

      console.log("MQTT url:", url);
      console.log("MQTT options:", options);

      // 2) connetti
      client = mqtt.connect(url, options);
      setMqttClient(client);

      client.on("connect", () => {
        console.log("✅ MQTT connesso:", url);

        // ✅ Subscribe ai topic
        client.subscribe("/scsshield/device/+/status", (err) => {
          if (err) console.error("Errore subscribe status:", err);
          else console.log("✅ Subscribed to /scsshield/device/+/status");
        });
        
        client.subscribe("/scsshield/device/+/status/percentuale", (err) => {
          if (err) console.error("Errore subscribe percentuale:", err);
          else console.log("✅ Subscribed to /scsshield/device/+/status/percentuale");
        });
        
        client.subscribe("/scsshield/device/+/modalita_termostato_impostata", (err) => {
          if (err) console.error("Errore subscribe modalita:", err);
          else console.log("✅ Subscribed to /scsshield/device/+/modalita_termostato_impostata");
        });
        
        client.subscribe("/scsshield/device/+/temperatura_termostato_impostata", (err) => {
          if (err) console.error("Errore subscribe temperatura:", err);
          else console.log("✅ Subscribed to /scsshield/device/+/temperatura_termostato_impostata");
        });
      });

      client.on("error", (err) => {
        console.error("❌ MQTT ERROR:", err?.message || err);
        try { client.end(); } catch {}
      });

      // ✅ Handler messaggi - usa 'devices' passato come parametro
      client.on("message", (topic, payload, packet) => {
        console.log("📨 MQTT message received:", topic);
        
        const data = new TextDecoder("utf-8").decode(payload);
        
        if (topic === "/scsshield/debug/bus") {
          setDebugSCSbus(prev => [...prev, data + '\n']);
        } else {
          const parts = topic.split("/");
          
          // ✅ Verifica struttura topic
          if (parts.length < 4) {
            console.warn("⚠️ Topic malformato:", topic);
            return;
          }
          
          const deviceNameFromTopic = parts[3].toLowerCase(); // ✅ Lowercase
          const mesg = data;
          
          console.log("  Device dal topic:", deviceNameFromTopic);
          console.log("  Messaggio:", mesg);
          
          // ✅ Trova dispositivo corrispondente
          const matchingDevice = devices.find(dev => 
            dev.nome_attuatore.toLowerCase() === deviceNameFromTopic
          );
          
          if (matchingDevice) {
            const dd = { 
              "nome_attuatore": matchingDevice.nome_attuatore,
              "stato": mesg, 
              "topic": topic 
            };
            setMQTT_data(dd);
            console.log("✅ Match trovato:", dd.nome_attuatore, "stato:", dd.stato);
          } else {
            console.warn("⚠️ Nessun dispositivo trovato per:", deviceNameFromTopic);
            console.log("  Dispositivi disponibili:", devices.map(d => d.nome_attuatore.toLowerCase()));
          }
        }
      });
    };

    // ✅ Carica dispositivi PRIMA, poi connetti MQTT passando i dispositivi
    (async () => {
      const devices = await loadDevices();
      await connectMqtt(devices);
    })();

    // Cleanup
    return () => {
      console.log("🔌 Chiusura connessioni MQTT...");
      
      if (client) {
        try {
          client.unsubscribe("/scsshield/device/+/status");
          client.unsubscribe("/scsshield/device/+/status/percentuale");
          client.unsubscribe("/scsshield/device/+/modalita_termostato_impostata");
          client.unsubscribe("/scsshield/device/+/temperatura_termostato_impostata");
          client.end();
        } catch (e) {
          console.error("Errore chiusura MQTT:", e);
        }
      }
    };
  }, []); // ✅ Dipendenze vuote = esegue solo al mount

  return (
    <>
      <div className="container-fluid">
        {lista_dispositivi.map((device, i) => (
          <div key={i} style={{marginBottom:"50px"}}>
            <Dispositivi device={device} mqttdata={MQTT_data} clientMWTT={MqttClient} />
          </div>
        ))}
      </div>
      {/* Debug console (commentato) */}
    </>
  );
}

export default Test;