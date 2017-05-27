'''
UDP server and client at the same time.
'''

import asyncore
import os
import struct
import time
from socket import AF_INET, SOCK_DGRAM, socket
from core.becnode import benencode, bendecode
from core.other import construct_message, MESSAGE_IDS, check_addr
from threading import Thread

PIECE_SIZE = 32000

def channel_file(file_, peer):
    '''
    Transmit file to peer by PIECE_SIZE sized bytes pieces.
    '''
    size = os.path.getsize(file_)
    sock = socket(AF_INET, SOCK_DGRAM)
    with open(file_, 'rb') as file_to_send:
        for offset in range(0, size, PIECE_SIZE):
            file_to_send.seek(offset, 0)
            data = file_to_send.read(PIECE_SIZE)
            sock.sendto(construct_message('piece', (file_, data, offset, size)), peer)
            time.sleep(0.01)
    sock.close()

class Peer(asyncore.dispatcher):
    '''
    TCP server listening to all the interfaces. After getting new connection
    it creates new peer object. Also contains list of all peers ever connected.
    '''
    def __init__(self, nickname, port):
        asyncore.dispatcher.__init__(self)
        self.create_socket(AF_INET, SOCK_DGRAM)
        self.set_reuse_addr()
        self.my_nickname = nickname
        self.bind(('', port))
        self.port = port
        self.peers = {}
        self.banlist = {}
        self.message_callback = []
        self.pending_files = {}
        self.message_handler = {}
        self.message_handler[MESSAGE_IDS['nickname']] = lambda e, x: self.add_peer(e, x)
        self.message_handler[MESSAGE_IDS['handshake']] = lambda e, x: self.process_handshake(e, x)
        self.message_handler[MESSAGE_IDS['peer-list']] = lambda e, x: self.fill_peer_list(e, x)
        self.message_handler[MESSAGE_IDS['nick']] = lambda e, x: self.change_nickname(e, x)
        self.message_handler[MESSAGE_IDS['piece']] = lambda e, x: self.write_piece(e)
        self.message_handler[MESSAGE_IDS['file']] = lambda e, x: self.other_messages(e, x, MESSAGE_IDS['file'])
        self.message_handler[MESSAGE_IDS['plain-text']] = lambda e, x: self.other_messages(e, x, MESSAGE_IDS['plain-text'])
        self.message_handler[MESSAGE_IDS['whisp']] = lambda e, x: self.other_messages(e, x, MESSAGE_IDS['whisp'])
        self.message_handler[MESSAGE_IDS['close']] = lambda e, x: self.other_messages(e, x, MESSAGE_IDS['close'])
        self.message_handler[MESSAGE_IDS['request']] = lambda e, x: self.other_messages(e, x, MESSAGE_IDS['request'])

    def handle_read(self):
        msg, addr = self.socket.recvfrom(32768)
        if msg:
            if not msg[0] == MESSAGE_IDS['piece']:
                payload = msg[1:].decode('utf8')
            else:
                payload = msg[1:]
            try:
                self.message_callback += self.message_handler[msg[0]](payload, addr)
            except KeyError:
                pass

    def writable(self):
        return False

    def send_close(self):
        '''
        Send peers messages indicating that you have left the room.
        '''
        for peer in self.peers.keys():
            self.socket.sendto(construct_message('close'), peer)
        self.peers = {}

    def add_peer(self, payload, addr):
        '''
        Add peer to peer-list of interface.
        '''
        message_callback = []
        self.peers[addr] = payload
        self.banlist[self.peers[addr]] = False
        message_callback.append(('add', self.peers[addr]))
        message_callback.append(('msg', self.peers[addr]+' has joined the room.'))
        return message_callback

    def process_handshake(self, payload, addr):
        '''
        When handshake received, we must send peer-list in response.
        '''
        message_callback = []
        peer_list = dict(list(self.peers.items()) + [((), self.my_nickname.nickname)])
        self.peers[addr] = payload
        self.banlist[self.peers[addr]] = False
        message_callback.append(('add', self.peers[addr]))
        message_callback.append(('msg', self.peers[addr]+' has joined the room.'))
        self.socket.sendto(construct_message('peer-list', benencode(peer_list)), addr)
        return message_callback

    def fill_peer_list(self, payload, addr):
        '''
        Fill peer-list and connect to every peer from list.
        '''
        message_callback = []
        orig_peer_list = bendecode(payload)
        if () in orig_peer_list:
            peer_list = orig_peer_list.copy()
            peer_list[addr] = peer_list[()]
            del peer_list[()]
            peer_list = benencode(peer_list)
            for peer in [x for x in self.peers.keys() if x != addr]:
                self.socket.sendto(construct_message('peer-list', peer_list), peer)
        else:
            for nickname in orig_peer_list.values():
                message_callback.append(('msg', nickname+' has joined the room.'))
        for nickname in orig_peer_list.values():
            message_callback.append(('add', nickname))
        self.connect_to_peers(orig_peer_list, addr)
        return message_callback

    def change_nickname(self, payload, addr):
        '''
        Change nickname of some peer.
        '''
        message_callback = []
        message_callback.append(('msg', self.peers[addr]+
                                 ' has changed his nickname to '+payload+'.'))
        message_callback.append(('nick', self.peers[addr], payload))
        self.banlist[payload] = self.banlist[self.peers[addr]]
        del self.banlist[self.peers[addr]]
        self.peers[addr] = payload
        return message_callback

    def write_piece(self, payload):
        '''
        Insert PIECE_SIZE sized bytes piece into a file.
        '''
        message_callback = []
        filename = payload[1:payload[0]+1].decode('utf8')
        data_length = struct.unpack('!I', payload[1+payload[0]:5+payload[0]])[0]
        data = payload[5+payload[0]:5+payload[0]+data_length]
        offset, size = struct.unpack('!II', payload[-8:])
        if not os.path.exists(self.pending_files[filename]):
            open(self.pending_files[filename], 'wb').close()
        path = self.pending_files[filename]
        with open(path, 'rb+') as file_:
            file_.seek(offset, 0)
            file_.write(data)
            if size - PIECE_SIZE <= offset:
                message_callback.append(('dload', filename, '100'))
                message_callback.append(('msg', os.path.basename(path)+
                                         ' was succesfully downloaded.'))
            else:
                message_callback.append(('dload', filename,
                                         str(round(((offset+PIECE_SIZE)/size)*100, 2))))
        return message_callback

    def other_messages(self, payload, addr, msg_id):
        '''
        Handle messages that don't need separate function.
        '''
        message_callback = []
        if msg_id == MESSAGE_IDS['file']:
            message_callback.append(('file', self.peers[addr]+' has sent file. '
                                     'Click to download. ', payload, addr))
        elif msg_id == MESSAGE_IDS['request']:
            Thread(target=lambda: channel_file(payload, addr)).start()
        elif msg_id == MESSAGE_IDS['close']:
            message_callback.append(('del', self.peers[addr]))
            del self.peers[addr]
        elif msg_id == MESSAGE_IDS['whisp']:
            if not self.banlist[self.peers[addr]]:
                message_callback.append(('msg', self.peers[addr]+' (whisp): '+payload))
        elif msg_id == MESSAGE_IDS['plain-text']:
            if not self.banlist[self.peers[addr]]:
                message_callback.append(('msg', self.peers[addr]+': '+payload))
        return message_callback

    def send_request(self, file_to_request, peer, file_to_save):
        '''
        Send peer a file request. Then peer will send it to us.
        '''
        self.pending_files[file_to_request] = file_to_save
        self.socket.sendto(construct_message('request', file_to_request), peer)

    def send_file(self, file_):
        '''
        Send peers link to file.
        '''
        for peer in self.peers.keys():
            self.socket.sendto(construct_message('file', file_), peer)

    def ban(self, nickname):
        '''
        Ban peer. We won't be able to read his messages until we unban him.
        '''
        if nickname in self.banlist:
            self.banlist[nickname] = True
        else:
            raise KeyError

    def unban(self, nickname):
        '''
        Unban peer.
        '''
        if nickname in self.banlist:
            self.banlist[nickname] = False
        else:
            raise KeyError

    def join_room(self, addr):
        '''
        Send handshake to one member of room we want to join to.
        '''
        if check_addr(addr):
            handshake = construct_message('handshake', self.my_nickname.nickname)
            self.socket.sendto(handshake, (addr.split(':')[0], int(addr.split(':')[1])))
        else:
            self.message_callback.append(('msg', 'Invalid address.'))

    def send_message(self, message, addr):
        '''
        Send message to peer with given ip address.
        '''
        self.socket.sendto(message, addr)

    def connect_to_peers(self, peer_list, source_addr):
        '''
        When someone has joined room, he have to join all the peers, not just one.
        A person who he joined to sends him list of all peers in response.
        Then this someone should connect to every peer from list.
        This function does it.
        '''
        for addr, nickname in peer_list.items():
            if not addr:
                self.peers[source_addr] = nickname
                self.banlist[nickname] = False
                continue
            message = construct_message('nickname', self.my_nickname.nickname)
            self.socket.sendto(message, addr)
            self.peers[addr] = nickname
            self.banlist[nickname] = False

    def get_peer_by_nick(self, nickname):
        '''
        Return ip address of peer with given nickname.
        '''
        try:
            return [addr for addr, nick in self.peers.items() if nick == nickname][0]
        except IndexError:
            return None

    def get_callback(self):
        '''
        This function is always called by chat interface. It returns all
        messages received since the last check.
        '''
        temp = self.message_callback
        self.message_callback = []
        return temp

def loop():
    '''
    Start asyncore loop with timeout set to 3 seconds.
    '''
    asyncore.loop(3)

def close_all():
    '''
    Close all the sockets created.
    '''
    asyncore.close_all()
