Agents
============
A (growing) set of agents is being provided to form a collaborating agent system. All agents can be started in
debugging mode via debug flag ``-d``.

Welcome handshake:

Whenever an agents starts it sends a PING broadcast to all peers. They respond with the required PONG response.

Ping Agent
-----------------
Simple agent which broadcasts PING messages.

.. code-block:: shell

   $ ./ping_agent.py -d

Control Agent
-----------------
Agent to send control messages to one or all agents in the system. For certain commands the RPC interface is
being used, e.g. start/stop of agent behaviour (call).

.. code-block:: shell

   $ ./ctrl.py --help

   Usage: ctrl.py [OPTIONS] COMMAND [ARGS]...

   Options:
     -d, --debug
     --help       Show this message and exit.

   Commands:
     broadcast
     call  # RPC call
     list-behaviour
     list-peers
     send-message

   # Example:
   $ python ctrl.py broadcast '{"c_type": "DemoData", "c_data": "{\"message\": \"Hello World\", \"date\": 1546300800.0}"}' "MSG_TYPE"
   $ python ctrl.py list-behaviour SqlAgent
   $ python ctrl.py send-message '{"c_type": "DemoData", "c_data": "{\"message\": \"Hallo World 2\", \"date\": 1546300800.0}"}' "MSG_TYPE" SqlAgent
   $ python ctrl.py call start|stop SqlAgent SqlBehav


Historian
-----------------
Agent to store messages in a SQL database.

Out of the box it comes with a sqlite database in the project root: ``example.db``.

.. code-block:: shell

   $ ./historian.py

To check that entries are stored in DB:

.. code-block:: shell

   $ python ctrl.py send-message '{"c_type": "DemoData", "c_data": "{\"message\": \"Hallo World 2\", \"date\": 1546300800.0}"}' "MSG_TYPE" SqlAgent
   $ sqlite3 example.db 'select * from json_data'

   -- Loading resources from /home/tw/.sqliterc
   id          ts                          sender      rmq_type    content_type  routing_key  data
   ----------  --------------------------  ----------  ----------  ------------  -----------  --------------------------------------------------
   1           2019-11-28 16:16:52.896147  ctrl        MSG_TYPE    DemoData      SqlAgent     {"message": "Hallo World 2", "date": 1546300800.0}



ASGI Agent for WEB exposure
---------------------------
An ASGI agent provides several WEB endpoints.

Every ASGI agent provides full agent functionality::

    $ ./asgi.py

This exposes the following endpoints::

    http:localhost:8000
    http:localhost:8000/ws
    http:localhost:8000/jsonrpc
    http:localhost:8000/openapi
    http://localhost:8000/static/frontend/index.html

