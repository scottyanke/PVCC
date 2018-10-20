#!/bin/python3
import sqlite3
import tkinter as tk
from tkinter import *
from tkinter.messagebox import showinfo
import time
import datetime
from datetime import date, datetime
import threading
import queue
import serial
import sys

# Any print statements in the program will only be seen if it was started from a
# terminal session.  Normally that is not the case as this is auto-started when
# the Raspberry Pi boots.  It can run from a terminal, although it doesn't need to.

# The serial port that is used is a USB to RS485 device that handles the conversion
# to the 2-wire communication line.  It also takes care of automatically switching
# betweeen receiving and transmitting.
serial_port = '/dev/ttyUSB0'

# The location of the Sqlite database used for historical data.  Originally it was
# on a separate USB flash drive, but that got really, really slow.
db = "/home/pi/hvac.db"
# The database was created using these statements -
"""
CREATE TABLE "ahu" ( "id" TEXT, "psi" REAL, "air" REAL, "time_taken" TEXT, "ac" TEXT   DEFAULT 'aa');
CREATE TABLE "ahu_temps" ( "id" TEXT, "time_taken" TEXT, "temp_1" REAL, "temp_2" REAL, "temp_3" REAL, "temp_4" REAL, "temp_5" REAL, "temp_6" REAL, "temp_7" REAL, "temp_8" REAL);
CREATE TABLE "boiler" ("time_taken" TEXT,"power" TEXT,"demand" TEXT,"burner" TEXT,"alarm" TEXT,"psi" REAL);
CREATE TABLE "readings" ( id` TEXT, `humidity` REAL, `temperature` REAL, `time_taken` TEXT );
"""

in_showme = 0       # Used to limit trying to open multiple windows on the GUI
num = 0
hall_num = 0
hvac_num = 0
# Various arrays used by the program to hold data.
tunnel_button = []
tunnel_data = []
tunnel_flag = []
hall_button = []
hall_data = []
hall_flag = []
hvac_button = []
hvac_data_psi = [0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0]
hvac_data_air = [0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0]
hvac_data_temp = [0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0]
hvac_data_ac = ['','','','','','','','','','']
hvac_flag = []
boiler_button = 0
thread_id = 0   # needed to cancel waiting thread, and start one immediately
the_time = ''   # This is stored once each cycle, so every device is the same time
do_it_now = 0   # a flag set to indicate to the threaded process we want it now

# The list of devices to ask for data from, and the order to ask.
units = ["y","z","A","B","C","D","E","1","2","3","4","5","6","7"]

# The names that show up on the button labels.
tunnel = {1:'100-even',
          2:'100-odd',
          3:'200-even',
          4:'200-odd',
          5:'400-even',
          6:'400-odd',
          7:'500s',
          8:'open',
          9:'open'}
# The halls are in a specific order, matching the building layout, mostly
halls = {1:'118',
         2:'209',
         3:'225',
         4:'NW TV',
         5:'302',
         6:'104',
         7:'HS Nurse',
         8:'604',
         9:'614',
         10:'310',
         11:'Front',
         12:'MS Dining',
         13:'514',
         14:'CL Dining',
         15:'CL TV',
         16:'415',
         17:' ',
         18:'Outside'}
hvac = {1:'AHU 1',
        2:'AHU 2',
        3:'AHU 3',
        4:'AHU 4',
        5:'AHU 5',
        6:'Boiler',
        7:' '}

# The names associated with each column of data when displayed through the gui
hvac_sensors = {'AHU 1':'Return,Discharge,Mixed,Outside,Social Serivces,Business Office,Fellowship, , ',
        'AHU 2':'Outside,Return,Mixed,Discharge,500s,200s, , ',
        'AHU 3':'Heritage,Northwoods,Discharge,Mixed,Return,Outside, , ',
        'AHU 4':'Return,Mixed,Discharge, , , , , ',
        'AHU 5':'Intake,Kitchen,Other,Outside, , , , ',
        'Boiler':'Demand,Burner,Alarm,Pressure'}
