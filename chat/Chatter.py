'''
Chat. Decentralized. Stylish. Simple.

Usage: python Chatter.py [-h] [-r room] [-n nickname]
Requirements: python v3+. No third-party modules are required.

Copyright: (c) 2015 by Koshara Pavel.
'''

from core.chat import Chat
from core.network import Peer
from configparser import ConfigParser
from core.interface import ChatGUI
from argparse import ArgumentParser
from core.other import Nickname, check_addr

def main():
    '''
    Entry point. Handle arguments and run and stop chat.
    '''
    config = ConfigParser()
    config.read('config.ini')
    parser = ArgumentParser(description='Decentralized chat.')
    parser.add_argument('-r', metavar='room', type=str,
                        help='Address of one member of a room to join to.'
                        ' If omitted, new room will be created.', default='')
    parser.add_argument('-n', metavar='nick', type=str,
                        help='Your nickname in chat.', default=config['DEFAULT']['Nickname'])
    parser.add_argument('-p', metavar='port', type=int,
                        help='Your port.')
    arguments = parser.parse_args()
    if not arguments.p:
        port = int(config['DEFAULT']['Port'])
    else:
        port = arguments.p
    if not check_addr(arguments.r) and arguments.r:
        print('Invalid address.')
    elif ' ' in arguments.n or '/' in arguments.n:
        print('Nickname should not contain spaces and slashes.')
    else:
        nickname = Nickname(arguments.n)
        server = Peer(nickname, port)
        chat = Chat(nickname, server)
        interface = ChatGUI(chat, server)
        try:
            chat.run(arguments.r)
            interface.run()
        finally:
            try:
                interface.close()
                server.send_close()
                chat.close()
            except RuntimeError:
                pass

if __name__ == '__main__':
    main()
