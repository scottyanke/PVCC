# Master program for collecting temperature, humidity, and boiler data
This is the master program that pulls together all of the sensor information
scattered throughout the building for temperatures, air and steam pressures,
and the status of air conditioners and the steam boiler.

## Where does it run?
This runs on a Raspberry Pi, using Raspbian as the operating system.  The program
is written in Python 3, and uses tkinter for the gui functions.  Sqlite3 is used
to record the received data.  The program is portable enough to run on almost any
machine with Linux or Windows as operating systems.  All it needs in a serial
port connected to a RS485 adapter.  A 5 inch touchscreen is used instead of a
keyboard due to a lack of desk space.  A mouse could be used with it.

## Where this came from...
Much of this program came from multiple sources as I don't normally use Python.
Kudos to those who've supplied examples.  Anyone can use this program for
examples of what to do (or not).  It is used 24 hours a day in a production
environment.

## Requirements
This python program requires python 3 (or greater), Sqlite version 3, tkinter for python,
and the usual python modules for threading, datetime, and serial functions.

RS485 is not required, although that is what this program normally uses to talk to all
the other devices.  A Raspberry Pi is used in this case, but a normal desktop pc could
also be used.  Even the touch screen is not a requirement, as a mouse could also be used.
No keyboard is required, as there is no data entry.

Since this part is an all-in-one python program, no compiler is used, nor is any makefile.