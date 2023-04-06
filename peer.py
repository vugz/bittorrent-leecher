import asyncio
import protocol
import struct
import bitarray
import traceback
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

        self.choke_event = asyncio.Event() # Starts choked == not set, which blocks on wait()
        self.choked = 1
        self.interested = 0
        self.am_choking = 1
        self.am_interested = 0

        self.bitfield = bitarray.bitarray('0' * pieces_manager.nr_pieces)  # peer's bitfield
        self.pieces_manager = pieces_manager                               # reference to pieces manager 
        self.connection = PeerConnection()                                 # connection state

        self.piece_handler = PieceHandler(max_blocks, pieces_hashes)  # structure with piece buffer

    async def connect(self, client_id, info_hash): 
        """ Connects and handshakes peer """
        try:
            await asyncio.wait_for(
                self.connection.initialize(self.ip, self.port, client_id, info_hash), 
                 timeout=2)
        except asyncio.TimeoutError:
            raise ConnectionError("Timed out connection")
    
    async def run_peer(self):
        # create listener and requester tasks
        requester_task = asyncio.create_task(self.requester())
        try:
            await self.listener()
        except ConnectionError:
            pass

        # await all tasks to complete
        requester_task.cancel()
        self.choked = 1
        self.choke_event.set()
        piece = await requester_task 

        print(piece)
        if piece and isinstance(piece, int):
            await self.pieces_manager.put_piece(piece)

        raise ConnectionError("hi")

    async def listener(self):
        """ Listens to messages """
        while True:
            try:
                # even if the peer is making us hold, no "have" messages for 2 seconds will timeout
                id, data = await asyncio.wait_for(self.connection.read_message(), 
                                                  timeout=2)
            except (asyncio.TimeoutError, ConnectionError):
                raise ConnectionError(f"Dropping unresponsive peer {self.ip}")

            await self.handle_message(id, data)
    
    async def requester(self):
        """ Requests pieces """
        try:
            while True:
                # get piece
                piece = await self.pieces_manager.pieces_queue.get()
                # check if thing has piece here...
                # if ...:
                #     # put back in queue and fetch new piece 
                #     continue
                while self.choked:
                    await self.choke_event.wait()
                    # try:
                    #     await asyncio.wait_for(self.choke_event.wait(), timeout=5.0)
                    # except asyncio.TimeoutError:
                    #     continue
                # print(f"Requesting {self.ip} piece{piece} and block{self.piece_handler.block}")
                await self.piece_handler.request_piece(piece, self.connection, self.pieces_manager)

        except asyncio.CancelledError:
            try:
            # this piece was not be procesrequest_piecesed
                return piece
            except UnboundLocalError:
                return None
    
    async def handle_message(self, id, data):
        # print(f"Got {id} {self.ip}")
        match id:
            case 0:
                self.choked = 1
                self.choke_event.clear()
            case 1:
                self.choked = 0
                self.choke_event.set()
            case 2:
                self.interested = 1
            case 3:
                self.interested = 0
            case 4:
                await self.handle_have(data)
            case 5:
                await self.handle_bitfield(data)
            case 6:
                pass
            case 7:
                await self.handle_piece(data)
            case 8:
                pass
            case 9:
                pass
            case default:
                pass
    
    async def handle_have(self, data):
        ...
   
    async def handle_bitfield(self, data):
        ...
    
    async def handle_piece(self, data):
        # peers may queue responses se we might get repeated blocks
        if not self._correct_piece(data[0:4]) or not self._correct_block(data[4:8]):
            self.piece_handler.set_fetched_block()
            return

        # print("GOT BLOCK")
        self.piece_handler.inc_block_count()
        self.piece_handler.add_block(data[8:])
        self.piece_handler.set_fetched_block()
    
    def _correct_piece(self, raw_piece):
        # print(raw_piece)
        return struct.unpack(">I", raw_piece)[0] == self.piece_handler.piece
    
    def _correct_block(self, raw_offset):
        # print(raw_offset)
        return struct.unpack(">I", raw_offset)[0] == self.piece_handler.block_count * BLOCK_SIZE 

        

class PieceHandler:
    def __init__(self, max_blocks, pieces_hashes):
        self.piece = 0
        self.block_count = 0
        self.max_blocks = max_blocks 
        self.pieces_hashes = pieces_hashes
        self.buffer = b""
        self.fetched = asyncio.Event()
    
    def _reset(self, piece):
        self.piece = piece 
        self.block_count = 0
        self.buffer = b""
        self.fetched.clear()
  
    def inc_block_count(self):
        self.block_count += 1
    
    def set_fetched_block(self):
        self.fetched.set()
    
    def add_block(self, data):
        self.buffer += data

    async def request_piece(self, piece, connection, piece_manager):
        # reset piece handler 
        self._reset(piece)
        # we will request by block index order and simply append to the buffer 
        while self.block_count < self.max_blocks:
            await connection.send_message(protocol.Request(self.piece, self.block_count))
            self.fetched.clear()
            # wait on listener to retrieve the requested piece
            await self.fetched.wait()
            # print(f"DIFF{self.block_count} - {self.max_blocks}")
        
        if not self.check_hash():
            await asyncio.shield(piece_manager.put_piece(self.piece))
            # print("Hash don't match")
            return
        
        # save piece
        await asyncio.shield(piece_manager.save_piece(self.buffer, self.piece))
    
    def check_hash(self):
        # print(self.pieces_hashes[self.piece])
        # print(hashlib.sha1(self.buffer).hexdigest())
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
            print("stopping here?")
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
            raise ConnectionError(str(e))
    
    async def _send(self, msg):
        self.writer.write(msg)
        await self.writer.drain()
    
    async def _recv(self, size):
        try:
            return await self.reader.read(size)
        except Exception:
            raise ConnectionError("Connection was reset by peer")

