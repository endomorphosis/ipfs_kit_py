import anyio

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
        self.listener = None

    async def handle_message(self, message):
        raise NotImplementedError

    async def handler(self, reader, writer):
        pass

    async def start(self):
        # anyio TCP server
        self.listener = await anyio.create_tcp_listener(local_host=self.host, local_port=self.port)
        # Get socket info
        sock = self.listener.extra(anyio.abc.SocketAttribute.raw_socket)
        addr = sock.getsockname()
        print(f'Serving on {addr}')
        async with self.listener:
            await self.listener.serve(self.handler)

    async def stop(self):
        if self.listener:
            await self.listener.aclose()

    async def send_response(self, recipient, response):
        pass
