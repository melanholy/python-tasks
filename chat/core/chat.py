"""
Chat. Decentralized. Stylish. Simple.

Usage: python chat.py [-h] [-room room]
Requirements: python v3+. No third-party modules are required.

Copyright: (c) 2015 by Koshara Pavel.
"""

import re
import core.network
from threading import Thread
from core.other import construct_message

class Chat(object):
    '''
    Class containing chat related static variables, which are elements
    of chat window and thread object responsible for work with peers.
    '''
    def __init__(self, nickname, server):
        self.netloop = Thread(target=core.network.loop)
        self.my_nickname = nickname
        self.server = server
        self.message_callback = []
        self.commands_handler = {}
        self.commands_handler['/leave'] = lambda e: self.leave_room()
        self.commands_handler['/join'] = lambda e: self.server.join_room(e[1])
        self.commands_handler['/nick'] = lambda e: self.change_nickname(e)
        self.commands_handler['/ban'] = lambda e: self.ban_peer(e)
        self.commands_handler['/whisp'] = lambda e: self.whisp_to_peer(e)
        self.commands_handler['/unban'] = lambda e: self.unban_peer(e)

    def leave_room(self):
        self.server.send_close()
        self.message_callback.append(('left', ))

    def change_nickname(self, parted_msg):
        try:
            self.my_nickname.nickname = ' '.join(parted_msg[1:])
            self.message_callback.append(('msg', 'You have changed your nickname to '+
                                          parted_msg[1]+'.'))
            for peer in self.server.peers.keys():
                self.server.send_message(construct_message('nick', parted_msg[1]), peer)
        except ValueError as exception:
            self.message_callback.append(('msg', exception.args[0]))

    def whisp_to_peer(self, parted_msg):
        nickname = parted_msg[1]
        peer = self.server.get_peer_by_nick(nickname)
        if not peer:
            raise KeyError
        msg = ' '.join(parted_msg[2:])
        self.message_callback.append(('msg', self.my_nickname.nickname+
                                      ' (to '+nickname+'): '+msg))
        self.server.send_message(construct_message('whisp', msg), peer)

    def run(self, room):
        '''
        Run asyncore loop asynchronously. *such a pun*
        '''
        if room:
            self.server.join_room(room)
        self.netloop.start()

    def close(self):
        '''
        When chat window is closed, we should close every connection
        made and stop asyncore.
        '''
        core.network.close_all()
        self.netloop.join()

    def ban_peer(self, parted_msg):
        '''
        Ban peer. You won't be able to see messages from banned peer.
        '''
        nickname = parted_msg[1]
        self.server.ban(nickname)
        self.message_callback.append(('msg', "You've banned "+nickname+'.'))

    def unban_peer(self, parted_msg):
        '''
        Unban peer.
        '''
        nickname = parted_msg[1]
        self.server.unban(nickname)
        self.message_callback.append(('msg', "You've unbanned "+nickname+'.'))

    def send_msg(self, message):
        '''
        Send message to peers.
        Some messages aren't going to be sent to peers. They do some things in
        client instead (e.g. /ban).
        '''
        msg = re.sub(r'\s+', ' ', message)
        if msg == '' or msg == ' ':
            return
        while msg[0] == ' ':
            msg = msg[1:]
        parted_msg = msg.split(' ')
        if msg[0] == '/' and parted_msg[0] in self.commands_handler:
            try:
                self.commands_handler[parted_msg[0]](parted_msg)
            except IndexError:
                self.message_callback.append(('msg', 'Incomplete command.'))
            except KeyError:
                self.message_callback.append(('msg', 'Wrong nickname.'))
        elif msg[0] == '/' and parted_msg[0] not in self.commands_handler:
            self.message_callback.append(('msg', 'Wrong command.'))
        else:
            self.message_callback.append(('msg', self.my_nickname.nickname+': '+msg))
            msg = construct_message('plain-text', msg)
            for peer in self.server.peers.keys():
                self.server.send_message(msg, peer)

    def get_callback(self):
        '''
        This function is always called by chat interface. It returns all
        messages received since the last check.
        '''
        temp = self.message_callback
        self.message_callback = []
        return temp
