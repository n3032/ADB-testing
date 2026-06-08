import pyvisa
from pyvisa.errors import VisaIOError
import time
import csv
from datetime import datetime
import sys
from ctypes import *
from dwfconstants import *

rm = pyvisa.ResourceManager()
psuresource = rm.list_resources()
print("Available VISA resources:")
for res in psuresource:
	print(f" - {res}")

chan1 = 1
volt7V2 = 1.0
rbfCurrThreshold = 0.004
burnCurrThreshold = 0.1
currLim = 3.0
errors = 0

DET1 = 1
DET2 = 2

psu = pyvisa.ResourceManager().open_resource(psuresource[0])



psu.write('*RST') # resets to default state
psu.write(f'VOLT {volt7V2}') # set voltage
psu.write(f'CURR {currLim}') # set current limit
#psu.write(f'{chan1}: VOLT {volt7V2}') # set voltage
#psu.write(f'{chan1}: CURR {currLim}') # set current limit
psu.write('OUTP ON')
while True:
    try:
        curr_val = float(psu.query('MEAS:CURR?'))
    except VisaIOError: # this was chatgpt'd 
        psu.clear()          # clears IO buffers
        time.sleep(1)
        errors += 1
        if errors > 5:
            psu.close()
            time.sleep(2)
            psu = pyvisa.ResourceManager().open_resource('USB0::0x1AB1::0x0E11::DP8C234305873::INSTR')
            print("PSU connection reset due to repeated timeouts")
            psu.timeout = 1000
            psu.write('*RST') # resets to default state
            psu.write(f'VOLT {volt7V2}') # set voltage
            psu.write(f'CURR {currLim}') # set current limit
            psu.write('OUTP ON')
            errors = 0
        continue             # retry loop
    print(f"{curr_val}")

psu.write('OUTP ON')
