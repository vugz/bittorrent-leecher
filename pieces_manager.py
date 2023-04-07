import math
import bitarray
import asyncio
import aiofiles
import os
from enum import Enum 

class Piece:
    MISSING = 0
    COMPLETE = 1
    PENDING = 2 

    def __init__(self):
        self.state = self.MISSING

class PiecesManager:
    def __init__(self, file, nr_pieces, piece_size):
        self.file = file 
        self.nr_pieces = nr_pieces 
        self.piece_size = piece_size 
        self.piece_bitmap = [Piece() for _ in range(self.nr_pieces)]
        self.pieces_queue = asyncio.Queue() 
        
    async def initialize(self):
        # create the output file
        if not os.path.exists(self.file):
            open(self.file, "wb+")

        # initialize queue
        for _ in range(self.nr_pieces):
            await self.pieces_queue.put(_)
    
    def get_piece(self, bitfield):
        """ Get a piece from the Queue """
        for i in range(len(bitfield)):
            if bitfield[i] and not self.piece_bitmap[i].state:
                self.piece_bitmap[i].state = Piece.PENDING
                return i
        
        return None
    
    async def put_piece(self, index):
        """ Put back a piece in the Queue """
        self.piece_bitmap[index].state = Piece.MISSING
    
    async def save_piece(self, piece, index):
        """ Save piece to disk """
        with open(self.file, mode="rb+") as fp:
            fp.seek(index * self.piece_size, 0)
            fp.write(piece)

        print(f"Sucessfully retrieved peice {index}")
        self.piece_bitmap[index].state = Piece.COMPLETE
        print("TASK_DONE_CALL")
        self.pieces_queue.task_done()
        for _ in self.piece_bitmap:
            print(_.state, end="")
        print("")

        

