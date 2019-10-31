import asyncio
import logging
import unittest.mock
from datetime import datetime, timedelta

import dateutil.parser
import pytest
from twpy import add_tz

from clocks import AsyncioClock, BaseClock, ExternalClock, TimerHandle

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

EC_UTC_INIT = dateutil.parser.parse("2015-01-01T00:00:00+00:00")


@pytest.fixture
def ac(event_loop):
    return AsyncioClock(loop=event_loop)


@pytest.fixture
def ec(event_loop):
    return ExternalClock(EC_UTC_INIT, loop=event_loop)


def test_baseclock_not_implemented():
    funcs = [
        ("time", []),
        ("utcnow", []),
        ("sleep", [0, 0]),
        ("sleep_until", [0, 0]),
        ("call_in", [0, 0]),
        ("call_at", [0, 0]),
    ]
    clock = BaseClock()
    for func, args in funcs:
        pytest.raises(NotImplementedError, getattr(clock, func), *args)


def test_asyncioclock_time(ac):
    loop = asyncio.get_event_loop()
    t1 = ac.time()
    t2 = loop.time()
    assert (t1 - t2) < 0.001


def test_asyncioclock_utcnow(ac):
    t1 = ac.utcnow()
    t2 = add_tz(datetime.utcnow())
    assert (t2 - t1).total_seconds() < 0.001


def test_asyncioclock_sleep(ac, event_loop):
    with unittest.mock.patch("asyncio.sleep") as mock:
        ret = ac.sleep(2, 3)
        assert ret is mock.return_value
        mock.assert_called_once_with(2, 3, loop=event_loop)


def test_asyncioclock_sleep_until(ac, event_loop):
    with unittest.mock.patch("asyncio.sleep") as mock:
        ac.time = lambda: 1
        ret = ac.sleep_until(3, 3)
        assert ret is mock.return_value
        mock.assert_called_once_with(2, 3, loop=event_loop)


def test_asyncioclock_call_in(event_loop, ac):
    assert ac._loop is event_loop
    with unittest.mock.patch.object(event_loop, "call_later") as mock:
        ret = ac.call_in(2, 3, 4)
        assert ret is mock.return_value
        mock.assert_called_once_with(2, 3, 4)


def test_asyncioclock_call_at(event_loop, ac):
    with unittest.mock.patch.object(event_loop, "call_at") as mock:
        t = ac.time() + 2
        ret = ac.call_at(t, 3, 4)
        assert ret is mock.return_value
        mock.assert_called_once_with(t, 3, 4)


def test_externalclock_init_time(ec):
    assert ec.time() == 0


def test_externalclock_init_utcnow(ec):
    assert ec.utcnow() == EC_UTC_INIT


def test_externalclock_time(ec):
    ec.set_time(60)
    assert ec.time() == 60


def test_externalclock_utcnow(ec):
    ec.set_time(60)
    assert ec.utcnow() == EC_UTC_INIT.replace(minute=1)


def test_externalclock_set_time_error(ec):
    ec.set_time(3)
    pytest.raises(ValueError, ec.set_time, 2)  # < ec.time()
    pytest.raises(ValueError, ec.set_time, 3)  # == ec.time()


def test_externalclock_sleep(ec):
    ec.set_time(1)
    res = "ohai"
    f = ec.sleep(2, res)
    ec.set_time(2)
    assert not f.done()
    ec.set_time(3)
    assert f.done()
    assert f.result() is res


def test_externalclock_sleep_until(ec):
    res = "ohai"
    f = ec.sleep_until(ec.utcnow() + timedelta(seconds=3), res)
    ec.set_time(2)
    assert not f.done()
    ec.set_time(3)
    assert f.done()
    assert f.result() is res


def test_externalclock_sleep_until_cancelled(ec):
    res = "ohai"
    f = ec.sleep_until(3, res)
    f.cancel()
    ec.set_time(3)
    assert f.done() and f.cancelled()
    pytest.raises(asyncio.CancelledError, f.result)


def test_externalclock_call_in(event_loop, ec):
    ec.set_time(1)

    # Triggered when the callback "cb" is called
    done = event_loop.create_future()

    # Callback for call_in()
    cb = unittest.mock.Mock()
    cb.side_effect = lambda result: done.set_result(result)

    f = ec.call_in(1, cb, "spam")
    assert type(f) is TimerHandle
    ec.set_time(2)
    assert f._future.done()

    # Wait until the callback was called
    event_loop.run_until_complete(done)
    assert done.result() == "spam"
    cb.assert_called_once_with("spam")


def test_externalclock_call_at(event_loop, ec):
    # Triggered when the callback "cb" is called
    done = event_loop.create_future()

    # Callback for call_at()
    cb = unittest.mock.Mock()
    cb.side_effect = lambda result: done.set_result(result)

    f = ec.call_at(ec.utcnow().replace(second=2), cb, "spam")
    assert type(f) is TimerHandle
    ec.set_time(2)
    assert f._future.done()

    # Wait until the callback was called
    event_loop.run_until_complete(done)
    assert done.result() == "spam"
    cb.assert_called_once_with("spam")


def test_externalclock_call_at_cancelled(event_loop, ec):
    # Callback for call_at()
    cb = unittest.mock.Mock()

    f = ec.call_at(2, cb, "spam")
    f.cancel()
    ec.set_time(2)
    assert not f._future._callbacks
    assert f._future.cancelled()

    # Wait some time and make sure the callback wasn't called
    event_loop.run_until_complete(asyncio.sleep(0.001))
    assert cb.call_count == 0


def test_past_date(ac, ec):
    pytest.raises(ValueError, ac.sleep_until, -1)
    pytest.raises(ValueError, ec.sleep, 0)
    pytest.raises(ValueError, ec.call_in, 0, None)


@pytest.mark.asyncio
async def test_agent_xxx(event_loop, ec):
    until = 3
    await ec.clock_setter(until=until)
    assert ec.utcnow() == EC_UTC_INIT + timedelta(seconds=until)
