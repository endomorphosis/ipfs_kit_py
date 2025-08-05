import asyncio

class Message:
    def __init__(self, sender, command, args):
        self.sender = sender
        self.command = command
        self.args = args

class MCP:
    def __init__(self):
        self.peers = {}

    async def connect(self, peer):
        self.peers[peer.identity] = peer

    async def disconnect(self, peer):
        del self.peers[peer.identity]

    async def send(self, recipient, message):
        if recipient in self.peers:
            await self.peers[recipient].send(message)

class Server:
    def __init__(self, host="0.0.0.0", port=8888):
        self.host = host
        self.port = port
        self.server = None

    async def handle_message(self, message):
        raise NotImplementedError

    async def handler(self, reader, writer):
        pass

    async def start(self):
        self.server = await asyncio.start_server(
            self.handler, self.host, self.port)
        addr = self.server.sockets[0].getsockname()
        print(f'Serving on {addr}')
        async with self.server:
            await self.server.serve_forever()

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()

    async def send_response(self, recipient, response):
        pass
