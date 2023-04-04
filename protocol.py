# Not all messages are included here because the seeding functionality is not implemented (yet)
import struct

class Handshake:
    def __new__(self, client_id, info_hash):
        return struct.pack(">B19s8x20s20s", 19, b"BitTorrent protocol", info_hash, client_id.encode())

class KeepAlive:
    def __new__(self):
        return struct.pack(">I", 0)

class Interested:
    def __new__(self):
        return struct.pack(">IB", 1, 2)

class NotInterested:
    def __new__(self):
        return struct.pack(">IB", 1, 3)

class Request:
    def __new__(self, index, offset):
        return struct.pack(">IBIII", 13, 6, index, offset * 2**14, 2**14)

class Cancel:
    def __new__(self, index, offset):
        return struct.pack(">IBIII", 13, 8, index, offset * 2**14, 2**14)