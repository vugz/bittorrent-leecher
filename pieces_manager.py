import math
import bitarray
import asyncio
class PiecesManager:
    def __init__(self, meta_info):
        self.file = meta_info 
        self.nr_pieces = meta_info 
        self.piece_bitmap = bitarray.bitarray('0' * self.nr_pieces)
        self.pieces_queue = asyncio.Queue() 
    
    @property
    def file(self, meta_info):
        return self._file
    
    @file.setter
    def file(self, meta_info):
        self._file = meta_info[b"info"][b"name"].decode("utf-8")
    
    @property
    def nr_pieces(self):
        return self._nr_pieces
    
    @nr_pieces.setter
    def nr_pieces(self, meta_info):
        self._nr_pieces = math.ceil(
            meta_info[b"info"][b"length"] / meta_info[b"info"][b"piece length"])
        
    async def initialize(self):
        for i in range(self.nr_pieces):
            await self.piece_queue.put(i)