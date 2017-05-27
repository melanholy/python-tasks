'''
A class representing peer. Receives and sends messages.
'''

import struct
import time
import threading
import random
from select import select
from socket import socket, SOL_SOCKET, SO_REUSEADDR, SO_ERROR
from collections import OrderedDict
from errno import EINPROGRESS, EALREADY, EWOULDBLOCK
from core.config import MAX_REQUEST, PEER_TIMEOUT, PORT

HANDSHAKE_LEN = 68
MESSAGES = {
    'keep-alive': b'\x00\x00\x00\x00',
    'choke': b'\x00\x00\x00\x01\x00',
    'unchoke': b'\x00\x00\x00\x01\x01',
    'interested': b'\x00\x00\x00\x01\x02',
    'not-interested': b'\x00\x00\x00\x01\x03',
    'have': b'\x00\x00\x00\x05\x04',
    'request': b'\x00\x00\x00\r\x06',
    'cancel': b'\x00\x00\x00\r\x08',
    'bitfield': b'\x05',
    'piece': b'\x07'
}

class SocketHandler():
    '''
    Call select() for all sockets of Server and Peer instances created in
    currently executing program.
    '''
    socket_map = {}
    alive = True

    @staticmethod
    def loop():
        '''
        Infite loop calling select().
        '''
        while SocketHandler.alive:
            filenos = list(SocketHandler.socket_map.keys())
            if filenos == []:
                time.sleep(0.001)
                continue
            for fileno in filenos:
                try:
                    if not SocketHandler.socket_map[fileno].alive:
                        del SocketHandler.socket_map[fileno]
                except KeyError:
                    pass
            try:
                SocketHandler.handle_sockets(*select(filenos, filenos, filenos, 3))
            except OSError:
                pass
            time.sleep(0.001)

    @staticmethod
    def handle_sockets(read, write, exc):
        '''
        Call appropriate methods for sockets.
        '''
        for sock in read:
            obj = SocketHandler.socket_map.get(sock)
            if isinstance(obj, Server):
                obj.accept()
            elif isinstance(obj, Peer):
                obj.recv()
        for sock in write:
            obj = SocketHandler.socket_map.get(sock)
            if isinstance(obj, Peer):
                obj.send()
        for sock in exc:
            obj = SocketHandler.socket_map.get(sock)
            if obj is not None:
                obj.close()

    @staticmethod
    def close():
        '''
        Stop loop().
        '''
        for obj in list(SocketHandler.socket_map.values()):
            obj.close()
        SocketHandler.alive = False

def construct_message(type_, *args):
    '''
    Construct a message used for communications between peers.
    '''
    message = bytearray()
    if len(MESSAGES[type_]) > 3:
        message += MESSAGES[type_]
    else:
        message += struct.pack('!I', args[0])+MESSAGES[type_]
        args = args[1:]
    for arg in args:
        try:
            message += struct.pack('!I', arg)
        except struct.error:
            message += arg
    return message

class Server():
    '''
    A socket listening to incoming connections from peers.
    '''
    def __init__(self, port_offset):
        self.sock = socket()
        while True:
            self.port = random.randint(32000, 33000)
            try:
                self.sock.bind(('', self.port))
                break
            except OSError:
                pass
        self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        
        self.sock.listen(5)
        self.sock.setblocking(0)
        SocketHandler.socket_map[self.sock.fileno()] = self
        self.peers = []
        self.alive = True

    def close(self):
        '''
        Close socket.
        '''
        self.alive = False
        del SocketHandler.socket_map[self.sock.fileno()]
        self.sock.close()

    def accept(self):
        '''
        Accept incoming connection and add new socket to peer queue.
        '''
        try:
            sock = self.sock.accept()
        except OSError:
            self.close()
            return
        self.peers.append(sock[0])

    def take_number_of_peers(self, number):
        '''
        Take number of peers from peer queue.
        '''
        temp = self.peers[:number]
        self.peers = self.peers[number:]
        return temp

