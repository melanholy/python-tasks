'''
Decode bencoded string and encode objects to bencoded string.
'''

def bendecode(string):
    '''
    Decode benencoded object.
    '''
    if not isinstance(string, str):
        raise TypeError('Can\'t decode \'{}\' object. Must be \'str\''.format(type(string)))
    try:
        return DECODE_FUNCS[string[0]](string, 0)[0]
    except (ValueError, KeyError, IndexError):
        raise ValueError('Invalid bencoded string.')

def decode_str(string, pos):
    '''
    Decode benencoded string.
    '''
    leng = string[pos:string.index(':', pos)]
    pos += len(leng)+1
    return string[pos:pos+int(leng)], pos+int(leng)

def decode_int(string, pos):
    '''
    Decode benencoded number.
    '''
    return int(string[pos+1:string.index('e', pos)]), string.index('e', pos)+1

def decode_list(string, pos):
    '''
    Decode benencoded list.
    '''
    result = []
    pos += 1
    while string[pos] != 'e':
        element, pos = DECODE_FUNCS[string[pos]](string, pos)
        result.append(element)
    return result, pos+1

def decode_tuple(string, pos):
    '''
    Decode benencoded tuple.
    '''
    result = []
    pos += 1
    while string[pos] != 'e':
        element, pos = DECODE_FUNCS[string[pos]](string, pos)
        result.append(element)
    return tuple(result), pos+1

def decode_dict(string, pos):
    '''
    Decode benencoded dictionary.
    '''
    result = {}
    pos += 1
    while string[pos] != 'e':
        key, pos = DECODE_FUNCS[string[pos]](string, pos)
        result[key], pos = DECODE_FUNCS[string[pos]](string, pos)
    return result, pos+1

def benencode(data):
    '''
    Encode object using bencode.
    '''
    try:
        return ENCODE_FUNCS[type(data)](data)
    except KeyError:
        raise TypeError('Can\'t encode \'{}\' object.'.format(type(data)))

def encode_list(list_):
    '''
    Encode list using bencode.
    '''
    result = 'l'
    for elem in list_:
        result += ENCODE_FUNCS[type(elem)](elem)
    return result+'e'

def encode_tuple(tuple_):
    '''
    Encode tuple using bencode.
    '''
    result = 't'
    for elem in tuple_:
        result += ENCODE_FUNCS[type(elem)](elem)
    return result+'e'

def encode_str(string):
    '''
    Encode string using bencode.
    '''
    return str(len(string))+':'+string

def encode_dict(dic):
    '''
    Encode dictionary using bencode.
    '''
    result = 'd'
    for key, val in sorted(dic.items()):
        result += ENCODE_FUNCS[type(key)](key)+ENCODE_FUNCS[type(val)](val)
    return result+'e'

def encode_int(number):
    '''
    Encode number using bencode.
    '''
    return 'i'+str(number)+'e'


ENCODE_FUNCS = {}
ENCODE_FUNCS[tuple] = encode_tuple
ENCODE_FUNCS[list] = encode_list
ENCODE_FUNCS[dict] = encode_dict
ENCODE_FUNCS[int] = encode_int
ENCODE_FUNCS[str] = encode_str
DECODE_FUNCS = {}
DECODE_FUNCS['t'] = decode_tuple
DECODE_FUNCS['l'] = decode_list
DECODE_FUNCS['d'] = decode_dict
DECODE_FUNCS['i'] = decode_int
for i in range(0, 10):
    DECODE_FUNCS[str(i)] = decode_str
