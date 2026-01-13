# just to make sure script works with PSU

import pyvisa
import time
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
volt3V3 = 3.3
currLim = 3.0

psu.write('*RST') # resets to default state
psu.write(f'INST:NSEL {chan1}') # select channel 1
psu.write(f'VOLT {volt3V3}') # set voltage
psu.write(f'CURR {currLim}') # set current limit

time.sleep(0.2)

psu.write(f'INST:NSEL {chan1}')
psu.write('OUTP ON')

t0 = time.time() #start time
print("output on\n")

while time.time() - t0 < 5.0:
	timeElapsed = time.time() - t0
	curr = float(psu.query('MEAS:CURR?'))
	print(f"Time: {format_time(timeElapsed)}, Current: {curr:.3f} A")
	time.sleep(0.5)

psu.write('INST:NSEL 1')
psu.write('OUTP OFF')
psu.write('*RST')
print("output off\n")