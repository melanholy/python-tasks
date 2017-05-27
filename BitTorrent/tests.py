import unittest
import mock
import struct
import core.torrent
from LeetTorrent import check_file
from core.becnode import bendecode, benencode
from core.network import Peer, construct_message
from core.tracker import Tracker
from core.torrent import Torrent
from hashlib import sha1

class TestBencode(unittest.TestCase):
    def test_encoder_correct_type(self):
        self.assertEqual(benencode('Hello, World'), '12:Hello, World')
        self.assertEqual(benencode(('Hello, World', 72, [2, 1])), 't12:Hello, Worldi72eli2ei1eee')
        self.assertEqual(benencode(58230596782467402), 'i58230596782467402e')
        self.assertEqual(benencode({'foo': 'bar', 'hello': 6, 'test': [2, 3, 1488], 'yo': {'Root': 'Head'}}),
                         'd3:foo3:bar5:helloi6e4:testli2ei3ei1488ee2:yod4:Root4:Headee')
        self.assertEqual(benencode([1, 2, 3, '19', 'Jonas', {'Foxtrot': 'Uniform', 'Charlie': ['Kilo']}]),
                         'li1ei2ei3e2:195:Jonasd7:Charliel4:Kiloe7:Foxtrot7:Uniformee')

    def test_encoder_wrong_type(self):
        self.assertRaises(TypeError, benencode, None)
        self.assertRaises(TypeError, benencode, {1, 2, 3})
        self.assertRaises(TypeError, benencode, True)
        self.assertRaises(TypeError, benencode, {'lala': 2, 'jones': False})

    def test_decoder_correct_string(self):
        self.assertEqual(bendecode('12:Hello, World'), 'Hello, World')
        self.assertEqual(bendecode('t12:Hello, Worldi72ee'), ('Hello, World', 72))
        self.assertEqual(bendecode('i58230596782467402e'), 58230596782467402)
        self.assertEqual(bendecode('d3:foo3:bar5:helloi6e4:testli2ei3ei1488ee2:yod4:Root4:Headee'),
                         {'foo': 'bar', 'hello': 6, 'test': [2, 3, 1488], 'yo': {'Root': 'Head'}})
        self.assertEqual(bendecode('li1ei2ei3e2:195:Jonasd7:Charliel4:Kiloe7:Foxtrot7:Uniformee'),
                         [1, 2, 3, '19', 'Jonas', {'Foxtrot': 'Uniform', 'Charlie': ['Kilo']}])
        self.assertEqual(bendecode('i3e4:kakali74ed3:gag1:ge8:umbrellae'), 3)

    def test_decoder_incorrect_string(self):
        self.assertRaises(ValueError, bendecode, 'l3:den6:jjae')
        self.assertRaises(ValueError, bendecode, 'di666e5:lalal3:keke')
        self.assertRaises(ValueError, bendecode, 'di666e5:lalal')
        self.assertRaises(ValueError, bendecode, 'l3:den4:jaja')
        self.assertRaises(TypeError, bendecode, 'dli666e4:liste5:lalale')
        self.assertRaises(ValueError, bendecode, 'l3:fo4:reste')
        self.assertRaises(ValueError, bendecode, 'dla3gaae')

    def test_decoder_wrong_type(self):
        self.assertRaises(TypeError, bendecode, None)
        self.assertRaises(TypeError, bendecode, True)
        self.assertRaises(TypeError, bendecode, [1, 2])
        self.assertRaises(TypeError, bendecode, b'presidentcocojambo')

