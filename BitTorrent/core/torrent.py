'''
A class to work with torrents.
'''

import time
import os
import sys
from hashlib import sha1
from threading import Thread
from core.tracker import Tracker
from core.becnode import benencode
from core.network import Peer, Server, SocketHandler
from core.config import ENDGAME_PERCENT, MAX_PEERS, UPLOAD_PEERS, PEER_ID, KEY

SHA_LEN = 20
SPEED_DELTA = 100

def read_file_with_offset(file_, offset, length):
    '''
    Read length bytes from position offset from given file.
    '''
    if not os.path.exists(file_['path']):
        return b''
    with open(file_['path'], 'rb') as fiel:
        fiel.seek(offset, 0)
        data = fiel.read(length)
    return data

class Torrent(object):
    '''
    It is just more comfortable to work with a class.
    This class contains some torrenting-related methods and variables.
    '''
    torrents_count = 0

    def __init__(self, speed_limit, upload_limit):
        self.files, self.length = [], 0
        self.piece_length = 0
        self.pieces = {}
        self.downloaded = 0
        self.handshake = b''
        self.trackers = []
        self.got = 0
        self.uploaded = 0
        self.server = None
        self.upload_peers = 0
        self.speed_limit = speed_limit
        self.upload_limit = upload_limit
        self.start_time = 0
        self.seeding = False
        self.peers, self.backup_peers = [], []

    def set_up(self, data, out_folder):
        '''
        Additional init that works with network.
        '''
        self.server = Server(Torrent.torrents_count)
        self.files, self.length = Torrent.get_filedata(data['info'], out_folder)
        self.piece_length = data['info']['piece length']
        for index, file_ in enumerate(self.files):
            print(str(index+1)+'. '+file_['path'])
        print(
            'Choose files to download. Type 0 to download all or numbers of needed files.'
        )
        to_download = input()
        self.pieces = self.get_pieces(data['info'])
        if to_download == '0':
            for file_ in self.files:
                file_['needed'] = True
        else:
            list_of = to_download.split(', ')
            for index, file_ in enumerate(self.files):
                if str(index+1) in list_of:
                    file_['needed'] = True
                else:
                    self.length -= file_['length']
        for index, piece in enumerate(self.pieces):
            piece['needed'] = bool([x for x in self.map_piece(index) if x['needed']])
        info = benencode(data['info'])
        info_hash = sha1(info.encode("latin-1")).digest()
        self.handshake = b'\x13'+b'BitTorrent protocol'+b'\x00'*8+info_hash+PEER_ID
        self.downloaded = self.check_existing_data()
        payload = {
            'info_hash': info_hash, 'peer_id': PEER_ID,
            'uploaded': 0, 'downloaded': self.downloaded,
            'left': self.length - self.downloaded,
            'numwant': 500, 'no_peer_id': 1, 'compact': 1,
            'corrupt': 0, 'event': 'started',
            'port': self.server.port, 'ip': 0, 'key': KEY
        }
        self.trackers = Torrent.get_tracker_list(data, payload)

    def get_pieces(self, data):
        '''
        Return dictionary containing 20-bytes long pieces from .torrent file.
        '''
        hashes = data['pieces'].encode('latin-1')
        pieces = [
            {'hash': hashes[i:i+SHA_LEN], 'have': False,
             'requested': (False, None),
             'size': data['piece length'],
             'offset': int(i/SHA_LEN*data['piece length'])}
            for i in range(0, len(hashes), SHA_LEN)
        ]
        over = len(pieces) * data['piece length'] - self.length
        pieces[-1]['size'] -= over
        return pieces

    @staticmethod
    def get_filedata(data, out_folder):
        '''
        Return a dictionary containing information about files and their total length.
        '''
        files = []
        if 'files' in data:
            length = 0
            for file_info in data['files']:
                if out_folder:
                    path = (out_folder+'/'+data['name']+'/'+
                            '/'.join(file_info['path'])).encode('latin-1').decode('utf8')
                else:
                    path = (data['name']+'/'+
                            '/'.join(file_info['path'])).encode('latin-1').decode('utf8')
                files.append({'path': path, 'length': file_info['length']})
                os.makedirs(os.path.dirname(path), exist_ok=True)
                length += file_info['length']
        else:
            if out_folder:
                files.append(
                    {'path': out_folder+'/'+data['name'].encode('latin-1').decode('utf8'),
                     'length': data['length']}
                )
                os.makedirs(out_folder, exist_ok=True)
            else:
                files.append(
                    {'path': data['name'].encode('latin-1').decode('utf8'),
                     'length': data['length']}
                )
            length = data['length']
        for file_ in files:
            file_['needed'] = False
        return files, length

    def construct_bitfield(self):
        '''
        Construct bitfield, a bytestring indicating what pieces we have.
        '''
        bits = ''
        result = bytearray()
        for piece in self.pieces:
            bits += str(int(piece['have']))
            if len(bits) == 8:
                result += bytes(chr(int(bits, 2)), encoding='latin1')
                bits = ''
        if bits:
            result += bytearray(chr(int((bits+'0'*8)[:8], 2)), encoding='latin1')
        return result

    def update_peer_list(self, need_peers):
        '''
        Delete dead peers and add new ones from backup or from trackers' GET responses.
        '''
        self.upload_peers -= len(
            [peer for peer in self.peers if not peer.is_alive() and peer.upload]
        )
        self.peers = [peer for peer in self.peers if peer.is_alive()]
        for peer in self.server.take_number_of_peers(UPLOAD_PEERS - self.upload_peers):
            self.upload_peers += 1
            self.peers.append(Peer(self.handshake, True, peer))
        if not need_peers:
            return
        while self.backup_peers and len(self.peers) < MAX_PEERS:
            self.peers.append(Peer(self.handshake))
            self.peers[-1].connect(
                self.backup_peers[0]['ip'],
                self.backup_peers[0]['port']
            )
            del self.backup_peers[0]
        for tracker in [tracker for tracker in self.trackers if tracker.can_reannounce()]:
            addresses = tracker.get_peers()
            for ip_addr, port in addresses:
                if len(self.peers) < MAX_PEERS:
                    self.peers.append(Peer(self.handshake))
                    self.peers[len(self.peers)-1].connect(ip_addr, port)
                else:
                    self.backup_peers.append({'ip': ip_addr, 'port': port})

    def check_existing_data(self):
        '''
        Check if there are any data downloaded already.
        '''
        downloaded = 0
        no_data = True
        for file_ in [x for x in self.files if x['needed']]:
            if os.path.exists(file_['path']):
                no_data = False
            else:
                open(file_['path'], 'w').close()
        if no_data:
            return 0
        print('Checking existing files...')
        pieces_amount = len(self.pieces)
        for index, piece in enumerate(self.pieces):
            piece_map = self.map_piece(index)
            data = b''.join([read_file_with_offset(x['file'], x['offset'], x['length'])
                             for x in piece_map])
            perc = str(round(100*(index+1)/pieces_amount, 2))
            sys.stdout.write('\r'+perc+' '*(5-len(perc))+'% checked.      ')
            piece['have'] = Torrent.validate_piece(piece, data)
            if piece['have'] and piece['needed']:
                for piece_of_piece in [x for x in piece_map if x['needed']]:
                    downloaded += piece_of_piece['length']
        sys.stdout.write('\n')
        return downloaded

    @staticmethod
    def validate_piece(piece, data):
        '''
        Check if given piece has correct hash-sum.
        '''
        return piece['hash'] == sha1(data).digest()

    def map_piece(self, index):
        '''
        Return a list of dictionaries that looks like below:
        [{file0, offset0, length0}, {file1, offset1, length1}, ...]
        File - file in which given piece should be written to.
        Offset - starting position of the piece within the file.
        Length - length of part of given piece tha will be written in File file.
        '''
        piece_map = []
        if len(self.files) == 1:
            piece_map.append(
                {'file': self.files[0], 'offset': self.pieces[index]['offset'],
                 'length': self.pieces[index]['size'], 'needed': True}
            )
            return piece_map
        start = index * self.piece_length
        file_index = 0
        for file_ in self.files:
            if start - file_['length'] <= 0:
                break
            file_index += 1
            start -= file_['length']
        not_mapped = self.pieces[index]['size']
        while True:
            if not_mapped <= self.files[file_index]['length'] - start:
                piece_map.append(
                    {'file': self.files[file_index], 'offset': start,
                     'length': not_mapped, 'needed': self.files[file_index]['needed']}
                )
                return piece_map
            piece_map.append(
                {'file': self.files[file_index], 'offset': start,
                 'length': self.files[file_index]['length'] - start,
                 'needed': self.files[file_index]['needed']}
            )
            not_mapped = not_mapped - self.files[file_index]['length'] + start
            file_index += 1
            start = 0

    @staticmethod
    def get_tracker_list(data, payload):
        '''
        Return a list containing all the trackers found in .torrent file.
        '''
        trackers = []
        if 'announce-list' in data:
            for tracker in data['announce-list']:
                trackers.append(Tracker(tracker[0], payload))
        if data['announce'] not in [tracker.url for tracker in trackers]:
            trackers.append(Tracker(data['announce'], payload))
        return trackers

    def send_blocks_to_peers(self):
        '''
        Send peers bitfields and blocks of data.
        '''
        upspeed = self.uploaded/(1024*(time.time()-self.start_time))
        bitfield = self.construct_bitfield()
        for peer in self.peers:
            if peer.need_bitfield:
                peer.send_bitfield(bitfield)
            if not (self.upload_limit != -1 or self.upload_limit - SPEED_DELTA > upspeed):
                return
            for index, blocks in peer.need_piece.items():
                data = b''.join([read_file_with_offset(x['file'], x['offset'], x['length'])
                                 for x in self.map_piece(index)])
                for block in blocks:
                    self.uploaded += block[1]
                    peer.send_block(data[block[0]:block[0]+block[1]], index, block)

    def construct_request(self, peer, endgame):
        '''
        Construct and send request message to peer.
        '''
        pieces_to_request = {}
        for index, piece in enumerate(self.pieces):
            if not endgame:
                if peer.has_piece(index) and not piece['have'] and \
                   (not piece['requested'][0] or piece['requested'][1] and \
                    time.time()-piece['requested'][1] > 10) and \
                   peer.can_request() and piece['needed']:
                    piece['requested'] = (True, time.time())
                    peer.requests += piece['size']/(2**14)
                    pieces_to_request[index] = piece['size']
                elif not peer.can_request():
                    break
            elif not peer.endgame:
                if peer.has_piece(index) and not piece['have'] and piece['needed']:
                    pieces_to_request[index] = piece['size']
        peer.send_request(pieces_to_request)
        peer.endgame = endgame

    def check_peers(self, endgame):
        '''
        Send and receive messages to and from peers. Also this method frozes
        peers if download speed is near the limit.
        '''
        speed = 0
        for peer in self.peers:
            speed += peer.downloaded/(1024*(time.time()-peer.timer))
        if self.speed_limit - speed < SPEED_DELTA and self.speed_limit:
            for peer in self.peers:
                peer.frozen = True
        available_peers = [
            peer for peer in self.peers if (peer.can_request() or endgame and peer.unchoked) and \
                                           (self.speed_limit > speed or not self.speed_limit)
        ]
        completed_pieces = []
        for peer in available_peers:
            self.construct_request(peer, endgame)
            completed_pieces.append(peer.get_completed_pieces())
        return completed_pieces

    def insert_pieces(self, completed_pieces, endgame):
        '''
        Insert pieces into files.
        '''
        to_insert = {}
        for piece_set in [x for x in completed_pieces if x]:
            for index, piece in piece_set.items():
                if Torrent.validate_piece(self.pieces[index], piece) and \
                   not self.pieces[index]['have']:
                    if endgame:
                        for peer in self.peers:
                            peer.send_cancel(index, self.pieces[index]['size'])
                    self.pieces[index]['have'] = True
                    self.pieces[index]['requested'] = (True, None)
                    self.got += self.pieces[index]['size']
                    to_insert[index] = piece
                else:
                    self.pieces[index]['requested'] = (False, None)
        for index, piece in to_insert.items():
            for peer in self.peers:
                peer.send_have(index)
            for filemap in self.map_piece(index):
                if filemap['needed']:
                    with open(filemap['file']['path'], 'rb+') as fiel:
                        fiel.seek(filemap['offset'], 0)
                        self.downloaded += len(piece[:filemap['length']])
                        fiel.write(piece[:filemap['length']])
                        piece = piece[filemap['length']:]
                else:
                    piece = piece[filemap['length']:]

    def stop_download(self):
        '''
        Send trackers GET requests indicating that download has stopped.
        If we don't send this message, tracker won't give us peer-list next time.
        '''
        for tracker in [x for x in self.trackers if x.reachable]:
            tracker.update_payload(
                {'event': 'stopped', 'numwant': 0,
                 'downloaded': self.downloaded,
                 'left': self.length - self.downloaded,
                 'uploaded': self.uploaded}
            )
            tracker.announce()

