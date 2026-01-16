import pyvisa
import time
import csv
from datetime import datetime
from pyvisa.errors import VisaIOError

psu = pyvisa.ResourceManager().open_resource('USB0::0x1AB1::0x0E11::DP8C234305873::INSTR')
psu.timeout = 1000

def format_time(seconds: float) -> str:
    minutes = int(seconds) // 60
    secs = seconds - minutes * 60
    return f"{minutes:02d}:{secs:06.3f}"  # MM:SS.mmm

chan1 = 1
volt7V2 = 7.2
currThreshold = 0.5
currLim = 3.0
iterations = 1
maxIterations = 1

psu.write('*RST') # resets to default state
psu.write(f'INST:NSEL {chan1}') # select channel 1
psu.write(f'VOLT {volt7V2}') # set voltage
psu.write(f'CURR {currLim}') # set current limit

time.sleep(0.2)

# keep cumulative results across iterations
iterTime = []
iterCurr = []
iterPower = []

print("Starting timer test...\n")

while iterations<=maxIterations:
    psu.write(f'INST:NSEL {chan1}')
    psu.write('OUTP ON')

    t0 = time.time() #start time

    print("Output enabled.\n")

    testing = True

    timeElapsed = 0.0
    pollTime = []
    curr = []
    power = []
    errors = 0

    psu.write(f'INST:NSEL {chan1}')
    while testing:
        try:
            volt_val = float(psu.query('MEAS:VOLT?'))
            curr_val = float(psu.query('MEAS:CURR?'))
            pow_val = float(psu.query('MEAS:POWE?'))
        except VisaIOError:
            psu.clear()          # clears IO buffers
            time.sleep(1)
            errors += 1
            if errors > 5:
                psu.close()
                time.sleep(2)
                psu = pyvisa.ResourceManager().open_resource('USB0::0x1AB1::0x0E11::DP8C234305873::INSTR')
                print("PSU connection reset due to repeated timeouts; timer may be reset")
                psu.timeout = 1000
                psu.write('*RST') # resets to default state
                psu.write(f'INST:NSEL {chan1}') # select channel 1
                psu.write(f'VOLT {volt7V2}') # set voltage
                psu.write(f'CURR {currLim}') # set current limit
                psu.write(f'INST:NSEL {chan1}')
                psu.write('OUTP ON')
            continue             # retry loop
        timeElapsed = time.time() - t0

        print(f"Time: {format_time(timeElapsed)}, Voltage: {volt_val:.3f}, Current: {curr_val:.3f} A, Power: {pow_val:.3f} W")

        if curr_val >= currThreshold: testing = False

        curr.append(curr_val)
        power.append(pow_val)
        pollTime.append(timeElapsed)
        time.sleep(0.25) #polling interval
        if (timeElapsed % 60) < 0.25:
            err = psu.query('SYST:ERR?')
            if not err.startswith('0'):
                print("PSU error:", err)

    print(f"Test #{iterations} complete; Current spike detected\n")
    print(f"Time elapsed: {format_time(timeElapsed)}\n")

    print("Resetting...\n")
    psu.write('INST:NSEL 1')
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

    print("Data saved to " + filename)

    iterTime.append(timeElapsed)
    iterCurr.append((sum(curr)-curr[-1])/(len(curr)-1) if curr else 0)
    iterPower.append((sum(power)-power[-1])/(len(power)-1) if power else 0)

    iterations += 1

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

print("Final results saved to " + results_filename)