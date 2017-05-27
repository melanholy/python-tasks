'''
Your python script suffers from lack of bugs? You've came to the right place.
This so called Debugger will help you to find old bugs. It may also add new ones.

Usage: python Debugger.py [-h]

Requirements: python v3.4. No third-party modules are needed.

Copyright: (c) 2015 by Koshara Pavel.
'''

ENV = globals().copy()

from argparse import ArgumentParser
from core.debugger import Debugger
from core.interface import DebuggerGUI

def main():
    '''
    Entry point. Handle arguments and run interface.
    '''
    parser = ArgumentParser(description='''Your python script suffers from lack of bugs? 
    	You've came to the right place. This so called Debugger will help you to find old
    	 bugs. It may also add new ones.
		Requirements: python v3.4(the only version program was tested in). No third-party
		modules are needed.''')
    parser.parse_args()
    interface = DebuggerGUI(Debugger(ENV))
    interface.run()

if __name__ == '__main__':
    main()
