import unittest
from mock import patch, mock_open
from core.becnode import bendecode, benencode
from core.network import Peer, close_all, channel_file
from core.other import construct_message, get_smile_positions, check_addr, Nickname
from core.chat import Chat

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

class TestModuleOther(unittest.TestCase):
    def test_construct_message(self):
        self.assertEqual(construct_message('close'), b'\x05')
        self.assertEqual(construct_message('nick', 'petrushka'), b'\x06petrushka')
        self.assertEqual(construct_message('peer-list', 'get over there'), b'\x03get over there')
        self.assertRaises(TypeError, construct_message, 'tipok')

    def test_get_smile_positions(self):
        self.assertEqual(get_smile_positions(':pirate:'), [(0, 8)])
        self.assertEqual(get_smile_positions('hahaha:pirate:bottleofrum'), [(6, 14)])
        self.assertEqual(get_smile_positions(':pirate::vomit::smile:'), [(0, 8), (8, 15), (15, 22)])
        self.assertEqual(get_smile_positions(':pirate:smile:pirate:wall::'), [(0, 8), (13, 21)])
        self.assertEqual(get_smile_positions(':pirat: is a :badguy: but :cool:'), [(26, 32)])
        self.assertEqual(get_smile_positions(':piratekokoko'), [])

    def test_check_addr(self):
        self.assertEqual(check_addr('127.9.9.9'), False)
        self.assertEqual(check_addr('127.9.9'), False)
        self.assertEqual(check_addr('127.9.9.9:23'), True)
        self.assertEqual(check_addr('127.9.9.:255'), False)
        self.assertEqual(check_addr('255.255.255.255:202304302'), True)
        self.assertEqual(check_addr('1:2'), False)
        self.assertEqual(check_addr('karamba'), False)

