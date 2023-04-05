import asyncio
import protocol
import struct
import bitarray
import traceback

from config import BLOCK_SIZE

class ConnectionError(Exception):
    """ Custom connection error class """
    ...
    
class Peer:
    def __init__(self, ip, port, pieces_manager, max_blocks, pieces_hashes):
        self.ip = ip
        self.port = port

        self.choked = asyncio.Event() # Starts choked == not set, which blocks on wait()
        self.interested = 0
        self.am_choking = 1
        self.am_interested = 0

        self.bitfield = bitarray.bitarray('0' * pieces_manager.nr_pieces)  # peer's bitfield
        self.pieces_manager = pieces_manager                               # reference to pieces manager 
        self.connection = PeerConnection()                                 # connection state

        self.piece_handler = PieceHandler(max_blocks, pieces_hashes)  # structure with piece buffer

    @property
    def piece_handler(self):
        return self._piece_handler
    
    @piece_handler.setter
    def piece_handler(self, meta_info):
        max_blocks = utils.nr_blocks_in_piece(meta_info)
        pieces_hashes = utils.piece_hashes
        self._piece_handler = PieceHandler

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
        listener_task = asyncio.create_task(self.listener())
        requester_task = asyncio.create_task(self.requester())

        # wait for either task to complete
        done, pending = await asyncio.wait(
            [listener_task, requester_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # cancel any remaining tasks
        for task in pending:
            task.cancel()

        # await all tasks to complete
        print(await asyncio.gather(*pending, return_exceptions=True))
        print(await asyncio.gather(*done, return_exceptions=True))

        raise ConnectionError("hi")

    async def listener(self):
        """ Listens to messages """
        while True:
            try:
                # even if the peer is making us hold, no "have" messages for 2 seconds will timeout
                id, data = await asyncio.wait_for(self.connection.read_message(), 
                                                  timeout=5)
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
                await self.choked.wait()
                # print(f"Requesting {self.ip} piece{piece} and block{self.piece_handler.block}")
                await self.piece_handler.request_piece(piece, self.connection)

        except asyncio.CancelledError:
            return 2
    
    async def handle_message(self, id, data):
        # print(f"Got {id} {self.ip}")
        match id:
            case 0:
                self.choked.clear()
            case 1:
                self.choked.set()
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

        print("GOT BLOCK")
        self.piece_handler.inc_block_count()
        self.piece_handler.add_block(data)
        self.piece_handler.set_fetched_block()
    
    def _correct_piece(self, raw_piece):
        print(raw_piece)
        return struct.unpack(">I", raw_piece)[0] == self.piece_handler.piece
    
    def _correct_block(self, raw_offset):
        print(raw_offset)
        return struct.unpack(">I", raw_offset)[0] == self.piece_handler.block_count * BLOCK_SIZE 

        

class PieceHandler:
    def __init__(self, max_blocks, pieces_hashes):
        self.piece = 0
        self.block_count = 0
        self.max_blocks = max_blocks 
        self.pieces_hashes = pieces_hashes
        self.buffer = b""
        self.fetched = asyncio.Event()
    
    @property
    def max_blocks(self):
        return self._max_blocks
    
    @max_blocks.setter
    def max_blocks(self, meta_info):
        self._max_blocks = utils.nr_blocks_in_piece(meta_info)
        
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

    async def request_piece(self, piece, connection):
        # reset piece handler 
        self._reset(piece)
        # we will request by block index order and simply append to the buffer 
        while self.block_count < self.max_blocks:
            await connection.send_message(protocol.Request(self.piece, self.block_count))
            self.fetched.clear()
            # wait on listener to retrieve the requested piece
            await self.fetched.wait()
            print(f"{self.block_count} - {self.max_blocks}")
        print(f"Got piece {self.piece}!------------------------------------------")
    
    # async def check_hash(self):
    #     return hashlib.sha1(self.buffer).hexdigest() == 


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

