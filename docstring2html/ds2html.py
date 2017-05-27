'''
Extract all methods, classes, functions and their docstrings
from python code and put them into html document.

Usage: python ds2html.py [-h] file [files...]
Requirements: python v3+ and jinja2.

Copyright: (c) 2015 by Koshara Pavel.
'''

import ast
import os
import shutil
import re
import html
from jinja2 import Template
from argparse import ArgumentParser
from collections import OrderedDict

ASTTYPES = {}
ASTTYPES[ast.Num] = lambda x: x.n
ASTTYPES[ast.NameConstant] = lambda x: x.value
ASTTYPES[ast.Name] = lambda x: x.id
ASTTYPES[ast.Str] = lambda x: x.s
ASTTYPES[ast.Tuple] = lambda x: tuple([ASTTYPES[type(y)](y) for y in x.elts])
ASTTYPES[ast.Attribute] = lambda x: ASTTYPES[type(x.value)](x.value)+'.'+x.attr
ASTTYPES[ast.List] = lambda x: str([ASTTYPES[type(y)](y) for y in x.elts])
ASTTYPES[ast.Bytes] = lambda x: x.s
ASTTYPES[ast.Call] = lambda x: (ASTTYPES[type(x.func)](x.func)+
                                '('+', '.join([str(ASTTYPES[type(y)](y)) for y in x.args])+')')
ASTTYPES[ast.UnaryOp] = lambda x: x.operand.n*-1
ASTTYPES[ast.Dict] = lambda x: dict((ASTTYPES[type(x.keys[y])](x.keys[y]),
                                     ASTTYPES[type(x.values[y])](x.values[y]))
                                    for y in range(0, len(x.keys)))
ASTTYPES[ast.Set] = lambda x: str(set([ASTTYPES[type(y)](y) for y in x.elts]))
TYPES = ['str', 'list', 'tuple', 'int', 'float', 'None', 'bool', 'False',
         'True', 'bytes', 'bytearray']

def fill_html(htmlfile, astrees, files, args):
    '''
    Fill html file with code.
    This function gathers all docstrings into one dictionary and sends it into jinja2
    Template render. Then rendered html-code goes to htmlfile.
    '''
    data = OrderedDict()
    for filename, astree in astrees.items():
        data[filename] = {}
        #main docstring
        data[filename]['docstr'] = replace(ast.get_docstring(astree))
        #classes
        classes = []
        for node in [node for node in astree.body if isinstance(node, ast.ClassDef)]:
            docstr = replace(ast.get_docstring(node))
            #methods
            methods = extract_functions(node.body)
            classes.append({'methods': methods, 'name': node.name, 'docstr': docstr})
        data[filename]['classes'] = classes
        #functions
        data[filename]['functions'] = extract_functions(astree.body)
    with open(args.p, encoding="utf8") as pattern:
        template = pattern.read()
    template = Template(template, trim_blocks=True, lstrip_blocks=True, autoescape=False)
    htmlcode = template.render(data=data, files=files, mode=args.m)
    htmlcode = rst_to_html(htmlcode)
    htmlfile.write(htmlcode)

def rst_to_html(data):
    '''
    Translate basic elements of reStructuredText to html.
    '''
    data = re.sub(r'\*\*([^<]+?)\*\*', r'<b>\1</b>', data)
    data = re.sub(r'\*(.+?)\*', r'<i>\1</i>', data)
    data = re.sub(r'``(.+?)``', r'<tt class="literal">\1</tt>', data)
    for literal in [x for x in re.findall(r'`.+?`', data) if 'id="'+x[1:-1]+'"' not in data]:
        data = data.replace(literal, '<tt class="literal">'+literal[1:-1]+'</tt>')
    data = re.sub(r'(?<!\.\.)( \w+):(:)<br><br>(.+?)(<br>[^&<]|</p>)', r'\1\2<pre>\3</pre>\4',
                  data, flags=re.DOTALL)
    data = re.sub(r'\.\. sourcecode:: .+?<br><br>(.+?)(<br>[^&<]|</p>)', r'<pre>\1</pre>\2',
                  data, flags=re.DOTALL)
    data = re.sub(r'`(.+?)`', r'<a class="flink" href="#\1">\1</a>', data)
    data = data.replace(':class:', '').replace(':meth:', '').replace(':exc:', '') \
               .replace(':attr:', '').replace(':ref:', '').replace(':func:', '') \
               .replace(':keyword:', '').replace(':mod:', '')
    data = re.sub(r'\.\. versionadded:: (.+?)<', r'<i>New in version \1</i><', data)
    data = re.sub(r'\.\. versionchanged:: (.+?)<', r'<i>Changed in version \1</i><', data)
    data = re.sub(r'\.\. deprecated:: (.+?)<', r'<i>Deprecated since version \1</i><', data)
    data = re.sub(r'<br>\.\. admonition:: (.+?)<br><br>',
                  r'<h1 style="font-weight:100;font-size:136%">\1</h1>', data)
    data = re.sub(r'\.\. (\w+?:):<br><br>(.+?)(<br><br>)', r'\1<pre>\2</pre>\3',
                  data, flags=re.DOTALL)
    data = make_tables(data)
    data = re.sub(r'<br>:[^\s]+ (\w+)', r'<br><i>\1</i>', data)
    return data

