import pytest
from starlette.testclient import TestClient

import asgi_agent
from agent import Agent
from core import Core


@pytest.fixture
def app():
    config = dict(UPDATE_PEER_INTERVAL=1.0)
    agent = Core(identity="AsgiAgent", config=config)
    return asgi_agent.AsgiAgent(agent=agent, debug=True)


@pytest.mark.parametrize('url', ["/", "/ws_html", "/openapi"])
def test_app_smoke(app, url):
    with TestClient(app) as client:
        response = client.get(url)
        assert response.status_code == 200


def test_jsonrpc():
    config = {
        "configure_rpc": True
    }
    agent = Agent(identity="TestAsgiAgent", config=config)
    app = asgi_agent.AsgiAgent(agent=agent, debug=True)
    with TestClient(app) as client:
        headers = {"content-type": "application/json"}

        payload = {
            "method": "example_rpc_method",
            "params": [1, 2],
            "jsonrpc": "2.0",
            "id": 1,
        }
        response = client.post("/jsonrpc", json=payload, headers=headers).json()
        print(f"------> {response}")
        assert response.get("result") == 2