class Peer():
    '''
    A class representing peer.
    '''
    def __init__(self, handshake, upload=False, sock=None):
        self.write_buffer = bytearray()
        self.current_msg = b''
        self.handshake = handshake
        self.piece_buffer = {}
        self.connected = False
        self.unchoked = False
        self.completed_pieces = {}
        self.handshaked = False
        self.lock = threading.Lock()
        self.endgame = False
        self.requests = 0
        self.alive = True
        self.connect_time = time.time()
        self.current_msg_len = 0
        self.bitfield = {}
        self.timer = 0
        self.a = 1
        self.downloaded = 0
        self.upload = upload
        self.need_bitfield = False
        self.need_piece = {}
        self.max_requests = 1
        self.frozen = False
        self.sock = sock
        if self.sock is None:
            self.sock = socket()
        self.sock.setblocking(0)
        SocketHandler.socket_map[self.sock.fileno()] = self

    def close(self):
        '''
        Close socket.
        '''
        self.alive = False
        try:
            del SocketHandler.socket_map[self.sock.fileno()]
        except KeyError:
            pass
        self.sock.close()

    def recv(self):
        '''
        Receive messages from peer.
        '''
        if not self.connected:
            self.check_connection()
        try:
            stream = bytearray(self.sock.recv(MAX_REQUEST))
        except (ConnectionAbortedError, ConnectionResetError):
            self.close()
            return
        if self.timer and self.downloaded and not self.frozen:
            self.max_requests = round((self.downloaded/(time.time()-self.timer))/MAX_REQUEST)
            if not self.max_requests:
                self.max_requests = 1
        if stream:
            messages = self.parse_stream(stream)
            if messages:
                self.handle_messages(messages)

    def send(self):
        '''
        Send messages to peer.
        '''
        if not self.connected:
            self.check_connection()
        with self.lock:
            if self.write_buffer:
                sent = self.sock.send(self.write_buffer)
                self.write_buffer = self.write_buffer[sent:]

    def check_connection(self):
        err = self.sock.getsockopt(SOL_SOCKET, SO_ERROR)
        if err != 0:
            self.close()
        self.connected = True
        with self.lock:
            self.write_buffer += self.handshake

    def is_alive(self):
        '''
        Check if peer is OK.
        '''
        if time.time() - self.connect_time > PEER_TIMEOUT and not self.handshaked:
            self.close()
        return self.alive

    def connect(self, ip_address, port):
        '''
        Connect to given ip_address using given port.
        '''
        errno = self.sock.connect_ex((ip_address, port))
        if errno in (EINPROGRESS, EALREADY, EWOULDBLOCK):
            return
        if errno in (0, EISCONN):
            self.connected = True
            with self.lock:
                self.write_buffer += self.handshake
        else:
            self.close()

    def send_bitfield(self, bitfield):
        '''
        Send bitfield to peer.
        '''
        self.need_bitfield = False
        with self.lock:
            self.write_buffer += construct_message('bitfield', len(bitfield)+1, bitfield)

    def parse_stream(self, message):
        '''
        Return list of tuples containing two objects: message id and payload.
        '''
        message = self.current_msg + message
        #handshake received
        if message[1:20] == b'BitTorrent protocol':
            self.check_handshake(message)
            if self.upload:
                with self.lock:
                    self.write_buffer += self.handshake
            self.need_bitfield = True
            message = message[HANDSHAKE_LEN:]
            if not message:
                return
        messages = []
        while True:
            if not self.current_msg_len:
                try:
                    self.current_msg_len = struct.unpack('!I', message[:4])[0] + 4
                except struct.error:
                    if len(message) < 4:
                        self.current_msg = message
                        break
                    else:
                        self.close()
            if len(message) < self.current_msg_len:
                self.current_msg = message
                break
            if self.current_msg_len == 4:
                message = message[self.current_msg_len:]
                self.current_msg_len = 0
                continue
            messages.append((message[4], message[5:self.current_msg_len]))
            message = message[self.current_msg_len:]
            self.current_msg_len = 0
        return messages

    def handle_messages(self, messages):
        '''
        Perform appropriate actions for each message in list.
        '''
        for msg_id, payload in messages:
            #choke
            if msg_id == 0:
                self.unchoked = False
                self.close()
                return
            #unchoke
            elif msg_id == 1:
                self.unchoked = True
            #have
            elif msg_id == 4:
                index = struct.unpack('!I', payload)[0]
                self.bitfield[index] = True
            #bitfield
            elif msg_id == 5:
                self.fill_bitfield(payload)
                if not self.upload:
                    with self.lock:
                        self.write_buffer += construct_message('interested')
            #piece (of cake)
            elif msg_id == 7:
                self.save_block(payload)
            #interested
            elif msg_id == 2:
                if self.upload:
                    with self.lock:
                        self.write_buffer += construct_message('unchoke')
            #request
            elif msg_id == 6:
                index, offset, length = struct.unpack('!III', payload)
                if index not in self.need_piece:
                    self.need_piece[index] = []
                self.need_piece[index].append((offset, length))

    def send_have(self, index):
        '''
        Send peer 'have' message.
        '''
        with self.lock:
            self.write_buffer += construct_message('have', index)

    def check_handshake(self, message):
        '''
        Check if handshake has correct info-hash.
        '''
        try:
            message.index(self.handshake[28:48])
            self.handshaked = True
        except ValueError:
            self.close()

    def send_block(self, data, index, offset):
        '''
        Send block of data to peer.
        '''
        with self.lock:
            self.write_buffer += construct_message('piece', len(data)+9, index, offset[0], data)
        del self.need_piece[index][self.need_piece[index].index(offset)]

    def save_block(self, message):
        '''
        Save block or, if completed, piece to buffer. Completed pieces
        will be written to files in main function.
        '''
        index, offset = struct.unpack('!II', message[:8])
        self.downloaded += len(message[8:])
        if index in self.piece_buffer:
            self.piece_buffer[index]['data'][offset] = message[8:]
        else:
            return
        if len(self.piece_buffer[index]['data']) == self.piece_buffer[index]['blocks_amount']:
            blocks = OrderedDict(sorted(self.piece_buffer[index]['data'].items()))
            self.completed_pieces[index] = b''.join(blocks.values())
            self.requests -= len(self.completed_pieces[index])/MAX_REQUEST
            del self.piece_buffer[index]

    def get_completed_pieces(self):
        '''
        Return dictionary containing fully downloaded pieces.
        '''
        if self.completed_pieces:
            temp = self.completed_pieces
            self.completed_pieces = {}
            return temp
        return None

    def fill_bitfield(self, bitfield):
        '''
        Fill bitfield dictionary with bools indicating whether this peer
        has the piece with key index.
        '''
        for i, byte in enumerate(bitfield):
            for j, bit in enumerate(('0'*8+bin(byte)[2:])[-8:]):
                self.bitfield[i*8+j] = bit

    def send_request(self, pieces):
        '''
        Request pieces divided to 2^14 bytes blocks.
        The number of simultaneously pending requests is calculated
        based on peer's transmission speed.
        '''
        if self.timer == 0:
            self.timer = time.time()
        to_write = bytearray()
        for piece_index, piece_size in pieces.items():
            self.piece_buffer[piece_index] = {'index': piece_index, 'size': piece_size,
                                              'data': {}, 'blocks_amount': 0}
            last_block_size = piece_size % MAX_REQUEST
            for offset in range(0, piece_size - last_block_size, MAX_REQUEST):
                self.piece_buffer[piece_index]['blocks_amount'] += 1
                to_write += construct_message('request', piece_index, offset, MAX_REQUEST)
            if last_block_size:
                self.piece_buffer[piece_index]['blocks_amount'] += 1
                to_write += construct_message('request', piece_index,
                                              piece_size - last_block_size, last_block_size)
        with self.lock:
            self.write_buffer += to_write

    def send_cancel(self, piece_index, piece_size):
        '''
        Cancel the request(only used in endgame).
        '''
        last_block_size = piece_size % MAX_REQUEST
        for offset in range(0, piece_size - last_block_size, MAX_REQUEST):
            with self.lock:
                self.write_buffer += construct_message(
                    'cancel', piece_index, offset, MAX_REQUEST
                )
        if last_block_size:
            with self.lock:
                self.write_buffer += construct_message(
                    'cancel', piece_index, piece_size - last_block_size, last_block_size
                )

    def can_request(self):
        '''
        Check if peer is ready to accept the request.
        '''
        return self.unchoked and self.requests < self.max_requests

    def has_piece(self, index):
        '''
        Check if peer has piece with given index.
        '''
        try:
            return self.bitfield[index]
        except KeyError:
            return False
