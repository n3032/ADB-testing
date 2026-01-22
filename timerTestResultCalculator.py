import csv
import glob
import sys
from typing import List, Tuple

def parse_time(ts: str) -> float:
    """Parse 'MM:SS.mmm' into seconds (float)."""
    minutes, rest = ts.split(':')
    return int(minutes) * 60 + float(rest)

def parse_csv_file(path: str) -> Tuple[List[float], List[float], List[float]]:
    """Return (times_s, currents_A, powers_W)."""
    times, currents, powers = [], [], []
    with open(path, newline='') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 3:
                continue
            times.append(parse_time(row[0].strip()))
            currents.append(float(row[1]))
            powers.append(float(row[2]))
    return times, currents, powers

def avg(lst: List[float]) -> float:
    return sum(lst) / len(lst) if lst else 0.0

def format_time(seconds: float) -> str:
    minutes = int(seconds) // 60
    secs = seconds - minutes * 60
    return f"{minutes:02d}:{secs:06.3f}"

if __name__ == "__main__":
    paths = sys.argv[1:] or glob.glob("timer_test_*_data.csv")
    if not paths:
        print("No files found (use filenames or let it glob timer_test_*_data.csv)")
        sys.exit(1)       

    for p in paths:
        times, currents, powers = parse_csv_file(p)
        errors = 0
        downtime = 0.0
        for i in range(len(times)):
            if i > 0 and (times[i] - times[i-1] > 1.0):
                errors += 1
                downtime += times[i] - times[i-1]

        print(f"File: {p}")
        print(f"  samples: {len(times)}")
        print(f"  final time: {format_time(times[-1])}")
        print(f"  avg current: {avg(currents):.5f} A")
        print(f"  avg power: {avg(powers):.5f} W")
        print(f"  total energy: {avg(powers)*times[-1]:.3f} J")
        print(f"  detected errors (time gaps >1s): {errors}\n")
        print(f"  total downtime due to errors: {format_time(downtime)}\n")