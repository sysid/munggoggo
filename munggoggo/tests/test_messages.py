from dataclasses import dataclass
from datetime import datetime

import pytest
import pytz
from dataclasses_json import dataclass_json

from messages import Ping, to_rpc, from_rpc, RpcObject, DemoObj, RpcMessage, RpcMessageTypes, SerializableObject, \
    DemoData, WrongMessageFormatException, ServiceStatus, CoreStatus, PongControl

m = {
    'body_size': 5,
    'headers': {'foo': b'bar'},
    'content_type': 'application/json',
    'content_encoding': '',
    'delivery_mode': 1,
    'priority': 0,
    'correlation_id': None,
    'reply_to': None,
    'expiration': None,
    'message_id': '83b81a6583ee11cd89418201d89add72',
    'timestamp': '2019-08-22 17:19:53',
    'type': 'xxx',
    'user_id': 'guest',
    'app_id': 'twagent',
    'cluster_id': '',
    'consumer_tag': 'twagent',
    'delivery_tag': 1,
    'exchange': '',
    'redelivered': False,
    'routing_key': 'twagent',
    'body': "xxxxx".encode()
}


def test_rpc_wrap():
    json = r'{"c_type": "Ping", "c_data": "{\"ping\": \"ping Hallo\"}", "request_type": 1}'
    ping = Ping(ping="ping Hallo")
    msg = to_rpc(ping)
    assert msg == json


def test_rpc_unwrap():
    json = r'{"c_type": "Ping", "c_data": "{\"ping\": \"ping Hallo\"}", "request_type": 1}'
    ping = from_rpc(json)
    assert isinstance(ping, Ping)


class TestRpcMessage:
    def test_is_req(self):
        m = RpcMessage(c_type='c_type', c_data='c_data')
        assert m.is_request()
        m = RpcMessage(c_type='c_type', c_data='c_data', request_type=RpcMessageTypes.RPC_RESPONSE)
        assert m.is_response()


class TestRpcObject:
    def test_rpc_object(self):
        rpc = RpcObject()
        msg = rpc.to_rpc()
        # assert msg == '{"c_type": "RpcObject", "c_data": "{}"}'
        assert msg == '{"c_type": "RpcObject", "c_data": "{}", "request_type": 1}'
        rt, rpc = RpcObject.from_rpc(msg)
        assert isinstance(rpc, RpcObject)
        assert rt is RpcMessageTypes.RPC_REQUEST

    def test_rpc_object_response(self):
        rpc = RpcObject()
        msg = rpc.to_rpc(rt=RpcMessageTypes.RPC_RESPONSE)
        # assert msg == '{"c_type": "RpcObject", "c_data": "{}"}'
        assert msg == '{"c_type": "RpcObject", "c_data": "{}", "request_type": 2}'
        rt, rpc = RpcObject.from_rpc(msg)
        assert isinstance(rpc, RpcObject)
        assert rt is RpcMessageTypes.RPC_RESPONSE

    def test_ping_to_rpc(self):
        # json = r'{"c_type": "Ping", "c_data": "{\"ping\": \"ping Hallo\"}"}'
        json = r'{"c_type": "Ping", "c_data": "{\"ping\": \"ping Hallo\"}", "request_type": 1}'
        ping = Ping(ping="ping Hallo")
        msg = ping.to_rpc()
        assert msg == json

    def test_ping_from_rpc(self):
        json = r'{"c_type": "Ping", "c_data": "{\"ping\": \"ping Hallo\"}", "request_type": 1}'
        _, ping = Ping.from_rpc(json)
        assert isinstance(ping, Ping)

    def test_ping_from_rpc_via_rpc_object(self):
        json = r'{"c_type": "Ping", "c_data": "{\"ping\": \"ping Hallo\"}", "request_type": 1}'
        _, ping = RpcObject.from_rpc(json)
        assert isinstance(ping, Ping)

    def test_demo_to_rpc_timezone_conversion(self):
        json = r'{"c_type": "DemoObj", "c_data": "{\"message\": \"Hallo\", \"date\": 1546300800.0}", "request_type": 1}'
        date = datetime(2019, 1, 1, tzinfo=pytz.UTC)
        demo = DemoObj(message="Hallo", date=date)
        msg = demo.to_rpc()
        assert msg == json

    def test_demo_from_rpc_timezone_conversion(self):
        json = r'{"c_type": "DemoObj", "c_data": "{\"message\": \"Hallo\", \"date\": 1546300800.0}", "request_type": 1}'
        _, demo = RpcObject.from_rpc(json)
        assert isinstance(demo, DemoObj)
        assert demo.date == datetime(2019, 1, 1, tzinfo=pytz.UTC)


class TestSerializableObject:
    def test_json_object(self):
        obj = SerializableObject()
        msg = obj.serialize()
        assert msg == '{"c_type": "SerializableObject", "c_data": "{}"}'
        obj = SerializableObject.deserialize(msg)
        assert isinstance(obj, SerializableObject)

    def test_deserialize_error_wrong_message_format(self):
        msg = 'wrong-format'
        # msg = '{"c_data": "{}"}'
        with pytest.raises(WrongMessageFormatException):
            obj = SerializableObject.deserialize(msg)

    def test_deserialize_error_unknown_object(self):
        msg = '{"c_type": "UnknownObject", "c_data": "{}"}'
        with pytest.raises(WrongMessageFormatException):
            obj = SerializableObject.deserialize(msg)

    def test_demo_data_timezone_conversion_to_utc(self):
        json = r'{"c_type": "DemoData", "c_data": "{\"message\": \"Hallo\", \"date\": 1546300800.0}"}'
        date = datetime(2019, 1, 1, tzinfo=pytz.UTC)
        demo = DemoData(message="Hallo", date=date)
        msg = demo.serialize()
        assert msg == json

        obj = SerializableObject.deserialize(msg)
        assert isinstance(obj, DemoData)
        assert obj.date.tzinfo == pytz.UTC

    def test_extract_type(self):
        date = datetime(2019, 1, 1, tzinfo=pytz.UTC)
        demo = DemoData(message="Hallo", date=date)
        msg = demo.serialize()

        msg_type = SerializableObject.extract_type(msg)
        assert msg_type == 'DemoData'

    def test_deserialize_new_msg_class(self):
        json = r'{"c_type": "MyData", "c_data": "{\"message\": \"Hallo\", \"date\": 1546300800.0}"}'
        date = datetime(2019, 1, 1, tzinfo=pytz.UTC)

        # given a new message type
        @dataclass_json
        @dataclass
        class MyData(SerializableObject):
            message: str
            date: datetime = None

        demo = MyData(message="Hallo", date=date)
        msg = demo.serialize()
        assert msg == json

        # when a serialized message of the new type is deserialized with type as parameter
        obj = SerializableObject.deserialize(msg, msg_type=MyData)

        # then the new type must result
        assert isinstance(obj, MyData)


def test_core_status():
    behav_status = ServiceStatus(name="behav12", state="running")
    status = CoreStatus(name="behav12", state="running", behaviours=[behav_status])

    msg = '{"status": {"name": "behav12", "state": "running", "behaviours": [{"name": "behav12", "state": "running"}]}}'
    assert PongControl(status=status).to_json() == msg
    y = PongControl.from_json(msg)
    print(y)
    assert y.status == status
