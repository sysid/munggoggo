# coding=utf-8
import datetime
import itertools


def _agent_in_msg(agent, msg):
    # return msg.to == agent or msg.sender == agent
    return msg.app_id == agent


class TraceStore(object):
    """Stores and allows queries about events."""

    def __init__(self, size):
        self.size = size
        self.store = []

    def reset(self):
        """Resets the trace store"""
        self.store = []

    def append(self, event, category=None):
        """
        Adds a new event to the trace store.
        The event may hava a category

        Args:
          event (spade.message.Message): the event to be stored
          category (str, optional): a category to classify the event (Default value = None)

        """
        date = datetime.datetime.now()
        self.store.insert(0, (date, event, category))
        if len(self.store) > self.size:
            del self.store[-1]

    def len(self):
        """
        Length of the store

        Returns:
          int: the size of the trace store

        """
        return len(self.store)

    def latest(self):
        return self.store[0]

    def all(self, limit=None):
        """
        Returns all the events, until a limit if defined

        Args:
          limit (int, optional): the max length of the events to return (Default value = None)

        Returns:
          list: a list of events

        """
        return self.store[:limit][::-1]

    def received(self, limit=None):
        """
        Returns all the events that have been received (excluding sent events), until a limit if defined

        Args:
          limit (int, optional): the max length of the events to return (Default value = None)

        Returns:
          list: a list of received events

        """
        return list(itertools.islice((itertools.filterfalse(lambda x: x[1].sent, self.store)), limit))[::-1]

    def filter(self, limit=None, app_id=None, category=None):
        """
        Returns the events that match the filters

        Args:
          limit (int, optional): the max length of the events to return (Default value = None)
          app_id (str, optional): only events that have been sent or received from 'app_id' (Default value = None)
          category (str, optional): only events belonging to the category (Default value = None)

        Returns:
          list: a list of filtered events

        """
        if category and not app_id:
            msg_slice = itertools.islice((x for x in self.store if x[2] == category), limit)
        elif app_id and not category:
            msg_slice = itertools.islice((x for x in self.store if _agent_in_msg(app_id, x[1])), limit)
        elif app_id and category:
            msg_slice = itertools.islice((x for x in self.store if _agent_in_msg(app_id, x[1]) and x[2] == category), limit)
        else:
            msg_slice = self.all(limit=limit)
            return msg_slice

        return list(msg_slice)[::-1]