# The DS18B20 addresses, and what button they are associated with.  The first two bytes are
# not needed, as they are always the same.  Because look-ups are used, the second number does
# not have to be in any particular order, but it does have to match a button number.
sensors = {'dc36811402d4':15,
         'fa7c24170383':10,
         '8fa7241703a9':5,
         '42e924170392':13,
         '2934811402a7':4,
         '967c241703b3':3,
         '55f6641503bd':7,
         '7564811402cb':2,
         '2d96641501c2':1,
         '75a964150259':6,
         '3df36415024d':11,
         '5ad16415027a':12,
         'a78024170399':8,
         'd0d66415028a':14,
         'c50f251703e3':9,
         '8897641501ac':16,
         '5ca264150124':17,
         '76c5311801b0':18}

# The processing part of the code starts here.  The GuiPart class is used
# with Tkinter to display buttons on the screen of the Raspberry Pi.  Some
# buttons are used as labels, because defining them as labels on the Pi has
# created some issues with how things are redrawn.  Only one button is
# active at a time.

# Much of this section was taken from examples posted by other people.
class GuiPart:
    global db
    def __init__(self, master, queue):
        self.master = master
        self.queue = queue
        # Set up the GUI
        self.title = tk.Label(master,font=("Arial",6))  # it doesn't need to be big, or even there
        self.title.grid(column=0,row=0,columnspan=7,sticky="ew")

        self.fill_left_label = tk.Label(left_frame, text=' ',width=2)
        self.fill_left_label.grid(column=0, row=0)

        self.tunnel_label = tk.Button(tunnel_frame, text="Tunnels",
            font=("Arial", 11), relief=FLAT)    # its a button being used as a label because redraws don't work on Raspian
        self.tunnel_label.grid(column=0,row=0,sticky="new")
        self.tunnel_label.config(activebackground=
            self.tunnel_label.cget('background'))

        self.fill1_label = tk.Label(filler1_frame, text=" ", width=2)
        self.fill1_label.grid(column=0,row=0)

        self.hall_label = tk.Button(hall_frame, text="Halls", font=("Arial", 11),
            relief=FLAT)    # its a button being used as a label because redraws don't work on Raspian
        self.hall_label.grid(column=0,row=0,columnspan=3,sticky="new")
        self.hall_label.config(activebackground=self.hall_label.cget('background'))

        self.fill2_label = tk.Label(filler2_frame, text=" ", width=2)
        self.fill2_label.grid(column=0,row=0)

        self.hvac_label = tk.Button(hvac_frame, text="HVAC", font=("Arial", 11),
            relief=FLAT)    # its a button being used as a label because redraws don't work on Raspian
        self.hvac_label.grid(column=0,row=0,sticky="new")
        self.hvac_label.config(activebackground=self.hvac_label.cget('background'))


        self.fill_right_label = tk.Label(right_frame, text=' ',width=2)
        self.fill_right_label.grid(column=0, row=0)

        # status_label is actually a button that displays the current status of
        # polling, and when pressed it starts polling regardless of what time
        # it is.  It is updated by the threaded process.
        self.status_label = tk.Button(master, text='Starting', font=('Arial', 12),
            command=self.get_readings)
        self.status_label.grid(column=0,row=4,columnspan=7,sticky="ew")

        try:    # open the sqlite database for use reading and writing
            self.dbconnect = sqlite3.connect(db);
            self.dbconnect.row_factory = sqlite3.Row;
            self.cursor = self.dbconnect.cursor();
            db_cursor = self.cursor
            db_connect = self.dbconnect
        except:
            print("Unable to open the database " + db)
            raise    # The database is required to poll data, or python goes weird with the cursor
        for num in range(7):    # There are 7 tunnels, so that many tunnel buttons
            add_new_tunnel(self.cursor)
        for hall_num in range(15):  # 15 hallway sensors (DS18B20s)
            add_new_hall(self.cursor)
        for hvac_num in range(6):   # 5 air handlers plus the boiler
            add_new_hvac(self.cursor)
        add_boiler(self.cursor)
        self.status_label.configure(text = 'Waiting at ' + \
            time.strftime('%m/%d/%y %H:%M:%S'),foreground='black')

    def block_readings(self):
        #do nothing.  Seriously, prevent things from happening with the gui.
        time.sleep(1)
    def get_readings(self):     # pressing the button forces everything to be polled
        global thread_id
        global do_it_now
        root.after_cancel(thread_id)
        do_it_now = 1
        root.after(200,client.commThread)   # Start polling for new data after 200 milliseconds
    def show_running(self):     # Update the status button on the bottom of the screen.
        global the_time
        self.status_label.configure(text = 'Getting readings...',foreground='green',
            command=self.block_readings)
        the_time = time.strftime('%Y-%m-%d %H:%M:%S.000')
        root.update()
    def show_idle(self):        # Done after polling everything.
        self.status_label.configure(text = 'Last reading at ' + \
            time.strftime('%m/%d/%y %H:%M:%S'),foreground='black',command=self.get_readings)
        root.update()

