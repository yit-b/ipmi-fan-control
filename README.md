# ipmi fan control

ipmi kinda sucks. This motherboard doesn't work with lm-sensors or pwmconfig. This script checks my CPU and Nvidia GPU temps once a second and adjusts all the fans.

## Requirements:
- python
- ipmitools
    ```
    sudo apt install ipmitools
    ```
- (optional) cuda toolkit if you want to monitor GPU temps


## Usage
Beware! If you run without installing, the script will not restart if it dies and it will not start again on boot.
```
usage: fanspeed.py [-h] [-c CONFIG] [-o OVERRIDE]

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        configuration file containing temperature and fan speed ranges
  -o OVERRIDE, --override OVERRIDE
                        Manually set the fan speed to the specified speed in percent
```

```
sudo python3 fanspeed.py --config config.yaml
```

## Install:
1. (optional) Configure your desired temperature ranges by modifying [config.yaml](config.yaml). You can do this later by making changes here and re-running the install script.
3. Run the install script. It creates a systemd service that runs the [fanspeed.py](fanspeed.py) script:
    ```
    sudo ./install.sh
    ```

## Uninstall
Beware! Before stopping the systemd service, the uninstall script will attempt to set fans at 100% to prevent system damage.
```
sudo ./uninstall.sh
```

## Default Fan Curve:
For all temperatures between the ranges defined in [config.yaml](config.yaml), fan speed is interpolated along a curve.

Feel free to use whatever curve suits your needs best, but this is the one I decided on. It's a mutation of the sigmoid function that ramps up slowly and takes off as temperatures get close to the configured upper bound.

![Default fan curve](Figure_1.png)