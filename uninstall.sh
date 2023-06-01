systemctl stop customfancontrol.service
systemctl status customfancontrol.service
systemctl disable customfancontrol.service
systemctl daemon-reload

python3 /usr/local/bin/fanspeed.py --override 100

rm /etc/systemd/system/customfancontrol.service
rm /usr/local/bin/fanspeed.py
rm /etc/fanspeed_config.yaml

