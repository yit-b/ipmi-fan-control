from enum import Enum
import subprocess
import time
import json
import sched
import math
from typing import Callable, Dict, Final, List
import yaml
import argparse

class Mode(Enum):
    MAX = 1

def mode_2_fn(mode: Mode) -> Callable:
    """
    Return a function corresponding to the Mode enum
    """
    return {
        1: max,
    }[mode.value]

def fan_curve(norm_temp: float) -> float:
    """
    Generalised logistic function
    https://en.wikipedia.org/wiki/Generalised_logistic_function
    Slowly ramp fan speed as lower temperature is crossed but quickly increase
    after. F and G params are x and y offsets respectively
    """
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
    """
    Normalize val between 0 and 1
    """
    return min((max(val, min_val) - min_val) / (max_val - min_val), 1.0)

def denorm(val, min_val, max_val):
    """
    Denormalize val (between 0 and 1) to the provided range
    """
    return val * (max_val - min_val) + min_val

def get_cpu_temps() -> List[float]:
    cpu_temp_check_cmd = "sensors -j"
    p = subprocess.run(cpu_temp_check_cmd.split(" "), check=True, 
                       capture_output=True)
    temps_json = json.loads(p.stdout.decode("utf-8"))
    cpu_temps = temps_json["coretemp-isa-0000"]
    core_keys = [k for k in cpu_temps if k.startswith("Core ")]
    core_temp_objects = [cpu_temps[k] for k in core_keys]
    temps = []
    for o in core_temp_objects:
        temps.append([v for k,v in o.items() if k.endswith("_input")][0])
    return temps

def get_gpu_temps() -> List[float]:
    gpu_temp_check_cmd = (
        "nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader"
    )
    p = subprocess.run(gpu_temp_check_cmd.split(" "), check=True, 
                       capture_output=True)
    temps = list(map(int, p.stdout.decode("utf-8").strip().split("\n")))
    return temps

def set_fan_speed(fan_speed: int):
    """
    Set fan speeds to the specified speed for all fan groups
    """
    for group_idx in range(0, 2):
        fan_speed_set_cmd = (
            f"ipmitool raw 0x30 0x70 0x66 0x01 {hex(group_idx)} {hex(fan_speed)}"
        )
        p = subprocess.run(fan_speed_set_cmd.split(" "), check=True, 
                           capture_output=True)

def set_fans(config: Dict, mode_fn: Callable, has_cuda: bool, scheduler) -> None:
    scheduler.enter(1, 1, set_fans, (config, mode_fn, has_cuda, scheduler,))

    cpu_temp_range: Final = config["temps"]["cpu"]
    gpu_temp_range: Final = config["temps"]["gpu"]
    fan_speed_range: Final = config["fans"]
    gpu_temp_fn = get_gpu_temps if has_cuda else lambda _: []

    cpu_temps = get_cpu_temps()
    cpu_temps_normalized = [norm(t, cpu_temp_range["lower"], 
                                 cpu_temp_range["upper"]) for t in cpu_temps]

    gpu_temps = gpu_temp_fn()
    gpu_temps_normalized = [norm(t, gpu_temp_range["lower"], 
                                    gpu_temp_range["upper"]) for t in gpu_temps]

    norm_fan = fan_curve(mode_fn(gpu_temps_normalized + cpu_temps_normalized))
    denorm_fan = int(denorm(norm_fan, fan_speed_range["min"], 
                            fan_speed_range["max"]))
    
    set_fan_speed(denorm_fan)
        
    print(f"CPU(s): {cpu_temps}C, GPU(s): {gpu_temps}C, Fan speed: {denorm_fan}%")

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', type=str,
                        help="configuration file containing temperature and fan speed ranges")
    parser.add_argument('-o', '--override', type=int,
                        help="Manually set the fan speed to the specified speed in percent")
    args = parser.parse_args()

    if args.override is not None:
        # Manually set the fan speeds to the specified value
        set_fan_speed(args.override)
        return

    with open(args.config, "rb") as f:
        config: Final[Dict] = yaml.safe_load(f)

    has_cuda: Final[bool] = subprocess.run(["nvidia-smi"], 
                                           capture_output=True).returncode == 0
    mode = Mode.MAX
    mode_fn = mode_2_fn(mode)

    if has_cuda:
        print("CUDA detected. Gathering GPU temperatures via nvidia-smi")

    # import matplotlib.pyplot as plt
    # import numpy as np
    # plt.plot([i for i in np.arange(0, 1.2, 0.05)], [fan_curve(i) * (FULL_FAN_SPEED - IDLE_FAN_SPEED) + IDLE_FAN_SPEED for i in np.arange(0, 1.2, 0.05)])
    # plt.ylabel("Fan speed %")
    # plt.xlabel("Normalized Temperature")
    # plt.show()
    # return

    scheduler = sched.scheduler(time.time, time.sleep)
    scheduler.enter(1, 1, set_fans, (config, mode_fn, has_cuda, scheduler))
    scheduler.run()


if __name__ == "__main__":
    main()