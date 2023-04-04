import asyncio
import protocol
import struct

class ConnectionError(Exception):
    ...
    
class Peer:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.choking = 1
        self.interested = 0
        self.am_chocking = 1
        self.am_interested = 0
        self.bitfield = None
        self.connection = PeerConnection()
    
    async def connect(self, client_id, info_hash): 
        """ Connects and handshakes peer """
        try:
            await asyncio.wait_for(
                self.connection.initialize(self.ip, self.port, client_id, info_hash), 
                    timeout=2)
        except asyncio.TimeoutError:
            raise ConnectionError("Timed out connection")
        

class PeerConnection:
    def __init__(self):
        self.reader = None
        self.writer = None
    
    async def initialize(self, ip, port, client_id, info_hash):
        """ Initializes connection and handshakes peer """
        await self._open(ip, port)

        await self._send(protocol.Handshake(client_id, info_hash))

        response = await self._recv(struct.calcsize(">B19s8x20s20s"))
        # check received info_hash
        if response[28:48] != info_hash:
            raise ConnectionError(f"Got bad handshake from peer {ip}:{port}")

    async def read_message(self):
        """ Read a BitTorrent protocol message """
        length = await self._recv(struct.calcsize(">I"))

        if length == b'0':
            raise ConnectionError("Connection closed")
        
        # unpack into python int 
        length = struct.unpack(">I", length)[0]

        message = b""
        # read message
        while length > 0:
            data = await self._recv(length)
            message += data
            length -= len(data)
        
        return message
    
    async def send_message(self, msg):
        await self._send(msg)


    async def _open(self, ip, port):
        """ Opens connection to peer with StreamReader and StreamWriter wrappers """
        try:
            self.reader, self.writer = await asyncio.open_connection(ip, port)
        except Exception as e:
            raise ConnectionError(str(e))
    
    async def _send(self, msg):
        self.writer.write(msg)
        await self.writer.drain()
    
    async def _recv(self, size):
        try:
            return await self.reader.read(size)
        except ConnectionResetError:
            raise ConnectionError("Connection was reset by peer")


