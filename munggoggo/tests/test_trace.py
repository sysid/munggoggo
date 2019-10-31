import datetime
import itertools
from collections import namedtuple

from messages import TraceStoreMessage
from trace import TraceStore


def test_factory_fixture(trace_store_message_factory):
    msg = trace_store_message_factory()
    assert isinstance(msg, TraceStoreMessage)


def test_init():
    trace = TraceStore(10)

    assert trace.size == 10
    assert trace.store == []


def test_reset():
    trace = TraceStore(10)
    for i in range(5):
        trace.append(i)
    assert len(trace.store) == 5

    trace.reset()
    assert len(trace.store) == 0


def test_append():
    trace = TraceStore(10)
    trace.append("EVENT")
    assert len(trace.store) == 1
    assert trace.store[0][1] == "EVENT"
    assert type(trace.store[0][0]) == datetime.datetime
    assert trace.store[0][2] is None


def test_append_to_top():
    trace = TraceStore(10)
    for i in range(5):
        trace.append(i)
    trace.append("EVENT")
    assert len(trace.store) == 6
    assert trace.store[0][1] == "EVENT"


def test_append_with_category():
    trace = TraceStore(10)
    trace.append("EVENT", "CATEGORY")
    assert len(trace.store) == 1
    assert trace.store[0][1] == "EVENT"
    assert type(trace.store[0][0]) == datetime.datetime
    assert trace.store[0][2] == "CATEGORY"


def test_append_max_size():
    trace = TraceStore(2)
    for i in range(5):
        trace.append(i)

    assert len(trace.store) == 2
    assert trace.store[0][1] == 4
    assert trace.store[1][1] == 3


def test_len():
    trace = TraceStore(10)
    for i in range(5):
        trace.append(i)
    assert trace.len() == 5


def test_all():
    trace = TraceStore(10)
    for i in range(5):
        trace.append(i)
    all = trace.all()
    events = [e[1] for e in all]

    assert events == [0, 1, 2, 3, 4]


def test_latest():
    trace = TraceStore(10)
    for i in range(5):
        trace.append(i)
    latest = trace.latest()
    assert latest[1] == 4


def test_all_limit():
    trace = TraceStore(10)
    for i in range(5):
        trace.append(i)
    all = trace.all(limit=2)
    events = [e[1] for e in all]

    assert events == [3, 4]


def test_received():
    Event = namedtuple("Event", ["value", "sent"])
    trace = TraceStore(10)
    for i in range(5):
        trace.append(Event(i, True))

    empty_received = trace.received()
    assert len(empty_received) == 0

    for i in range(5, 10):
        trace.append(Event(i, False))

    received = [r[1].value for r in trace.received()]
    assert len(received) == 5
    assert received == [5, 6, 7, 8, 9]

    limit_received = [r[1].value for r in trace.received(limit=3)]
    assert len(limit_received) == 3
    assert limit_received == [7, 8, 9]


def test_filter():
    trace = TraceStore(10)
    for i in range(5):
        trace.append(i)

    result = [x[1] for x in trace.filter()]
    assert result == [0, 1, 2, 3, 4]


def test_filter_limit():
    trace = TraceStore(10)
    for i in range(5):
        trace.append(i)

    result = [x[1] for x in trace.filter(limit=3)]
    assert result == [2, 3, 4]


def test_filter_from(trace_store_message_factory):
    cycle = itertools.cycle(range(3))
    trace = TraceStore(10)
    for i in range(5):
        msg = trace_store_message_factory(
            body=str(i),
            app_id="{}@sender".format(next(cycle))
        )
        trace.append(msg)

    result = [x[1].body for x in trace.filter(app_id="0@sender")]
    assert result == ["0", "3"]


def test_filter_from_limit(trace_store_message_factory):
    cycle = itertools.cycle(range(3))
    trace = TraceStore(10)
    for i in range(5):
        msg = trace_store_message_factory(
            body=str(i),
            app_id="{}@sender".format(next(cycle))
        )
        trace.append(msg)

    result = [x[1].body for x in trace.filter(app_id="0@sender", limit=1)]
    assert result == ["3"]


def test_filter_category():
    cycle = itertools.cycle(range(3))
    trace = TraceStore(10)
    for i in range(5):
        trace.append(i, str(next(cycle)))

    result = [x[2] for x in trace.filter(category="0")]
    assert result == ["0", "0"]


def test_filter_category_limit():
    cycle = itertools.cycle(range(3))
    trace = TraceStore(10)
    for i in range(5):
        trace.append(1, str(next(cycle)))

    result = [category for (tw, event, category) in trace.filter(category="0", limit=1)]
    assert result == ["0"]


def test_filter_from_and_category(trace_store_message_factory):
    cycle = itertools.cycle(range(3))
    trace = TraceStore(10)
    for i in range(5):
        c = str(next(cycle))
        msg = trace_store_message_factory(
            body=str(c),
            app_id="{}@sender".format(c)
        )
        trace.append(msg, c)

    result = [(event.body, category) for (tw, event, category) in trace.filter(app_id="1@sender", category="1")]
    assert result == [("1", "1"), ("1", "1")]


def test_filter_from_and_category_and_limit(trace_store_message_factory):
    cycle = itertools.cycle(range(3))
    trace = TraceStore(10)
    for i in range(5):
        c = str(next(cycle))
        msg = trace_store_message_factory(
            body=str(c),
            app_id="{}@sender".format(c)
        )
        trace.append(msg, c)

    # result = [(x[1].body, x[2]) for x in trace.filter(app_id="1@sender", category="1", limit=1)]
    result = [(event.body, category) for (ts, event, category) in trace.filter(app_id="1@sender", category="1", limit=1)]
    assert result == [("1", "1")]


def test_decomposition():
    trace = TraceStore(10)
    for i in range(5):
        event = dict(name=f"name{i}", id={i})
        trace.append(event)
    all = trace.all()
    events = [event['name'] for (date, event, category) in all]
    # print(events)
    assert events == ['name0', 'name1', 'name2', 'name3', 'name4']

