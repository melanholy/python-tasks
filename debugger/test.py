import inspect
import sys
import asyncore

def isdebugging():
    print(sys.gettrace())

asyncore.close_all()
isdebugging()

import b

b.ultra()

v = 4
print(v)
