
import anyio
import json

class MCPClient:
    def __init__(self, server_host='127.0.0.1', server_port=8888):
        self.server_host = server_host
        self.server_port = server_port

    async def send(self, command, args):
        stream = await anyio.connect_tcp(self.server_host, self.server_port)
        try:
            message = {"command": command, "args": args}
            await stream.send(json.dumps(message).encode())
            data = await stream.receive(1024)
            return json.loads(data.decode())
        finally:
            await stream.aclose()
