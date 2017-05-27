'''
A debugger class that can execute program in three modes: run, debug and trace.
All the conrol is done from the interface.
'''

import sys
import time
import os

PROGRAM_FILES = [
    os.path.abspath('Debugger.py'),
    os.path.abspath('core/debugger.py'),
    os.path.abspath('core/interface.py')
]

class Pipe(object):
    '''
    A class that simulates stdout and stderr.
    '''
    def __init__(self, redirector):
        self.redirector = redirector

    def write(self, string):
        '''
        Redirects stdout to the place user wants it to be in.
        '''
        self.redirector(string)

    def flush(self):
        '''
        Since it's not a real stdout, we don't need to flush.
        '''
        pass

class StopExec(Exception):
    '''
    Exception to stop execution of the program.
    '''

class Debugger():
    '''
    Python debugger base class.

    This class takes care of details of the trace facility.
    A class that will be using this one should implement user interaction.
    '''
    def __init__(self, env):
        self.env = env
        self.lineno = 0
        self.globals = {}
        self.locals = {}
        self.running = False
        self.callback = []
        self.abort = False
        self.mode = ''
        self.cont = False
        self.breakpoints = {'<string>': []}
        self.vars_replacements = []
        self.trace_functions = {
            'line': lambda e, v: self.dispatch_line(e),
            'call': lambda e, v: self.dispatch_call(e),
            'return': lambda e, v: self.dispatch_return(e),
            'exception': lambda e, v: self.dispatch_exception()
        }
        self.file = '<string>'
        self.step = ''
        self.callstack = []
        self.out = False

    def run(self, code, mode, args, file_):
        '''
        Run the program in given mode.
        Possible modes are: debug, trace, run.
        '''
        self.running = True
        self.globals = self.env.copy()
        self.globals['__file__'] = file_
        with open(file_) as input_file:
            import ast
            doc = ast.get_docstring(ast.parse(input_file.read()))
            self.globals['__doc__'] = doc
        self.locals = self.globals
        try:
            code = compile(code, '<string>', 'exec')
        except SyntaxError:
            self.callback.append(('stdout', 'File has invalid syntax.\n'))
            self.running = False
            return
        self.mode = mode
        if args:
            sys.argv = [sys.argv[0]]+args.split(' ')
        try:
            #sys.stdout = Pipe(lambda e: self.callback.append(('stdout', e)))
            #sys.stderr = Pipe(lambda e: self.callback.append(('exception', e)))
            if mode != 'run':
                sys.settrace(self.tracer)
            exec(code, self.globals, self.globals)
        except StopExec:
            pass
        finally:
            sys.settrace(None)
            self.callback.append(('stop', ))
            self.running = False
            self.cont = False
            self.lineno = 0
            self.step = ''
            self.file = '<string>'
            self.out = False
            self.callstack = []
            self.globals = {}
            self.locals = {}
            self.abort = False

    def stop(self):
        '''
        Stop execution of the program.
        '''
        if self.running:
            self.abort = True

    def tracer(self, frame, event, arg):
        '''
        This function is called every time any command was executed.
        Thanks to sys.settrace.
        '''
        return self.trace_functions[event](frame, arg)

    def dispatch_line(self, frame):
        '''
        Stop on this line if current mode is trace or if there is a
        breakpoint on this line. Otherwise continue execution.
        '''
        if frame.f_code.co_filename == '<string>' or \
            frame.f_code.co_filename not in PROGRAM_FILES and \
            os.path.exists(frame.f_code.co_filename):
            if self.mode == 'trace' or (frame.f_lineno in self.breakpoints[self.file] \
                and self.mode == 'debug'):
                if len(self.callstack) != 0 and self.step == 'stepout':
                    self.out = True
                self.file = frame.f_code.co_filename
                if self.file not in self.breakpoints:
                    self.breakpoints[self.file] = []
                self.locals = frame.f_locals
                self.callback.append(('line', frame.f_lineno, self.globals, self.locals))
                if self.mode == 'debug':
                    self.callback.append(('brpoint', ))
                while not self.cont and not self.out:
                    time.sleep(0.1)
                    if self.abort:
                        raise StopExec
                for replacement in self.vars_replacements:
                    if replacement[2] == 'local':
                        frame.f_locals[replacement[0]] = replacement[1]
                    else:
                        frame.f_globals[replacement[0]] = replacement[1]
                self.vars_replacements = []
                self.cont = False
            return self.tracer

    def dispatch_call(self, frame):
        '''
        Call function and add it to the callstack.
        '''
        if frame.f_code.co_filename == '<string>' or \
            frame.f_code.co_filename not in PROGRAM_FILES and \
            os.path.exists(frame.f_code.co_filename):
            if frame.f_code.co_name != '<module>':
                if self.step == 'step' or self.step == 'stepout':
                    return
                self.callstack.append(1)
                args = '('
                args += ', '.join(x[0]+'='+str(x[1]) for x in frame.f_locals.items())
                self.callback.append(('enter_func', frame.f_code.co_name, args+')'))
            return self.tracer

    def edit_variable(self, variable, value, type_, scope):
        '''
        Change value of given variable.
        '''
        code = 'v = {}({})'.format(type_, value)
        locals_ = {}
        try:
            exec(compile(code, '<str>', 'exec'), locals_, locals_)
        except:
            raise ValueError('Invalid value or type.')
        value = locals_['v']
        self.vars_replacements.append((variable, value, scope))

    def dispatch_return(self, frame):
        '''
        Delete function from callstack.
        '''
        if frame.f_code.co_filename == '<string>' or \
            frame.f_code.co_filename not in PROGRAM_FILES and \
            os.path.exists(frame.f_code.co_filename):
            if frame.f_code.co_name != '<module>':
                self.out = False
                self.callstack.pop()
                self.callback.append(('leave_func', frame.f_code.co_name))
            return self.tracer

    def dispatch_exception(self):
        '''
        Don't need to do anything. Exception will be caught later.
        '''
        return self.tracer

    def get_callback(self):
        '''
        Return all messages from callback.
        '''
        temp = self.callback
        self.callback = []
        return temp
