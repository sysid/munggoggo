import React, {useEffect, useState} from "react";
import Button from "react-bootstrap/Button";
import Spinner from "react-bootstrap/Spinner";

import PropTypes from 'prop-types';
import Card from "react-bootstrap/Card";
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";

const Behaviour = props => {
    const {behaviour, ws, is_online} = props;
    const [isToggleOn, setIsToggleOn] = useState(true);

    useEffect(() => {
        setIsToggleOn(behaviour.state !== "running");
    }, []);

    const sendMessage = (data) => {

        // websockete can be null because of reconnect setup
        try {
            console.log(data); // catch error
            ws.send(data) //send data to the server
        } catch (error) {
            console.error(error) // catch error
        }
    };

    const handleClick = () => {
        setIsToggleOn(!isToggleOn);
        const msg = {
            originator: behaviour,
            command: isToggleOn ? "Start" : "Stop"
        };
        sendMessage(JSON.stringify(msg));
    };

    if (!is_online) {
        return null;
    }

    return (
        <Card className="behaviour mx-auto">
            <Row className={"mx-auto"}>
                <Col>
                    <Button
                        variant={isToggleOn ? "success" : "primary"}
                        onClick={handleClick}
                    >
                        {isToggleOn ? 'ON' : 'OFF'}
                    </Button>
                </Col>
                <Col className={"d-flex align-items-center"}>
                    {behaviour.name}
                </Col>
                <Col className={"d-flex align-items-center"}>
                    {is_online && behaviour.state === "running" && <Spinner animation="grow" size="sm"/>}
                </Col>
            </Row>
        </Card>
    );
};

Behaviour.propTypes = {};

export default Behaviour;

