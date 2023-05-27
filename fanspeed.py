import subprocess
import time
import json
import sched
import math

UPPER_CPU_TEMP = 80.0
LOWER_CPU_TEMP = 50.0

UPPER_GPU_TEMP = 80.0
LOWER_GPU_TEMP = 50.0

FULL_FAN_SPEED = 100
IDLE_FAN_SPEED = 37

def curve(temperature):
    # Generalised logistic function
    # Slowly ramp fan speed as lower temperature is crossed but quickly increase after
    A = IDLE_FAN_SPEED
    K = FULL_FAN_SPEED
    C = 1
    Q = 1.65
    B = 0.5
    v = 3.3
    fan_speed = A + ((K-A) / (C+Q * math.exp(-B * temperature + 40) ) ** (1 / v))
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
    return cpu_temp

def get_gpu_temp():
    gpu_temp_check_cmd = "nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader"
    p = subprocess.run(gpu_temp_check_cmd.split(" "), check=True, capture_output=True)
    gpu_temp = int(p.stdout.decode("utf-8"))
    return gpu_temp

def set_fans(scheduler):
    scheduler.enter(1, 1, set_fans, (scheduler,))

    # cpu_temp_norm = get_cpu_temp()
    cpu_temp = get_cpu_temp_json()
    # cpu_temp_norm = norm(cpu_temp, LOWER_CPU_TEMP, UPPER_CPU_TEMP)
    gpu_temp = get_gpu_temp()
    # gpu_temp_norm = norm(gpu_temp, LOWER_GPU_TEMP, UPPER_GPU_TEMP)

    speed_setting = int(curve(cpu_temp))
    
    # norm_temp = max(cpu_temp_norm, gpu_temp_norm)
    # speed_setting = int(norm_temp * (FULL_FAN_SPEED - IDLE_FAN_SPEED) + IDLE_FAN_SPEED)

    for group_idx in range(0, 2):
        fan_speed_set_cmd = f"ipmitool raw 0x30 0x70 0x66 0x01 {hex(group_idx)} {hex(speed_setting)}"
        p = subprocess.run(fan_speed_set_cmd.split(" "), check=True, capture_output=True)
    print(f"CPU: {cpu_temp}C, GPU: {gpu_temp}C, Fan speed: {speed_setting}%")

def main():

    # import matplotlib.pyplot as plt
    # plt.plot([i for i in range(20, 120, 1)], [int(curve(i)) for i in range(20, 120, 1)])
    # plt.ylabel("Fan speed %")
    # plt.xlabel("CPU Temperature C")
    # plt.show()
    # return

    # for i in range(20, 90, 1):
    #     print(f"Temp: {i}, fans: {round(curve(i))}")
    # return

    my_scheduler = sched.scheduler(time.time, time.sleep)
    my_scheduler.enter(1, 1, set_fans, (my_scheduler,))
    my_scheduler.run()


if __name__ == "__main__":
    main()