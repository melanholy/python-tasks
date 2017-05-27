import unittest
import ds2html

class TestDocstring2html(unittest.TestCase):
    def test_replace(self):
        self.assertEqual(ds2html.replace('\n\n'), '<br><br>')
        self.assertEqual(ds2html.replace('func()'), '<tt class="literal">func()</tt>')
        self.assertEqual(ds2html.replace(' None '), ' <tt class="literal">None</tt> ')
        self.assertEqual(ds2html.replace('__main_function()'), '<tt class="literal">__main_function()</tt>')
        self.assertEqual(ds2html.replace('     '), '&nbsp&nbsp&nbsp&nbsp ')
        self.assertEqual(ds2html.replace(None), '')
        self.assertEqual(ds2html.replace('\nargparse\n========\n'), '<br><h3 style="font-size:120%">argparse</h3>')
        self.assertEqual(ds2html.replace(' None?'), ' <tt class="literal">None</tt>?')
        self.assertEqual(ds2html.replace('\n========\nargparse\n========\n'), '<br><h3><br>argparse<br><br></h3>')
        self.assertEqual(ds2html.replace('>>>foo\nbar\n'), '<pre>&gt;&gt;&gt;foo<br>bar</pre><br>')
        self.assertEqual(ds2html.replace('Bullet lists:\n\n- This is item 1\n- Bullets are "-", '
                                         '"*" or "+".\nContinuing text must be aligned.\n\nlalala'),
                                         'Bullet lists:<br><br><ul><li> This is item 1<br><li> Bullets are &quot;-&quot;, &quot;*&quot; or &quot;+&quot;.<br></ul>Continuing text must be aligned.<br><br>lalala')

    def test_func_extract(self):
        import ast
        with open('testscript.py', encoding='utf8') as f:
            astree = ast.parse(f.read())
        funcs = ds2html.extract_functions(astree.body)
        for func in funcs:
            if func['name'] == 'poll':
                self.assertEqual(func['sign'], 'timeout=0.0, map=None')
                self.assertEqual(func['docstr'], '')
            if func['name'] == 'loop':
                self.assertEqual(func['sign'], 'timeout=30.0, use_poll=False, map=None, count=None')
                self.assertEqual('', func['docstr'])
            if func['name'] == 'main':
                self.assertEqual(func['sign'], '')
                self.assertEqual(func['docstr'], 'Entry point. Gather all files in one <tt class="literal">list</tt> and start create_docs function.')
            if func['name'] == 'fill_html':
                self.assertEqual(func['sign'], 'htmlfile, astrees, files, args')
                self.assertIn('Fill html file with code.', func['docstr'])

    def test_rst_to_html(self):
        self.assertEqual(ds2html.rst_to_html('Return a formatted dump of the tree in *node*.' \
                                             ' This is :class:``mainly`` useful **for** debugging purposes.'),
                         'Return a formatted dump of the tree in <i>node</i>. '
                         'This is <tt class="literal">mainly</tt> useful <b>for</b> '
                         'debugging purposes.')
        self.assertEqual(ds2html.rst_to_html(' Code::<br><br>a = 2 if a == 3: return 8 <br>NewLine'),
                         ' Code:<pre>a = 2 if a == 3: return 8 </pre><br>NewLine')
        self.assertEqual(ds2html.rst_to_html(':copyright: Copyright 2008 by Armin Ronacher.<br>:license: Python License.'), 
                         '<table>\n<tbody>\n<tr valign="top"><td><b>Copyright:</b></td><td> Copyright 2008 by Armin Ronacher.'
                         '</td></tr><tr><td><b>License:</b></td><td> Python License.</td></tr></tbody></table>')
        self.assertEqual(ds2html.rst_to_html('.. versionchanged:: 666<br>'), '<i>Changed in version 666</i><br>')
        self.assertEqual(ds2html.rst_to_html('.. note::<br><br>This is test.<br><br>'), 'note:<pre>This is test.</pre><br><br>')
        self.assertEqual(ds2html.rst_to_html('<br>:param length: max length of file.'), '<br><i>length</i>: max length of file.')

    def test_get_files(self):
        self.assertEqual(ds2html.get_files(['.']), 
                         (['./tests.py', './ds2html.py', './testscript.py'], ['..tests.py', '..ds2html.py', '..testscript.py']))
        self.assertEqual(ds2html.get_files(['../BitTorrent/core']),
                         (['../BitTorrent/core/tests.py', '../BitTorrent/core/torrent.py', '../BitTorrent/core/peer.py',
                           '../BitTorrent/core/becnode.py', '../BitTorrent/core/tracker.py', '../BitTorrent/core/__init__.py'], 
                          ['core.tests.py', 'core.torrent.py', 'core.peer.py', 'core.becnode.py', 'core.tracker.py', 'core.__init__.py']))

if __name__ == '__main__':
    unittest.main()
