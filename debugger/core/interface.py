'''
A class that contains methods for work with debugger interface.
'''

import tkinter
import tkinter.filedialog
import time
import math
import os
from tkinter import ttk
from threading import Thread

class DebuggerGUI(object):
    '''
    Interface for debugger written using Tkinter.
    '''
    def __init__(self, debugger):
        self.debugger = debugger
        self.interface = tkinter.Tk()
        self.programs = {}
        self.cur_program = None
        self.breakpoints = {}
        self.mode = ''
        self.message_handler = {
            'leave_func': lambda e: self.callstack.delete('end'),
            'enter_func': lambda e: self.callstack.insert('end', e[0]+e[1]),
            'stop': lambda e: self.stop_program(),
            'stdout': self.add_msg_to_outputbox,
            'exception': self.handle_exception,
            'line': self.update_state
        }
        self.interface.title('Debugger')
        bot = ttk.Frame(self.interface, height=10)
        top = ttk.Frame(self.interface)
        middle = ttk.Frame(self.interface)
        right = ttk.Frame(self.interface)
        self.add_buttons(top)
        self.callstack = tkinter.Listbox(right, selectmode='single', width=40)
        self.callstack.pack(side='bottom', fill='y', expand=1)
        self.callstack.insert('end', 'Callstack:')
        self.var_list = tkinter.Listbox(right, selectmode='single', width=40)
        self.var_list.pack(side='top', fill='y', expand=1)
        self.var_list.insert('end', 'Globals:')
        self.var_list.insert('end', 'Locals:')
        menu = tkinter.Menu(tearoff=0)
        menu.add_command(label='Edit', command=self.edit_variable)
        self.var_list.bind('<Button-3>', lambda e: self.context_menu(e, menu))
        self.codebox = ttk.Notebook(middle)
        self.codebox.bind('<<NotebookTabChanged>>', lambda e: self.change_tab())
        self.codebox.pack(fill='both', expand=1)
        right.pack(side='right', fill='y')
        top.pack(side='top')
        middle.pack(side='top', fill='both', expand=1)
        bot.pack(side='bottom', fill='both', expand=1)
        self.configure_menu()
        self.configure_output_box(bot)
        self.codebox_line_height = 0
        self.selected_var = None
        self.cur_file = ''
        self.cur_brpoint = None
        self.files = []

    def add_buttons(self, master):
        '''
        Add step, step in, step out, continue and stop buttons to the GUI.
        '''

        def add_button(text, binding):
            button = ttk.Button(master, text=text)
            button.bind('<Button-1>', binding)
            button.pack(side='left')

        add_button('Step', lambda e: self.next_step('step'))
        add_button('Step In', lambda e: self.next_step('stepin'))
        add_button('Step Out', lambda e: self.next_step('stepout'))
        add_button('Continue', lambda e: self.continue_prog())
        add_button('Stop', lambda e: self.stop_program())

    def change_tab(self):
        '''
        Make selected tab active.
        '''
        tab_id = self.codebox.tabs()[self.codebox.index('current')]
        textbox, brpoint_panel, file_ = self.programs[tab_id]
        self.cur_program = textbox
        self.cur_file = file_
        self.cur_brpoint = brpoint_panel

    def add_tab_to_codebox(self, code, file_, main=False):
        '''
        Add tab for file opened and set its configuration.
        '''

        def set_line_height(textbox):
            self.codebox_line_height = textbox.winfo_height()/textbox['height']

        frame = ttk.Frame(self.codebox)
        textbox = tkinter.Text(frame, font=('Helvetica', 10))
        self.codebox.add(frame, text=os.path.basename(file_))
        tab_id = self.codebox.tabs()[-1]
        textbox.insert('end', code)
        textbox.configure(state=tkinter.DISABLED)
        textbox.bind('<MouseWheel>', self.move_text_with_wheel)
        textbox.bind('<Button-4>', lambda e: self.move_text_with_wheel_linux(-1))
        textbox.bind('<Button-5>', lambda e: self.move_text_with_wheel_linux(1))
        textbox.tag_config('breakpoint', background='red')
        textbox.tag_config('current', background='yellow')
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side='right', fill='y')
        textbox.pack(side='right', fill='both', expand=1)
        scrollbar['command'] = lambda e, v: self.move_text_with_scrollbar(v)
        textbox['yscrollcommand'] = scrollbar.set
        brpoint_panel = tkinter.Canvas(frame, width=15, yscrollcommand=scrollbar.set)
        brpoint_panel.bind('<Button-1>', self.set_breakpoint)
        brpoint_panel.pack(side='left', fill='both')
        self.programs[tab_id] = (textbox, brpoint_panel, '<string>' if main else file_)
        self.files.append(file_)
        self.interface.after(500, lambda: set_line_height(textbox))
        self.codebox.select(tab_id)

    def configure_output_box(self, master):
        '''
        Set config of box containing program stdout.
        '''
        self.outputbox = tkinter.Text(master, height=10, state=tkinter.DISABLED)
        self.outputbox.pack(side='left', fill='both', expand=1)
        scrollbar = ttk.Scrollbar(master)
        scrollbar['command'] = self.outputbox.yview
        scrollbar.pack(side='right', fill='y')
        self.outputbox['yscrollcommand'] = scrollbar.set

    def configure_menu(self):
        '''
        Configure topmenu. It allows user to stop or run the script
        or load new script.
        '''
        topmenu = tkinter.Menu(self.interface, tearoff=0)
        self.interface.config(menu=topmenu)
        topmenu_file = tkinter.Menu(topmenu, tearoff=0)
        topmenu.add_cascade(label="File", menu=topmenu_file)
        topmenu_file.add_command(label="Load", command=self.load_file)
        topmenu_run = tkinter.Menu(topmenu, tearoff=0)
        topmenu.add_cascade(label="Run", menu=topmenu_run)
        topmenu_run.add_command(label="Run", command=lambda: self.run_program('run'))
        topmenu_run.add_command(label="Trace", command=lambda: self.run_program('trace'))
        topmenu_run.add_command(label="Debug", command=lambda: self.run_program('debug'))

    def add_msg_to_outputbox(self, message):
        '''
        Insert message in the end of outputbox.
        '''
        self.outputbox.config(state=tkinter.NORMAL)
        self.outputbox.insert('end', message[0].replace('\\n', '\n'))
        self.outputbox.see('end')
        self.outputbox.config(state=tkinter.DISABLED)

    def handle_exception(self, message):
        '''
        Print information about exception occurred in user's script.
        '''
        self.outputbox.config(state=tkinter.NORMAL)
        self.outputbox.insert('end', message)
        self.outputbox.see('end')
        self.outputbox.config(state=tkinter.DISABLED)

    def update_state(self, args):
        '''
        Mark the line currently executing and add current local and
        global variables to list.
        '''
        lineno = str(args[0])
        locals_ = args[2].copy()
        globals_ = args[1].copy()
        self.cur_program.config(state=tkinter.NORMAL)
        self.cur_program.tag_remove('current', '0.0', 'end')
        self.cur_program.tag_add('current', lineno+'.0', lineno+'.end')
        self.cur_program.see(lineno+'.0')
        self.cur_program.config(state=tkinter.DISABLED)
        self.var_list.delete('0', 'end')
        self.var_list.insert('end', 'Globals:')
        for var, val in globals_.items():
            self.var_list.insert('end', var+': '+str(val))
        self.var_list.insert('end', 'Locals:')
        for var, val in locals_.items():
            self.var_list.insert('end', var+': '+str(val))

    def move_text_with_wheel(self, event):
        '''
        Move text in codebox and all breakpoints on breakpoint panel
        using mouse wheel.
        '''
        scroll_speed = 0.086
        brpoint_panel_width = 100
        velocity = -1 if event.delta > 0 else 1
        yview = self.cur_program.yview()[0]
        self.cur_program.yview('moveto', yview+scroll_speed*velocity)
        full_height = self.cur_program.winfo_height()/(self.cur_program.yview()[1]-self.cur_program.yview()[0])
        self.cur_brpoint['scrollregion'] = (0, 0, brpoint_panel_width, full_height)
        self.cur_brpoint.yview('moveto', yview+scroll_speed*velocity)
        return 'break'

    def move_text_with_wheel_linux(self, velocity):
        '''
        Move text in codebox and all breakpoints on breakpoint panel
        using mouse wheel.
        '''
        scroll_speed = 0.086
        brpoint_panel_width = 100
        yview = self.cur_program.yview()[0]
        self.cur_program.yview('moveto', yview+scroll_speed*velocity)
        full_height = self.cur_program.winfo_height()/(self.cur_program.yview()[1]-self.cur_program.yview()[0])
        self.cur_brpoint['scrollregion'] = (0, 0, brpoint_panel_width, full_height)
        self.cur_brpoint.yview('moveto', yview+scroll_speed*velocity)
        return 'break'

    def move_text_with_scrollbar(self, pos):
        '''
        Move text in codebox and all breakpoints on breakpoint panel
        using scrollbar.
        '''
        pos = float(pos)
        brpoint_panel_width = 100
        full_height = self.cur_program.winfo_height()/(self.cur_program.yview()[1]-self.cur_program.yview()[0])
        self.cur_brpoint['scrollregion'] = (0, 0, brpoint_panel_width, full_height)
        self.cur_brpoint.yview('moveto', pos)
        self.cur_program.yview('moveto', pos)

    def next_step(self, step):
        '''
        Execute next line and set current mode to "trace".
        '''
        if self.mode == 'run' or len(self.codebox.tabs()) == 0:
            return
        self.debugger.mode = 'trace'
        self.debugger.step = step
        self.mode = 'trace'
        if self.debugger.running:
            self.debugger.cont = True

    def continue_prog(self):
        '''
        Execute program until the EOF or until the next breakpoint.
        '''
        if self.mode == 'run' or len(self.codebox.tabs()) == 0:
            return
        self.debugger.mode = 'debug'
        self.mode = 'debug'
        if self.debugger.running:
            self.debugger.cont = True

    def set_breakpoint(self, event):
        '''
        Add breakpoint to breakpoint list of interpreter and mark the
        line with breakpoint.
        '''
        center_of_brpoint_panel = 9
        brpoint_mark_radius = 6
        full_height = self.cur_program.winfo_height()/(self.cur_program.yview()[1]-self.cur_program.yview()[0])
        yview = self.cur_program.yview()[0]*full_height
        line = str(math.ceil((yview+event.y)/self.codebox_line_height))
        if self.cur_program.get(line+'.0', line+'.end') != '':
            if int(line) not in self.debugger.breakpoints[self.cur_file]:
                posy = yview+event.y
                posy -= posy%self.codebox_line_height-self.codebox_line_height*0.4
                posx = center_of_brpoint_panel
                name = self.cur_brpoint.create_oval(
                    posx-brpoint_mark_radius,
                    posy+brpoint_mark_radius,
                    posx+brpoint_mark_radius,
                    posy-brpoint_mark_radius,
                    fill='red'
                )
                if self.cur_file not in self.breakpoints:
                    self.breakpoints[self.cur_file] = {}
                self.breakpoints[self.cur_file][line] = name
                self.debugger.breakpoints[self.cur_file].append(int(line))
                self.cur_program.tag_add('breakpoint', line+'.0', line+'.end')
            else:
                del self.debugger.breakpoints[self.cur_file][self.debugger.breakpoints[self.cur_file].index(int(line))]
                self.cur_brpoint.delete(self.breakpoints[self.cur_file][line])
                self.cur_program.tag_remove('breakpoint', line+'.0', line+'.end')

    def stop_program(self):
        '''
        Stop execution of program.
        '''
        if len(self.codebox.tabs()) == 0:
            return
        for prog in self.programs.values():
            prog[0].tag_remove('current', '0.0', 'end')
        self.callstack.delete('0', 'end')
        self.callstack.insert('end', 'Callstack:')
        self.var_list.delete('0', 'end')
        self.var_list.insert('end', 'Globals:')
        self.var_list.insert('end', 'Locals:')
        self.debugger.stop()

    def run_program(self, mode):
        '''
        Start execution of program in given mode.
        Possible modes are: debug, trace, run.
        '''
        def run():
            self.mode = mode
            args = inbox.get()
            tab_id = self.codebox.tabs()[self.codebox.index('current')]
            textbox = self.programs[tab_id][0]
            code = textbox.get('0.0', 'end')
            interpreter = Thread(target=lambda: self.debugger.run(code, mode, args, self.files[0]))
            painter = Thread(target=self.paint)
            interpreter.daemon = True
            painter.daemon = True
            interpreter.start()
            painter.start()
            toplevel.destroy()

        if self.debugger.running or len(self.codebox.tabs()) == 0:
            return
        self.codebox.select(self.codebox.tabs()[0])
        toplevel = tkinter.Toplevel()
        toplevel.title('Arguments')
        inbox = ttk.Entry(toplevel, width=25)
        send_btn = ttk.Button(toplevel, text='Run')
        send_btn.bind('<Button-1>', lambda e: run())
        message = tkinter.Message(master=toplevel, text='Enter arguments', width=400)
        message.pack(side='top')
        inbox.pack()
        send_btn.pack(side='bottom')

    def edit_variable(self):
        '''
        Show menu that allows you to change value of variable.
        '''

        def edit():
            value = value_inbox.get()
            type_ = type_inbox.get()
            try:
                self.debugger.edit_variable(
                    self.selected_var[0],
                    value,
                    type_,
                    self.selected_var[1]
                )
            except ValueError as exception:
                print(exception)
            toplevel.destroy()

        toplevel = tkinter.Toplevel(master=self.interface, width=40)
        toplevel.title('Edit variable')
        top = ttk.Frame(toplevel)
        bot = ttk.Frame(toplevel)
        value_inbox = ttk.Entry(top, width=25)
        value_label = tkinter.Label(top, text='Value: ')
        type_label = tkinter.Label(bot, text='Type: ')
        type_inbox = ttk.Entry(bot, width=25)
        send_btn = ttk.Button(toplevel, text='Edit')
        send_btn.bind('<Button-1>', lambda e: edit())
        message = tkinter.Message(master=toplevel, text='Enter value and type', width=400)
        message.pack(side='top')
        send_btn.pack(side='bottom')
        value_label.pack(side='left')
        value_inbox.pack(side='right')
        type_label.pack(side='left')
        type_inbox.pack(side='right')
        bot.pack(side='bottom')
        top.pack(side='bottom')
        toplevel.focus_force()

    def context_menu(self, event, menu):
        '''
        Event for context menu invokation.
        '''
        widget = event.widget
        index = widget.nearest(event.y)
        if widget.get(str(index)) in ['Locals:', 'Globals:']:
            return
        if event.y / 17 > index + 1 or index == -1:
            return
        scope = 'global'
        var_list = list(widget.get('0', 'end'))
        if index > var_list.index('Locals:'):
            scope = 'local'
        self.selected_var = (widget.get(index).split(':')[0], scope)
        menu.post(event.x_root, event.y_root)

    def load_file(self):
        '''
        Ask to open a new file.
        '''
        if self.debugger.running:
            self.outputbox.config(state=tkinter.NORMAL)
            self.outputbox.insert(
                'end',
                'You must stop execution of current script before open new one.'
            )
            self.outputbox.config(state=tkinter.DISABLED)
            return
        file_ = tkinter.filedialog.Open().show()
        if not file_:
            return
        for prog in self.programs:
            self.codebox.forget(prog)
        self.programs = {}
        with open(file_) as input_file:
            code = input_file.read()
        self.add_tab_to_codebox(code, file_, True)

    def run(self):
        '''
        Show Debugger window.
        '''
        self.interface.mainloop()

    def debug_mode_msg_handler(self, messages, deal_later):
        '''
        Stores all messages in "deal_later" list until program stop.
        Then handles them all at once and fill variables list and callstack.
        '''
        deal_later += messages
        messages = []
        if ('brpoint', ) not in deal_later:
            return deal_later
        for message in deal_later:
            if message[0] != 'brpoint':
                self.message_handler[message[0]](message[1:])
        deal_later = []
        return []

    def run_mode_msg_handler(self, messages):
        '''
        Show only stdout and exception info.
        '''
        messages = [x for x in messages if x[0] == 'stdout' or x[0] == 'exception']
        for message in messages:
            if message[0] != 'brpoint':
                self.message_handler[message[0]](message[1:])

    def trace_mode_msg_handler(self, messages):
        '''
        Just handles messages. Variables list and callstack are filled in
        "next_step" function called every time user presses "Next step" button.
        '''
        for message in messages:
            if message[0] != 'brpoint':
                self.message_handler[message[0]](message[1:])

    def paint(self):
        '''
        Receive messages from interpreter and show changes on screen.
        '''
        deal_later = []
        while self.debugger.running:
            time.sleep(0.1)
            messages = self.debugger.get_callback()
            if self.debugger.file != self.cur_file:
                if self.debugger.file == '<string>':
                    self.codebox.select(self.codebox.tabs()[0])
                elif self.debugger.file not in self.files and self.debugger.file:
                    with open(self.debugger.file) as file_:
                        self.add_tab_to_codebox(file_.read(), self.debugger.file)
                else:
                    index = self.files.index(self.debugger.file)
                    tab_id = self.codebox.tabs()[index]
                    self.codebox.select(tab_id)
            if self.mode == 'debug':
                deal_later = self.debug_mode_msg_handler(messages, deal_later)
            elif self.mode == 'run':
                self.run_mode_msg_handler(messages)
            elif self.mode == 'trace':
                self.trace_mode_msg_handler(messages)
        messages = deal_later + self.debugger.get_callback()
        if self.mode == 'run':
            messages = [x for x in messages if x[0] == 'stdout' or x[0] == 'exception']
        for message in messages:
            if message[0] != 'brpoint':
                self.message_handler[message[0]](message[1:])
