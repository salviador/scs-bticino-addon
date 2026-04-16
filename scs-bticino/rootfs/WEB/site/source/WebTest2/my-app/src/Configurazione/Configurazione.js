import { useState, useEffect } from 'react';
import { Container, Navbar, Nav, Button, Card, Row, Col, Modal } from 'react-bootstrap';
import ConfigurazioneDispositivi from "./ConfigurazioneDispositivi"
import AggiungiAttuatore from "./AggiungiAttuatore"

import "./../App.css";


//const ADDRESS_SERVER = "http://192.168.1.16/";
const ADDRESS_SERVER = "/";


function Configurazioni() {
    const [lista_dispositivi, setListaDispositivi] = useState([]);

    //pop up error
    const [show, setShow] = useState(false);
    const handleClose = () => setShow(false);
    const handleShow = () => setShow(true);
    const [messaggio_da_visualizzare, setmessaggio_da_visualizzare] = useState('');

    const normalizeNomeAttuatore = (nome_attuatore) => {
        if (typeof nome_attuatore !== 'string') {
            return '';
        }
        return nome_attuatore.trim().toLowerCase();
    }

    const findAttuatore = (nome_attuatore) => {
        const nomeNormalizzato = normalizeNomeAttuatore(nome_attuatore);
        return lista_dispositivi.find(
            device => normalizeNomeAttuatore(device.nome_attuatore) === nomeNormalizzato
        );
    }

    const updateAttuatoreLocale = (nome_attuatore, updater) => {
        const nomeNormalizzato = normalizeNomeAttuatore(nome_attuatore);
        setListaDispositivi(lista_corrente =>
            lista_corrente.map(device => {
                if (normalizeNomeAttuatore(device.nome_attuatore) !== nomeNormalizzato) {
                    return device;
                }

                const updatedDevice = { ...device };
                updater(updatedDevice);
                return updatedDevice;
            })
        );
    }


    useEffect(() => {
        setListaDispositivi([]);
        const fetchData = async () => {
            await fetch(ADDRESS_SERVER + 'GetConfigurazionereact.json')
                .then(res => res.json())
                .then((data) => {
                    setListaDispositivi(data);
                });
        };
        fetchData();
    }, []);

    //POST ---->OK<----
    const post_request_update_database = (address, datas) => {
        var data = JSON.stringify(datas);
        const requestOptions = {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: data
        };
        fetch(ADDRESS_SERVER + address, requestOptions)
            .then(response => response.json())
            .then(data => {
                console.log("OKKKKKKKKKKKKKKKKK");
                console.log(data);
            }
            );
    }

    //AGGIORNA NEL DATABASE IL NOME ATTUATORE e nel HOOK ---->OK<----
    const handle_CHANHE_NOME = (value) => {
        //value.nome_attuatore
        //value.nuovonome

        const nomeAttuatore = normalizeNomeAttuatore(value.nome_attuatore);
        const nuovoNome = normalizeNomeAttuatore(value.nuovonome);
        if (nuovoNome === '') {
            setmessaggio_da_visualizzare("Il nome del nuovo Attuatore non puÃ² essere vuoto");
            handleShow();
            return;
        }

        var attuatoreEsistente = findAttuatore(nuovoNome);
        if (typeof attuatoreEsistente !== "undefined" &&
            normalizeNomeAttuatore(attuatoreEsistente.nome_attuatore) !== nomeAttuatore) {
            setmessaggio_da_visualizzare("Esiste giÃ  il nome dell'attuatore nel database");
            handleShow();
            return;
        }

        var datas = { 'nome_attuatore': nomeAttuatore, 'nuovo_nome': nuovoNome };
        post_request_update_database('AGGIORNA_NOME_ATTUATORE.json', datas);

        updateAttuatoreLocale(nomeAttuatore, attuatore => {
            attuatore.nome_attuatore = nuovoNome;
        });
    }

    //AGGIORNA NEL DATABASE L'INDIRIZZO AMBIENTE e nel HOOK
    const handle_CHANHE_A = (value) => {
        const nomeAttuatore = normalizeNomeAttuatore(value.nome_attuatore);
        var datas = { 'nome_attuatore': nomeAttuatore, 'indirizzo_Ambiente': value.indirizzo_Ambiente };
        post_request_update_database('AGGIORNA_INDIRIZZO_A.json', datas);

        updateAttuatoreLocale(nomeAttuatore, attuatore => {
            attuatore.indirizzo_Ambiente = value.indirizzo_Ambiente;
        });
    }
    //AGGIORNA NEL DATABASE L'INDIRIZZO PL e nel HOOK
    const handle_CHANHE_PL = (value) => {
        const nomeAttuatore = normalizeNomeAttuatore(value.nome_attuatore);
        var datas = { 'nome_attuatore': nomeAttuatore, 'indirizzo_PL': value.indirizzo_PL };
        post_request_update_database('AGGIORNA_INDIRIZZO_PL.json', datas);

        updateAttuatoreLocale(nomeAttuatore, attuatore => {
            attuatore.indirizzo_PL = value.indirizzo_PL;
        });
    }
    //AGGIORNA NEL DATABASE IL TIPO ATTUATORE e nel HOOK
    const handle_TIPO = (value) => {
        const nomeAttuatore = normalizeNomeAttuatore(value.nome_attuatore);
        var datas = { 'nome_attuatore': nomeAttuatore, 'tipo_attuatore': value.tipo_attuatore };
        post_request_update_database('AGGIORNA_TIPO_ATTUATORE.json', datas);

        updateAttuatoreLocale(nomeAttuatore, attuatore => {
            attuatore.tipo_attuatore = value.tipo_attuatore;
        });
    }
    //AGGIORNA NEL DATABASE TIMER SALITA e nel HOOK
    const handle_TIMER_UP = (value) => {
        const nomeAttuatore = normalizeNomeAttuatore(value.nome_attuatore);
        var datas = { 'nome_attuatore': nomeAttuatore, 'timer_salita': value.timer_salita };
        post_request_update_database('AGGIORNA_TIMER_SERRANDETAPPARELLE.json', datas);

        updateAttuatoreLocale(nomeAttuatore, attuatore => {
            attuatore.timer_salita = value.timer_salita;
        });
    }
    //AGGIORNA NEL DATABASE TIMER DISCESA e nel HOOK
    const handle_TIMER_DOWN = (value) => {
        const nomeAttuatore = normalizeNomeAttuatore(value.nome_attuatore);
        var datas = { 'nome_attuatore': nomeAttuatore, 'timer_discesa': value.timer_discesa };
        post_request_update_database('AGGIORNA_TIMER_SERRANDETAPPARELLE.json', datas);

        updateAttuatoreLocale(nomeAttuatore, attuatore => {
            attuatore.timer_discesa = value.timer_discesa;
        });
    }
    //AGGIORNA NEL DATABASE ***ELIMINA*** e nel HOOK
    const handle_ELIMINA = (value) => {
        const nomeAttuatore = normalizeNomeAttuatore(value.nome_attuatore);
        var datas = { 'nome_attuatore': nomeAttuatore };
        post_request_update_database('RIMUOVI_ATTUATORE.json', datas);

        //Aggiorna Lista nel Array HOOK
        var myArray = lista_dispositivi.filter(function (device) {
            return normalizeNomeAttuatore(device.nome_attuatore) !== nomeAttuatore;
        });
        setListaDispositivi(myArray);
    }

    //-----------------------------------------------
    //AGGIUNGI NUOVO ATTUATORE  
    const handel_AGIUNGInew = (value) => {
        const nomeAttuatore = normalizeNomeAttuatore(value.nome_attuatore);
        if (nomeAttuatore === '') {
            setmessaggio_da_visualizzare("Il nome del nuovo Attuatore non può essere vuoto");
            handleShow();
            //Pop up
        } else {
            const nuovoAttuatore = { ...value, nome_attuatore: nomeAttuatore };
            //Controlla se esiste in "lista_dispositivi"
            var attuatore = findAttuatore(nomeAttuatore);
            if (typeof attuatore === "undefined") {
                //Ok inserisci nel database!!!

                post_request_update_database('AGGIUNGI_ATTUATORE.json', nuovoAttuatore);

                //Aggiungi in lista_dispositivi
                setListaDispositivi(lista_dispositivi => [...lista_dispositivi, nuovoAttuatore]);
            } else {
                //ERROE c'è già --> "POPUP"
                setmessaggio_da_visualizzare("Esiste già il nome dell'attuatore nel database");
                handleShow();
            }
        }
    }






    return (
        <>
            <div className="container-fluid">
                {lista_dispositivi.map((device, i) => (
                    <div key={device.nome_attuatore} >
                        <ConfigurazioneDispositivi device={device} handle_CHANHE_NOME={handle_CHANHE_NOME}
                            handle_CHANHE_A={handle_CHANHE_A} handle_CHANHE_PL={handle_CHANHE_PL}
                            handle_TIPO={handle_TIPO} handle_TIMER_UP={handle_TIMER_UP} handle_TIMER_DOWN={handle_TIMER_DOWN}
                            handle_ELIMINA={handle_ELIMINA} />
                    </div>
                ))}

                <AggiungiAttuatore handel_AGIUNGInew={handel_AGIUNGInew} />

                <Modal
                    show={show}
                    onHide={handleClose}
                    backdrop="static"
                    keyboard={false}
                >
                    <Modal.Header closeButton>
                        <Modal.Title>Errore</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        {messaggio_da_visualizzare}
                  </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={handleClose}>
                            Ok
                     </Button>
                    </Modal.Footer>
                </Modal>
            </div>

        </>
    );
}



export default Configurazioni;
