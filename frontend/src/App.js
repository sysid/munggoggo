import React, {useEffect, useState} from 'react';
import './index.css';
import AgentList from "./AgentList";
import Container from "react-bootstrap/Container";
import Col from "react-bootstrap/Col";
import Row from "react-bootstrap/Row";

const App = () => {
    const [is_online, setIs_online] = useState(false);
    const [ws, setWs] = useState(null);
    const [dataFromServer, setDataFromServer] = useState();
    let timeout = 250; // Initial timeout duration as a class variable
    useEffect(() => {
        connect();
    }, []);

    /**
     * @function connect
     * This function establishes the connect with the websocket
     * and also ensures constant reconnection if connection closes
     */
    const connect = () => {
        const ws = new WebSocket("ws://localhost:8000/ws");
        // let that = this; // cache the this
        let connectInterval;

        // websocket onopen event listener
        ws.onopen = () => {
            console.log("connected websocket main component");

            setWs(ws);
            setIs_online(true);

            timeout = 250; // reset timer to 250 on open of websocket connection
            clearTimeout(connectInterval); // clear Interval on on open of websocket connection
        };

        ws.onmessage = evt => {
            // listen to data sent from the websocket server
            const message = JSON.parse(evt.data)
            setDataFromServer(message);
            console.debug(message)
        };

        // websocket onclose event listener
        ws.onclose = e => {
            setIs_online(false);
            console.log(
                `Socket is closed. Reconnect will be attempted in ${Math.min(
                    10000 / 1000,
                    (timeout + timeout) / 1000
                )} second.`,
                e.reason
            );

            timeout = timeout + timeout; //increment retry interval
            connectInterval = setTimeout(check, Math.min(10000, timeout)); //call check function after timeout
        };

        // websocket onerror event listener
        ws.onerror = err => {
            setIs_online(false);
            console.error(
                "Socket encountered error: ",
                err.message,
                "Closing socket"
            );

            ws.close();
        };
    };

    /**
     * utilited by the @function connect to check if the connection is close,
     * if so attempts to reconnect
     */
    const check = () => {
        if (!ws || ws.readyState === WebSocket.CLOSED) connect(); //check if websocket instance is closed, if so call `connect` function.
    };

    return (
            <Layout className={"App"}>
                <AgentList websocket={ws} data={dataFromServer} is_online={is_online}/>
            </Layout>
    );
};

const Layout = ({ children }) => (
    <Container>
        <Col style={{ maxWidth: 550 }}>
            <Row>
                {children}
            </Row>
        </Col>
    </Container>
);

export default App;