def extract_functions(node):
    '''
    Return list containing dictionaries representing functions extracted
    from given ast node.
    '''
    functions = []
    for node in [x for x in node if isinstance(x, ast.FunctionDef)]:
        docstr = replace(ast.get_docstring(node))
        functions.append({'name': node.name, 'sign': get_sign(node), 'docstr': docstr})
    return functions

def make_tables(string):
    '''
    Converts rst tables looking like below:

        :licence: blah-blah
        :author: Petya Levkin

    to html tables.
    '''
    table = False
    table_code = ''
    orig_table = ''
    table_codes = {}
    for line in string.split('<br>'):
        match = re.match(r':(\w+):(.+)', line)
        if match:
            if not table:
                table = True
                orig_table += line+'<br>'
                table_code += ('<table>\n<tbody>\n<tr valign="top"><td><b>'+
                               match.group(1).capitalize()+':</b></td><td>'+
                               match.group(2)+'</td></tr>')
            else:
                orig_table += line+'<br>'
                table_code += ('<tr><td><b>'+match.group(1).capitalize()+
                               ':</b></td><td>'+match.group(2)+'</td></tr>')
        if not match and table:
            table_codes[orig_table] = table_code+'</tbody></table>'
            orig_table = ''
            table_code = ''
            table = False
    if table:
        table_codes[orig_table] = table_code+'</tbody></table>'
    for key, value in table_codes.items():
        string = string.replace(key[:-4], value)
    return string

def replace(string):
    '''
    Replace all line feeds with breaks and double white spaces with two
    non-breakable spaces and decorate some elements of text. For html.
    '''
    if string is None:
        return ''
    string = html.escape(string)
    res = re.search(r'\n([\*+-][^\n]+\n(?:(?:  [^\n]+\n)+)?)+', string)
    if res:
        res = res.group(0)[1:]
        table = '<ul>'+res.replace(res[0]+' ', '<li> ').replace('\n'+res[0], '</li>')+'</ul>'
        string = string.replace(res, table)
    string = re.sub(r'(_?_?(?:[a-z\.]+?_)+\w*\([\w, =\[\]]*\))',
                    r'<tt class="literal">\1</tt>', string)
    string = re.sub(r'([a-z]+?\([\w, =\[\]]*\))(?!<)', r'<tt class="literal">\1</tt>', string)
    for type_ in TYPES:
        string = re.sub('( )('+type_+')( )', r'\1<tt class="literal">\2</tt>\3', string)
        string = re.sub(r'( )('+type_+r')([^\w\s\d])', r'\1<tt class="literal">\2</tt>\3', string)
    string = decorate_code(string)
    string = string.replace('\n', '<br>').replace('  ', '&nbsp&nbsp')
    return string

def decorate_code(string):
    '''
    Converts some rst elements to html. Need to be separated from
    rst_to_html because of \\n replacements.
    '''
    current_code = ''
    codes = []
    code = string[:3] == '&gt;&gt;&gt;'
    for line in string.split('\n'):
        if code:
            current_code += line+'\n'
        if re.match(r'\s*&gt;&gt;&gt;', line) or (re.match(r'\s*\.\.\.', line)
                                                  or re.match(r'\s*Traceback', line)) and code:
            if not code:
                if current_code not in codes:
                    codes.append(current_code)
                current_code = ''
                current_code += line+'\n'
            code = True
        else:
            code = False
    if current_code:
        codes.append(current_code[:-1])
    for code in [x for x in codes if x]:
        string = string.replace(code, '<pre>'+code+'</pre>')
    specsymbols = ['"', '`', '`', '=', "'", '-', '`', ':', '~', r'\^', r'\_', r'\*',
                   r'\+', r'\#', r'\<', r'\>']
    titles = []
    subtitles = []
    for symbol in specsymbols:
        titles += re.findall(symbol+r'+\n.+?\n'+symbol+r'+\n', string)
    for title in titles:
        word = ''.join([x for x in title if x not in specsymbols])
        string = string.replace(title, '<h3>'+word+'</h3>')
    for symbol in specsymbols:
        subtitles += re.findall(r'.+?\n'+symbol+r'+\n', string)
    for title in subtitles:
        word = ''.join([x for x in title if x not in specsymbols and x != '\n'])
        string = string.replace(title, '<h3 style="font-size:120%">'+word+'</h3>')
    return string

