import math
import bitarray
import asyncio
import aiofiles
import os

class PiecesManager:
    def __init__(self, file, nr_pieces, piece_size):
        self.file = file 
        self.nr_pieces = nr_pieces 
        self.piece_size = piece_size 
        self.piece_bitmap = bitarray.bitarray('0' * self.nr_pieces)
        self.pieces_queue = asyncio.Queue() 
        
    async def initialize(self):
        # create the output file
        if not os.path.exists(self.file):
            open(self.file, "wb+")

        # initialize queue
        for i in range(self.nr_pieces):
            await self.pieces_queue.put(i)
    
    async def get_piece(self):
        """ Get a piece from the Queue """
        await self.pieces_queue.get()
    
    async def put_piece(self, index):
        """ Put back a piece in the Queue """
        await self.pieces_queue.put(index)
        self.pieces_queue.task_done()

    
    async def save_piece(self, piece, index):
        """ Save piece to disk """
        async with aiofiles.open(self.file, mode="rb+") as fp:
            await fp.seek(index * self.piece_size, 0)
            await fp.write(piece)
            await fp.flush()

        print(f"Sucessfully retrieved peice {index}")
        print(self.pieces_queue.qsize())
        self.pieces_queue.task_done()

        

