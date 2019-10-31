import React from "react";
import md5 from "blueimp-md5";
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Behaviour from "./Behaviour";

import PropTypes from 'prop-types';
import Image from "react-bootstrap/Image";
import Card from "react-bootstrap/Card";

const Agent = props => {
    const {peer} = props;
    const behaviours = peer.behaviours;
    const digest = md5(peer.name);
    return (
        <Card className={"agent p-2"}>
            <Card.Header>{peer.name}</Card.Header>
            <Card.Body>
                <Row >
                    <Col sm={3} >
                        <Image roundedCircle src={`http://www.gravatar.com/avatar/${digest}?d=monsterid`} alt="Logo"/>
                    </Col>
                    <Col className={"d-flex align-items-center"}>
                        {typeof behaviours !== 'undefined' && behaviours.map((behav, index) =>
                            <Behaviour behaviour={behav} key={index} {...props} />
                        )}
                    </Col>
                </Row>
            </Card.Body>
        </Card>
    );
};

Agent.propTypes = {};

export default Agent;
