from enum import Enum
import subprocess
import time
import json
import sched
import math
from typing import Callable, Final, List
import statistics

UPPER_CPU_TEMP: Final[float] = 80.0
LOWER_CPU_TEMP: Final[float] = 50.0

UPPER_GPU_TEMP: Final[float] = 70.0
LOWER_GPU_TEMP: Final[float] = 50.0

FULL_FAN_SPEED: Final[float] = 100
IDLE_FAN_SPEED: Final[float] = 30

HAS_CUDA: Final[bool] = subprocess.run(["nvidia-smi"], capture_output=True).returncode == 0

class Mode(Enum):
    MAX = 1
    AVG = 2
    MEDIAN = 3

def mode_2_fn(mode: Mode) -> Callable:
    return {
        1: max,
        2: statistics.mean,
        3: statistics.median,
    }[mode.value]

def fan_curve(norm_temp: float) -> float:
    # Generalised logistic function
    # https://en.wikipedia.org/wiki/Generalised_logistic_function
    # Slowly ramp fan speed as lower temperature is crossed but quickly increase after
    # F and G params are x and y offsets respectively
    A = 0
    K = 1.005 # Slightly > 1 so we can actually reach 100% fans
    C = 1
    Q = 1
    B = 13
    v = 2
    F = 9.7
    G = 0
    fan_speed = A + ((K-A) / (C+Q * math.exp(-B * norm_temp + F) ) ** (1 / v)) + G
    return fan_speed

def norm(val, min_val, max_val):
    return min((max(val, min_val) - min_val) / (max_val - min_val), 1.0)

def denorm(val, min_val, max_val):
    return val * (max_val - min_val) + min_val

def get_cpu_temps() -> List[float]:
    cpu_temp_check_cmd = "sensors -j"
    p = subprocess.run(cpu_temp_check_cmd.split(" "), check=True, capture_output=True)
    temps_json = json.loads(p.stdout.decode("utf-8"))
    cpu_temps = temps_json["coretemp-isa-0000"]
    core_keys = [k for k in cpu_temps if k.startswith("Core ")]
    core_temp_objects = [cpu_temps[k] for k in core_keys]
    temps = []
    for o in core_temp_objects:
        temps.append([v for k,v in o.items() if k.endswith("_input")][0])
    return temps

def get_gpu_temps() -> List[float]:
    if not HAS_CUDA:
        return []
    gpu_temp_check_cmd = "nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader"
    p = subprocess.run(gpu_temp_check_cmd.split(" "), check=True, capture_output=True)
    temps = list(map(int, p.stdout.decode("utf-8").strip().split("\n")))
    return temps

def set_fans(mode_fn, scheduler) -> None:
    scheduler.enter(1, 1, set_fans, (mode_fn, scheduler,))

    cpu_temps = get_cpu_temps()
    cpu_temps_normalized = [norm(t, LOWER_CPU_TEMP, UPPER_CPU_TEMP) for t in cpu_temps]

    gpu_temps = get_gpu_temps()
    gpu_temps_normalized = [norm(t, LOWER_GPU_TEMP, UPPER_GPU_TEMP) for t in gpu_temps]

    norm_fan = fan_curve(mode_fn(gpu_temps_normalized + cpu_temps_normalized))
    denorm_fan = int(denorm(norm_fan, IDLE_FAN_SPEED, FULL_FAN_SPEED))

    for group_idx in range(0, 2):
        fan_speed_set_cmd = f"ipmitool raw 0x30 0x70 0x66 0x01 {hex(group_idx)} {hex(denorm_fan)}"
        p = subprocess.run(fan_speed_set_cmd.split(" "), check=True, capture_output=True)
        
    print(f"CPU(s): {cpu_temps}C, GPU(s): {gpu_temps}C, Fan speed: {denorm_fan}%")

def main():

    mode = Mode.AVG
    mode_fn = mode_2_fn(mode)

    if HAS_CUDA:
        print("CUDA detected. Gathering GPU temperatures via nvidia-smi")

    # import matplotlib.pyplot as plt
    # import numpy as np
    # plt.plot([i for i in np.arange(0, 1.2, 0.05)], [fan_curve(i) * (FULL_FAN_SPEED - IDLE_FAN_SPEED) + IDLE_FAN_SPEED for i in np.arange(0, 1.2, 0.05)])
    # plt.ylabel("Fan speed %")
    # plt.xlabel("Normalized Temperature")
    # plt.show()
    # return

    # for i in np.arange(20, 100, 5):
    #     norm_temp = norm(i, LOWER_CPU_TEMP, UPPER_CPU_TEMP)
    #     norm_fan = fan_curve(norm_temp)
    #     denorm_fan = int(norm_fan * (FULL_FAN_SPEED - IDLE_FAN_SPEED) + IDLE_FAN_SPEED)
    #     print(f"Temp: {i}, fans: {denorm_fan}")
    # return

    my_scheduler = sched.scheduler(time.time, time.sleep)
    my_scheduler.enter(1, 1, set_fans, (mode_fn, my_scheduler))
    my_scheduler.run()


if __name__ == "__main__":
    main()