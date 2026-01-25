
import anyio
import json

class MCPClient:
    def __init__(self, server_host='127.0.0.1', server_port=8888):
        self.server_host = server_host
        self.server_port = server_port

    async def send(self, command, args):
        reader, writer = await asyncio.open_connection(
            self.server_host, self.server_port)

        message = {"command": command, "args": args}
        writer.write(json.dumps(message).encode())
        await writer.drain()

        data = await reader.read(1024)
        writer.close()
        await writer.wait_closed()

        return json.loads(data.decode())
