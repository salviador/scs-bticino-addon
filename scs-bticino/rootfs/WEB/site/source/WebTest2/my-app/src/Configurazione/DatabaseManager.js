import React, { useState } from 'react';
import { Card, Button, Alert, Spinner } from 'react-bootstrap';

function DatabaseManager() {
    const [uploading, setUploading] = useState(false);
    const [message, setMessage] = useState(null);
    const [messageType, setMessageType] = useState('info'); // 'success', 'danger', 'warning', 'info'

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

        // Verifica che sia un file JSON
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
                showMessage('✅ Database caricato con successo! Ricaricamento pagina...', 'success');
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
            event.target.value = null; // Reset input
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
        <Card className="mb-4 shadow-sm">
            <Card.Header>
                <h4 className="my-0 font-weight-normal">🗄️ Gestione Database</h4>
            </Card.Header>
            <Card.Body>
                {message && (
                    <Alert variant={messageType} onClose={() => setMessage(null)} dismissible>
                        {message}
                    </Alert>
                )}

                <div className="d-grid gap-2">
                    <Button
                        variant="success"
                        size="lg"
                        onClick={downloadDatabase}
                        className="mb-2"
                    >
                        ⬇️ Scarica Database
                    </Button>

                    <div className="mb-2">
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

                <Alert variant="warning" className="mt-3 mb-0">
                    <strong>⚠️ Attenzione:</strong>
                    <ul className="mb-0 mt-2" style={{ fontSize: '0.9rem' }}>
                        <li>Il caricamento sostituisce completamente il database esistente</li>
                        <li>Viene creato automaticamente un backup prima del caricamento</li>
                        <li>La pagina si ricaricherà automaticamente dopo il caricamento</li>
                        <li>Assicurati che il file JSON sia valido prima di caricarlo</li>
                    </ul>
                </Alert>
            </Card.Body>
        </Card>
    );
}

export default DatabaseManager;