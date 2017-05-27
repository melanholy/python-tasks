'''
Utility functions and classes.
'''

import struct
import re
from socket import AF_INET, SOCK_DGRAM, socket

MESSAGE_IDS = {
    'nickname': 0,
    'plain-text': 1,
    'handshake': 2,
    'peer-list': 3,
    'whisp': 4,
    'close': 5,
    'nick': 6,
    'file': 7,
    'request': 8,
    'piece': 9
}
SMILEYS = ['smile', 'sad', 'pirate', 'wall', 'dwi', 'angry', 'cool', 'laugh',
           'vomit', 'sos', 'surprise', 'dunno']
SMILEREGEX = re.compile(r':[^: ]+:')

def get_ip_addr():
    '''
    Return ip address of machine if connected to network.
    Else return string unknown.
    '''
    try:
        return [(s.connect(('8.8.8.8', 80)), s.getsockname()[0], s.close())
                for s in [socket(AF_INET, SOCK_DGRAM)]][0][1]
    except OSError:
        return 'unknown'

def construct_message(type_, msg=''):
    '''
    Construct a message used for communications between peers.
    '''
    try:
        if type_ != 'piece':
            return struct.pack('!B', MESSAGE_IDS[type_])+bytes(msg, 'utf8')
        else:
            return struct.pack('!BB', MESSAGE_IDS[type_], len(bytes(msg[0], 'utf8')))+ \
                   bytes(msg[0], 'utf8')+struct.pack('!I', len(msg[1]))+msg[1]+ \
                   struct.pack('!I', msg[2])+struct.pack('!I', msg[3])
    except KeyError:
        raise TypeError('Wrong message ID.')

def get_smile_positions(message):
    '''
    Return list of tuples containing start and end position of
    every smile in message.
    '''
    smile_positions = []
    last_end = -1
    for match in SMILEREGEX.finditer(message):
        if message[match.span()[0]+1:match.span()[1]-1] in SMILEYS \
           and match.span()[0] != last_end:
            smile_positions.append(match.span())
            last_end = match.span()[1] - 1
    return smile_positions

def check_addr(addr):
    '''
    Check if given is valid.
    '''
    if not re.match(r'(\d{1,3}\.){3}\d{1,3}:\d+', addr):
        return False
    return True

class Nickname(object):
    '''
    A class for nickname. Consists of private variable _nickname and its getter and setter.
    '''
    def __init__(self, nickname):
        self._nickname = nickname

    @property
    def nickname(self):
        '''
        Getter for nickname.
        '''
        return self._nickname

    @nickname.setter
    def nickname(self, nickname):
        '''
        Setter for nickname.
        '''
        if ' ' in nickname or '/' in nickname:
            raise ValueError('Nickname should not contain spaces and slashes.')
        self._nickname = nickname