def get_sign(astfunc):
    '''
    Get signature of given ast.FunctionDef.
    '''
    args = astfunc.args.args
    defaults = []
    for value in astfunc.args.defaults:
        try:
            defaults.append('='+str(ASTTYPES[type(value)](value)))
        except KeyError:
            defaults.append('')
    defaults = list(reversed(defaults))
    while len(defaults) != len(args):
        defaults.append('')
    defaults = list(reversed(defaults))
    result = ', '.join([x.arg+defaults[index] for index, x in enumerate(args)])
    return html.escape(result)

def get_files(argfiles):
    '''
    Return two lists containing paths to files found in given
    arguments and their names.
    '''
    files, filenames = [], []
    for file_ in argfiles:
        if not os.path.exists(file_):
            print(file_+' doesn\'t exists or you have no permission to read it.')
        elif os.path.isdir(file_):
            file_ = file_.replace('\\', '/')
            if file_[-1] == '/':
                file_ = file_[:-1]
            if not os.path.exists(file_+'/__init__.py'):
                files += [file_+'/'+x for x in os.listdir(file_) if x[-3:] == '.py']
                filenames += [file_.replace(':', '')+'/'+x
                              for x in os.listdir(file_) if x[-3:] == '.py']
            else:
                modulename = os.path.basename(file_)
                tree = os.walk(file_)
                for dir_ in tree:
                    files += [dir_[0]+'/'+x for x in dir_[2] if x[-3:] == '.py']
                    filenames += [modulename+'/'+(dir_[0]+'/'+x).replace(file_, '')
                                  .replace('\\', '/')[1:]
                                  for x in dir_[2] if x[-3:] == '.py']
        elif file_[-3:] != '.py':
            print(file_+' is not a python file.')
        else:
            files.append(file_)
            filenames.append(os.path.basename(file_))
    filenames = [x.replace('/', '.') for x in filenames]
    return files, filenames

def create_docs(arguments, files, filenames):
    '''
    Create astrees and blank files and then send them into fill_html function.
    '''
    if arguments.m == 'sep':
        with open('indexpattern.html', encoding="utf8") as pattern:
            template = pattern.read()
        template = Template(template, trim_blocks=True, lstrip_blocks=True, autoescape=False)
        htmlcode = template.render(files=filenames, mode=arguments.m)
        with open(arguments.o+'/index.html', 'w') as indexfile:
            indexfile.write(htmlcode)
    astrees = OrderedDict()
    for index, file_ in enumerate(files):
        try:
            with open(file_, encoding='utf-8-sig') as inputfile:
                astree = ast.parse(inputfile.read())
        except (SyntaxError, TypeError):
            print(file_+' has invalid syntax.')
            continue
        except UnicodeDecodeError:
            continue
        filename = filenames[index]
        if arguments.m == 'sep':
            with open(arguments.o+'/'+(filename+'.html').replace('/', '.')
                      .replace(':', ''), 'w') as htmlfile:
                fill_html(htmlfile, {filename: astree}, filenames, arguments)
        else:
            astrees[filename] = astree
    if arguments.m == 'allin':
        with open(arguments.o+'/'+arguments.n, 'w') as htmlfile:
            fill_html(htmlfile, astrees, filenames, arguments)
    shutil.copy('style.css', arguments.o+'/style.css')

def main():
    '''
    Entry point. Gather all files in one list and start create_docs function.
    '''
    parser = ArgumentParser(description='Extracts all docstrings and '
                            'names of methods, classes and functions '
                            'from python code and puts them into html document.')
    parser.add_argument('files', metavar='file', type=str, nargs='+',
                        help='python files to convert. If file is a directory, all .py '
                        'files from it will be converted.')
    parser.add_argument('-m', metavar='mode', type=str,
                        help='create new html for each file(sep) or all in '
                        'one(allin). Default: allin.', default='allin')
    parser.add_argument('-n', metavar='filename', type=str,
                        help='output html filename. Default: out.html. '
                        'Works only with -m allin.', default='out.html')
    parser.add_argument('-p', metavar='pattern', type=str,
                        help='html-pattern written using jinja2. Default and example: '
                        'pattern.html', default='pattern.html')
    parser.add_argument('-o', metavar='filename', type=str,
                        help='Directory in which files will be saved. Default: out',
                        default='out')
    arguments = parser.parse_args()
    if os.path.exists(arguments.o) and not os.path.isdir(arguments.o):
        print('Unable to create '+arguments.o+'. Please select another directory.')
        return
    if not os.path.exists(arguments.o):
        os.mkdir(arguments.o)
    files, filenames = get_files(arguments.files)
    if arguments.m not in ['allin', 'sep']:
        print('Wrong mode')
        parser.print_help()
        return
    create_docs(arguments, files, filenames)

if __name__ == '__main__':
    main()
