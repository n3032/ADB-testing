import pyvisa
import time
import csv
from datetime import datetime
from typing import cast, Protocol

class PSU(Protocol):
    def write(self, command: str) -> None: ...
    def query(self, command: str) -> str: ...

rm = pyvisa.ResourceManager()
psu: PSU = cast(PSU, rm.open_resource('TCPIP0::172.16.2.13::INSTR'))

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
currLim = 3.0
iterations = 1
maxIterations = 3

psu.write('*RST') # resets to default state
psu.write(f'INST:NSEL {chan1}') # select channel 1
psu.write(f'VOLT {volt7V2}') # set voltage
psu.write(f'CURR {currLim}') # set current limit
psu.write(f'INST:NSEL {chan2}')
psu.write(f'VOLT {volt3V3}')
psu.write(f'CURR {currLim}')

time.sleep(0.2)

# keep cumulative results across iterations
iterTime = []
iterCurr = []
iterPower = []

print("Starting timer test...\n")

while iterations<=maxIterations:
    psu.write(f'INST:NSEL {chan1}')
    psu.write('OUTP ON')
    psu.write(f'INST:NSEL {chan2}')
    psu.write('OUTP ON')

    t0 = time.time() #start time

    print("output on\n")

    testing = True

    timeElapsed = 0.0
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

    print(f"test #{iterations} complete. current spike detected\n")
    print(f"time elapsed: {format_time(timeElapsed)}\n")

    print("resetting\n")
    psu.write('INST:NSEL 1')
    psu.write('OUTP OFF')
    psu.write('INST:NSEL 2')
    psu.write('OUTP OFF')
    time.sleep(3)

    # per-iteration file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # e.g. 20260112_153045
    filename = f"timer_test_{iterations}_{timestamp}_data.csv"

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Time (MM:SS.mmm)', 'Current (A)', 'Power (W)'])
        for t, c, p in zip(pollTime, curr, power):
            writer.writerow([format_time(t), f"{c:.6f}", f"{p:.6f}"])

    print("data saved to " + filename)

    iterTime.append(timeElapsed)
    iterCurr.append((sum(curr)-curr[-1])/(len(curr)-1) if curr else 0)
    iterPower.append((sum(power)-power[-1])/(len(power)-1) if power else 0)

    iterations += 1

# write final results to a text file
final_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
results_filename = f"final_results_{final_ts}.txt"
with open(results_filename, "w") as f:
    f.write("Final Results:\n")
    f.write(f"average time: {format_time(sum(iterTime)/len(iterTime))}\n")
    f.write(f"average power: {sum(iterPower)/len(iterPower):.6f} W\n")
    f.write(f"average current: {sum(iterCurr)/len(iterCurr):.6f} A\n")
    f.write("Individual Iteration Results:\n")
    for i in range(len(iterTime)):
        f.write(f"Iteration {i+1}: Time = {format_time(iterTime[i])}, Average current = {iterCurr[i]:.6f} A, Average power = {iterPower[i]:.6f} W\n")

print("final results saved to " + results_filename)