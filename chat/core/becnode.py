'''
Decode bencoded string and encode objects to bencoded string.
'''

def bendecode(string):
    if not isinstance(string, str):
        raise TypeError('Can\'t decode \'{}\' object. Must be \'str\''.format(type(string)))
    try:
        return decode_funcs[string[0]](string, 0)[0]
    except (ValueError, KeyError, IndexError):
        raise ValueError('Invalid bencoded string.')

def decode_str(string, pos):
    leng = string[pos:string.index(':', pos)]
    pos += len(leng)+1
    return string[pos:pos+int(leng)], pos+int(leng)

def decode_int(string, pos):
    return int(string[pos+1:string.index('e', pos)]), string.index('e', pos)+1

def decode_list(string, pos):
    result = []
    pos += 1
    while string[pos] != 'e':
        element, pos = decode_funcs[string[pos]](string, pos)
        result.append(element)
    return result, pos+1

def decode_tuple(string, pos):
    result = []
    pos += 1
    while string[pos] != 'e':
        element, pos = decode_funcs[string[pos]](string, pos)
        result.append(element)
    return tuple(result), pos+1

def decode_dict(string, pos):
    result = {}
    pos += 1
    while string[pos] != 'e':
        key, pos = decode_funcs[string[pos]](string, pos)
        result[key], pos = decode_funcs[string[pos]](string, pos)
    return result, pos+1

def benencode(data):
    try:
        return encode_funcs[type(data)](data)
    except KeyError:
        raise TypeError('Can\'t encode \'{}\' object.'.format(type(data)))

def encode_list(list_):
    result = 'l'
    for elem in list_:
        result += encode_funcs[type(elem)](elem)
    return result+'e'

def encode_tuple(tuple_):
    result = 't'
    for elem in tuple_:
        result += encode_funcs[type(elem)](elem)
    return result+'e'

def encode_str(string):
    return str(len(string))+':'+string

def encode_dict(dic):
    result = 'd'
    for key, val in sorted(dic.items()):
        result += encode_funcs[type(key)](key)+encode_funcs[type(val)](val)
    return result+'e'

def encode_int(number):
    return 'i'+str(number)+'e'


encode_funcs = {}
encode_funcs[tuple] = encode_tuple
encode_funcs[list] = encode_list
encode_funcs[dict] = encode_dict
encode_funcs[int] = encode_int
encode_funcs[str] = encode_str
decode_funcs = {}
decode_funcs['t'] = decode_tuple
decode_funcs['l'] = decode_list
decode_funcs['d'] = decode_dict
decode_funcs['i'] = decode_int
for i in range(0, 10):
    decode_funcs[str(i)] = decode_str
