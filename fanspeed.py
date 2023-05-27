import subprocess
import time
import json
import sched


MAX_CPU_TEMP = 80.0
MIN_CPU_TEMP = 50.0

MAX_GPU_TEMP = 80.0
MIN_GPU_TEMP = 50.0

MAX_FAN_SPEED = 64
MIN_FAN_SPEED = 25


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

    norm_temp = min((max(cpu_temp, MIN_CPU_TEMP) - MIN_CPU_TEMP) / (MAX_CPU_TEMP - MIN_CPU_TEMP), 1.0)
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
    cpu_temp_norm = norm(cpu_temp, MIN_CPU_TEMP, MAX_CPU_TEMP)
    gpu_temp = get_gpu_temp()
    gpu_temp_norm = norm(gpu_temp, MIN_GPU_TEMP, MAX_GPU_TEMP)
    
    norm_temp = max(cpu_temp_norm, gpu_temp_norm)
    speed_setting = int(norm_temp * (MAX_FAN_SPEED - MIN_FAN_SPEED) + MIN_FAN_SPEED)

    for group_idx in range(0, 2):
        fan_speed_set_cmd = f"ipmitool raw 0x30 0x70 0x66 0x01 0x{group_idx} 0x{speed_setting}"
        p = subprocess.run(fan_speed_set_cmd.split(" "), check=True, capture_output=True)
    print(f"CPU: {cpu_temp}C, GPU: {gpu_temp}C, Fan speed: {speed_setting}%")

def main():
    my_scheduler = sched.scheduler(time.time, time.sleep)
    my_scheduler.enter(1, 1, set_fans, (my_scheduler,))
    my_scheduler.run()


if __name__ == "__main__":
    main()