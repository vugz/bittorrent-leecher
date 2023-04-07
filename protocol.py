# Not all messages are included here because the seeding functionality is not implemented (yet)
import struct

CHOKE = 0
UNCHOKE = 1
INTERESTED = 2
NOT_INTERESTED = 3
HAVE = 4
BITFIELD = 5
REQUEST = 6 
PIECE = 7
CANCEL = 8

from config import BLOCK_SIZE

# Protocol messages take are of type <len><id><payload> where the payload might not exist
# The ``len`` prefix is a four byte big-endian value and `id`` is a single decimal byte

class Handshake:
    """ Handshake request
    format: <pstrlen><pstr><reserved><info_hash><peer_id>
    
    pstrlen: byte specifying message length
    pstr: string identifying the protoocl
    reserved: 8 reserved bytes
    info_hash: SHA1 hash of the info key in the meta-info dictionary
    peer_id: 20-byte string identifying the id of this client
    """
    def __new__(self, client_id, info_hash):
        return struct.pack(">B19s8x20s20s", 19, b"BitTorrent protocol", info_hash, client_id.encode())

class KeepAlive:
    """ Sent to prevent timeout from peer

    format: <len=0000>
    """
    def __new__(self):
        return struct.pack(">I", 0)

class Choke:
    """ Choke peer 
    
    format: <len=0001><id=0>
    """
    def __new__(self):
        return struct.pack(">I", 1, CHOKE)

class Unchoke:
    """ Unchoke peer

    format: <len=0001><id=1>
    """
    def __new__(self):
        return struct.pack(">I", 1, UNCHOKE)

class Interested:
    """ Notifies peer of interest in a piece

    format: <len=0001><id=2>
    """
    def __new__(self):
        return struct.pack(">IB", 1, INTERESTED)

class NotInterested:
    """ Notifies peer that there is no longer interest 
    
    format: <len=0001><id=3>
    """
    def __new__(self):
        return struct.pack(">IB", 1, NOT_INTERESTED)
class Request:
    """ Request a block from peer 
    
    format: <len=0013><id=6><index><begin><length>
    """
    def __new__(self, index, offset):
        """
        :index: index of the piece
        :block: offset within piece (identified by block index)
        """
        # We request 16KiB 
        # see this interesting drama https://wiki.theory.org/BitTorrentSpecification#request:_.3Clen.3D0013.3E.3Cid.3D6.3E.3Cindex.3E.3Cbegin.3E.3Clength.3E)
        return struct.pack(">IBIII", 13, REQUEST, index, offset * BLOCK_SIZE, BLOCK_SIZE)

class Cancel:
    """ Cancel previous made request

    format: <len=0013><id=8><index><begin><length>
    """
    def __new__(self, index, offset):
        return struct.pack(">IBIII", 13, CANCEL, index, offset * BLOCK_SIZE, BLOCK_SIZE)