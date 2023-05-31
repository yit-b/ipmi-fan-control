import subprocess
import time
import json
import sched
import math

UPPER_CPU_TEMP = 80.0
LOWER_CPU_TEMP = 50.0

UPPER_GPU_TEMP = 70.0
LOWER_GPU_TEMP = 50.0

FULL_FAN_SPEED = 100
IDLE_FAN_SPEED = 30

def curve(norm_temp):
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


def get_cpu_temp(normalized=True):
    cpu_temp_check_cmd = "ipmitool sdr type temperature"
    p = subprocess.run(cpu_temp_check_cmd.split(" "), check=True, capture_output=True)
    table = p.stdout.decode("utf-8").splitlines()

    rows = {}
    for row in table:
        r = [e.strip() for e in row.split("|")]
        name = r[0]
        temp = r[-1]
        if temp == "No Reading":
            temp = "0"
        rows[name] = int(temp.split(" degrees C")[0])

    cpu_temp = rows["CPU Temp"]
    print(f"CPU Temp: {cpu_temp}C")
    if not normalized:
        return cpu_temp

    norm_temp = min((max(cpu_temp, LOWER_CPU_TEMP) - LOWER_CPU_TEMP) / (UPPER_CPU_TEMP - LOWER_CPU_TEMP), 1.0)
    return norm_temp

def norm(val, min_val, max_val):
    return min((max(val, min_val) - min_val) / (max_val - min_val), 1.0)

def get_cpu_temp_json():
    cpu_temp_check_cmd = "sensors -j"
    p = subprocess.run(cpu_temp_check_cmd.split(" "), check=True, capture_output=True)
    temps_json = json.loads(p.stdout.decode("utf-8"))
    cpu_temp = int(temps_json["coretemp-isa-0000"]["Package id 0"]["temp1_input"])
    cpu_norm = norm(cpu_temp, LOWER_CPU_TEMP, UPPER_CPU_TEMP)
    return (cpu_temp, cpu_norm)

def get_gpu_temp():
    gpu_temp_check_cmd = "nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader"
    p = subprocess.run(gpu_temp_check_cmd.split(" "), check=True, capture_output=True)

    temps = [int(e) for e in p.stdout.decode("utf-8").split("\n") if e]
    max_gpu_temp = max(temps)
    gpu_norm = norm(max_gpu_temp, LOWER_GPU_TEMP, UPPER_GPU_TEMP)

    return (temps, gpu_norm)

def set_fans(scheduler):
    scheduler.enter(1, 1, set_fans, (scheduler,))

    cpu_temp, cpu_norm = get_cpu_temp_json()
    gpu_temp, gpu_norm = get_gpu_temp()

    max_norm = max(cpu_norm, gpu_norm)
    norm_fan = curve(max_norm)
    denorm_fan = int(norm_fan * (FULL_FAN_SPEED - IDLE_FAN_SPEED) + IDLE_FAN_SPEED)

    for group_idx in range(0, 2):
        fan_speed_set_cmd = f"ipmitool raw 0x30 0x70 0x66 0x01 {hex(group_idx)} {hex(denorm_fan)}"
        p = subprocess.run(fan_speed_set_cmd.split(" "), check=True, capture_output=True)
    print(f"CPU: {cpu_temp}C, GPU: {gpu_temp}C, Fan speed: {denorm_fan}%")

def main():

    # import matplotlib.pyplot as plt
    # import numpy as np
    # plt.plot([i for i in np.arange(0, 1.2, 0.05)], [curve(i) * (FULL_FAN_SPEED - IDLE_FAN_SPEED) + IDLE_FAN_SPEED for i in np.arange(0, 1.2, 0.05)])
    # plt.ylabel("Fan speed %")
    # plt.xlabel("Normalized Temperature")
    # plt.show()
    # return

    # for i in np.arange(20, 100, 5):
    #     norm_temp = norm(i, LOWER_CPU_TEMP, UPPER_CPU_TEMP)
    #     norm_fan = curve(norm_temp)
    #     denorm_fan = int(norm_fan * (FULL_FAN_SPEED - IDLE_FAN_SPEED) + IDLE_FAN_SPEED)
    #     print(f"Temp: {i}, fans: {denorm_fan}")
    # return

    my_scheduler = sched.scheduler(time.time, time.sleep)
    my_scheduler.enter(1, 1, set_fans, (my_scheduler,))
    my_scheduler.run()


if __name__ == "__main__":
    main()