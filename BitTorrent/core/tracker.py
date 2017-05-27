'''
A class representing Tracker.
'''

import time
import httplib2
import re
import struct
import random
from core.config import PORT
from core.becnode import bendecode
from urllib.parse import urlencode
from socket import socket, AF_INET, SOCK_DGRAM, timeout as SockTimeout, gaierror

MESSAGE_ORDER = [
    ('info_hash', ''), ('peer_id', ''), ('downloaded', '!Q'),
    ('left', '!Q'), ('uploaded', '!Q'), ('event', '!I'),
    ('ip', '!I'), ('key', '!I'), ('numwant', '!I'), ('port', '!H')
]
EVENTS = {'started': 2, 'stopped': 3}

class Tracker(object):
    '''
    A wrapper-object for torrent-tracker.
    '''
    def __init__(self, url, payload):
        self.url = url
        self.refresh_time = 0
        self.last_announce = 0
        self.payload = payload.copy()
        self.reachable = True
        self.udp_connected = False
        self.connection_id = b''

    def announce(self):
        '''
        Call announce method depending on urls types.
        '''
        return self.announce_udp() if self.url[:3] == 'udp' else self.announce_tcp()

    def announce_tcp(self):
        '''
        Send HTTP GET request to the tracker. Return decoded response.
        '''
        query = urlencode(self.payload)
        url = self.url+'&'+query if '?' in self.url else self.url+'?'+query
        try:
            resp = httplib2.Http().request(url)[1]
        except httplib2.ServerNotFoundError:
            self.reachable = False
            return b''
        if self.payload['event'] == 'stopped':
            return b''
        del self.payload['event']
        response = bendecode(resp.decode("latin1"))
        self.refresh_time = response['interval']
        self.last_announce = time.time()
        if not 'peers' in response:
            return None
        return bytes(response['peers'], 'latin1')

    def announce_udp(self):
        '''
        Send announce to the trackers that use UDP protocol.
        '''
        host = re.search(r'://(.+?):', self.url).group(1)
        port = int(re.search(r'.+?:.+?:(.+)', self.url).group(1))
        sock = socket(AF_INET, SOCK_DGRAM)
        with sock:
            sock.bind(('', PORT))
            sock.settimeout(2)
            try:
                sock.sendto(
                    struct.pack('!QII', 4497486125440, 0, random.randint(1, 10000)),
                    (host, port)
                )
            except (SockTimeout, gaierror):
                self.reachable = False
                return b''
            try:
                resp = sock.recvfrom(1024)
            except SockTimeout:
                self.reachable = False
                return b''
            self.connection_id = resp[0][-8:]
            announce = self.connection_id + struct.pack(
                '!II', 1, random.randint(1, 10000)
            )
            for key, size in MESSAGE_ORDER:
                value = self.payload[key]
                if isinstance(value, int):
                    value = struct.pack(size, value)
                if isinstance(value, str):
                    value = struct.pack(size, EVENTS[value])
                announce += value
            sock.sendto(announce, (host, port))
            if self.payload['event'] == 'stopped':
                return b''
            del self.payload['event']
            try:
                resp = sock.recvfrom(1024)
            except SockTimeout:
                self.reachable = False
                return b''
            resp = resp[0]
            if len(resp) < 20 or resp[0] == 3:
                self.reachable = False
                return b''
            self.refresh_time = struct.unpack('!I', resp[8:12])[0]
            self.last_announce = time.time()
            return resp[20:len(resp)+1]

    def can_reannounce(self):
        '''
        Determine whether you can send GET request to the tracker or not.
        '''
        return (self.refresh_time == 0 or
                time.time() - self.last_announce > self.refresh_time) \
                and self.reachable

    def get_peers(self):
        '''
        Send announce to the tracker and return list of tuples
        containing peers' ip addresses and ports.
        '''
        addresses = []
        plist = self.announce()
        if len(plist) == 0:
            return []
        if plist is None:
            return []
        for i in range(0, len(plist), 6):
            ip_addr = '{}.{}.{}.{}'.format(
                plist[i+0], plist[i+1],
                plist[i+2], plist[i+3]
            )
            port = plist[i+4]*256+plist[i+5]
            addresses.append((ip_addr, port))
        return addresses

    def update_payload(self, params):
        '''
        Change the payload that will be sent with next GET request.
        '''
        self.payload.update(params)