# The showme names are dumb, but this is code I started with that was taken from examples
# that other people have posted.

def close_showme(win):
    global in_showme
    win.destroy()
    root.update_idletasks()
    in_showme = 0

def focus_showme(win,b):
    b.focus_force()

# Creates a pop-up window that shows the history of temperatures and humidity for
# the device whose button was pushed.
def popup_showme(opt,cursor):
    global in_showme
    if in_showme != 0:
        return
    in_showme = 1
    win = tk.Toplevel()
    win.minsize(width=200, height=75)
    win.wm_title(opt + ' readings')
    win.transient(root)
    win.configure(background='')


    lb = tk.Listbox(win,width=35,height=10, font=("Arial Bold", 15))
    lb.configure(justify=tk.CENTER)
    lb.grid(column=0, row=0, padx=1)
    sbr = tk.Scrollbar(win, orient=tk.VERTICAL, width=25, command=lb.yview)
    sbr.grid(column=1, row=0,  sticky=('n,w,s'))
    lb['yscrollcommand'] = sbr.set

    b = tk.Button(win, text="Close", font=("Arial Bold", 14), width=38,
        command= lambda: close_showme(win))
    b.grid(row=1, column=0, columnspan=2)

    degree = u'\N{DEGREE SIGN}' # could probably do this globally, but don't want to...
    try:    # get the last 500 records for that specific id
        cursor.execute('''select * from readings where id = ? order by time_taken desc limit 500''',(opt,))
        rows = cursor.fetchall()
    except:
        pass
    count = 0
    total_count = 0
    show_record = 0
    try:
        for row in rows:    # Show every 20 minutes for last 24 hours, then drop to once an hour
            count = count + 1
            total_count = total_count + 1
            if total_count > 72 and count == 1:
                show_record = 1
            if total_count <= 72:
                show_record = 1
            if show_record == 1:
                show_record = 0
                humidity = row['humidity']
                temp = row['temperature']
                taken_time = row['time_taken']
                z= "  %s%% %s%s @ %s  " % (humidity,temp,degree,taken_time[5:16])
                if humidity < 1:
                    z = "%s%s @ %s" % (temp,degree,taken_time[5:16])
                lb.insert('end',z)
            if count == 3:
                count = 0
    except:
        pass
    # focus_showme forces this window to close before another window can be
    # opended.  On a 5" touchscreen, its important.
    win.bind("<FocusOut>", lambda event, p1=win, p2=b : focus_showme(p1, p2))
    b.focus_set()