def download(torrents, speed_limit, seed):
    '''
    Start and stop process of downloading.
    '''
    downloaded = 0
    length = 0
    for torrent in torrents:
        downloaded += torrent.downloaded
        length += torrent.length
    if downloaded >= length and not seed:
        print('All files have already been downloaded.')
        return
    print('Connecting to peers...')
    try:
        for torrent in torrents:
            torrent.update_peer_list(True)
            torrent.start_time = time.time()
        netloop = Thread(target=SocketHandler.loop)
        netloop.start()
        process_download(torrents, length, downloaded, speed_limit)
    except KeyboardInterrupt:
        seed = False
    if seed:
        print('\nDownload completed\nStart seeding')
        for torrent in torrents:
            for peer in [peer for peer in torrent.peers if not peer.upload]:
                peer.close()
        try:
            process_seeding(torrents)
        except KeyboardInterrupt:
            print('\nStopping seeding...')
    else:
        print('\nStopping download...')
    SocketHandler.close()
    netloop.join()
    for torrent in torrents:
        torrent.stop_download()
    if seed:
        print('Seeding stopped')
    else:
        print('Download completed')

def process_seeding(torrents):
    '''
    When download completed, this function continues to seed to peers.
    '''
    print('Seeding started. Press Ctrl+C to interrupt.')
    start_time = time.time()
    time.sleep(0.5)
    while True:
        peers = 0
        uploaded = 0
        for torrent in torrents:
            torrent.update_peer_list(False)
            uploaded += torrent.uploaded
            peers += len(torrent.peers)
        upspeed = round((uploaded/len(torrents))/(1024*(time.time()-start_time)), 2)
        sys.stdout.write(
            '\rUpload speed: {}{} KB/s. {} peers. '.format(
                str(upspeed), ' '*(7-len(str(upspeed))), str(peers)
            )
        )
        time.sleep(0.5)

