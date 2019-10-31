from starlette.requests import Request
from starlette.responses import Response

from starlette_jsonrpc.endpoint import JSONRPCEndpoint


class ExampleRpcEndpoint(JSONRPCEndpoint):
    """ExampleRpcEndpoint

    Wraps starlette-jsonrpc JSONRPCEndpoint to provide OPENAPI documentation.
    Forwards POST rpc call straight to JSONRPCEndpoint.
    """
    async def post(self, request: Request) -> Response:
        """
        description: RPC
        requestBody:
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            method:
                                type: string
                            params:
                                type: object
                            jsonrpc:
                                type: string
                            id:
                                type: integer
                        example:
                            method: 'multiply'
                            params: [5, 5]
                            jsonrpc: "2.0"
                            id: 1
        responses:
            200:
                description: result of RPC method
                content:
                    application/json:
                        schema:
                            type: object
                            properties:
                                result:
                                    type: object
                                jsonrpc:
                                    type: string
                                id:
                                    type: integer
                            example:
                                result: 25
                                jsonrpc: "2.0"
                                id: 1
        """
        # return await super(ExampleRpcEndpoint, self).post(request)
        return await super().post(request)