class TestPeerAndChat(unittest.TestCase):
    @patch('core.network.socket')
    @patch('asyncore.socket')
    def test_send_msg(self, mocksock, m):
        nick_one = Nickname('pacanchik')
        peer = Peer(nick_one, 9090)
        chat = Chat(nick_one, peer)
        chat.send_msg('/join 127.0.0.1:25823')
        mocksock.socket().sendto.assert_called_with(b'\x02pacanchik', ('127.0.0.1', 25823))
        chat.send_msg('/join 127.0..1:25823')
        self.assertEqual(peer.get_callback(), [('msg', 'Invalid address.')])
        chat.send_msg('/join ')
        self.assertEqual(peer.get_callback(), [('msg', 'Invalid address.')])
        peer.peers['500'] = 'kulak'
        peer.banlist['kulak'] = False
        chat.send_msg('          ')
        chat.send_msg('          privet')
        self.assertEqual(chat.get_callback(), [('msg', 'pacanchik: privet')])
        mocksock.socket().sendto.assert_called_with(b'\x01privet', ('500'))
        chat.send_msg('/join')
        self.assertEqual(chat.get_callback(), [('msg', 'Incomplete command.')])
        chat.send_msg('/nick rita petrova')
        self.assertEqual(chat.get_callback(), [('msg', 'Nickname should not contain spaces and slashes.')])
        chat.send_msg('/nick rita_petrova')
        self.assertEqual(chat.get_callback(), [('msg', 'You have changed your nickname to rita_petrova.')])
        mocksock.socket().sendto.assert_called_with(b'\x06rita_petrova', ('500'))
        chat.send_msg('/ban kulak')
        self.assertTrue(peer.banlist['kulak'])
        chat.send_msg('/unban kulak')
        self.assertFalse(peer.banlist['kulak'])
        self.assertEqual(chat.get_callback(), [('msg', "You've banned kulak."), ('msg', "You've unbanned kulak.")])
        chat.send_msg('/whisp tatat rococo')
        self.assertEqual(chat.get_callback(), [('msg', 'Wrong nickname.')])
        chat.send_msg('/whisp kulak rococo')
        self.assertEqual(chat.get_callback(), [('msg', 'rita_petrova (to kulak): rococo')])
        mocksock.socket().sendto.assert_called_with(b'\x04rococo', ('500'))
        chat.send_msg('/leave')
        mocksock.socket().sendto.assert_called_with(b'\x05', ('500'))
        chat.send_msg('/Darth Vader')
        self.assertEqual(chat.get_callback(), [('left',), ('msg', 'Wrong command.')])

    @patch('core.network.socket')
    @patch('asyncore.socket')
    def test_receive_msg(self, mocksock, m):
        nick_one = Nickname('pacanchik')
        peer = Peer(nick_one, 9090)
        mocksock.socket().recvfrom.return_value = b'\x00irina', ('500', 10)
        peer.handle_read()
        self.assertEqual(peer.get_callback(), [('add', 'irina'), ('msg', 'irina has joined the room.')])
        self.assertEqual(peer.peers[('500', 10)], 'irina')
        mocksock.socket().recvfrom.return_value = b'\x01sigaretki', ('500', 10)
        peer.handle_read()
        self.assertEqual(peer.get_callback(), [('msg', 'irina: sigaretki')])
        mocksock.socket().recvfrom.return_value = b'\x02cobain', ('400', 10)
        peer.handle_read()
        self.assertEqual(peer.get_callback(), [('add', 'cobain'), ('msg', 'cobain has joined the room.')])
        mocksock.socket().sendto.assert_called_with(b'\x03dte9:pacanchikt3:500i10ee5:irinae', ('400', 10))
        self.assertEqual(peer.peers[('400', 10)], 'cobain')
        mocksock.socket().recvfrom.return_value = b'\x03dte9:pacanchikt4:5000i10ee5:irinae', ('300', 10)
        peer.handle_read()
        self.assertEqual(set(peer.get_callback()), set([('add', 'irina'), ('add', 'pacanchik')]))
        self.assertEqual(peer.peers, {('400', 10): 'cobain', ('5000', 10): 'irina', ('300', 10): 'pacanchik', ('500', 10): 'irina'})
        mocksock.socket().recvfrom.return_value = b'\x04irina', ('500', 10)
        peer.handle_read()
        mocksock.socket().recvfrom.return_value = b'\x05', ('500', 10)
        peer.handle_read()
        self.assertEqual(peer.get_callback(), [('msg', 'irina (whisp): irina'), ('del', 'irina')])
        self.assertNotIn(('500', 10), peer.peers)
        mocksock.socket().recvfrom.return_value = b'\x06kasarb', ('400', 10)
        peer.handle_read()
        self.assertEqual(peer.peers[('400', 10)], 'kasarb')
        self.assertEqual(peer.get_callback(), [('msg', 'cobain has changed his nickname to kasarb.'), ('nick', 'cobain', 'kasarb')])
        mocksock.socket().recvfrom.return_value = b'i am hacker and trying to break your chat', ('228', 10243)
        peer.handle_read()

    @patch('core.network.os.path')
    @patch('core.network.socket')
    def test_channel_file(self, mocksock, osmock):
        osmock.getsize.return_value = 7
        m = mock_open(read_data=b'ranetki')
        with patch('core.network.open', m, create=True) as mockf:
            channel_file('some cool file', '400')
        mocksock().sendto.assert_called_with(b'\t\x0esome cool file\x00\x00\x00\x07'
                                             b'ranetki\x00\x00\x00\x00\x00\x00\x00\x07', '400')

    @patch('core.network.socket')
    @patch('core.network.os.path')
    @patch('asyncore.socket')
    def test_write_piece(self, mocksock, osmock, m):
        osmock.exists.return_value = True
        osmock.basename.return_value = 'file'
        nick_one = Nickname('pacanchik')
        peer = Peer(nick_one, 9090)
        peer.pending_files['some cool file'] = 'some cool path/file'
        m = mock_open()
        with patch('core.network.open', m, create=True) as mockf:
            callback = peer.write_piece(b'\x0esome cool file\x00\x00\x00\x07'
                             b'ranetki\x00\x00\x00\x0A\x00\x00\x00\x11')
            mockf().seek.assert_called_with(10, 0)
            mockf().write.assert_called_with(b'ranetki')
        self.assertEqual(callback, [('dload', 'some cool file', '100'), ('msg', 'file was succesfully downloaded.')])

if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        close_all()