def process_download(torrents, length, downloaded, speed_limit):
    '''
    Download file. Basically, this function is an infinite loop that
    checks if there are anything to do with peers and prints current
    state of download.
    '''
    print('Download started')
    start_time = time.time() - 0.1
    endgame = round(100*(downloaded)/length, 2) > ENDGAME_PERCENT
    speed = 0
    while downloaded < length:
        got = 0
        uploaded = 0
        peers = 0
        downloaded = 0
        for torrent in torrents:
            need_peers = not speed_limit or speed < speed_limit + SPEED_DELTA
            torrent.update_peer_list(need_peers)
            completed_pieces = torrent.check_peers(endgame)
            torrent.insert_pieces(completed_pieces, endgame)
            got += torrent.got
            uploaded += torrent.uploaded
            peers += len(torrent.peers)
            downloaded += torrent.downloaded
        perc = round(100*(downloaded)/length, 2)
        speed = round((got/len(torrents))/(1024*(time.time()-start_time)), 2)
        upspeed = round((uploaded/len(torrents))/(1024*(time.time()-start_time)), 2)
        endgame = perc > ENDGAME_PERCENT
        sys.stdout.write(
            '\r{}{}% downloaded. Speed {}{} KB/s. {} peers. Upload speed: {}{} KB/s '.format(
                str(perc), ' '*(5-len(str(perc))), str(speed),
                ' '*(7-len(str(speed))), str(peers), str(upspeed),
                ' '*(7-len(str(upspeed)))
            )
        )
        time.sleep(0.5)
