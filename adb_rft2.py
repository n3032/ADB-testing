import pyvisa
from pyvisa.errors import VisaIOError
import time
import csv
from datetime import datetime
import sys
from ctypes import *
from dwfconstants import *

# Load Digilent WaveForms SDK
if sys.platform.startswith("win"):
    dwf = cdll.dwf
elif sys.platform.startswith("darwin"):
    dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
else:
    dwf = cdll.LoadLibrary("libdwf.so")

hdwf = c_int()

if dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf)) == 0:
    print("failed to open DWF device")
    sys.exit(1)

# Set parameter for what happens when device closes
dwf.FDwfParamSet(DwfParamOnClose, c_int(0))  # 0 = run, 1 = stop, 2 = shutdown

# Disable auto-configure to manually configure Digital IO
dwf.FDwfDeviceAutoConfigureSet(hdwf, c_int(0))

psu = pyvisa.ResourceManager().open_resource('USB0::0x1AB1::0x0E11::DP8C234305873::INSTR')

#chat changes-----
# DIO configuration
# DIO0 = BURN (output)
# DIO1 = DET1 (input)
# DIO2 = DET2 (input)

# Enable output on DIO0 (DIO1 and DIO2 will be inputs by default)
dwf.FDwfDigitalIOOutputEnableSet(hdwf, c_int(0b00000001))
# Set initial output value
dwf.FDwfDigitalIOOutputSet(hdwf, c_int(0))
# Apply the Digital IO configuration
dwf.FDwfDigitalIOConfigure(hdwf)
#------

def format_time(seconds: float) -> str:
    minutes = int(seconds) // 60
    secs = seconds - minutes * 60
    return f"{minutes:02d}:{secs:06.3f}"  # MM:SS.mmm

def ask(prompt: str):
    print("-> " + prompt + " [y/n]")
    while True:
        resp = input().strip().lower()
        if not resp or resp == 'n':
            print("Verification failed, aborting...\n")
            psu.write('INST:NSEL 1'); psu.write('OUTP OFF')
            psu.write('INST:NSEL 2'); psu.write('OUTP OFF')
            burn(False)
            sys.exit(0)
        else:
            break

def read_DIO(pin: int) -> bool:
    dwRead = c_uint32() #io states returned as 32 bitmask
    dwf.FDwfDigitalIOStatus(hdwf) #sub for io.read_status
    dwf.FDwfDigitalIOInputStatus(hdwf, byref(dwRead)) #writes pin logic levels to dwRead
    return bool(dwRead.value & (1 << pin)) #extracts the pin we want

def burn(state: bool):
    dwf.FDwfDigitalIOOutputSet(
        hdwf, 
        c_int(1 if state else 0)
    )
    dwf.FDwfDigitalIOConfigure(hdwf)


chan1 = 1
volt7V2 = 7.2
rbfCurrThreshold = 0.004
burnCurrThreshold = 0.1
currLim = 3.0
errors = 0

DET1 = 1
DET2 = 2

psu.write('*RST') # resets to default state
psu.write(f'INST:NSEL {chan1}') # select channel 1
psu.write(f'VOLT {volt7V2}') # set voltage
psu.write(f'CURR {currLim}') # set current limit

time.sleep(0.2)

print("Starting RFT2 for TVAC thermal cycling...\n")

print("Ensure the following before proceeding:")
print("*  EGSE 7V2 is connected to PSU Channel 1 +.")
print("*  EGSE GND is connected to PSU Channel 1 -.")
print("*  AD3 GND is connected to EGSE GND.")
print("*  AD3 DIO0 is connected to EGSE BURN.")
print("*  AD3 DIO1 is connected to EGSE DET_1.")
print("*  AD3 DIO2 is connected to EGSE DET_2.") 
# print("*  ADB is NOT connected to the EGSE.")
print("*  RBF is NOT connected to ADB J2.")
print("*  ADB is connected to the EGSE.")
print("*  ADB DPL signal functionality has been tested.")
print("*  EGSE functionality has been tested.")
ask("Connections verified?")

print("Turning on EGSE...")

psu.write(f'INST:NSEL {chan1}')
psu.write('OUTP ON')

ask("Verified DS1 is ON?")
ask("Verified DS2 changes state every 3.8-3.9 seconds?")
ask("Ready to test burn signal functionality?")
print("Testing BURN signal functionality...")
burn(True)
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
            psu.write(f'INST:NSEL {chan1}') # select channel 1
            psu.write(f'VOLT {volt7V2}') # set voltage
            psu.write(f'CURR {currLim}') # set current limit
            psu.write(f'INST:NSEL {chan1}')
            psu.write('OUTP ON')
        continue             # retry loop
    print(f"{curr_val}")
    if curr_val >= burnCurrThreshold:
        break
burn(False)

print("Burn signal functionality verified.\n")
print("Turning off PSU...")
psu.write(f'INST:NSEL {chan1}')
psu.write('OUTP OFF')

print("RFT2 complete!")