class TestPeer(unittest.TestCase):
    def setUp(self):
        self.peer = Peer(b'aBitTorrent protocoltotallynotahandshake')

    def parser_test(self, mes, expcurm, expcurl, expmsg):
        self.assertEqual(self.peer.parse_stream(mes), expmsg)
        self.assertEqual(self.peer.current_msg, expcurm)
        self.assertEqual(self.peer.current_msg_len, expcurl)
        self.peer.current_msg = b''
        self.peer.current_msg_len = 0

    def test_fill_bitfield(self):
        self.peer.fill_bitfield(b'\x00')
        self.assertEqual(self.peer.bitfield, {0: '0', 1: '0', 2: '0', 3: '0', 4: '0', 5: '0', 6: '0', 7: '0'})
        self.peer.fill_bitfield(b'\x21')
        self.assertEqual(self.peer.bitfield, {0: '0', 1: '0', 2: '1', 3: '0', 4: '0', 5: '0', 6: '0', 7: '1'})
        self.peer.fill_bitfield(b'\xA0')
        self.assertEqual(self.peer.bitfield, {0: '1', 1: '0', 2: '1', 3: '0', 4: '0', 5: '0', 6: '0', 7: '0'})
        self.peer.fill_bitfield(b'\xAA')
        self.assertEqual(self.peer.bitfield, {0: '1', 1: '0', 2: '1', 3: '0', 4: '1', 5: '0', 6: '1', 7: '0'})

    def test_parser_normal_messages(self):
        message = self.peer.handshake
        self.assertEqual(self.peer.parse_stream(message), None)
        message = b'aBitTorrent protocoltotallynotahandshketjty'
        self.assertEqual(self.peer.parse_stream(message), None)
        self.assertFalse(self.peer.alive)
        self.peer.alive = True
        message = construct_message('keep-alive')
        self.assertEqual(self.peer.parse_stream(message), [])
        message = construct_message('choke')+construct_message('choke')+construct_message('choke')
        self.assertEqual(self.peer.parse_stream(message), [(0, b''),(0, b''),(0, b'')])
        message = construct_message('have', 4)+construct_message('interested')+construct_message('request', 2, 2, 8)
        self.assertEqual(self.peer.parse_stream(message), [(4, b'\x00\x00\x00\x04'),(2, b''),
                         (6, b'\x00\x00\x00\x02\x00\x00\x00\x02\x00\x00\x00\x08')])
        message = construct_message('have', 4)+construct_message('interested')+construct_message('request', 2, 2, 8)
        self.assertEqual(self.peer.parse_stream(message), [(4, b'\x00\x00\x00\x04'), (2, b''), (6, b'\x00\x00\x00\x02\x00\x00\x00\x02\x00\x00\x00\x08')])

    def test_parser_incomplete_messages(self):
        message = b'\x00\x00\xA0'
        self.parser_test(message, b'\x00\x00\xA0', 0, [])
        message = b'\x00\x00\x00\xA0'
        self.parser_test(message, b'\x00\x00\x00\xA0', 164, [])
        message = construct_message('choke')+construct_message('choke')+b'\x00\x00\x00\xA0'
        self.parser_test(message, b'\x00\x00\x00\xA0', 164, [(0, b''),(0, b'')])
        message = b'\x00\x00\x00\xA4\x05'
        self.parser_test(message, b'\x00\x00\x00\xA4\x05', 168, [])
        message = construct_message('have', 4)+b'\x00\x00\x00\xA4\x05\x00\x00\x00\x00\x00\x00'
        self.parser_test(message, b'\x00\x00\x00\xA4\x05\x00\x00\x00\x00\x00\x00', 168, [(4, b'\x00\x00\x00\x04')])

    def test_construct_message(self):
        self.assertEqual(construct_message('have', 4), b'\x00\x00\x00\x05\x04\x00\x00\x00\x04')
        self.assertEqual(construct_message('piece', 10, b'abcdef'), b'\x00\x00\x00\n\x07abcdef')
        self.assertEqual(construct_message('keep-alive'), b'\x00\x00\x00\x00')
        self.assertEqual(construct_message('cancel', 4, 4, 4, 5, 10, 1000), b'\x00\x00\x00\r\x08\x00\x00\x00\x04\x00\x00\x00\x04\x00\x00\x00\x04\x00\x00\x00\x05\x00\x00\x00\x0A\x00\x00\x03\xe8')
        self.assertEqual(construct_message('not-interested'), b'\x00\x00\x00\x01\x03')

    def test_message_handler(self):
        self.peer.handle_messages([(0, b'')])
        self.assertFalse(self.peer.alive)
        self.peer.alive = True
        self.peer.handle_messages([(1, None), (4, b'\x00\x00\x00\xFF')])
        self.assertTrue(self.peer.bitfield[255])
        self.assertTrue(self.peer.unchoked)
        self.peer.handle_messages([(5, b'\xAA'), (2, None)])
        self.assertEqual(self.peer.write_buffer, b'\x00\x00\x00\x01\x02')
        self.peer.upload = True
        self.peer.write_buffer = b''
        self.peer.handle_messages([(5, b'\xAA'), (2, None)])
        self.assertEqual(self.peer.write_buffer, b'\x00\x00\x00\x01\x01')
        self.peer.upload = False
        self.peer.piece_buffer[1] = {'data': {}, 'blocks_amount': 2}
        self.peer.handle_messages([(7, b'\x00\x00\x00\x01\x00\x00\x00\x04lalala')])
        self.assertEqual(self.peer.downloaded, 6)
        self.assertEqual(self.peer.piece_buffer[1]['data'][4], b'lalala')
        self.peer.handle_messages([(6, b'\x00\x00\x00\x01\x00\x00\x00\x04\x00\x00\x00\x00')])
        self.assertEqual(self.peer.need_piece[1], [(4, 0)])

    def test_save_block(self):
        self.peer.piece_buffer[1] = {'data': {}, 'blocks_amount': 2}
        self.peer.save_block(b'\x00\x00\x00\x01\x00\x00\x00\x04lalala')
        self.assertEqual(self.peer.downloaded, 6)
        self.assertEqual(self.peer.piece_buffer[1]['data'][4], b'lalala')
        self.peer.save_block(b'\x00\x00\x00\x01\x00\x00\x00\x06lalalala')
        self.assertEqual(self.peer.downloaded, 14)
        self.assertEqual(self.peer.piece_buffer, {})
        self.assertEqual(self.peer.get_completed_pieces(), {1: b'lalalalalalala'})

    def test_send_request(self):
        self.peer.write_buffer = b''
        self.peer.send_request({4:40000})
        self.assertEqual(self.peer.write_buffer, struct.pack('!'+'IBIII'*3, 13, 6, 4, 0, 16384, 13, 6, 4, 16384, 16384, 13, 6, 4, 16384*2, 40000-16384*2))
        self.peer.write_buffer = b''
        self.peer.send_request({4:17, 200:75})
        self.assertTrue(struct.pack('!'+'IBIII', 13, 6, 4, 0, 17 in self.peer.write_buffer))
        self.assertTrue(struct.pack('!'+'IBIII', 13, 6, 200, 0, 75 in self.peer.write_buffer))

class TestTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = Tracker('mir.ru', {'event': 'clue'})

    def test_get_peers(self):
        with mock.patch('core.tracker.httplib2') as mck:
            mck.Http().request.return_value = None, b'd5:peers12:\x7F\x00\x00\x01\x02\x02\x9F\x00\xA0\x01\x04\x108:intervali100ee'
            self.assertEqual(self.tracker.get_peers(), [('127.0.0.1', 514), ('159.0.160.1', 1040)])
            mck.Http().request.return_value = None, b'd5:peers0:8:intervali100ee'
            self.tracker.update_payload({'event': 'jajajaj'})
            self.assertEqual(self.tracker.get_peers(), [])

    def test_update_payload(self):
        self.tracker.payload = {}
        self.tracker.update_payload({'1': 400, '600': 100})
        self.assertTrue('1' in self.tracker.payload)
        self.assertEqual(self.tracker.payload['1'], 400)
        self.assertEqual(self.tracker.payload['600'], 100)

class TestTorrent(unittest.TestCase):
    def setUp(self):
        with mock.patch('core.torrent.Server') as mck:
            self.torrent = Torrent(0, -1)

    def test_get_pieces(self):
        self.torrent.length = 111
        self.assertEqual(self.torrent.get_pieces({'pieces': 'bbbb'*5, 'piece length': 111}), [{'hash': b'bbbb'*5, 'have': False, 'requested': (False, None), 'size': 111, 'offset': 0}])
        self.torrent.length = 350
        self.assertEqual(self.torrent.get_pieces({'pieces': 'aaaa'*5*4, 'piece length': 100}), 
                                                 [{'hash': b'aaaa'*5, 'have': False, 'requested': (False, None), 'size': 100, 'offset': 0},
                                                  {'hash': b'aaaa'*5, 'have': False, 'requested': (False, None), 'size': 100, 'offset': 100},
                                                  {'hash': b'aaaa'*5, 'have': False, 'requested': (False, None), 'size': 100, 'offset': 200},
                                                  {'hash': b'aaaa'*5, 'have': False, 'requested': (False, None), 'size': 50, 'offset': 300}])

    def test_construct_bitfield(self):
        self.assertEqual(self.torrent.construct_bitfield(), b'')
        self.torrent.pieces = [{'have': True}, {'have': False}, {'have': False}]
        self.assertEqual(self.torrent.construct_bitfield(), b'\x80')
        self.torrent.pieces = [{'have': True}, {'have': False}, {'have': False}, {'have': True}, {'have': False}, {'have': False}, {'have': True}, {'have': True}, {'have': True}]
        self.assertEqual(self.torrent.construct_bitfield(), b'\x93\x80')

    def test_update_peers(self):
        mock_dead_peer = mock.MagicMock()
        mock_dead_peer.configure_mock(name='dead peer')
        mock_dead_peer.is_alive.return_value = False
        mock_alive_peer = mock.MagicMock()
        mock_alive_peer.configure_mock(name='alive peer')
        mock_alive_peer.is_alive.return_value = True
        self.torrent.peers = [mock_alive_peer, mock_dead_peer, mock_alive_peer, mock_dead_peer, mock_alive_peer, mock_alive_peer]
        with mock.patch('core.torrent.Server') as servmck:
            self.torrent.server = servmck
            self.torrent.update_peer_list(True)
            self.assertEqual(len([x for x in self.torrent.peers if x.name == 'alive peer']), 4)
            with mock.patch('core.torrent.Peer'):
                self.torrent.backup_peers = [{'ip': '127.0.0.1', 'port': 48300}, {'ip': '255.255.123.23', 'port': 777}, {'ip': '234.23.5.1', 'port': 70}]
                self.torrent.update_peer_list(True)
                self.assertEqual(len(self.torrent.peers), 7)
                self.assertEqual(len(self.torrent.backup_peers), 0)
                core.torrent.MAX_PEERS = 8
                with mock.patch('core.torrent.Tracker') as mck:
                    mck.get_peers.return_value = [('', 2), ('126.24.54.34', 92)]
                    mck.can_reannounce.return_value = True
                    self.torrent.trackers = [mck]
                    self.torrent.update_peer_list(True)
                    self.assertEqual(len(self.torrent.peers), 8)
                    self.assertEqual(len(self.torrent.backup_peers), 1)

    def test_map_piece(self):
        self.torrent.files = [{'path': 'kiki', 'length': 23}]
        self.torrent.pieces = [{'offset': 0, 'size': 23}]
        self.assertEqual(self.torrent.map_piece(0), [{'file': {'path': 'kiki', 'length': 23}, 'needed': True, 'offset': 0, 'length': 23}])
        self.torrent.files = [{'length': 3, 'needed': True}, {'length': 40, 'needed': True}]
        self.assertEqual(self.torrent.map_piece(0), [{'file': {'needed': True, 'length': 3}, 'needed': True, 'length': 3, 'offset':0},
                                                      {'file': {'needed': True, 'length': 40}, 'needed': True, 'length': 20, 'offset': 0}])
        self.torrent.files = [{'length': 22, 'needed': True}, {'length': 19, 'needed': False}, {'length': 40, 'needed': True}]
        self.torrent.piece_length = 24
        self.torrent.pieces = [{'offset': 4, 'size': 19}, {'offset': 4, 'size': 19}]
        self.assertEqual(self.torrent.map_piece(1), [{'offset': 2, 'needed': False, 'file': {'needed': False, 'length': 19}, 'length': 17}, 
                                                      {'offset': 0, 'needed': True, 'file': {'needed': True, 'length': 40}, 'length': 2}])

    def test_check_data(self):
        with mock.patch('core.torrent.os.path') as mck:
            with mock.patch('core.torrent.read_file_with_offset') as fmck:
                mck.exists.return_value = True
                self.torrent.piece_length = 1
                self.torrent.pieces = [{'offset': 0, 'size': 19, 'hash': sha1(b'lalala').digest(), 'needed': True}]
                self.torrent.files = [{'path': 'lala', 'length': 22, 'needed': True}]
                fmck.return_value = b'lalala'
                self.assertEqual(self.torrent.check_existing_data(), 19)
                fmck.assert_called_with({'length': 22, 'path': 'lala', 'needed': True}, 0, 19)

