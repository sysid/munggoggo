import asyncio

import pytest
from async_timeout import timeout

from behaviour import Behaviour
from core import Core
from messages import CoreStatus
from settings import UPDATE_PEER_INTERVAL


@pytest.mark.asyncio
class TestBasics:
    async def test_core(self):
        identity = "core1"

        async with Core(identity=identity) as a:
            await asyncio.sleep(0)
            assert a.started

        assert not a.started  # type: ignore

    async def test_agent_fixture(self, core1):
        assert await core1.dummy()


    async def test_without_contextmanager(self, event_loop):
        identity = "twagent"
        a = Core(identity=identity)
        await a.start()
        assert a.started

        await asyncio.sleep(0.1)  # relinquish cpu

        await a.stop()
        await asyncio.sleep(0.1)  # relinquish cpu
        assert a._stopped.is_set()
        assert a.state == 'shutdown'
        a.service_reset()
        assert not a.started
        assert a.state == 'init'

    async def test_status(self, core1):
        print(core1.status.to_json())
        assert isinstance(core1.status, CoreStatus)
        assert core1.status.to_json() == '{"name": "core1", "state": "running", "behaviours": []}'


@pytest.mark.usefixtures("init_rmq")
@pytest.mark.asyncio
class TestCommunication:
    async def test_direct_send_recv(self, core1):
        # when messages is sent to correct receiver
        await core1.direct_send(msg="Hallo Thomas", msg_type="type", target=core1.identity)

        # allow callback on_direct_message to run
        await asyncio.sleep(0.1)  # relinquish cpu

        # then one message should show up in trace.store
        msg = core1.traces.store[0][1]
        assert "Hallo" in msg.body

        # when messages is sent to wrong receiver
        await core1.direct_send(msg="Hallo Thomas", msg_type="type", target="does-not-exist")
        await asyncio.sleep(0.1)  # relinquish cpu

        # still only one message should show up in trace.store
        msg = core1.traces.store[0][1]
        assert "Hallo" in msg.body

    async def test_fanout_send_recv(self, ctrl, core1, core2):
        # when messages is sent to all receivers
        await ctrl.fanout_send(msg="Hallo Thomas", msg_type='type')
        await asyncio.sleep(0.2)  # relinquish cpu

        # then one message should show up in trace.store
        msg = ctrl.traces.store[0][1]
        assert "Hallo" in msg.body

        msg = core1.traces.store[0][1]
        assert "Hallo" in msg.body

        msg = core2.traces.store[0][1]
        assert "Hallo" in msg.body

        assert ctrl.loop is core1.loop is core2.loop


@pytest.mark.asyncio
async def test_get_behaviour(core1):

    # given
    class Behav1(Behaviour):
        async def run(self):
            await asyncio.sleep(0)

    class Behav2(Behaviour):
        async def run(self):
            await asyncio.sleep(0)

    await core1.add_runtime_dependency(Behav1(core1))
    await core1.add_runtime_dependency(Behav2(core1))

    # when
    # then
    behav = core1.get_behaviour('Behav1')
    assert str(behav) == f'{core1.identity}.Behav1'
    behav = core1.get_behaviour('Behav2')
    assert str(behav) == f'{core1.identity}.Behav2'


@pytest.mark.usefixtures("init_rmq")
@pytest.mark.asyncio
class TestPeriodicPeerUpdate:
    async def test_service_itertimer(self, core1, capsys):
        """ demonstrate itertimer usage """

        with pytest.raises(asyncio.TimeoutError):
            # given timeout
            async with timeout(timeout=0.2):
                # when itertimer interval < timeout
                async for sleep_time in core1.itertimer(0.1):
                    # then at least once the function is called
                    print('another second passed, just woke up...')
                    captured = capsys.readouterr()  # prevents visibility on commandline
                    assert 'another second passed' in captured.out
                    assert captured.err == ""

    async def test_update_peers_self(self, core1):
        # given
        # when core is initialized

        # then peerlist contains self
        assert len(core1.peers.all()) == 1
        identities = [status.name for (date, status, category) in core1.peers.all()]
        assert 'core1' in identities

    async def test_update_peers_self_create_status_message(self, core1):
        # given
        expected = {'from': 'core1', 'peers': [{'name': 'core1', 'state': 'running', 'behaviours': []}]}

        # when core is initialized

        # then messages must be created
        msg = core1._create_peer_msg()
        assert msg == expected

    async def test_periodic_update_peers(self):
        identity = "core1"

        # given config
        config = dict(UPDATE_PEER_INTERVAL=0.1)

        async with Core(identity=identity, config=config) as a:
            await asyncio.sleep(0)

            # given core is stated
            assert a.started

            # when waited for at least one update interval
            await asyncio.sleep(0.2)

            # then peerlist contains self multiple times
            identities = [status.name for (date, status, category) in a.peers.all()]
            assert 'core1' in identities
            assert len(a.peers.all()) > 1

    async def test_update_peers_two(self, ctrl):
        identity = "core1"

        # given config
        config = dict(UPDATE_PEER_INTERVAL=0.1)

        async with Core(identity=identity, config=config) as a:
            await asyncio.sleep(0)

            # given core is stated
            assert a.started

            # when waited for at least one update interval
            await asyncio.sleep(0.2)

            # then peerlist contains self multiple times
            identities = [status.name for (date, status, category) in a.peers.all()]
            assert 'core1' in identities
            assert 'ctrl' in identities

