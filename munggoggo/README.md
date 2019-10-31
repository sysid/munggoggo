# Agent

start/stop methods initialize everything. Late initialization necessary because of event loop
setup by external programs like uvicorn's on_start hook

# behaviour
- implements business logic

## Subsystems
- subsystems are instantianted per behaviour

### PubSub
- one queue per behaviour, because all incoming messages are forwarded to behaviour message queue
  and need to be dispatched, so one topic queue can subscribe to all relevant topics
  
# RMQ
- message ack when message gets picked off queue by agent dispatcher, but before consumption by handler of behaviour
  queue

- fanout exchange: 'admin'
- topic exchange: 'topic'

## Agent Bindings
- direct queue: 'name' queue bound to default exchange
- fanout queue: random queue bound to admin exchange

### Behaviour Bindings
- agent.Behaviour.pubsub_queue: PublishSubscribe Subsystem
  
  
# Gotchas
- pytest.capslog only captureing portions of printout (different  contest?) -> not usable  ..... see lower remark
- fixtures initialize exchanges -> rabtap bindings removed
- class variables are evaluated during load-time vs. run-time, so table-redefinition changes table in metadata
- make sure, no agents are running

# Testing
- make sure, no agents are running
## log capture
- caplog fixtrues captures all logs WITHIN test, but not output of preparing fixtures
