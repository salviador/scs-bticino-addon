import React, { useState, useEffect } from 'react';
import { Container, Card, Button, Form, Row, Col, Alert, Table, Badge, Modal } from 'react-bootstrap';
import DatabaseManager from './DatabaseManager';
import '../App.css';

const ADDRESS_SERVER = "/";

function Configurazione() {
    const [listaDispositivi, setListaDispositivi] = useState([]);
    const [showModal, setShowModal] = useState(false);
    const [modalMode, setModalMode] = useState('add'); // 'add' or 'edit'
    const [currentDevice, setCurrentDevice] = useState(null);
    const [message, setMessage] = useState(null);
    const [messageType, setMessageType] = useState('info');

    // Form state
    const [formData, setFormData] = useState({
        nome_attuatore: '',
        tipo_attuatore: 'on_off',
        indirizzo_Ambiente: '',
        indirizzo_PL: '',
        timer_salita: '',
        timer_discesa: ''
    });

    // Carica dispositivi all'avvio
    useEffect(() => {
        loadDevices();
    }, []);

    const loadDevices = async () => {
        try {
            const response = await fetch(ADDRESS_SERVER + "GetConfigurazionereact.json");
            const data = await response.json();
            setListaDispositivi(data);
        } catch (error) {
            console.error("Errore caricamento dispositivi:", error);
            showMessage("❌ Errore caricamento dispositivi", "danger");
        }
    };

    const showMessage = (text, type = 'info') => {
        setMessage(text);
        setMessageType(type);
        setTimeout(() => setMessage(null), 5000);
    };

    const handleOpenModal = (mode, device = null) => {
        setModalMode(mode);
        
        if (mode === 'edit' && device) {
            setCurrentDevice(device);
            setFormData({
                nome_attuatore: device.nome_attuatore,
                tipo_attuatore: device.tipo_attuatore,
                indirizzo_Ambiente: device.indirizzo_Ambiente,
                indirizzo_PL: device.indirizzo_PL,
                timer_salita: device.timer_salita || '',
                timer_discesa: device.timer_discesa || ''
            });
        } else {
            setCurrentDevice(null);
            setFormData({
                nome_attuatore: '',
                tipo_attuatore: 'on_off',
                indirizzo_Ambiente: '',
                indirizzo_PL: '',
                timer_salita: '',
                timer_discesa: ''
            });
        }
        
        setShowModal(true);
    };

    const handleCloseModal = () => {
        setShowModal(false);
        setCurrentDevice(null);
    };

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: value
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        // Validazione
        if (!formData.nome_attuatore || !formData.tipo_attuatore) {
            showMessage("❌ Nome e tipo dispositivo sono obbligatori", "danger");
            return;
        }

        try {
            const url = modalMode === 'add' 
                ? ADDRESS_SERVER + "AGGIUNGI_ATTUATORE.json"
                : ADDRESS_SERVER + "AGGIORNA_TIPO_ATTUATORE.json";

            const payload = {
                nome_attuatore: formData.nome_attuatore.toLowerCase(),
                tipo_attuatore: formData.tipo_attuatore,
                indirizzo_Ambiente: parseInt(formData.indirizzo_Ambiente) || 0,
                indirizzo_PL: parseInt(formData.indirizzo_PL) || 0
            };

            // Aggiungi timer se tipo serranda/tapparella
            if (formData.tipo_attuatore === 'serrande_tapparelle') {
                payload.timer_salita = parseInt(formData.timer_salita) || 0;
                payload.timer_discesa = parseInt(formData.timer_discesa) || 0;
            }

            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                showMessage(
                    modalMode === 'add' 
                        ? "✅ Dispositivo aggiunto con successo!" 
                        : "✅ Dispositivo modificato con successo!",
                    "success"
                );
                handleCloseModal();
                setTimeout(() => loadDevices(), 500);
            } else {
                showMessage("❌ Errore nel salvare il dispositivo", "danger");
            }
        } catch (error) {
            console.error("Errore:", error);
            showMessage("❌ Errore di connessione", "danger");
        }
    };

    const handleDelete = async (device) => {
        if (!window.confirm(`Sei sicuro di voler eliminare "${device.nome_attuatore}"?`)) {
            return;
        }

        try {
            const response = await fetch(ADDRESS_SERVER + "RIMUOVI_ATTUATORE.json", {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nome_attuatore: device.nome_attuatore })
            });

            if (response.ok) {
                showMessage("✅ Dispositivo eliminato con successo!", "success");
                setTimeout(() => loadDevices(), 500);
            } else {
                showMessage("❌ Errore nell'eliminare il dispositivo", "danger");
            }
        } catch (error) {
            console.error("Errore:", error);
            showMessage("❌ Errore di connessione", "danger");
        }
    };

    const getDeviceIcon = (tipo) => {
        const icons = {
            'on_off': '💡',
            'dimmer': '🔆',
            'serrande_tapparelle': '🪟',
            'sensori_temperatura': '🌡️',
            'termostati': '🎚️',
            'serrature': '🔒',
            'campanello_porta': '🔔',
            'gruppi': '📦'
        };
        return icons[tipo] || '❓';
    };

    const getDeviceLabel = (tipo) => {
        const labels = {
            'on_off': 'On/Off',
            'dimmer': 'Dimmer',
            'serrande_tapparelle': 'Serranda/Tapparella',
            'sensori_temperatura': 'Sensore Temperatura',
            'termostati': 'Termostato',
            'serrature': 'Serratura',
            'campanello_porta': 'Campanello',
            'gruppi': 'Gruppo'
        };
        return labels[tipo] || tipo;
    };

    return (
        <Container>
            <div className="pricing-header px-3 py-3 pt-md-5 pb-md-4 mx-auto text-center">
                <h1 className="display-4">Configurazione Dispositivi</h1>
                <p className="lead">Gestisci i dispositivi del bus SCS BTicino</p>
            </div>

            {message && (
                <Alert variant={messageType} onClose={() => setMessage(null)} dismissible>
                    {message}
                </Alert>
            )}

            {/* ✅ DATABASE MANAGER */}
            <DatabaseManager />

            {/* GESTIONE DISPOSITIVI */}
            <Card className="mb-4 shadow-sm">
                <Card.Header className="d-flex justify-content-between align-items-center">
                    <h4 className="my-0 font-weight-normal">🔌 Dispositivi Configurati</h4>
                    <Button variant="primary" onClick={() => handleOpenModal('add')}>
                        ➕ Aggiungi Dispositivo
                    </Button>
                </Card.Header>
                <Card.Body>
                    {listaDispositivi.length === 0 ? (
                        <Alert variant="info">
                            Nessun dispositivo configurato. Clicca su "Aggiungi Dispositivo" per iniziare.
                        </Alert>
                    ) : (
                        <Table responsive hover>
                            <thead>
                                <tr>
                                    <th>Tipo</th>
                                    <th>Nome</th>
                                    <th>Indirizzo A</th>
                                    <th>Indirizzo PL</th>
                                    <th>Azioni</th>
                                </tr>
                            </thead>
                            <tbody>
                                {listaDispositivi.map((device, index) => (
                                    <tr key={index}>
                                        <td>
                                            <span style={{ fontSize: '1.5rem', marginRight: '0.5rem' }}>
                                                {getDeviceIcon(device.tipo_attuatore)}
                                            </span>
                                            <Badge bg="secondary">
                                                {getDeviceLabel(device.tipo_attuatore)}
                                            </Badge>
                                        </td>
                                        <td><strong>{device.nome_attuatore}</strong></td>
                                        <td>{device.indirizzo_Ambiente}</td>
                                        <td>{device.indirizzo_PL}</td>
                                        <td>
                                            <Button
                                                variant="outline-primary"
                                                size="sm"
                                                className="me-2"
                                                onClick={() => handleOpenModal('edit', device)}
                                            >
                                                ✏️ Modifica
                                            </Button>
                                            <Button
                                                variant="outline-danger"
                                                size="sm"
                                                onClick={() => handleDelete(device)}
                                            >
                                                🗑️ Elimina
                                            </Button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                    )}
                </Card.Body>
            </Card>

            {/* MODAL AGGIUNGI/MODIFICA */}
            <Modal show={showModal} onHide={handleCloseModal} size="lg">
                <Modal.Header closeButton>
                    <Modal.Title>
                        {modalMode === 'add' ? '➕ Aggiungi Dispositivo' : '✏️ Modifica Dispositivo'}
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Form onSubmit={handleSubmit}>
                        <Row>
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Nome Dispositivo *</Form.Label>
                                    <Form.Control
                                        type="text"
                                        name="nome_attuatore"
                                        value={formData.nome_attuatore}
                                        onChange={handleInputChange}
                                        placeholder="es: luce camera"
                                        required
                                        disabled={modalMode === 'edit'}
                                    />
                                    <Form.Text className="text-muted">
                                        Il nome verrà convertito automaticamente in minuscolo
                                    </Form.Text>
                                </Form.Group>
                            </Col>

                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Tipo Dispositivo *</Form.Label>
                                    <Form.Select
                                        name="tipo_attuatore"
                                        value={formData.tipo_attuatore}
                                        onChange={handleInputChange}
                                        required
                                    >
                                        <option value="on_off">💡 On/Off</option>
                                        <option value="dimmer">🔆 Dimmer</option>
                                        <option value="serrande_tapparelle">🪟 Serranda/Tapparella</option>
                                        <option value="sensori_temperatura">🌡️ Sensore Temperatura</option>
                                        <option value="termostati">🎚️ Termostato</option>
                                        <option value="serrature">🔒 Serratura</option>
                                        <option value="campanello_porta">🔔 Campanello</option>
                                        <option value="gruppi">📦 Gruppo</option>
                                    </Form.Select>
                                </Form.Group>
                            </Col>
                        </Row>

                        <Row>
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Indirizzo Ambiente (A)</Form.Label>
                                    <Form.Control
                                        type="number"
                                        name="indirizzo_Ambiente"
                                        value={formData.indirizzo_Ambiente}
                                        onChange={handleInputChange}
                                        placeholder="0-15"
                                        min="0"
                                        max="15"
                                    />
                                </Form.Group>
                            </Col>

                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Indirizzo Punto Luce (PL)</Form.Label>
                                    <Form.Control
                                        type="number"
                                        name="indirizzo_PL"
                                        value={formData.indirizzo_PL}
                                        onChange={handleInputChange}
                                        placeholder="0-15"
                                        min="0"
                                        max="15"
                                    />
                                </Form.Group>
                            </Col>
                        </Row>

                        {/* Timer per serrande/tapparelle */}
                        {formData.tipo_attuatore === 'serrande_tapparelle' && (
                            <Row>
                                <Col md={6}>
                                    <Form.Group className="mb-3">
                                        <Form.Label>Timer Salita (ms)</Form.Label>
                                        <Form.Control
                                            type="number"
                                            name="timer_salita"
                                            value={formData.timer_salita}
                                            onChange={handleInputChange}
                                            placeholder="es: 20000"
                                        />
                                    </Form.Group>
                                </Col>

                                <Col md={6}>
                                    <Form.Group className="mb-3">
                                        <Form.Label>Timer Discesa (ms)</Form.Label>
                                        <Form.Control
                                            type="number"
                                            name="timer_discesa"
                                            value={formData.timer_discesa}
                                            onChange={handleInputChange}
                                            placeholder="es: 20000"
                                        />
                                    </Form.Group>
                                </Col>
                            </Row>
                        )}

                        <Alert variant="info" className="mb-0">
                            <small>
                                <strong>ℹ️ Nota:</strong> Gli indirizzi devono corrispondere a quelli 
                                configurati fisicamente sul bus SCS.
                            </small>
                        </Alert>
                    </Form>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={handleCloseModal}>
                        Annulla
                    </Button>
                    <Button variant="primary" onClick={handleSubmit}>
                        {modalMode === 'add' ? '➕ Aggiungi' : '💾 Salva Modifiche'}
                    </Button>
                </Modal.Footer>
            </Modal>
        </Container>
    );
}

export default Configurazione;