import bencode
import asyncio
import random
import struct
import ipaddress
import os
import binascii

from tracker import Tracker

class Vutor:
    def __init__(self, torrent, *, max_peers=35, port=6881):
        self.file = torrent 
        self.max_peers = max_peers 
        self.pcq_peers = asyncio.Queue()
        self.meta_info = torrent 
        self.port = port 
        self.client_id = "-VU0001-" + binascii.hexlify(os.urandom(6)).decode("utf-8")
        self.peers = set()
    
    @property
    def meta_info(self):
        return self._meta_info

    @meta_info.setter
    def meta_info(self, file):
        with open(file, "rb") as fp:
            self._meta_info = bencode.load(fp)
    
    @property
    def port(self):
        return self._port
    
    @port.setter
    def port(self, value):
        if value < 0 and value > 2**16:
            raise ValueError(f"Port number must be in range {0} to {2**16}")
        self._port = value
    

    async def run(self):
        tracker_coro = asyncio.create_task(self.tracker_worker_coro())

        workers = [
            asyncio.create_task(self.worker_coro())
            for _ in range(self.max_peers)
        ]

        await asyncio.sleep(15) 

        tracker_coro.cancel()
        for worker in workers:
            worker.cancel()

    async def tracker_worker_coro(self):
        tracker = Tracker(self.meta_info)

        while True:
            try:
                print("Requesting Tracker")
                resp = await tracker.request_peers(self.client_id, self.port)
                peer_list = self.decode_peers_list(resp[b"peers"])

                for peer in peer_list:
                    if {peer} - self.peers:
                        self.peers.add(peer)
                        await self.pcq_peers.put(peer)
                
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                await tracker.close()
                return
    
    async def worker_coro(self):
        try:
            while True:
                peer = await self.pcq_peers.get()
                print(f"Handling peer {peer}")
                await asyncio.sleep(20)
        except asyncio.CancelledError:
            return

    def decode_peers_list(self, raw_str):
        return [(self._decode_ip(raw_str[i:i+4]),
                    self._decode_port(raw_str[i+4:i+6]))
                                for i in range (0, len(raw_str), 6)]

    def _decode_ip(self, data):
        return str(ipaddress.ip_address(data))
    
    def _decode_port(self, data):
        return struct.unpack(">H", data)[0]



if __name__ == '__main__':
    client = Vutor("debian.iso.torrent", max_peers=100, port=8421)
    asyncio.run(client.run(), debug=True)