class FilesTest(unittest.TestCase):
    def test_check_file(self):
        data = {
            'announce-list': [['http://bt2.rutracker.org/ann?uk=tLc63KZ1Z1'], ['http://retracker.local/announce']],
            'announce': 'http://bt2.rutracker.org/ann?uk=tLc63KZ1Z1',
            'info': {
                'files': [{'path': ['10 - Foolish Father.mp3'], 'length': 10924032}, {'path': ['06 - The British Are Coming.mp3'], 'length': 10006528}],
                'pieces': '\x8f\x95°#I\x0e',
                'piece length': 131072,
                'name': 'Weezer - Everything Will Be Alright In the End (2014)'
            }
        }
        self.assertTrue(check_file(data))
        ann = data['announce']
        del data['announce']
        self.assertTrue(check_file(data))
        del data['announce-list']
        self.assertFalse(check_file(data))
        data['announce'] = ann
        self.assertTrue(check_file(data))
        pieces = data['info']['pieces']
        del data['info']['pieces']
        self.assertFalse(check_file(data))
        data['info']['pieces'] = pieces
        leng = data['info']['piece length']
        del data['info']['piece length']
        self.assertFalse(check_file(data))
        data['info']['piece length'] = leng
        name = data['info']['name']
        del data['info']['name']
        self.assertFalse(check_file(data))
        data['info']['name'] = name
        files = data['info']['files']
        del data['info']['files']
        self.assertFalse(check_file(data))
        data['info']['files'] = files
        leng = data['info']['files'][0]['length']
        del data['info']['files'][0]['length']
        self.assertFalse(check_file(data))

if __name__ == '__main__':
    unittest.main()
