import asyncio
import protocol
import struct
import bitstring
import hashlib
import logging

from config import BLOCK_SIZE

class ConnectionError(Exception):
    """ Custom connection error class """
    ...
    
class Peer:
    def __init__(self, ip, port, pieces_manager, max_blocks, pieces_hashes):
        self.ip = ip
        self.port = port

        self.choked = 1
        self.interested = 0
        self.am_choking = 1
        self.am_interested = 0

        self.bitfield = bitstring.BitArray(pieces_manager.nr_pieces)  # peer's bitfield
        self.pieces_manager = pieces_manager                               # reference to pieces manager 
        self.connection = PeerConnection()                                 # connection state

        self.piece_handler = PieceHandler(max_blocks, pieces_hashes)  # structure with piece buffer

    async def connect(self, client_id, info_hash): 
        """ Connects and handshakes peer """
        try:
            await asyncio.wait_for(
                self.connection.initialize(self.ip, self.port, client_id, info_hash), 
                 timeout=1)
        except asyncio.TimeoutError:
            raise ConnectionError("Timed out connection")
    
    async def run_peer(self):
        """ Listens to messages """
        while True:
            try:
                # even if the peer is making us hold, no "have" messages for 2 seconds will timeout
                id, data = await asyncio.wait_for(self.connection.read_message(), 
                                                  timeout=2)
            except Exception: 
                # enqueue piece aborted mid download
                if self.piece_handler.piece:
                    self.pieces_manager.put_piece(self.piece_handler.piece)
                raise ConnectionError(f"Dropping unresponsive peer {self.ip}")

            await self.handle_message(id, data)
    
            if self.choked:
                continue

            if self.piece_handler.piece is None:
                self.piece_handler.piece = self.pieces_manager.get_piece(self.bitfield)
            
            await self.piece_handler.request_piece(self.connection)
    
    
    async def handle_message(self, id, data):
        match id:
            case protocol.CHOKE:
                self.choked = 1
            case protocol.UNCHOKE:
                self.choked = 0
            case protocol.INTERESTED:
                self.interested = 1
            case protocol.NOT_INTERESTED:
                self.interested = 0
            case protocol.HAVE:
                await self.handle_have(data)
            case protocol.BITFIELD:
                await self.handle_bitfield(data)
            case protocol.PIECE:
                await self.handle_piece(data)
            case protocol.CANCEL:
                pass
            case default:
                pass
    
    async def handle_have(self, data):
        self.bitfield[struct.unpack(">I", data)[0]] = 1
        
    async def handle_bitfield(self, data):
        self.bitfield = bitstring.BitArray(data)
    
    async def handle_piece(self, data):
        # peers may queue responses se we might get repeated blocks
        await self.piece_handler.handle_piece(data, self.pieces_manager)

class PieceHandler:
    def __init__(self, max_blocks, pieces_hashes):
        self.piece = None 
        self.block_count = 0
        self.max_blocks = max_blocks 
        self.pieces_hashes = pieces_hashes
        self.buffer = b""
    
    def _reset(self):
        self.piece = None 
        self.block_count = 0
        self.buffer = b""

    def _correct_piece(self, raw_piece):
        return struct.unpack(">I", raw_piece)[0] == self.piece
    
    def _correct_block(self, raw_offset):
        return struct.unpack(">I", raw_offset)[0] == self.block_count * BLOCK_SIZE 

    async def request_piece(self, connection):
        if self.piece is None:
            return
        await connection.send_message(protocol.Request(self.piece, self.block_count))

    async def handle_piece(self, data, piece_manager):
        if not self._correct_piece(data[0:4]) or not self._correct_block(data[4:8]):
            return

        self.buffer += data[8:]
        self.block_count += 1

        if self.block_count < self.max_blocks:
            return

        if not self.match_hashes():
            piece_manager.put_piece(self.piece)
        else:
            await piece_manager.save_piece(self.buffer, self.piece)

        self._reset()
    
    def match_hashes(self):
        return hashlib.sha1(self.buffer).hexdigest() == self.pieces_hashes[self.piece]


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
        """ Read a BitTorrent protocol message.
        Returns a tuple with the message ID and message contents 
        """
        length = await self._recv(struct.calcsize(">I"))

        if length == b'':
            raise ConnectionError("Connection closed by peer")
        
        # unpack into python int 
        length = struct.unpack(">I", length)[0]

        # keep alive message
        if length == 0:
            return 0, None

        message = b""
        # read message
        while length > 0:
            data = await self._recv(length)
            message += data
            length -= len(data)
        
        return message[0], message[1:]
    
    async def send_message(self, msg):
        await self._send(msg)


    async def _open(self, ip, port):
        """ Opens connection to peer with StreamReader and StreamWriter wrappers """
        try:
            self.reader, self.writer = await asyncio.open_connection(ip, port)
        except Exception as e:
            logging.debug(str(e))
            raise ConnectionError("Failed opening connection to peer")
    
    async def _send(self, msg):
        self.writer.write(msg)
        await self.writer.drain()
    
    async def _recv(self, size):
        try:
            return await self.reader.read(size)
        except Exception as e:
            logging.debug(str(e))
            raise ConnectionError("Connection was reset by peer")

