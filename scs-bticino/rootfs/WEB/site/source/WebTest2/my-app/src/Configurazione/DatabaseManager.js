import React, { useState } from 'react';
import { Container, Card, Button, Alert, Spinner, Row, Col } from 'react-bootstrap';

function DatabaseManager() {
    const [uploading, setUploading] = useState(false);
    const [message, setMessage] = useState(null);
    const [messageType, setMessageType] = useState('info');

    const showMessage = (text, type = 'info') => {
        setMessage(text);
        setMessageType(type);
        setTimeout(() => setMessage(null), 5000);
    };

    const downloadDatabase = async () => {
        try {
            const response = await fetch('/download_database');
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Download failed');
            }
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `scs_database_${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showMessage('✅ Database scaricato con successo!', 'success');
        } catch (error) {
            console.error('Download error:', error);
            showMessage(`❌ Errore download: ${error.message}`, 'danger');
        }
    };

    const uploadDatabase = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        if (!file.name.endsWith('.json')) {
            showMessage('❌ Seleziona un file JSON valido', 'danger');
            event.target.value = null;
            return;
        }

        setUploading(true);
        showMessage('⏳ Caricamento database in corso...', 'info');

        const formData = new FormData();
        formData.append('database', file);

        try {
            const response = await fetch('/upload_database', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            
            if (response.ok) {
                showMessage('✅ Database caricato! Ricaricamento pagina...', 'success');
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                showMessage(`❌ Errore: ${result.error}`, 'danger');
            }
        } catch (error) {
            console.error('Upload error:', error);
            showMessage(`❌ Errore upload: ${error.message}`, 'danger');
        } finally {
            setUploading(false);
            event.target.value = null;
        }
    };

    const createBackup = async () => {
        try {
            const response = await fetch('/backup_database', {
                method: 'POST'
            });
            const result = await response.json();
            
            if (response.ok) {
                showMessage(`✅ Backup creato: ${result.backup_file}`, 'success');
            } else {
                showMessage(`❌ Errore backup: ${result.error}`, 'danger');
            }
        } catch (error) {
            console.error('Backup error:', error);
            showMessage(`❌ Errore: ${error.message}`, 'danger');
        }
    };

    return (
        <Container style={{ paddingTop: "2rem", paddingBottom: "2rem" }}>
            <div className="pricing-header px-3 py-3 pt-md-5 pb-md-4 mx-auto text-center">
                <h1 className="display-4">🗄️ Gestione Database</h1>
                <p className="lead">Backup, scarica e carica il database di configurazione</p>
            </div>

            <Row className="justify-content-center">
                <Col lg={8}>
                    <Card className="shadow-sm">
                        <Card.Header className="bg-primary text-white">
                            <h4 className="my-0">Operazioni Database</h4>
                        </Card.Header>
                        <Card.Body>
                            {message && (
                                <Alert variant={messageType} onClose={() => setMessage(null)} dismissible>
                                    {message}
                                </Alert>
                            )}

                            <div className="d-grid gap-3">
                                <Button
                                    variant="success"
                                    size="lg"
                                    onClick={downloadDatabase}
                                >
                                    ⬇️ Scarica Database
                                </Button>

                                <div>
                                    <label htmlFor="upload-db" style={{ width: '100%' }}>
                                        <Button
                                            variant="primary"
                                            size="lg"
                                            as="span"
                                            disabled={uploading}
                                            style={{ width: '100%' }}
                                        >
                                            {uploading ? (
                                                <>
                                                    <Spinner
                                                        as="span"
                                                        animation="border"
                                                        size="sm"
                                                        role="status"
                                                        aria-hidden="true"
                                                        className="me-2"
                                                    />
                                                    Caricamento...
                                                </>
                                            ) : (
                                                '⬆️ Carica Database'
                                            )}
                                        </Button>
                                    </label>
                                    <input
                                        id="upload-db"
                                        type="file"
                                        accept=".json"
                                        onChange={uploadDatabase}
                                        disabled={uploading}
                                        style={{ display: 'none' }}
                                    />
                                </div>

                                <Button
                                    variant="warning"
                                    size="lg"
                                    onClick={createBackup}
                                >
                                    💾 Crea Backup Manuale
                                </Button>
                            </div>

                            <Alert variant="info" className="mt-4 mb-0">
                                <strong>ℹ️ Informazioni:</strong>
                                <ul className="mb-0 mt-2" style={{ fontSize: '0.9rem' }}>
                                    <li><strong>Scarica:</strong> Salva una copia del database sul tuo computer</li>
                                    <li><strong>Carica:</strong> Sostituisce il database attuale (viene creato un backup automatico)</li>
                                    <li><strong>Backup:</strong> Crea una copia di sicurezza in /data/backups/ (max 20 backup)</li>
                                    <li>La pagina si ricaricherà automaticamente dopo il caricamento</li>
                                </ul>
                            </Alert>

                            <Alert variant="warning" className="mt-3 mb-0">
                                <strong>⚠️ Attenzione:</strong>
                                <ul className="mb-0 mt-2" style={{ fontSize: '0.9rem' }}>
                                    <li>Il caricamento sostituisce completamente il database esistente</li>
                                    <li>Assicurati che il file JSON sia valido prima di caricarlo</li>
                                    <li>I dispositivi verranno ricaricati automaticamente</li>
                                </ul>
                            </Alert>
                        </Card.Body>
                    </Card>
                </Col>
            </Row>
        </Container>
    );
}

export default DatabaseManager;