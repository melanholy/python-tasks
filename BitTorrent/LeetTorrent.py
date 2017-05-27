'''
Simple bittorrent-client. v0.4. OMG IT CAN SEED!!!

Usage: python tor.py [-h] [-o folder] [-ds speed] [-us speed] [-s] file [file ...]
Requirements: python v3.4. httplib2 module.

Copyright: (c) 2015 by Koshara Pavel.
'''

import os
from core.torrent import Torrent, download
from argparse import ArgumentParser
from core.becnode import bendecode

def check_file(data):
    '''
    Check if file has all needed fields.
    '''
    if 'announce' not in data and 'announce-list' not in data or 'info' not in data:
        return False
    if 'piece length' not in data['info'] or 'pieces' not in data['info']:
        return False
    if 'files' not in data['info'] and 'length' not in data['info'] or 'name' not in data['info']:
        return False
    if 'files' in data['info']:
        for file_ in data['info']['files']:
            if 'length' not in file_ or 'path' not in file_:
                return False
    else:
        if 'length' not in data['info']:
            return False
    return True

def main():
    '''
    Entry point. Gathers all incoming data and configures download.
    '''
    parser = ArgumentParser(description='Simple bittorrent-client. v0.4. OMG IT CAN SEED!!!')
    parser.add_argument('files', metavar='file', type=str, nargs='+',
                        help='torrent file[s] which you want to download')
    parser.add_argument('-o', metavar='folder', type=str,
                        help='output folder. Default: current folder.', default='')
    parser.add_argument('-ds', metavar='speed', type=int,
                        help='Max download speed in KB/s. Default: unlimited.', default=0)
    parser.add_argument('-us', metavar='speed', type=int,
                        help='Max upload speed in KB/s. Default: unlimited.', default=-1)
    parser.add_argument('-s', action='store_true',
                        help='This key tells BitTorent not to stop seeding after '
                        'download is completed.')
    arguments = parser.parse_args()
    if arguments.ds and arguments.ds < 200:
        print('Download speed limit should be more than 200 KB/s')
        return
    if arguments.us < 0 and arguments.us != -1:
        print('Speed cannot be less than zero.')
        return
    for index, file_ in enumerate(arguments.files):
        if not os.path.exists(file_):
            print(file_+' doesn\'t exists or you have no permission to read it.')
            del arguments.files[index]
    filesdata = []
    for file_ in arguments.files:
        with open(file_, 'rb') as tor_file:
            try:
                data = bendecode(tor_file.read().decode('latin1'))
                filesdata.append(data)
            except (ValueError, TypeError):
                print('File '+file_+' is bencoded incorrectly.')
    for data in filesdata:
        if not check_file(data):
            print('Some of files is invalid.')
            return
    for data in filesdata:
        print(data['info']['name'].encode('iso8859-1'))
    torrents = []
    for i in range(0, len(filesdata)):
        torrents.append(Torrent(arguments.ds, arguments.us))
        torrents[i].set_up(filesdata[i], arguments.o)
        Torrent.torrents_count += 1
    download(torrents, arguments.ds, arguments.s)

if __name__ == '__main__':
    main()
