'''
A module that stores all the constants that client needs.
'''

import string
import random
from configparser import ConfigParser

CONFIG = ConfigParser()
CONFIG.read('config.ini')
MAX_REQUEST = int(CONFIG['CONSTANTS']['MaxRequest'])
PEER_TIMEOUT = int(CONFIG['DEFAULT']['PeerTimeOut'])
PORT = int(CONFIG['DEFAULT']['Port'])
PEER_ID = bytes(
    CONFIG['DEFAULT']['PeerId'] +
    ''.join(random.choice(string.ascii_uppercase + string.digits)
            for x in range(12)),
    'utf-8'
)
KEY = random.randint(1, 10000)
MAX_PEERS = int(CONFIG['DEFAULT']['MaxPeers'])
UPLOAD_PEERS = 20
ENDGAME_PERCENT = float(CONFIG['DEFAULT']['EndgamePercent'])
