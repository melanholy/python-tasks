import unittest
import mock
from core.debugger import Debugger, StopExec

ENV = globals().copy()

class TestAll(unittest.TestCase):
    def setUp(self):
        self.db = Debugger(ENV)

    def test_dis_line(self):
        frame = mock.Mock()
        frame.f_code.co_filename = "C:\\Python34\\Lib\\nonexistinglib.py"
        frame.f_lineno = 0
        frame.f_locals = {'a': 4, 'zero': '0'}
        trace = self.db.dispatch_line(frame)
        self.assertIsNone(trace)
        frame.f_code.co_filename = "tests.py"
        trace = self.db.dispatch_line(frame)
        self.assertIsNotNone(trace)
        self.db.mode = 'trace'
        self.db.cont = True
        self.db.dispatch_line(frame)
        self.assertEqual(self.db.get_callback(), [('line', 0, {}, {'a': 4, 'zero': '0'})])
        self.assertFalse(self.db.cont)
        self.db.abort = True
        self.assertRaises(StopExec, self.db.dispatch_line, frame)
        self.db.abort = False
        self.db.breakpoints['<string>'].append(0)
        self.db.cont = True
        self.db.mode = 'debug'
        self.db.file = '<string>'
        self.db.get_callback()
        self.db.dispatch_line(frame)
        self.assertEqual(self.db.get_callback(), [('line', 0, {}, {'a': 4, 'zero': '0'}), ('brpoint',)])

    def test_var_replacement(self):
        frame = mock.Mock()
        frame.f_code.co_filename = "<string>"
        frame.f_lineno = 0
        frame.f_locals = {'a': 4, 'zero': '0'}
        self.db.vars_replacements = [('zero', 1000000, 'local')]
        self.db.mode = 'trace'
        self.db.cont = True
        self.db.dispatch_line(frame)
        self.assertEqual(self.db.get_callback(), [('line', 0, {}, {'zero': 1000000, 'a': 4})])
        self.assertEqual(self.db.locals['zero'], 1000000)
        self.db.cont = True
        frame.f_globals = {'variable': 'value'}
        self.db.vars_replacements = [('variable', ['totallynotavalue'], 'global')]
        self.db.dispatch_line(frame)
        self.assertEqual(frame.f_globals, {'variable': ['totallynotavalue']})

    def test_edit_var(self):
        self.db.vars_replacements = []
        self.db.edit_variable('z', '34+7', 'int', 'local')
        self.assertEqual(self.db.vars_replacements, [('z', 41, 'local')])
        self.db.vars_replacements = []
        self.db.edit_variable('z', '"dddd"', 'str', 'local')
        self.assertEqual(self.db.vars_replacements, [('z', 'dddd', 'local')])
        self.db.vars_replacements = []
        self.db.edit_variable('z', '{"a": 4050, "wat": []}', 'dict', 'global')
        self.assertEqual(self.db.vars_replacements, [('z', {'a': 4050, 'wat': []}, 'global')])
        self.db.vars_replacements = []
        self.db.edit_variable('z', '("a", 4050, {"wat": []})', 'list', 'global')
        self.assertEqual(self.db.vars_replacements, [('z', ['a', 4050, {'wat': []}], 'global')])
        self.db.vars_replacements = []
        self.assertRaises(ValueError, self.db.edit_variable, 'z', '("a", 4050, {"wat": []})', 'lt', 'global')
        self.assertRaises(ValueError, self.db.edit_variable, 'z', '("a", 405"wat": []})', 'list', 'global')
        self.assertRaises(ValueError, self.db.edit_variable, 'z', 'wat', 'int', 'global')

    def test_dis_call(self):
        frame = mock.Mock()
        frame.f_code.co_filename = "<string>"
        frame.f_lineno = 0
        frame.f_code.co_name = 'epicfunc'
        frame.f_locals = {}
        self.db.dispatch_call(frame)
        self.assertEqual(self.db.get_callback(), [('enter_func', 'epicfunc', '()')])
        frame.f_locals = {'a': 4}
        self.db.dispatch_call(frame)
        self.assertEqual(self.db.get_callback(), [('enter_func', 'epicfunc', '(a=4)')])
        self.db.step = 'step'
        trace = self.db.dispatch_call(frame)
        self.assertEqual(self.db.callstack, [1, 1])
        self.assertIsNone(trace)
        self.db.get_callback()

    def test_dis_return(self):
        frame = mock.Mock()
        frame.f_code.co_filename = "<string>"
        frame.f_lineno = 0
        frame.f_code.co_name = 'epicfunc'
        frame.f_locals = {}
        self.db.callstack = [1]
        self.db.dispatch_return(frame)
        self.assertEqual(self.db.get_callback(), [('leave_func', 'epicfunc')])

if __name__ == '__main__':
    unittest.main()
