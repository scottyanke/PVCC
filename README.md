This is the master program that pulls together all of the sensor information
scattered throughout the building for temperatures, air and steam pressures,
and the status of air conditioners and the steam boiler.

This runs on a Raspberry Pi, using Raspbian as the operating system.  The program
is written in Python 3, and uses tkinter for the gui functions.  Sqlite3 is used
to record the received data.  The program is portable enough to run on almost any
machine with Linux or Windows as operating systems.  All it needs in a serial
port connected to a RS485 adapter.  A 5 inch touchscreen is used instead of a
keyboard due to a lack of desk space.  A mouse could be used instead.

Much of this program came from multiple sources as I don't normally use Python.
Kudos to those who've supplied examples.  Anyone can use this program for
examples of what to do (or not).  It is used 24 hours a day in a production
environment.
