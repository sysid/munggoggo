import React from 'react';

import Agent from "./Agent";
import Badge from "react-bootstrap/Badge";

const AgentList = props => {
    const {websocket, is_online, data} = props; // websocket instance passed as props to the child component.
    let new_props = {
        ws: websocket,
        is_online: is_online,
        peers: (typeof data !== 'undefined') ? data['peers'] : []
    };

    return (
        <div>
            <h2>System is <Badge variant={is_online ? "success" : "secondary"}>{is_online ? "online" : "offline"}</Badge></h2>
            {typeof new_props.peers !== 'undefined' && new_props.peers.map((peer, index) =>
                <Agent key={index} peer={peer} {...new_props} />
            )}
        </div>
    );
};

export default AgentList;