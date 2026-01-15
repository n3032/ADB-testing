import pyvisa
from pyvisa.errors import VisaIOError
import time
import csv
from datetime import datetime
import sys
from ctypes import *

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

psu = pyvisa.ResourceManager().open_resource('USB0::0x1AB1::0x0E11::DP8C234305873::INSTR')

#chat changes-----
# DIO configuration
# DIO0 = BURN (output)
# DIO1 = DET1 (input)
# DIO2 = DET2 (input)

dwf.FDwfDigitalIOOutputEnableSet(hdwf, c_int(0b00000001))  # DIO0 output
dwf.FDwfDigitalIOOutputSet(hdwf, c_int(0))                # BURN LOW

dwf.FDwfDigitalIOInputEnableSet(hdwf, c_int(0b00000110))  # DIO1, DIO2 inputs
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


chan1 = 1
volt7V2 = 7.2
rbfCurrThreshold = 0.004
burnCurrThreshold = 0.5
currLim = 3.0
errors = 0

DET1 = 1
DET2 = 2

psu.write('*RST') # resets to default state
psu.write(f'INST:NSEL {chan1}') # select channel 1
psu.write(f'VOLT {volt7V2}') # set voltage
psu.write(f'CURR {currLim}') # set current limit

time.sleep(0.2)

print("Starting full functional test...\n")

print("Ensure the following before proceeding:")
print("*  GND is connected to EGSE GND.")
print("*  DIO0 is connected to EGSE BURN.")
print("*  DIO1 is connected to EGSE DET_1.")
print("*  DIO2 is connected to EGSE DET_2.")
print("*  ADB is NOT connected to the EGSE.")
ask("Connections verified?")

print("Testing BURN functionality...")
burn(True)
ask("Verified EGSE BURN is ON?")
burn(False)

print("*  Set up and tension burn wires.\n")

ask("Verified stability of burn wires?")

print("*  Connect ADB to EGSE.")

ask("ADB connected to EGSE?")

print("Turning on EGSE...")

psu.write(f'INST:NSEL {chan1}')
psu.write('OUTP ON')

ask("Verified DS1 is ON and EGSE BURN is OFF?")

print("*  Depress SW1.")
print("Waiting for DET1 to trigger...")
while not read_DIO(DET1):
    time.sleep(0.1)
print("DET1 triggered.")
ask("Verified DS2 is ON and EGSE DET1 is OFF?")

print("*  Release SW1.")
print("Waiting for DET1 to release...")
while read_DIO(DET1):
    time.sleep(0.1)
print("DET1 released.")

print("*  Depress SW2.")
print("Waiting for DET2 to trigger...")
while not read_DIO(DET2):
    time.sleep(0.1)
ask("Verified DS2 is ON and EGSE DET2 is OFF?")

print("*  Release SW2.")
print("Waiting for DET2 to release...")
while read_DIO(DET2):
    time.sleep(0.1)
print("DET2 released.")

print("*  Connect RBF to J2")
ask("Verified DS1 is OFF?")

print("*  Tape SW1 and SW2 down.")
ask("Ready to remove RBF?")

print("*  Remove RBF from J2")
print("Waiting for current spike indicating RBF removal...")

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
    if curr_val >= rbfCurrThreshold:
        break

print("RBF removal current spike detected. Starting timer...\n")

t0 = time.time() #start time

testing = True

timeElapsed = 0.0
pollTime = []
curr = []
volt = []
power = []
errors = 0
burning = False
burnStartIndex = 0
burnTime = 0.0

psu.write(f'INST:NSEL {chan1}')
while testing:
    try:
        curr_val = float(psu.query('MEAS:CURR?'))
        volt_val = float(psu.query('MEAS:VOLT?'))
        pow_val = float(psu.query('MEAS:POWE?'))
    except VisaIOError:
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
    timeElapsed = time.time() - t0

    print(f"Time: {format_time(timeElapsed)}, Voltage: {volt_val:.3f}V, Current: {curr_val:.6f} A, Power: {pow_val:.6f} W")

    if curr_val >= burnCurrThreshold and not burning:
        print("Timer triggered at time:", format_time(timeElapsed))
        burnStartIndex = len(curr)
        burnTime = timeElapsed
        burning = True

    if not burning and (read_DIO(DET1) or read_DIO(DET2)):
        print("Test aborted due to early deployment detection.")
        testing = False
        break

    if burning and (read_DIO(DET1) and read_DIO(DET2)):
        print("Both deployments detected. Ending test.")
        testing = False

    curr.append(curr_val)
    volt.append(volt_val)
    power.append(pow_val)
    pollTime.append(timeElapsed)
    time.sleep(0.25)
    if (timeElapsed % 60) < 0.25:
        err = psu.query('SYST:ERR?')
        if not err.startswith('0'):
            print("PSU error:", err)


print("Shutting off power...\n")
psu.write('INST:NSEL 1')
psu.write('OUTP OFF')
time.sleep(3)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # e.g. 20260112_153045

with open(f"full_functional_test_{timestamp}_data.csv", 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['Time (MM:SS.mmm)', 'Current (A)', 'Power (W)'])
    for t, c, p in zip(pollTime, curr, power):
        writer.writerow([format_time(t), f"{c:.6f}", f"{p:.6f}"])

print("data saved to " + f"full_functional_test_{timestamp}_data.csv")

# write final results to a text file
with open(f"full_functional_test_{timestamp}.txt", "w") as f:
    f.write(f"Final Results for test {timestamp}\n")
    f.write("Timer segment:\n")
    f.write(f"Time elapsed: {format_time(burnTime)}\n")
    f.write(f"Average voltage: {sum(volt[:burnStartIndex])/len(volt[:burnStartIndex]):.6f} V\n")
    f.write(f"Average current: {sum(curr[:burnStartIndex])/len(curr[:burnStartIndex]):.6f} A\n")
    f.write(f"Average power: {sum(power[:burnStartIndex])/len(power[:burnStartIndex]):.6f} W\n")
    f.write(f"Energy consumed: {sum(power[:burnStartIndex])/len(power[:burnStartIndex])*burnTime:.3f} J\n")
    f.write("\n")
    f.write("Burn segment:\n")
    f.write(f"Time elapsed: {format_time(timeElapsed - burnTime)}\n")
    f.write(f"Average voltage: {sum(volt[burnStartIndex:])/len(volt[burnStartIndex:]):.6f} V\n")
    f.write(f"Average current: {sum(curr[burnStartIndex:])/len(curr[burnStartIndex:]):.6f} A\n")
    f.write(f"Average power: {sum(power[burnStartIndex:])/len(power[burnStartIndex:]):.6f} W\n")
    f.write(f"Energy consumed: {sum(power[burnStartIndex:])/len(power[burnStartIndex:])*(timeElapsed - burnTime):.3f} J\n")
    f.write("\n")
    f.write("Overall Results:\n")
    f.write(f"Total time elapsed: {format_time(timeElapsed)}\n")
    f.write(f"Overall average voltage: {sum(volt)/len(volt):.6f} V\n")
    f.write(f"Overall average current: {sum(curr)/len(curr):.6f} A\n")
    f.write(f"Overall average power: {sum(power)/len(power):.6f} W\n")
    f.write(f"Total energy consumed: {sum(power)*timeElapsed/len(power):.3f} J\n")

print("Final results saved to " + f"full_functional_test_{timestamp}.txt")
