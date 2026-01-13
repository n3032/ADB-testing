# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

import pyvisa
import time
import csv

def format_time(seconds: float) -> str:
    minutes = int(seconds) // 60
    secs = seconds - minutes * 60
    return f"{minutes:02d}:{secs:06.3f}"  # MM:SS.mmm

chan1 = 1
chan2 = 2
chan3 = 3
volt7V2 = 7.2
volt3V3 = 3.3
currThreshold = 0.5
currLim = 2.0
iterations = 1
maxIterations = 3
timeTotal = 0

psu = pyvisa.ResourceManager().open_resource('TCPIP0::172.16.2.13::INSTR')

psu.write('*RST') #resets to default state
psu.write(f'INST:NSEL {chan1}') # select channel 1
psu.write(f'VOLT {volt7V2}') # set voltage
psu.write(f'CURR {currLim}') # set current limit
psu.write(f'INST:NSEL {chan2}')
psu.write(f'VOLT {volt3V3}')
psu.write(f'CURR {currLim}')

time.sleep(0.2)

while iterations<=maxIterations:
    psu.write(f'INST:NSEL {chan1}')
    psu.write('OUTP ON')
    psu.write(f'INST:NSEL {chan2}')
    psu.write('OUTP ON')

    t0 = time.time() #start time

    print("output on")

    testing = True

    pollTime = []
    curr = []
    power = []

    while testing:
        psu.write(f'INST:NSEL {chan1}')
        curr.append(float(psu.query('MEAS:CURR?')))
        power.append(float(psu.query('MEAS:POWE?')))
        timeElapsed = time.time() - t0

        if curr[-1] >= currThreshold: testing = False
        
        pollTime.append(timeElapsed)
        time.sleep(0.05) #polling interval

    print(f"test #{iterations} complete. current spike detected")
    print(f"time elapsed: {format_time(timeElapsed)}")
    timeTotal += timeElapsed

    print("resetting")
    psu.write('INST:NSEL 1')
    psu.write('OUTP OFF')
    psu.write('INST:NSEL 2')
    psu.write('OUTP OFF')
    time.sleep(3)

    filename = f"timer_test_{iterations}_data.csv"

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Time (MM:SS.mmm)', 'Current (A)', 'Power (W)'])
        for t, c, p in zip(pollTime, curr, power):
            writer.writerow([format_time(t), f"{c:.6f}", f"{p:.6f}"])

    iterations += 1

timeAvg = timeTotal/maxIterations
print(f"average time: {format_time(timeAvg)}")