# Used to show data from the air handlers
def popup_showhvac(opt,cursor):
    global in_showme
    if in_showme != 0:
        return
    in_showme = 1
    win = tk.Toplevel()
    win.minsize(width=200, height=85)
    win.wm_title(opt + ' readings')
    win.transient(root)
    win.configure(background='')

    lb = tk.Listbox(win,width=35,height=10, font=("Arial Bold", 15),fg='dark slate gray')
    lb.configure(justify=tk.LEFT)
    lb.grid(column=0, row=0, padx=1)
    sbr = tk.Scrollbar(win, orient=tk.VERTICAL, width=25, command=lb.yview)
    sbr.grid(column=1, row=0,  sticky=('n,w,s'))
    lb['yscrollcommand'] = sbr.set

    b = tk.Button(win, text="Close", font=("Arial Bold", 14), width=38,
        command= lambda: close_showme(win))
    b.grid(row=1, column=0, columnspan=2)

    s = hvac_sensors.get(opt)
    sensor_list = s.split(',')
    degree = u'\N{DEGREE SIGN}'
    count = 0
    total_count = 0
    show_record = 0
    # Get the last 500 records for an air handler identified by opt
    cursor.execute('''select * from ahu where id = ? order by time_taken desc limit 500''',(opt,))
    for row in cursor.fetchall():   # Show every 20 minutes for last 24 hours, then drop to once an hour
        #r = reg(cursor, row)
        count = count + 1
        total_count = total_count + 1
        if total_count > 72 and count == 1:
            show_record = 1
        if total_count <= 72:
            show_record = 1
        if show_record == 1:
            show_record = 0
            psi = row['psi']    # Air compressor pressure
            air = row['air']    # statis pressure in the air handler
            taken_time = row['time_taken']  # when...
            ac = row['ac']      # status of the air conditioning units
            ac1 = ''
            ac2 = ''
            if len(ac) > 0:
                if ac[0] == 'A':
                    ac1 = 'AC is on'
                try:
                    if ac[1] == 'A':
                        ac2 = ', AC2 is on'
                except:
                    ac2 = ''
                    pass
            z= " %s @ %s  " % (opt,taken_time[5:16])
            lb.insert('end',z)
            lb.itemconfig(lb.size()-1,fg='black')
            z= "  Compressor=%s psi, Velocity=%s kPa" % (psi,air)
            if opt != "AHU 5":      # air handler 5 does NOT have a compressor or static sensors
                lb.insert('end',z)
            z= "  %s %s" % (ac1,ac2)
            if len(ac1) > 1:
                lb.insert('end',z)
            try:
                cursor.execute('''select * from ahu_temps where id = ? and time_taken = ?''',
                    (opt,row[3]),)
                row_temps = cursor.fetchall()
                for row_temp in row_temps:
                    for i in range(8):
                        if isinstance(row_temp[i + 2],numbers.Real) and len(sensor_list[i]) > 2:
                            z= '  %s air is %4.1f%s' % (sensor_list[i],row_temp[i+2],degree)
                            lb.insert('end',z)
            except:
                print ('Error getting DB record for HVAC air handler')  # diagnostics
                pass
        if count == 3:
            count = 0
    win.bind("<FocusOut>", lambda event, p1=win, p2=b : focus_showme(p1, p2))
    b.focus_set()

# Show what the boiler history has been
def popup_boiler(opt,cursor):
    global in_showme
    if in_showme != 0:
        return
    in_showme = 1
    win = tk.Toplevel()
    win.minsize(width=280, height=75)
    win.wm_title('Boiler readings')
    win.transient(root)
    win.configure(background='')


    lb = tk.Listbox(win,width=48,height=10, font=("Arial Bold", 15))
    lb.configure(justify=tk.LEFT)
    lb.grid(column=0, row=0, padx=1)
    sbr = tk.Scrollbar(win, orient=tk.VERTICAL, width=25, command=lb.yview)
    sbr.grid(column=1, row=0,  sticky=('n,w,s'))
    lb['yscrollcommand'] = sbr.set

    b = tk.Button(win, text="Close", font=("Arial Bold", 14), width=50,
        command= lambda: close_showme(win))
    b.grid(row=1, column=0, columnspan=2, sticky=('e,w'))

    degree = u'\N{DEGREE SIGN}'
    count = 0
    total_count = 0
    show_record = 0
    # Get the last 500 boiler records
    cursor.execute('''select * from boiler order by time_taken desc limit 500''')
    #rows = cursor.fetchall()
    try:
        for row in cursor.fetchall():   # Show every record for the last 24 hours, then drop to once an hour
            count = count + 1
            total_count = total_count + 1
            if total_count > 72 and count == 1:
                show_record = 1
            if total_count <= 72:
                show_record = 1
            if show_record == 1:
                show_record = 0
                taken_time = row['time_taken']
                if row['power'] == 'On':
                    power = 'Boiler On, '
                else:
                    power = 'Boiler Off,'
                if row['demand'] == 'On':
                    demand = 'Demand, '
                else:
                    demand = ''
                if row['burner'] == 'On':
                    burner = 'Burner on, '
                else:
                    burner = ''
                if row['alarm'] == 'On':
                    alarm = 'Alarm'
                else:
                    alarm = ''
                psi = row['psi']

                z= " %s %s%s%s%s  %.2fpsi" % (taken_time[5:16],power,demand,burner,alarm,psi)
                lb.insert('end',z)
            if count == 3:
                count = 0
    except:
        raise
    win.bind("<FocusOut>", lambda event, p1=win, p2=b : focus_showme(p1, p2))
    b.focus_set()

