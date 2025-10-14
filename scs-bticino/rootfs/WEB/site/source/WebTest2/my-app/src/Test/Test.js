import { useState, useEffect } from 'react';
import Dispositivi from './Dispositivi';
import mqtt from "mqtt";
import "./../App.css";

const ADDRESS_SERVER = "/";

function Test() {
  const [lista_dispositivi, setListaDispositivi] = useState([]);
  const [MqttClient, setMqttClient] = useState([]);
  const [MQTT_data, setMQTT_data] = useState("");
  const [DebugSCSbus, setDebugSCSbus] = useState("");

  useEffect(() => {
    let client = null;

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

      console.log("MQTT url..............:", url);
      console.log("options:", options);

      // 2) connetti
      client = mqtt.connect(url, options);
      setMqttClient(client);

      client.on("connect", () => {
        console.log("MQTT Connesso....ok!");        
        client.publish("ciao","ciaooooooooooooooooooo1");
        client.publish("ciao","ciaooooooooooooooooooo2");
        client.publish("ciao","ciaooooooooooooooooooo3");
        client.publish("ciao","ciaooooooooooooooooooo4");
        client.publish("ciao","ciaooooooooooooooooooo5");

        console.log("✅ MQTT connesso:", url);


        client.subscribe("/scsshield/device/+/status");
        client.subscribe("/scsshield/device/+/status/percentuale");
        client.subscribe("/scsshield/device/+/modalita_termostato_impostata");
        client.subscribe("/scsshield/device/+/temperatura_termostato_impostata");
          // _client.subscribe("/scsshield/debug/bus");
      });

      client.on("error", (err) => {
        console.error("MQTT ERROR:", err?.message || err);
        try { client.end(); } catch {}
      });

      client.on("message", (topic, payload, packet) => {
        const data = new TextDecoder("utf-8").decode(payload);
        if (topic.localeCompare("/scsshield/debug/bus") == 0) {
            setDebugSCSbus(DebugSCSbus => [...DebugSCSbus, data + '\n']);
        } else {
            var m = (topic).split("/");
            var nomeDevice = m[3];
            var mesg = (data)   //.toLowerCase();
            const dd = { "nome_attuatore": nomeDevice, "stato": mesg, "topic": topic };
            setMQTT_data(dd);
            console.log(dd.nome_attuatore);
            console.log(dd.stato);
        }
      });
    };

    (async () => {
      await loadDevices();
      await connectMqtt();
    })();


    return () => {
        console.log("CLOSEEE");
        setListaDispositivi([]);

        client.unsubscribe("/scsshield/device/+/status");
        client.unsubscribe("/scsshield/device/+/status/percentuale");
        client.unsubscribe("/scsshield/device/+/modalita_termostato_impostata");
        client.unsubscribe("/scsshield/device/+/temperatura_termostato_impostata");
        client.end();
        //MqttClient.close();
        // cleaning up the listeners here
    }
  }, []);

 return (
        <>
            <div className="container-fluid">
                {lista_dispositivi.map((device, i) => (
                    <div key={i} style={{marginBottom:"50px"}} >
                        <Dispositivi device={device} mqttdata={MQTT_data} clientMWTT={MqttClient} />
                    </div>
                ))}
            </div>
            {
            /*<div className="DebugSCSbus" style={{ textAlign: "center" }}>
                <textarea style={{ width: "80%" }} value={DebugSCSbus} rows={12} cols={50} name="Debug Bus" placeholder='' />
            </div>
            */
            }
        </>
    );




}

export default Test;
