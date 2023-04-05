import math
import bitarray
import asyncio
class PiecesManager:
    def __init__(self, file, nr_pieces, piece_size):
        self.file = file 
        self.nr_pieces = nr_pieces 
        self.piece_size = piece_size 
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
    
    @property
    def piece_size(self):
        return self._piece_size
    
    @piece_size.setter
    def piece_size(self, meta_info):
        self._piece_size = meta_info[b"info"][b"piece length"]
        
    async def initialize(self):
        for i in range(self.nr_pieces):
            await self.pieces_queue.put(i)