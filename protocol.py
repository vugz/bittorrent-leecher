import struct

class Handshake:
    def __new__(self, client_id, info_hash):
        return struct.pack(">B19s8x20s20s", 19, b"BitTorrent protocol", info_hash, client_id.encode())