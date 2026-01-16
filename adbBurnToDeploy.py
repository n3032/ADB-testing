import pyvisa
from pyvisa.errors import VisaIOError
import dwfpy as dwf
import time
import csv
from datetime import datetime
import sys

psu = pyvisa.ResourceManager().open_resource('USB0::0x1AB1::0x0E11::DP8C234305873::INSTR')
ad = dwf.Device()
if ad is None:
    print("failed to open DWF device")
    sys.exit(1)
io = ad.digital_io
if io is None:
    print("failed to open DWF digital IO")
    sys.exit(1)
io[0].setup(enabled = True, state = False)
io[1].setup(enabled = False, configure = True)
io[2].setup(enabled = False, configure = True)

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
            if resp == 'y':
                break
            else:
                print("Please respond with 'y' or 'n'.")

def read_DIO(pin: int) -> bool:
    io.read_status()
    return io[pin].input_state

def burn(burn: bool):
    io[0].output_state = burn


chan1 = 1
volt7V2 = 7.2
currLim = 3.0
errors = 0

DET1 = 1
DET2 = 2

psu.write('*RST') # resets to default state
psu.write(f'INST:NSEL {chan1}') # select channel 1
psu.write(f'VOLT {volt7V2}') # set voltage
psu.write(f'CURR {currLim}') # set current limit

time.sleep(0.2)

print("Starting burn wire consistency test...\n")

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

print("*  Set up antennas, and depress SW1 and SW2.")
ask("Ready to begin burn test?")

burn(True)

print("Burn test started. Monitoring deployment...\n")

t0 = time.time() #start time

testing = True

timeElapsed = 0.0
pollTime = []
curr = []
volt = []
power = []
errors = 0
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

    if (read_DIO(DET1) and read_DIO(DET2)):
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
burn(False)
psu.write('INST:NSEL 1')
psu.write('OUTP OFF')

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # e.g. 20260112_153045

with open(f"burn_test_{timestamp}_data.csv", 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['Time (MM:SS.mmm)', 'Current (A)', 'Power (W)'])
    for t, c, p in zip(pollTime, curr, power):
        writer.writerow([format_time(t), f"{c:.6f}", f"{p:.6f}"])

print("Data saved to " + f"burn_test_{timestamp}_data.csv")

with open(f"burn_test_{timestamp}.txt", "w") as f:
    f.write(f"Final Results for test {timestamp}\n")
    f.write(f"Total time elapsed: {format_time(timeElapsed)}\n")
    f.write(f"Overall average voltage: {sum(volt)/len(volt):.6f} V\n")
    f.write(f"Overall average current: {sum(curr)/len(curr):.6f} A\n")
    f.write(f"Overall average power: {sum(power)/len(power):.6f} W\n")
    f.write(f"Total energy consumed: {sum(power)*timeElapsed/len(power):.3f} J\n")

print("Final results saved to " + f"full_functional_test_{timestamp}.txt")
