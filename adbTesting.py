# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

import pyvisa
import time

chan1 = 1
chan2 = 2
chan3 = 3
volt7V2 = 7.2
volt3V3 = 3.3
currThreshold = idk
currLim = 3
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
    psu.write('INST:NSEL 1')
    psu.write('OUTP ON')
    psu.write('INST:NSEL 2')
    psu.write('OUTP ON')

    t0 = time.time() #start time

    print("output on")

    testing = True

    while testing:
        psu.write(f'INST:NSEL {chan1}')
        curr = float(psu.query('MEAS:CURR?'))
        timeElapsed = time.time() - t0

        if curr >= currThreshold: testing = False

        time.sleep(0.05) #polling interval

    print(f"test #{iterations} complete. current spike detected")
    print(f"time elapsed: {timeElapsed:.3f} seconds")
    timeTotal += timeElapsed

    print("resetting")
    psu.write('INST:NSEL 1')
    psu.write('OUTP OFF')
    psu.write('INST:NSEL 2')
    psu.write('OUTP OFF')
    time.sleep(3)

    iterations += 1

timeAvg = timeTotal/maxIterations
print(f"average time: {timeAvg:.3f} seconds")








