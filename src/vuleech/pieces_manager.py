import math
import asyncio
import aiofiles
import os
import logging
import aiofiles

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
        self.gotten_pieces = 0
        self.factor = math.ceil(nr_pieces / 100)
        
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
    
    def put_piece(self, index):
        """ Put back a piece in the Queue """
        self.piece_bitmap[index].state = Piece.MISSING
    
    async def save_piece(self, piece, index):
        """ Save piece to disk """
        async with aiofiles.open(self.file, mode="rb+") as fp:
            await fp.seek(index * self.piece_size, 0)
            await fp.write(piece)
            await fp.flush()

        logging.info(f"Sucessfully retrieved peice {index}")
        
        self.gotten_pieces += 1

        if not self.gotten_pieces % self.factor:
            # TODO make it a ncurses client?
            done = int(math.ceil(self.gotten_pieces * 100 / self.nr_pieces % 100))
            if not done:
                done = 100
            print(f"({done}%) " + "[" +"*" *done + "-" * (100 - done) + "]")

        self.piece_bitmap[index].state = Piece.COMPLETE
        self.pieces_queue.task_done()

        

