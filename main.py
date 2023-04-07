import bencode
import asyncio
import random
import struct
import ipaddress
import os
import binascii
import hashlib
import logging
import bitarray
import math
import traceback

from tracker import Tracker

from peer import Peer
from peer import ConnectionError
from pieces_manager import PiecesManager 

from config import BLOCK_SIZE


class Vutor:
    """ We could have a metainfo dataclass or similar, might
    be refactored into that in the future, for now
    this class will serve also as that

    This might seem weird, but here we simply pass the meta_info once
    decoded to the setter function to set the values necessary for the client,
    it might look weird but it is tidier and visually more concise.

    Every attribute is sequentially initialized, often times relying on the previous
    """

    def __init__(self, torrent, *, max_peers=35, port=6881):
        self.meta_info = torrent                  # decoded meta-info dict
        self.file = self.meta_info                # file name
        self.piece_size = self.meta_info 
        self.nr_pieces = self.meta_info           # total nr of pieces
        self.nr_blocks_in_piece = \
                    self.piece_size / BLOCK_SIZE  # nr of blocks in piece

        self.pieces_hashes = self.meta_info       # tuple with the hashes of all pieces
        self.info_hash = self.meta_info           # hash of info dict 

        self.peers = set()                # scheduled or active peers
        self.max_peers = max_peers        # max peers 
        self.pcq_peers = asyncio.Queue()  # peers producer consumer queue

        self.port = port 
        self.client_id = "-VU0001-" + binascii.hexlify(os.urandom(6)).decode("utf-8")

        self.pieces_manager = PiecesManager(self.file, self.nr_pieces, self.piece_size) 
    
    @property
    def meta_info(self):
        return self._meta_info

    @meta_info.setter
    def meta_info(self, file):
        with open(file, "rb") as fp:
            self._meta_info = bencode.load(fp)
    
    @property
    def file(self):
        return self._file
    
    @file.setter
    def file(self, meta_info):
        self._file = meta_info[b"info"][b"name"].decode("utf-8")

    @property
    def piece_size(self):
        return self._piece_size
    
    @piece_size.setter
    def piece_size(self, meta_info):
        self._piece_size = meta_info[b"info"][b"piece length"]
    
    @property
    def nr_pieces(self):
        return self._nr_pieces
    
    @nr_pieces.setter
    def nr_pieces(self, meta_info):
        self._nr_pieces = math.ceil(meta_info[b"info"][b"length"] / self.piece_size) 

    @property
    def info_hash(self):
        return self._info_hash
    
    @info_hash.setter
    def info_hash(self, meta_info):
        self._info_hash = hashlib.sha1(bencode.dumps(meta_info[b"info"])).digest() 
   
    @property
    def pieces_hashes(self):
        return self._pieces_hashes
    
    @pieces_hashes.setter
    def pieces_hashes(self, meta_info):
        raw_hash_str = meta_info[b"info"][b"pieces"]
        self._pieces_hashes = [raw_hash_str[20 * i: 20 + 20*i].hex() for i in range(self.nr_pieces)]

    @property
    def port(self):
        return self._port
    
    @port.setter
    def port(self, value):
        if value < 0 and value > 2**16:
            raise ValueError(f"Port number must be in range {0} to {2**16}")
        self._port = value
    

    async def run(self):
        await self.pieces_manager.initialize()

        tracker_coro = asyncio.create_task(self.tracker_worker_coro())

        workers = [
            asyncio.create_task(self.worker_coro())
            for _ in range(self.max_peers)
        ]

        await self.pieces_manager.pieces_queue.join()
        print(self.pieces_manager.pieces_queue.qsize())
        print("End reached?!")
        print(self.pieces_manager.piece_bitmap)
        for i in range(self.nr_pieces):
            if self.pieces_manager.piece_bitmap[i].state != 1:
                print(f"Failed piece {i}")
        
        print("Done")
        for _ in self.pieces_manager.piece_bitmap:
            print(_.state, end="")

        tracker_coro.cancel()
        for worker in workers:
            worker.cancel()
        

    async def tracker_worker_coro(self):
        tracker = Tracker(self.meta_info[b"announce"])

        while True:
            try:
                logging.info("Requesting Tracker")
                resp = await tracker.request_peers(self.client_id, self.port, self.info_hash)
                peer_list = tracker.decode_peers_list(resp[b"peers"])

                for peer in peer_list:
                    if {peer} - self.peers:
                        # add to peer lookup set
                        self.peers.add(peer)
                        # add to peers queue
                        await self.pcq_peers.put(peer)
                
                # a lot of good peers are not sent in the first requests
                if tracker.req_count > 1000:
                    await asyncio.sleep(tracker.interval)
                else:
                    await asyncio.sleep(10)

            except asyncio.CancelledError:
                await tracker.close()
                return
    
    async def worker_coro(self):
        try:
            while True:
                # get peer from Queue
                peer = await self.pcq_peers.get()

                # instantiate peer 
                print(peer)
                peer = Peer(peer[0], peer[1], self.pieces_manager, self.nr_blocks_in_piece, self.pieces_hashes)

                # connect to peer
                try:
                    await peer.connect(self.client_id, self.info_hash)
                    logging.info(f"Connected to peer {peer.ip}:{peer.port}")
                    await peer.run_peer()
                except Exception as e:
                    logging.debug(str(e))
                    # remove from peers lookup set
                    peer_tup = (peer.ip, peer.port)
                    self.peers.remove(peer_tup)
                    continue

                await asyncio.sleep(60)

        except asyncio.CancelledError:
            return


if __name__ == '__main__':
    # this does not support seeding, so the port is irrelevant
    client = Vutor(os.sys.argv[1], max_peers=45, port=6881)
    print(client.file)
    asyncio.run(client.run(), debug=True)



