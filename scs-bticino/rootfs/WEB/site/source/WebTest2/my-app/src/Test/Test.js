import { useState, useEffect } from 'react';
import Dispositivi from './Dispositivi';
import mqtt from "mqtt";
import "./../App.css";

const ADDRESS_SERVER = "/";

function Test() {
  const [lista_dispositivi, setListaDispositivi] = useState([]);
  const [mqttClient, setMqttClient] = useState(null);
  const [MQTT_data, setMQTT_data] = useState("");
  const [DebugSCSbus, setDebugSCSbus] = useState("");

  useEffect(() => {
    let _client = null;

    const loadDevices = async () => {
      const data = await fetch(ADDRESS_SERVER + "GetConfigurazionereact.json").then(r => r.json());
      setListaDispositivi(data);
    };

    const connectMqtt = async () => {
      // 1) prendi config dal backend
      const cfg = await fetch("/mqtt_config.json").then(r => r.json());
      const host = window.location.hostname;                 // es. homeassistant.local
      const proto = cfg.use_tls ? "wss" : "ws";
      const url = `${proto}://${host}:${cfg.ws_port}${cfg.path || ""}`;

      const options = { reconnectPeriod: 2000, clean: true };
      if (cfg.username) options.username = cfg.username;
      if (cfg.password) options.password = cfg.password;

      // 2) connetti
      _client = mqtt.connect(url, options);
      setMqttClient(_client);

      _client.on("connect", () => {
        console.log("MQTT connesso:", url);
        _client.subscribe("/scsshield/device/+/status");
        _client.subscribe("/scsshield/device/+/status/percentuale");
        _client.subscribe("/scsshield/device/+/modalita_termostato_impostata");
        _client.subscribe("/scsshield/device/+/temperatura_termostato_impostata");
        // _client.subscribe("/scsshield/debug/bus");
      });

      _client.on("error", (err) => {
        console.error("MQTT ERROR:", err?.message || err);
        try { _client.end(); } catch {}
      });

      _client.on("message", (topic, payload) => {
        const data = new TextDecoder("utf-8").decode(payload);
        if (topic === "/scsshield/debug/bus") {
          setDebugSCSbus(prev => [...prev, data + "\n"]);
          return;
        }
        const parts = topic.split("/");
        const nomeDevice = parts[3] || "";
        const mesg = data.toLowerCase();
        setMQTT_data({ nome_attuatore: nomeDevice, stato: mesg, topic });
      });
    };

    (async () => {
      await loadDevices();
      await connectMqtt();
    })();

    return () => {
      try {
        if (_client) {
          _client.unsubscribe("/scsshield/device/+/status");
          _client.unsubscribe("/scsshield/device/+/status/percentuale");
          _client.unsubscribe("/scsshield/device/+/modalita_termostato_impostata");
          _client.unsubscribe("/scsshield/device/+/temperatura_termostato_impostata");
          _client.end(true);
        }
      } catch {}
    };
  }, []);

  return (
    <>
      <div className="container-fluid">
        {lista_dispositivi.map((device, i) => (
          <div key={i} style={{ marginBottom: "50px" }}>
            {/* nome prop corretto: clientMQTT */}
            <Dispositivi device={device} mqttdata={MQTT_data} clientMQTT={mqttClient} />
          </div>
        ))}
      </div>
      {/* Debug opzionale
      <div className="DebugSCSbus" style={{ textAlign: "center" }}>
        <textarea style={{ width: "80%" }} value={DebugSCSbus} rows={12} cols={50} />
      </div>
      */}
    </>
  );
}

export default Test;
