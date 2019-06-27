# homcalendar.py

from tkinter import Frame, Label, Entry, Button, font
from tkcalendar import Calendar, DateEntry

class wCalendar(object):
    def __init__(self, top):
        #self.master = master
        #top = tk.Toplevel(master)
        cal = Calendar(top, selectmode='none')
        date = cal.datetime.today() + cal.timedelta(days=2)
        cal.calevent_create(date, 'Hello World', 'message')
        cal.calevent_create(date, 'Reminder 2', 'reminder')
        cal.calevent_create(date + cal.timedelta(days=-2), 'Reminder 1', 'reminder')
        cal.calevent_create(date + cal.timedelta(days=3), 'Message', 'message')

        cal.tag_config('reminder', background='red', foreground='yellow')
        cal.pack(fill="both", expand=True)
        #cal.pack(fill="none", expand=False)
        #ttk.Label(top, text="Hover over the events.").pack()



def build_screen_calendar(root):
    cal_frame = Frame(root, bg='blue', width=300, height=390)
    cal = wCalendar(cal_frame)
    cal_frame.grid(row=0, column=0)


