import os

TIMEOUT = 3  # None to deactivate
# TIMEOUT = None  # None to deactivate

RMQ_RPC_QUEUE_NAME = "rpc_queue"
RMQ_URL = "amqp://guest:guest@localhost/"

DEFAULT_ENCODING = "utf-8"
DEFAULT_API_THEME = "swaggerui"
DEFAULT_SESSION_COOKIE = "Responder-Session"
DEFAULT_SECRET_KEY = "NOTASECRET"

BINDING_KEY_FANOUT = 'admin'
BINDING_KEY_TOPIC = 'topic'

PROJ_PATH = os.getenv('PROJ_DIR')

SQLITE_PATH = f"{PROJ_PATH}/example.db"
DB_URL = f'sqlite:///{SQLITE_PATH}'
# DB_URL = 'sqlite:///example.db'
# DB_URL = 'sqlite:///:memory:'

# UPDATE_PEER_INTERVAL = 1.0
UPDATE_PEER_INTERVAL = 0.1
# UPDATE_PEER_INTERVAL = None

DEFAULT_CORS_PARAMS = {
    "allow_origins": (),
    "allow_methods": ("GET",),
    "allow_headers": (),
    "allow_credentials": False,
    "allow_origin_regex": None,
    "expose_headers": (),
    "max_age": 600,
}

ws_html = """<!DOCTYPE html>
<head>
<meta charset="utf-8">
<title>Responder</title>
<script>
const ws = new WebSocket('ws://localhost:8000/ws');

ws.addEventListener('message', function (event) {
    var msg = "Message from server: " + event.data;
    document.body.innerHTML = "<p>" + msg + "</p>";
    console.log(event);
});
</script>
</head>
<body>
</body>
"""

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:8000/ws");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""

html2 = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <input id="Start" type="button" value="start" onclick="sendAction(this.value);" />
        <input id="Stop" type="button" value="stop" onclick="sendAction(this.value);" />
        <input id="Save" type="button" value="save" onclick="sendAction(this.value);" />
        <input id="Delete" type="button" value="delete" onclick="sendAction(this.value);" />
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:8000/ws");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText");
                ws.send(JSON.stringify(input.value));
                input.value = '';
                event.preventDefault();
            }
            function sendAction(action) {
                ws.send(action)
            }
        </script>
    </body>
</html>
"""