# The add_new functions create the buttons when this program first starts.  It
# associates names to each button which are used later.
def add_new_tunnel(cursor):
    global num
    global tunnel_button
    tunnel_button.append(num)
    tunnel_data.append(num)
    tunnel_data[num] = "..."
    i = num + 1
    cmd1 = lambda: popup_showme(tunnel.get(i),cursor)
    tunnel_button[num]= tk.Button(tunnel_frame, text=tunnel.get(i) + "\n" + tunnel_data[num],
        font=("Arial Bold", 12), width=12, command=cmd1)
    tunnel_button[num].grid(column=0, row=i, sticky='ew',padx=1)
    tunnel_flag.append(num)
    tunnel_flag[num] = 1
    num = num + 1

def add_new_hall(cursor):
    global hall_num
    global hall_button
    i = hall_num + 1
    cmd1 = lambda: popup_showme(halls.get(i),cursor)
    hall_button.append(hall_num)
    hall_data.append(hall_num)
    hall_data[hall_num] = "..."
    hall_button[hall_num]= tk.Button(hall_frame, text=halls.get(i) + "\n" + hall_data[hall_num],
        font=("Arial Bold", 12), width=10, command=cmd1)
    hall_row = i
    hall_col = 0
    if i > 5:   # 3 across by 5 down, button-wise
        hall_row = i - 5
        hall_col = 1
        if i > 10:
            hall_row = i - 10
            hall_col = 2
    hall_button[hall_num].grid(column=hall_col, row=hall_row, sticky='enw',padx=1)
    hall_flag.append(hall_num)
    hall_flag[hall_num] = 1
    hall_num = hall_num + 1

def add_new_hvac(cursor):
    global hvac_num
    global hvac_button
    hvac_button.append(hvac_num)
    hvac_data_psi.append(hvac_num)
    hvac_data_air.append(hvac_num)
    hvac_data_psi[hvac_num] = "..."
    i = hvac_num + 1
    cmd1 = lambda: popup_showhvac(hvac.get(i),cursor)
    hvac_button[hvac_num]= tk.Button(hvac_frame, text=hvac.get(i) + "\n" + hvac_data_psi[hvac_num],
        font=("Arial Bold", 12), width=12, command=cmd1)
    hvac_button[hvac_num].grid(column=0, row=i, sticky='ew',padx=1)
    hvac_flag.append(hvac_num)
    hvac_flag[hvac_num] = 1
    hvac_num = hvac_num + 1

def add_boiler(cursor):
    global boiler_button
    cmd1 = lambda: popup_boiler('S',cursor)
    boiler_button= tk.Button(hvac_frame, text="Boiler\n         \n \n              ",
        font=("Arial Bold", 12), width=12,relief=FLAT,command=cmd1)
    boiler_button.grid(column=0, row=6, sticky='ew',padx=1)
    boiler_button.config(activebackground=boiler_button.cget('background'))

