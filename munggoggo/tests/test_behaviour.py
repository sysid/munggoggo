import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

import pytest
import pytz
from dataclasses_json import dataclass_json

from behaviour import Behaviour, SqlBehav
from messages import CoreStatus, DemoData, SerializableObject
from model import json_data
from twpy import utcnow


@pytest.mark.asyncio
class TestBasics:
    async def test_behaviour(self, core1):
        b = Behaviour(core1)
        await core1.add_runtime_dependency(b)

        assert b.started

        await b.stop()
        assert b.state == "shutdown"

    async def test_behaviour_status(self, core1):
        status = '{"name": "core1", "state": "running", "behaviours": [{"name": "core1.Behaviour", "state": "running"}]}'
        b = Behaviour(core1)
        await core1.add_runtime_dependency(b)

        print(core1.status.to_json())
        assert isinstance(core1.status, CoreStatus)
        assert core1.status.to_json() == status

    async def test_receive_direct_sent(self, behav):
        # Given

        # when message of type xxx is sent
        await behav.direct_send(msg="xxxxx", msg_type="xxx")
        await asyncio.sleep(0.1)  # relinquish cpu

        # then message in queue and can be received
        assert behav.mailbox_size() == 1
        msg = await behav.receive(timeout=3)
        await asyncio.sleep(0.1)  # relinquish cpu
        assert "xxxxx" in msg.body.decode()
        assert behav.mailbox_size() == 0

    @pytest.mark.parametrize("n", [0, 2])
    async def test_receive_all(self, behav, n):
        # Given

        # when two messages of type xxx is sent
        for i in range(n):
            await behav.direct_send(msg=f"{i}:xxxxx", msg_type="xxx")
        await asyncio.sleep(0.1)  # relinquish cpu

        # then mailbox_size must be two
        assert behav.mailbox_size() == n
        async for msg in behav.receive_all():
            assert "xxxxx" in msg.body.decode()

        assert behav.mailbox_size() == 0


@pytest.fixture()
async def sql_behav(core1):
    topics = ["x.y", "x.z", "a.#"]
    b = SqlBehav(core1, binding_keys=topics)
    await core1.add_runtime_dependency(b)

    yield b


@pytest.mark.usefixtures("rm_sqlite")
@pytest.mark.asyncio
class TestSqlBehaviour:
    async def test_connect_to_db(self, core1, json_data_values):
        json_data_values = [
            {
                "content_type": "type1",
                "ts": utcnow(),
                "data": '{"a": "aaa", "b": "bbb"}',
            },
            {
                "content_type": "type1",
                "ts": utcnow(),
                "data": '{"a": "xxx", "b": "yyy"}',
            },
        ]

        b = SqlBehav(core1)
        await core1.add_runtime_dependency(b)
        assert b.started

        # Execute many
        query = json_data.insert()
        await b.db.execute_many(query=query, values=json_data_values)

        query = json_data.select()
        rows = await b.db.fetch_all(query=query)
        assert len(rows) == len(json_data_values)

        await b.stop()
        assert b.state == "shutdown"

    async def test_receive_topic_and_store(self, sql_behav):
        # Given SerializableObject message
        msg = DemoData(
            message="xxxx", date=datetime(2019, 1, 1, tzinfo=pytz.UTC)
        ).serialize()

        # when messages are published
        await sql_behav.publish(msg, "x.y")
        await asyncio.sleep(0.1)  # relinquish cpu

        # then message must be written in database
        query = json_data.select()
        rows = await sql_behav.db.fetch_all(query=query)
        assert len(rows) == 1

    async def test_receive_topic_and_store_wrong_format(self, sql_behav, caplog):
        caplog.set_level(logging.DEBUG)

        # Given SerializableObject message
        msg = "xxx"

        # when messages are published
        await sql_behav.publish(msg, "x.y")
        await asyncio.sleep(0.1)  # relinquish cpu

        # then message must not be written in database due to wrong format
        query = json_data.select()
        rows = await sql_behav.db.fetch_all(query=query)

        assert any([record for record in caplog.records if record.levelname == "ERROR"])
        assert "Wrong message format:" in caplog.text

    async def test_receive_topic_and_store_many(self, sql_behav):
        """ time sensitive, depends on performance/sleep """
        n = 30
        for i in range(n):
            # Given SerializableObject message
            msg = DemoData(
                message=f"message: {i}", date=datetime(2019, 1, 1, tzinfo=pytz.UTC)
            ).serialize()
            # when n messages are published
            await sql_behav.publish(msg, "x.y")

        await asyncio.sleep(1)  # relinquish cpu

        # then n message must be written in database
        query = json_data.select()
        rows = await sql_behav.db.fetch_all(query=query)
        assert len(rows) == n

    async def test_receive_topic_and_store_serializable_obj(self, sql_behav):
        # Given SerializableObject message
        @dataclass_json
        @dataclass
        class MyData(SerializableObject):
            message: str
            date: datetime = None

        # when this message type is added to behaviour
        sql_behav.add_msg_type(MyData)

        # when message of this type is sent to correct topic
        msg = MyData(
            message="xxxx", date=datetime(2019, 1, 1, tzinfo=pytz.UTC)
        ).serialize()
        # when messages are published
        await sql_behav.publish(msg, "x.y")
        await asyncio.sleep(0.1)  # relinquish cpu

        # then message must be written in database
        query = json_data.select()
        rows = await sql_behav.db.fetch_all(query=query)
        assert len(rows) == 1

    async def test_receive_topic_and_store_unknown_obj(self, sql_behav, caplog):
        caplog.set_level(logging.DEBUG)

        # Given SerializableObject message
        @dataclass_json
        @dataclass
        class MyData(SerializableObject):
            message: str
            date: datetime = None

        # when this message type is not added to behaviour
        # when message of this type is then sent to topic
        msg = MyData(
            message="xxxx", date=datetime(2019, 1, 1, tzinfo=pytz.UTC)
        ).serialize()
        # when messages are published
        await sql_behav.publish(msg, "x.y")
        await asyncio.sleep(0.1)  # relinquish cpu

        # then message must not be written in database
        assert any([record for record in caplog.records if record.levelname == "ERROR"])
        assert "Unknown message type" in caplog.text
