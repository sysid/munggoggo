munggoggo.agent
===============
Async I/O agent, stop with CTRL-C. Inherits from ``Core``.

You can attach configuration parameters to an agent on ``self.config`` via config dict parameter.

.. automodule:: agent
   :members:

munggoggo.core
==============
Core functionality of an agent.

- provides a configurable FIFO cache of all received messages
- holds a cache of all peers and their last update timestamp (keepalive message)

.. automodule:: core
   :members:

