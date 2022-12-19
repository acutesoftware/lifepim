#!/usr/bin/python3
# coding: utf-8
# infolink.py


import time
import sys
import os
import tkinter as Tkinter
from win32gui import GetWindowText, GetForegroundWindow
import config as mod_cfg
  
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

        # paths
        self.fname = mod_cfg.diary_pcusage_base_fname + GetPCName() + '_' + GetUser() + '.txt'
        self.diary_file =  mod_cfg.diary_base_fname + GetPCName() + '_' + GetUser() + '.txt'
        self.errFile =  mod_cfg.diary_base_error_fname + GetPCName() + '_' + GetUser() + '.txt'
        
        try:
            ensure_dir(self.fname)
        except:
            print('problem trying to create sub folder for data')
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
            self.wm_iconbitmap(bitmap = mod_cfg.icon_file)  # was Wall Clock.ico, now Stopwatch_On.png
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

        print('logfile    = ', self.fname)
        print('diary file = ', self.diary_file)


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

        # Log PC usage (only works in windows)
        txt = get_active_window()
        self.lstRaw.append(txt)
        self.labelVariable.set(current)
        print(txt)        
  
    def jobs_1_min(self):
        print('running tasks each min...')
        self.record()

    def jobs_10_min(self):
        print('running tasks each 10 min...')
        self.summarise_usage()

    def TodayAsString(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    
    def cmd_infolink_help(self):
        print('help')

    def cmd_infolink_home(self):
        print('home')

    def cmd_infolink_exit(self):
        print('exiting...')
        sys.exit(0)


    def record(self):
        """ appends the current list of logged events in memory (lstRaw) to 
            the raw diary file.
            Usually called once a minute
        """
        self.lstPcUsage = []
        self.tot_seconds = 1   # remember - you are logging by MINUTE, not seconds
        self.startTime = self.TodayAsString()
        for i in self.lstRaw:
            if i == '':
                i = '[Screen Saver]'
            self.lstPcUsage.append(self.startTime + ',' + format(self.tot_seconds, "03d") + ',' + i)
            
                    
        #self.lstPcUsage.append(self.startTime + ',' + format(self.tot_seconds, "03d") + ',' + txt)
        
        # now save the list to the raw file
        try:
            with open(self.fname, "a", encoding='utf-8') as f:
                for txt in self.lstPcUsage:
                    f.write(txt + '\n')
            tot_seconds = 1
            self.lstRaw = []	# only reset raw list if save successful
        except:
            print(self.TodayAsString() + "ERROR - cant open output file\n" + self.fname)
            
    def summarise_usage(self):
        """ aggregates the 10 minutes of logged data to Diary Events 
        INPUT FILE - pc_usage_Ent_duncan.txt
            2014-05-02 22:04:00,001,T:\\user\\AIKIF
            2014-05-02 22:04:00,001,T:\\user\\AIKIF
            2014-05-02 22:04:00,001,T:\\user\\AIKIF
            2014-05-02 22:04:00,001,c:\\python33\\python.exe
            2014-05-02 22:04:00,001,c:\\python33\\python.exe
            2014-05-02 22:04:00,001,c:\\python33\\python.exe
            2014-05-02 22:04:00,001,c:\\python33\\python.exe
            2014-05-02 22:04:00,001,c:\\python33\\python.exe		
        OUTPUT FILE - diary_Ent_duncan.txt
            2014-05-02,22:04,3,T:\\user\\AIKIF
            2014-05-02,22:04,5,c:\\python33\\python.exe
        
        """
        
        try:	# SUMMARISE THE RAW FILE
            with open(self.fname, "r") as f:
                diaryRecs = []
                prevText = ''
                lines = 0
                tme = 0
                prevTime = ''
                curDiaryEntry = []
                for row in f:
                    item = row.split(',')
                    startTime = item[0]
                    tme += int(item[1])				# raw data captured every second by default
                    txt = row[24:]  				# cant use item[2] in case of commas
                    lines += 1
                    if lines == 1: 					# set previous checks on first run
                        prevTime = startTime[0:16]
                        prevText = txt
                    
                    if txt != prevText or startTime[0:16] != prevTime:	# check for new entry
                        diaryRecs.append(curDiaryEntry)
                        tme = 1
                        prevText = txt
                        prevTime = startTime[0:16]
                    curDiaryEntry = [startTime, tme, txt]  
                diaryRecs.append(curDiaryEntry)   # write the last line	

        except Exception as ex:
            self.logErr('ERROR - could not read raw logfile = ' + str(ex) )
            
        try:	# SAVE THE AGGREGATED LIST TO DIARY FILE
            with open(self.diary_file, "a") as f:
                for line in diaryRecs:
                    if len(line) > 1:
                        dte = line[0][0:10]
                        tme = line[0][11:16]
                        lng = line[1]
                        det = line[2].strip()
                        #print('dte=', dte, 'tme=', tme, 'len=', lng, 'det=', det)
                        f.write(dte + ',' + tme + ',' + str(lng) + ',' + det + '\n')

        
            try: # IFF successfully saved, then try removing raw file
                os.remove(self.fname)
            except:
                self.logErr("Cant delete " + f)
        except:
            self.logErr('ERROR - could not open diary file')
        
    
    def logErr(self, txt):
        logEntry = self.TodayAsString() + '; ' + txt
        try:
            with open(self.errFile, "a") as f:
                f.write(logEntry + '\n')
        except:
            print(self.TodayAsString() + '; ' + "ERROR - cant save logs!")
            


#########################################################################################
def get_active_window():
    active_window_name = None
    try:
        if sys.platform in ['linux', 'linux2']:
            active_window_name = 'Linux todo - install wnck'
        elif sys.platform in ['Windows', 'win32', 'cygwin']:
            active_window_name = GetWindowText(GetForegroundWindow())
        elif sys.platform in ['Mac', 'darwin', 'os2', 'os2emx']:
            active_window_name = 'Linux todo - install AppKit'
        return active_window_name
    except Exception as ex:
        return 'error getting active window - ' + str(ex)




if __name__ == "__main__":
    main()