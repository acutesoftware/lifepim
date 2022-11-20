#!/usr/bin/python3
# coding: utf-8
# infolink.py


import time
import sys
import os
import tkinter as Tkinter
  
def main():
    app = simpleapp_tk(None)
    app.title('InfoLink')
    app.update_timeText()
    app.mainloop()
 
def GetUser():
    try:
        import getpass
        usr = getpass.getuser()
    except:
        usr = 'username'
    return usr

def GetPCName():
    try:
        import socket
        pcname = socket.gethostname()
    except:
        pcname = 'computer'
    return pcname
    
def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)
    
class simpleapp_tk(Tkinter.Tk):
    def __init__(self,parent):
        Tkinter.Tk.__init__(self,parent)
        self.parent = parent
        self.screenWidth = self.winfo_screenwidth()
        self.screenHeight = self.winfo_screenheight()
        self.appWidth = 170
        self.appHeight = 25
        self.lstRaw = []
        self.lstPcUsage = []
        self.prevText = ''
        self.startTime = self.TodayAsString()
        self.tot_seconds = 1

        self.initialize()

    def initialize(self):
        """ 
        intitialse the toolbar application InfoLink 
        """
        #geometry('%dx%d+%d+%d' % (w, h, x, y))
        self.geometry('%dx%d+%d+%d' % (self.appWidth, self.appHeight, self.screenWidth - self.appWidth - 50, self.screenHeight - self.appHeight - 60))
        self.grid()

        # label for toolbar
        self.labelVariable = Tkinter.StringVar()
        label = Tkinter.Label(self,textvariable=self.labelVariable, anchor="w",fg="darkblue",bg="white", font=("Arial", 9, "bold"))
        label.grid(column=1,row=1,sticky='EW')
        self.labelVariable.set(u"                            ")
        try:
            self.wm_iconbitmap(bitmap = os.getcwd() + "\\Wall Clock.ico")
        except:
            print('REMINDER - YOU ARE RUNNING IN DEV DIRECTORY')

        # Button to call menu
        self.menuButton = Tkinter.Button(self,text=u"...", command=self.do_popup)
        self.menuButton.grid(column=0,row=1)
        self.grid_columnconfigure(1,weight=1)
        
        # popup menu
        self.popup = Tkinter.Menu(self, tearoff=0)
        self.popup.add_command(label="Exit", command=self.cmd_infolink_exit) 
        self.popup.add_command(label="Help", command=self.cmd_infolink_help)
        self.popup.add_separator()
        self.popup.add_command(label="Home", command=self.cmd_infolink_home)
        
        # final main screen setup
        self.resizable(True,False)
        self.update()
        self.geometry(self.geometry())       
        print(self.TodayAsString() + ' - Started InfoLink for LifePIM')

    def do_popup(self):
        # display the popup menu
        self.popup.post(self.screenWidth - self.appWidth + 60, self.screenHeight - self.appHeight - 95)
            
    def update_timeText(self):
        """ This is called every second by the last line in this function (app.after(1000)
            TODO - May change the method as the second on the toolbar is not exact.
            
            This function captures the currently active window and appends to a list which
            is later aggregated and logged to the diary.
            
            Every minute [tme ends with ':00']  it calls the record function to append raw data
            Every 10 min [tme ends with '0:00'] it calls the summarise function to build diary files
            
        """
    
        #current = time.strftime("%H:%M:%S")

        #current = time.strftime("%a %d-%b %-I:%M:%S %p")   # leading hour zero removal not OS portable
        dte = time.strftime("%a %d-%b") 
        tme = time.strftime("%I:%M:%S %p")
        if tme[0:1] == '0':
            tme = tme[1:] 
        current = dte + '  ' + tme
        
        
        self.labelVariable.set(current)
        if self.TodayAsString()[-3:] == ':00':
            self.jobs_1_min()
            
        if self.TodayAsString()[-4:] == '0:00':   # check tasks every 10 minutes
            self.jobs_10_min()
            
        # Call the update_timeText() function after 1 second
        self.after(1000, self.update_timeText)

    def jobs_1_min(self):
        print('running tasks each min...')

    def jobs_10_min(self):
        print('running tasks each 10 min...')

    def TodayAsString(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    
    def cmd_infolink_help(self):
        print('help')

    def cmd_infolink_home(self):
        print('home')

    def cmd_infolink_exit(self):
        print('exiting...')
        sys.exit(0)

        
        
if __name__ == "__main__":
    main()