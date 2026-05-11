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

print("Starting full functional test for TVAC...\n")

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
psu.write('INST:NSEL {chan1}')
psu.write('OUTP OFF')

print("Burn signal functionality verified.\n")

ask("Ready to start timer?")

print("Starting timer...\n")

time.sleep(1)

psu.write(f'INST:NSEL {chan1}')
psu.write('OUTP ON')

t0 = time.time() #start time

testing = True

timeElapsed = 0.0
pollTime = []
curr = []
volt = []
power = []
errors = 0
burning = False
dpl1Bool = False
dpl2Bool = False
burnStartIndex = 0
burnTime = 0.0
dpl1Time = 0.0
dpl2Time = 0.0


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

    print(f"Time: {format_time(timeElapsed)}, Voltage: {volt_val:.4f}V, Current: {curr_val:.4f} A, Power: {pow_val:.3f} W")

    if curr_val >= burnCurrThreshold and not burning:
        print("Timer triggered at time:", format_time(timeElapsed))
        burnStartIndex = len(curr)
        burnTime = timeElapsed
        burning = True

    if not burning and (read_DIO(DET1) or read_DIO(DET2)):
        print("Test aborted due to early deployment detection.")
        testing = False
        break

    if burning and (read_DIO(DET1)) and not dpl1Bool:
        print("DPL1 detected.")
        dpl1Time = timeElapsed
        dpl1Bool = True

    if burning and (read_DIO(DET2)) and not dpl2Bool:
        print("DPL2 detected.")
        dpl2Time = timeElapsed
        dpl2Bool = True

    if curr_val <= burnCurrThreshold and burning:
        print("Self-disable detected. Ending test.")
        testing = False

    curr.append(curr_val)
    volt.append(volt_val)
    power.append(pow_val)
    pollTime.append(timeElapsed)
    if not burning:
        time.sleep(0.25)
    else:
        time.sleep(0.05)
    
    if (timeElapsed % 60) < 0.25:
        err = psu.query('SYST:ERR?')
        if not err.startswith('0'):
            print("PSU error:", err)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # e.g. 20260112_153045

with open(f"adb_fft_{timestamp}_data.csv", 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['Time (MM:SS.mmm)', 'Voltage (V)', 'Current (A)', 'Power (W)'])
    for t, v, c, p in zip(pollTime, volt, curr, power):
        writer.writerow([format_time(t), f"{v:.4f}", f"{c:.4f}", f"{p:.3f}"])

print("Data saved to " + f"adb_fft_{timestamp}_data.csv")

timer_segment_duration = burnTime
if dpl1Time > dpl2Time:
    deployment_duration = dpl1Time-burnTime
else:
    deployment_duration = dpl2Time-burnTime
burn_segment_duration = timeElapsed - burnTime

def safe_avg(data):
    return sum(data) / len(data) if data else 0

timer_avg_power = safe_avg(power[:burnStartIndex])
burn_avg_power = safe_avg(power[burnStartIndex:])

with open(f"adb_fft_{timestamp}.txt", "w") as f:
    f.write(f"Final Results for test {timestamp}\n")
    f.write("Timer segment:\n")
    f.write(f"Time elapsed: {format_time(timer_segment_duration)}\n")
    f.write(f"Average voltage: {safe_avg(volt[:burnStartIndex]):.5f} V\n")
    f.write(f"Average current: {safe_avg(curr[:burnStartIndex]):.6f} A\n")
    f.write(f"Average power: {timer_avg_power:.5f} W\n")
    f.write(f"Energy consumed: {timer_avg_power * timer_segment_duration:.3f} J\n")
    f.write("\n")
    f.write("Burn segment:\n")
    f.write(f"Time elapsed: {format_time(burn_segment_duration)}\n")
    f.write(f"Average voltage: {safe_avg(volt[burnStartIndex:]):.5f} V\n")
    f.write(f"Average current: {safe_avg(curr[burnStartIndex:]):.6f} A\n")
    f.write(f"Calculated resistance: {(safe_avg(volt[burnStartIndex:])/(safe_avg(curr[burnStartIndex:])-timer_avg_power)):.3f} ohms\n" )
    f.write(f"Average power: {burn_avg_power:.5f} W\n")
    f.write(f"Energy consumed: {burn_avg_power * burn_segment_duration:.3f} J\n")
    f.write(f"DPL1 time: {format_time(dpl1Time-burnTime)}\n")
    f.write(f"DPL2 time: {format_time(dpl2Time-burnTime)}\n")
    f.write(f"Overall deployment time: {format_time(deployment_duration)}\n")
    f.write("\n")
    f.write("Overall Results:\n")
    f.write(f"Total time elapsed: {format_time(timeElapsed)}\n")
    f.write(f"Total energy consumed: {(burn_avg_power * burn_segment_duration+timer_avg_power * timer_segment_duration):.3f} J\n")

print("Final results saved to " + f"adb_fft_{timestamp}.txt")
print("Remember to verify DS4 is ON, measure and log the equivalent resistance, and turn off the power supply!")
print("FFT complete!")