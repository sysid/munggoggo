munggoggo.messages
===================

I decided not to go for pickle, although it would
simplify the serialization process significantly due to its capability to handle any python objects.

However, in order to allow for communication with non-python world I went for JSON encoding and wrapping objects
into a common data structure based on python dataclasses.

Message Definition and Serialization:
_____________________________________

Self describing data serialization format based on json and python dataclasses.

Two stage serialization

1. serialize payload by using dataclasses and marshmallow (dataclass with dataclass_json decorator)
2. wrap result into RPC dataclass with two fields: {c_type: str, c_data: json_payload}

Deserialization:

1. extract the class_type of payload from the SerializedObject (obj.c_type)
2. deserizalize the json_payload with the class_type as schema into the respective python object


Caveat when serializing dataclasses:

As specified in the datetime docs, if your datetime object is naive, it will assume your system local timezone
when calling .timestamp(). JSON nunbers corresponding to a datetime field in your dataclass are decoded into
a datetime-aware object, with tzinfo set to your system local timezone.
Thus, if you encode a datetime-naive object, you will decode into a datetime-aware object.
This is important, because encoding and decoding won't strictly be inverses.

When using tz-aware objects everything should be fine

Rabbit MQ Message attributes and their semantic here:

.. code-block:: shell

   body:            payload
   headers:         message headers
   headers_raw:     message raw headers
   content_type:    application/json
   content_encoding:
   delivery_mode:   delivery mode
   priority:        priority (not used)
   correlation_id:  correlation id
   reply_to:        reply to
   routing_key:     routing_key (e.g. topic)
   expiration:      expiration in seconds (or datetime or timedelta)
   message_id:      message id
   timestamp:       timestamp
   type:            type  -> (RmqMessageTypes: not rmq relevant, for application to communicate semantics)
   user_id:         user id -> (rmq user, e.g. guest)
   app_id:          app id -> (sender identity)


.. automodule:: messages
   :members:
