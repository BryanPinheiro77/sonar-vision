#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Le o serial por N segundos (argv[1]) e anexa em ./serial.log; porta em argv[2].
import os,select,termios,time,sys
from pathlib import Path
port=sys.argv[2] if len(sys.argv)>2 else "/dev/cu.usbmodem101"
fd=os.open(port,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
a=termios.tcgetattr(fd)
a[0]=0; a[1]=0; a[2]=termios.CS8|termios.CREAD|termios.CLOCAL; a[3]=0
a[4]=termios.B115200; a[5]=termios.B115200; a[6][termios.VMIN]=0; a[6][termios.VTIME]=0
termios.tcsetattr(fd,termios.TCSANOW,a)
try:
 with Path("serial.log").open('ab') as log:
  end=time.monotonic()+float(sys.argv[1] if len(sys.argv)>1 else 35)
  while time.monotonic()<end:
   if select.select([fd],[],[],0.25)[0]:
    try:data=os.read(fd,8192)
    except BlockingIOError:continue
    if data:
     log.write(data);log.flush();print(data.decode(errors='replace'),end='',flush=True)
finally:os.close(fd)
