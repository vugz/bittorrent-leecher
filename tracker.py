import asyncio
import aiohttp
import hashlib
import bencode

from urllib.parse import urlencode

class Tracker:
    def __init__(self, meta_info):
        self.url = meta_info[b"announce"].decode("utf-8")
        self.info_hash = meta_info[b"info"]
        self.interval = 0
        self.http_session = aiohttp.ClientSession()
    
    @property
    def info_hash(self):
        return self._info_hash
    
    @info_hash.setter
    def info_hash(self, value):
        self._info_hash = hashlib.sha1(bencode.dumps(value)).digest() 


    async def request_peers(self, client_id, port):
        async with self.http_session.get(self._build_request(client_id, port)) as resp:
            if resp.status != 200:
                print("Coulnd't resolve Tracker")
            response = bencode.loads(await resp.read())
        
        try:
            self.interval = response[b"interval"]
        except KeyError:
            pass

        return response
    
    async def close(self):
        await self.http_session.close()
    
    def _build_request(self, client_id, port):
        params = {
            "info_hash": self.info_hash,
            "peer_id": client_id,
            "port": port,
            "uploaded": 0,
            "downloaded": 0,
            "left": 0,
            "compact": 1
        }

        return self.url + "?" + urlencode(params)