# This is the class that polls each device for data every 20 minutes (every 30 seconds
# for the boiler).  It is threaded to run based on time instead of user input.
class ThreadedClient:
    last_boiler_demand = 'Off'
    last_boiler_power = 'Off'
    last_boiler_burner = 'Off'
    last_boiler_alarm = 'Off'
    last_boiler_psi = 0.0
    last_minute = 61

    def __init__(self, master,queue1,gui):
        global thread_id
        self.master = master
        self.queue = queue1
        self.gui = gui
        try:
            self.ser = serial.Serial(serial_port, 9600, timeout=3,  rtscts=0) # open serial port
        except:
            print("Unable to open the serial port")
            raise
        self.running = 1
        thread_id = master.after(20, self.commThread)   # run after 20 milliseconds

    # The thread that does much of the work.  None of this is interactive, although it may be started by a button.
    def commThread(self):
        global thread_id
        global the_time
        global do_it_now
        if self.running:
            now_minute = datetime.now().minute  # Used to limit non-boiler polling

            if now_minute != self.last_minute or do_it_now == 1:    # Not a fan of python logic...
                self.last_minute = now_minute
                if now_minute == 0 or now_minute == 20 or now_minute == 40 or do_it_now == 1:
                    do_it_now = 0
                    self.gui.show_running( )    # Update the label to show this process is running
                    root.update()
                    try:
                        conn = sqlite3.connect(db);
                        cursor = conn.cursor();
                    except:
                        print("Unable to open the database")
                        pass
                    # Clear all the button labels so nothing is hanging on
                    for loc in range(7):
                        tunnel_button[loc].configure(text=tunnel.get(loc+1) + "\n...")
                    for loc in range(15):
                        hall_button[loc].configure(text=halls.get(loc + 1) + "\n...")
                    for loc in range(6):
                        hvac_button[loc].configure(text=hvac.get(loc+1) + '\n...')
                    root.update()
                    # Run through each device in the list
                    for sensor in units:
                        if sensor < 'A':    # This type of device is used in the tunnels (numbers 1 to 9)
                            serialcmd = '\x1b'+sensor   # x1b is the escape character, and its followed by the sensor id
                            self.ser.write(serialcmd.encode())     # write a string
                            try:
                                msg = self.ser.read_until('\n').decode("utf-8")
                                if len(msg) > 8:
                                    if msg[1] == ':' and msg[7] == ':':
                                        try:
                                            loc = int(msg[0]) - 1
                                            hum = msg[2:6]
                                            temp = msg[8:13]
                                            degree = u'\N{DEGREE SIGN}'
                                            tunnel_data[loc] = "%s%% %s%s" % (hum,temp,degree)
                                            tunnel_button[loc].configure(text=tunnel.get(loc+1).rstrip() +
                                                "\n" + tunnel_data[loc])
                                            try:
                                                sql = "insert into readings values ('{}',{:.3f},{:.3f},'{}')".format(tunnel.get(loc+1).strip(),float(hum),float(temp),the_time)
                                                cursor.execute(sql)
                                                conn.commit()
                                                time.sleep(0.05)
                                            except:
                                                print ('Failed to insert tunnel data')
                                                print (sql)
                                                pass
                                            tunnel_flag[loc] = 0
                                        except:
                                            print ('Error processing the message for tunnels')
                                            pass
                            except:
                                pass

                        if sensor >= 'A' and sensor <= 'E': # These are the five air handlers, A, B, C, D and E
                            serialcmd = '\x1b'+sensor
                            self.ser.reset_input_buffer()
                            self.ser.write(serialcmd.encode())
                            while True:
                                msg = self.ser.read_until('\n').decode("utf-8")
                                if len(msg) == 0 or len(msg) < 5:
                                    break

                                loc = ord(msg[0]) - ord('A')
                                hold_loc = loc
                                try:
                                    if msg[2].isdigit():
                                        temp = float(msg[4:10])
                                        offset = int(msg[2])
                                        hvac_data_temp[offset] = float(temp)
                                except:
                                    hvac_data_temp[0] = 0.0
                                    pass
                                # msg[2] ids the sub-type of record from the monitoring device
                                if msg[2] == 'T':   # A sub-type of T is a DS18B20
                                    try:
                                        ds18b20 = msg[8:20]
                                        try:
                                            loc = sensors.get(ds18b20) - 1
                                            loc_name = halls.get(loc + 1).strip()
                                        except:
                                            pass
                                        temp = msg[21:26]
                                        degree = u'\N{DEGREE SIGN}'
                                        if loc < 17:
                                            hall_data[loc] = "{:.1f}{}".format(float(temp),degree)
                                            hall_button[loc].configure(text=loc_name + "\n" +
                                                hall_data[loc])
                                            try:
                                                sql = "insert into readings values ('{}',0,{:.3f},'{}')".format(loc_name,float(temp),the_time)
                                                cursor.execute(sql)
                                                conn.commit()
                                            except:
                                                print ('Error adding db record for air handler ds18b20')
                                                print (sql)
                                                raise
                                        else:
                                            loc = hold_loc
                                            hvac_data_temp[3] = float(temp)
                                            hvac_button[loc].configure(text="AHU 5" +
                                                "\n{:.1f}{} outside".format(float(temp),degree))
                                    except:
                                        print ('Error processing the message for air handler hallway sensors')
                                        pass
                                if msg[2] == 'P':       #look for pressure reading from air compressor
                                    try:
                                        temp = msg[4:8]
                                        hvac_data_psi[loc] = float(temp)
                                        hvac_button[loc].configure(text=hvac.get(loc+1) +
                                            '\n' + temp + 'psi')
                                        if hvac_data_psi[loc] < 10 or hvac_data_psi[loc] > 25:
                                            hvac_button[loc].configure(bg='red')
                                        else:
                                            hvac_button[loc].configure(bg='#d9d9d9')
                                    except:
                                        print ("Failed on the pressure reading")
                                        pass
                                if msg[2] == 'A':   # The unit should have air moving
                                    try:
                                        temp = msg[4:9]
                                        if msg[4] == '-':
                                            temp = msg[5:10]
                                        hvac_data_air[loc] = float(temp)
                                    except:
                                        print ("Failed on the air movement reading")
                                        pass
                                if msg[2] == 'B':   # status of the Air Conditioners
                                    try:
                                        hvac_data_ac[loc] = msg[4:5]
                                        if msg[4] == 'A':   # Capital A is on, little a is off
                                            tt = hvac_button[loc].cget('text')
                                            hvac_button[loc].configure(text=tt + ', AC')
                                            root.update()
                                        if msg[5] == 'A':
                                            tt = hvac_button[loc].cget('text')
                                            hvac_button[loc].configure(text=tt + ', AC2')
                                            root.update()

                                    except:
                                        print ("Failed on the air conditioner reading")
                                        raise
                                if msg[2] == 'D':   # D is for DONE, the last record sent by the air handler
                                    try:
                                        try:
                                            if hvac_data_psi[loc] == '...':
                                                sql = "insert into ahu values ('{}',0.0,{:.3f},'{}','{}')".format(hvac.get(loc+1),hvac_data_air[loc],the_time,hvac_data_ac[loc])
                                            else:
                                                sql = "insert into ahu values ('{}',{:.3f},{:.3f},'{}','{}')".format(hvac.get(loc+1),hvac_data_psi[loc],hvac_data_air[loc],the_time,hvac_data_ac[loc])
                                            cursor.execute(sql)
                                            conn.commit();
                                        except:
                                            print ('Error putting AHU psi into DB.')
                                            print (sql)
                                            pass
                                        t1 = hvac_data_temp[0]  # up to 8 temperature sensors on each air handler
                                        t2 = hvac_data_temp[1]
                                        t3 = hvac_data_temp[2]
                                        t4 = hvac_data_temp[3]
                                        t5 = hvac_data_temp[4]
                                        t6 = hvac_data_temp[5]
                                        t7 = hvac_data_temp[6]
                                        t8 = hvac_data_temp[7]
                                        for x in range(8):
                                            hvac_data_temp[x] = 0.0
                                        try:
                                            sql = "insert into ahu_temps values ('{}','{}',{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f})".format(hvac.get(loc+1),the_time,t1,t2,t3,t4,t5,t6,t7,t8)
                                            cursor.execute(sql)
                                            conn.commit()
                                        except:
                                            print ('Error putting AHU data into DB.')
                                            print (sql)
                                            pass
                                    except:
                                        print ('Error adding air handler to DB.')
                                        pass
                                    break

                        if sensor >= 'a' and sensor <= 'z':     # The hallway DS18B20s are a through z
                            serialcmd = '\x1b{}t'.format(sensor)
                            self.ser.reset_input_buffer()
                            self.ser.write(serialcmd.encode())     # write a string
                            while True:
                                msg = self.ser.read_until('\n').decode("utf-8")
                                if len(msg) == 0 or len(msg) < 20:
                                    break
                                if msg[3] == 'D':
                                    break
                                if msg[1] == ':' and msg[2] == '[':
                                    ds18b20 = msg[8:20]
                                    loc = sensors.get(ds18b20) - 1
                                    loc_name = halls.get(loc + 1).strip()
                                    temp = msg[21:26]
                                    degree = u'\N{DEGREE SIGN}'
                                    hall_data[loc] = "{:.1f}{}".format(float(temp),degree)
                                    hall_button[loc].configure(text=loc_name + "\n" + hall_data[loc])
                                    try:
                                        sql = "insert into readings values ('{}',0,{:.3f},'{}')".format(loc_name,float(temp),the_time)
                                        cursor.execute(sql)
                                        conn.commit()
                                    except:
                                        print ('Error adding db record for ds18b20')
                                        print (sql)
                                        pass
                                    hall_flag[loc] = 0
                            #serialcmd = '\x1b{}s'.format(sensor)
                            #self.ser.write(serialcmd.encode())
                        time.sleep(0.7)
                        root.update()
                    conn.close()
                    self.gui.show_idle( )

            #print ('Getting boiler status at {}:{}'.format(datetime.now().minute,datetime.now().second))
            boiler_demand = 'Off'
            boiler_burner = 'Off'
            boiler_power = 'Off'
            boiler_alarm = 'Off'
            boiler_psi = 0.00
            serialcmd = '\x1bS'     # Capital S is the steam boiler monitor
            self.ser.write(serialcmd.encode())     # write a string
            try:
                msg = self.ser.read_until('\n').decode("utf-8")
                if len(msg) > 20:
                    if msg[1] == ':' and msg[7] == ':':
                        try:
                            boiler_psi = float(msg[2:6])    # The steam pressure (0 to 15 psi)
                            if msg[14] == '1':  # msg[14 to 17] is power,demand,burner, and alarm
                                boiler_power = 'On'
                            if msg[15] == '1':
                                boiler_demand = 'On'
                            if msg[16] == '1':
                                boiler_burner = 'On'
                            if msg[17] == '1':
                                boiler_alarm = 'On'
                            if boiler_power == 'On':
                                boiler_button.configure(bg='cyan',activebackground='cyan',text="Boiler\nDemand {}\nBurner {}\nSteam {:.2f}psi".format(boiler_demand,boiler_burner,boiler_psi))
                                if boiler_psi < 2.5:
                                    boiler_button.configure(bg='Red',activebackground='Red')
                            else:
                                if boiler_psi > 1:
                                    boiler_button.configure(bg='#d9d9d9',activebackground='#d9d9d9',text="Boiler\nSteam {:.2f}psi".format(boiler_psi))
                                else:
                                    boiler_button.configure(bg='#d9d9d9',activebackground='#d9d9d9',text="")
                            root.update()
                            try:    # Only record if something changed, other than pressure
                                if self.last_boiler_power != boiler_power \
                                or self.last_boiler_demand != boiler_demand \
                                or self.last_boiler_burner != boiler_burner \
                                or self.last_boiler_alarm != boiler_alarm:
                                    try:
                                        conn = sqlite3.connect(db);
                                        cursor = conn.cursor();
                                        the_time = time.strftime('%Y-%m-%d %H:%M:%S.000')
                                        # write the boiler record to the database using the current time
                                        sql = "insert into boiler values ('{}','{}','{}','{}','{}',{:.2f})".format(the_time,boiler_power,boiler_demand,boiler_burner,boiler_alarm,boiler_psi)
                                        #print (sql)    # for diagnostics
                                        cursor.execute(sql)
                                        conn.commit()
                                        conn.close()
                                    except:
                                        print ('Failed to insert record for boiler into the database')
                                        print (sql)
                                        pass
                            except:
                                pass
                            self.last_boiler_demand = boiler_demand
                            self.last_boiler_power = boiler_power
                            self.last_boiler_burner = boiler_burner
                            self.last_boiler_alarm = boiler_alarm
                            self.last_boiler_psi = boiler_psi
                        except:
                            print ('Error processing the message for boiler')
                            pass
            except:
                pass
            if self.last_boiler_alarm == 'On':  # Change to RED if boiler is in an alarm state.
                boiler_button.configure(background='Red',activebackground='Red')
                root.update()
            thread_id = self.master.after(29000, self.commThread)  # wait 29 seconds then run again
    def endApplication(self):
        self.running = 0    # flag to indicate shutdown

in_showme = 0
root = tk.Tk()
root.title("Temperature / Humidity Monitor")
root.geometry('800x460')
left_frame = tk.Frame(root, bg='')
left_frame.grid(row=1, column=0)
tunnel_frame = tk.Frame(root, bg='')
tunnel_frame.grid(row=1, column=1)
filler1_frame = tk.Frame(root, bg='', width=5)
filler1_frame.grid(row=1, column=2)
hall_frame = tk.Frame(root, bg='')
hall_frame.grid(row=1, column=3,sticky='n')
filler2_frame = tk.Frame(root, bg='', width=5)
filler2_frame.grid(row=1, column=4)
hvac_frame = tk.Frame(root, bg='')
hvac_frame.grid(row=1, column=5, sticky='n')
right_frame = tk.Frame(root, bg='',width=5)
right_frame.grid(row=1, column=6)

queue1 = queue.Queue(  )
gui = GuiPart(root, queue1)
client = ThreadedClient(root,queue1,gui)
root.mainloop(  )
