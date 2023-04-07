import aiohttp
import bencode
import ipaddress
import struct

from urllib.parse import urlencode

class Tracker:
    def __init__(self, url):
        self.url = url.decode("utf-8") 
        self.interval = 0
        self.http_session = aiohttp.ClientSession()
        self.req_count = 0

    async def request_peers(self, client_id, port, info_hash):
        async with self.http_session.get(self._build_request(client_id, port, info_hash)) as resp:
            if resp.status != 200:
                #logging.debug("Couldn't resolve Tracker")
                return
            #logging.debug("Recived Tracker response")
            response = bencode.loads(await resp.read())
        
        try:
            self.interval = response[b"interval"]
        except KeyError:
            pass

        self.req_count += 1

        return response

    def decode_peers_list(self, raw_str):
        return [(self._decode_ip(raw_str[i:i + 4]),
                    self._decode_port(raw_str[i + 4:i + 6]))
                                for i in range (0, len(raw_str), 6)]

    async def close(self):
        await self.http_session.close()

    def _build_request(self, client_id, port, info_hash):
        params = {
            "info_hash": info_hash,
            "peer_id": client_id,
            "port": port,
            "uploaded": 0,
            "downloaded": 0,
            "left": 0,
            "compact": 1
        }

        return self.url + "?" + urlencode(params)

    def _decode_ip(self, data):
        return str(ipaddress.ip_address(data))
    
    def _decode_port(self, data):
        return struct.unpack(">H", data)[0]


