import { useState, useEffect } from 'react';
import { Container, Card, Row, Col } from 'react-bootstrap';

import "./../App.css";

function SensoriConsumo({ device, valuedataRT }) {
    const [statoSensore, setStatoSensore] = useState("-- W");

    useEffect(() => {
        if (device.nome_attuatore === valuedataRT.nome_attuatore) {
            setStatoSensore(valuedataRT.stato + " W");
        }
    }, [device.nome_attuatore, valuedataRT]);

    return (
        <>
            <Container style={{ paddingTop: "20px" }} >
                <Card style={{ width: '100%', border: "1px solid black" }}>
                    <Card.Header>
                        <Row>
                            <Col style={{ textAlign: 'left' }} className="text-primary">
                                <h5>{device.nome_attuatore}</h5>
                            </Col>
                            <Col style={{ textAlign: 'right', fontSize: "12px" }} >
                                <Row>
                                    <Col style={{ textAlign: 'right', marginRight: "12px" }}>
                                        Indirizzo: {device.indirizzo_Ambiente}
                                    </Col>
                                </Row>
                                <Row>
                                    <Col style={{ textAlign: 'right', marginRight: "12px" }}>
                                        Toroide / CONF: {device.indirizzo_PL}
                                    </Col>
                                </Row>
                            </Col>
                        </Row>
                    </Card.Header>
                    <Card.Body>
                        <Container fluid>
                            <Row>
                                <Col lg={8} style={{ alignSelf: "center" }}>
                                    <Row>
                                        <Col lg={8}><i>Potenza</i></Col>
                                        <Col lg={8}><b>{statoSensore}</b></Col>
                                    </Row>
                                </Col>
                            </Row>
                        </Container>
                    </Card.Body>
                    <Card.Footer className="text-muted" style={{ textAlign: "center" }}>
                        <p style={{ fontSize: "9px", margin: 0, padding: "0%" }}>-Tipo-</p>
                        <p style={{ fontSize: "15px", margin: 0, padding: "0%" }}>SENSORE-CONSUMO</p>
                    </Card.Footer>
                </Card>
            </Container>
        </>
    );
}

export default SensoriConsumo;
