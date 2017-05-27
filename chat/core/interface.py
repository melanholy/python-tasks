'''
A class that contains methods for work with chat interface.
'''

import tkinter
import tkinter.filedialog
import os
from time import sleep
from core.other import get_smile_positions, SMILEYS, get_ip_addr
from tkinter import ttk
from threading import Thread

class ChatGUI(object):
    '''
    Interface for chat written using tkinter.
    '''
    def __init__(self, chat, server):
        self.chat = chat
        self.server = server
        self.interface = tkinter.Tk()
        self.interface.title('Chat')
        bot = ttk.Frame(self.interface)
        top = ttk.Frame(self.interface)
        self.inbox = ttk.Entry(bot, width=100)
        self.configure_inbox(bot)
        self.add_menu()
        self.peer_list = tkinter.Listbox(top, selectmode=tkinter.SINGLE)
        self.configure_peer_list()
        self.messagebox = tkinter.Text(top, state=tkinter.DISABLED, height=30)
        self.configure_messagebox(top)
        top.pack(side='top', expand=1, fill='both')
        bot.pack(side='bottom', fill='both')
        self.mailchecker = Thread(target=self.loop)
        self.chat_running = True
        self.message_history = []
        self.selected_peer = None
        self.current_previous_msg = 0
        self.files_lines = {}
        self.images = {}
        self.callback_handler = {}
        self.callback_handler['msg'] = lambda e: self.add_message_to_messagebox(e[1])
        self.callback_handler['add'] = lambda e: self.peer_list.insert('end', e[1])
        self.callback_handler['del'] = lambda e: self.delete_peer(e)
        self.callback_handler['left'] = lambda e: self.leave_room()
        self.callback_handler['nick'] = lambda e: self.change_nickname(e)
        self.callback_handler['file'] = lambda e: self.add_file(e)
        self.callback_handler['dload'] = lambda e: self.update_download(e)
        for smile in SMILEYS:
            self.images[smile] = tkinter.PhotoImage(file='smileys/'+smile+'.gif')

    def update_download(self, message):
        self.messagebox.config(state='normal')
        self.messagebox.delete(self.files_lines[message[1]]+'.1',
                               self.files_lines[message[1]]+'.end')
        self.messagebox.insert(self.files_lines[message[1]]+'.1',
                               message[2]+'% downloaded.')
        self.messagebox.config(state='disabled')

    def delete_peer(self, message):
        peer_list = list(self.peer_list.get('0', 'end'))
        self.peer_list.delete(peer_list.index(message[1]))
        self.add_message_to_messagebox(message[1]+' has left the room.')

    def leave_room(self):
        self.peer_list.delete(0, 'end')
        self.add_message_to_messagebox('You have left the room.')

    def change_nickname(self, message):
        peer_list = list(self.peer_list.get('0', 'end'))
        index = peer_list.index(message[1])
        self.peer_list.delete(index)
        self.peer_list.insert(index, message[2])

    def add_file(self, message):
        self.add_message_to_messagebox(message[1])
        button = tkinter.Button(self.messagebox, text=os.path.basename(message[2]))
        button.bind('<Button-1>', lambda e: self.save_file(message[2], message[3]))
        self.messagebox.config(state=tkinter.NORMAL)
        self.messagebox.window_create('end', window=button)
        self.files_lines[message[2]] = str(int(self.messagebox.index('end').split('.')[0])-1)
        self.messagebox.insert('end', '\n')
        self.messagebox.config(state=tkinter.DISABLED)

    def configure_messagebox(self, master):
        '''
        Set configuration of messagebox and add scrollbar to it.
        '''
        self.messagebox.pack(side='left', fill='both', expand=1)
        scrollbar = ttk.Scrollbar(master)
        scrollbar['command'] = self.messagebox.yview
        scrollbar.pack(side='right', fill='y')
        self.messagebox['yscrollcommand'] = scrollbar.set

    def add_menu(self):
        '''
        Add menu. It contains help and file loader.
        '''
        topmenu = tkinter.Menu(self.interface, tearoff=0)
        self.interface.config(menu=topmenu)
        topmenu_file = tkinter.Menu(topmenu, tearoff=0)
        topmenu.add_cascade(label="File", menu=topmenu_file)
        topmenu_file.add_command(label="Load", command=self.load_file)
        topmenu_help = tkinter.Menu(topmenu, tearoff=0)
        topmenu_action = tkinter.Menu(topmenu, tearoff=0)
        topmenu.add_cascade(label="Actions", menu=topmenu_action)
        topmenu_action.add_command(label="Join room", command=self.join_room)
        topmenu_action.add_command(label="Leave room", command=lambda: self.chat.send_msg('/leave'))
        topmenu_action.add_command(label="Change nickname", command=self.change_nick)
        topmenu.add_cascade(label="Help", menu=topmenu_help)
        topmenu_help.add_command(label="About", command=self.show_about)
        topmenu_help.add_command(label="Commands", command=self.show_commands)
        topmenu_help.add_command(label="Smiles", command=self.show_smiles_info)
        topmenu_help.add_command(label="My addr", command=self.show_addr)

    def change_nick(self):
        '''
        Create window that allows you to change your nickname.
        '''
        def change():
            '''
            Send "nick" message.
            '''
            message = inbox.get()
            self.chat.send_msg('/nick '+message)
            toplevel.destroy()

        toplevel = tkinter.Toplevel(master=self.interface, width=40)
        toplevel.title('Change nickname')
        inbox = ttk.Entry(toplevel, width=25)
        send_btn = ttk.Button(toplevel, text='Change')
        send_btn.bind('<Button-1>', lambda e: change())
        message = tkinter.Message(master=toplevel, text='Enter nickname.', width=400)
        message.pack(side='top')
        send_btn.pack(side='bottom')
        inbox.pack()
        toplevel.focus_force()

    def join_room(self):
        '''
        Create window that allows you to join some room.
        '''
        def join():
            '''
            Send "join" message.
            '''
            message = inbox.get()
            self.chat.send_msg('/join '+message)
            toplevel.destroy()
        
        toplevel = tkinter.Toplevel(master=self.interface, width=40)
        toplevel.title('Join room')
        inbox = ttk.Entry(toplevel, width=25)
        send_btn = ttk.Button(toplevel, text='Join')
        send_btn.bind('<Button-1>', lambda e: join())
        message = tkinter.Message(master=toplevel, text='Enter ip address and port.', width=400)
        message.pack(side='top')
        send_btn.pack(side='bottom')
        inbox.pack()
        toplevel.focus_force()

    def show_addr(self):
        '''
        Show clint's ip address and port.
        '''
        toplevel = tkinter.Toplevel(master=self.interface, width=30)
        toplevel.title('Address')
        message = tkinter.Text(master=toplevel)
        message.insert('end', 'IP address: '+get_ip_addr()+'\nPort: '+str(self.server.port))
        message.config(width=30, height=4, state='disabled')
        message.pack()
        toplevel.focus_force()

    def configure_peer_list(self):
        '''
        Set configuration of peer list.
        '''
        menu = tkinter.Menu(tearoff=0)
        self.peer_list['selectbackground'] = 'white'
        self.peer_list['selectforeground'] = 'black'
        menu.add_command(label='Whisper', command=self.add_whisp)
        menu.add_command(label='Ban', command=lambda: self.chat.ban_peer(self.selected_peer))
        menu.add_command(label='Unban', command=lambda: self.chat.unban_peer(self.selected_peer))
        self.peer_list.bind('<Button-3>', lambda e: self.context_menu(e, menu))
        self.peer_list.pack(side='right', fill='y')

    def configure_inbox(self, master):
        '''
        Configure inbox and add "Send" button.
        '''
        self.inbox.focus()
        self.inbox.bind('<Return>', lambda e: self.send_msg())
        self.inbox.bind('<Up>', lambda e: self.add_previous_message(1))
        self.inbox.bind('<Down>', lambda e: self.add_previous_message(-1))
        send_btn = ttk.Button(master, text='Send')
        send_btn.bind('<Button-1>', lambda e: self.send_msg())
        self.inbox.pack(side='left', fill='x', expand=1)
        send_btn.pack(side='right')

    def show_about(self):
        '''
        Show general information about the chat and about the creator.
        '''
        toplevel = tkinter.Toplevel(master=self.interface, width=30)
        toplevel.title('About')
        with open('readme.txt') as readme:
            text = readme.read().split('\n')
            message = tkinter.Text(master=toplevel)
            message.insert('end', text[0]+'\n\n'+text[13])
            message.config(width=len(text[0])+2, height=4, state='disabled')
        message.pack()
        toplevel.focus_force()

    def show_commands(self):
        '''
        Show list of available commands.
        '''
        toplevel = tkinter.Toplevel()
        toplevel.title('Commands')
        with open('readme.txt') as readme:
            text = readme.read().split('\n')
            message = tkinter.Text(master=toplevel)
            message.insert('end', text[5]+'\n\n'+'\n'.join(text[6:12]))
        message.config(height=10, width=82, state='disabled')
        message.pack()
        toplevel.focus_force()

    def show_smiles_info(self):
        '''
        Show list of available smiles.
        '''
        toplevel = tkinter.Toplevel()
        toplevel.title('Smiles')
        message = tkinter.Text(master=toplevel)
        message.insert('end', 'List of available smiles:\n')
        for smile in self.images.keys():
            message.insert('end', '\n:'+smile+':')
            message.image_create('end', image=self.images[smile])
        message.config(state='disabled', width=30)
        message.pack()
        toplevel.focus_force()

    def add_previous_message(self, direction):
        '''
        Adds one of the previous messages to inbox.
        '''
        if direction == 1 and self.current_previous_msg == 0 or not len(self.message_history):
            return
        if direction == -1 and self.current_previous_msg == len(self.message_history):
            return
        self.current_previous_msg += -direction
        self.inbox.delete('0', 'end')
        try:
            self.inbox.insert('0', self.message_history[self.current_previous_msg])
        except IndexError:
            pass

    def load_file(self):
        '''
        Ask to open a file and then send it to all peers.
        '''
        file_ = tkinter.filedialog.Open().show()
        self.add_message_to_messagebox(self.chat.my_nickname.nickname+
                                       ' has sent a file. Click to download.')
        button = tkinter.Button(self.messagebox, text=os.path.basename(file_))
        self.messagebox.window_create('end', window=button)
        self.add_message_to_messagebox('')
        self.server.send_file(file_)

    def add_whisp(self):
        '''
        Add /whisp <nickname> message to the inbox.
        '''
        self.inbox.delete('0', 'end')
        self.inbox.insert('0', '/whisp '+self.selected_peer+' ')

    def context_menu(self, event, menu):
        '''
        Event for context menu invokation.
        '''
        widget = event.widget
        index = widget.nearest(event.y)
        self.peer_list.activate(index)
        if event.y / 17 > index + 1 or index == -1:
            return
        self.selected_peer = widget.get(index)
        menu.post(event.x_root, event.y_root)

    def add_message_to_messagebox(self, message):
        '''
        Add new message to the end of messagebox.
        '''
        try:
            self.message_history.append(message[message.index(': ')+2:])
        except ValueError:
            pass
        self.current_previous_msg = len(self.message_history)
        if len(self.message_history) > 20:
            del self.message_history[0]
        self.messagebox.config(state=tkinter.NORMAL)
        smile_positions = get_smile_positions(message)
        for start, end in reversed(smile_positions):
            smile = message[start+1:end-1]
            line_number = str(int(self.messagebox.index('end').split('.')[0])-1)
            message = message[:start]+message[end:]
            self.messagebox.insert(line_number+'.0', message[start:])
            self.messagebox.image_create(line_number+'.0', image=self.images[smile])
        try:
            self.messagebox.insert(line_number+'.0', message[:smile_positions[0][0]])
        except UnboundLocalError:
            self.messagebox.insert('end', message)
        self.messagebox.insert('end', '\n')
        self.messagebox.config(state=tkinter.DISABLED)
        self.messagebox.see('end')

    def save_file(self, filename, author):
        '''
        Ask for path to save file to and send peer the request.
        '''
        file_ = tkinter.filedialog.SaveAs(initialfile=os.path.basename(filename)).show()
        if file_:
            self.server.send_request(filename, author, file_)

    def send_msg(self):
        '''
        Send message to peers.
        '''
        message = self.inbox.get()
        self.inbox.delete('0', 'end')
        self.chat.send_msg(message)

    def close(self):
        '''
        Stop the work.
        '''
        self.chat_running = False
        self.mailchecker.join()

    def run(self):
        '''
        Start the work.
        '''
        self.mailchecker.start()
        self.interface.mainloop()

    def loop(self):
        '''
        An infinite loop checking if there is anything in peers' message callbacks.
        If there is, this method calls methods that will handle messages.
        '''
        while self.chat_running:
            sleep(0.2)
            messages = self.server.get_callback()
            messages += self.chat.get_callback()
            for message in messages:
                self.callback_handler[message[0]](message)
