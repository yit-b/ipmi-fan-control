systemctl stop customfancontrol.service
cp customfancontrol.service /etc/systemd/system/customfancontrol.service && \
systemctl daemon-reload && \
systemctl start customfancontrol.service && \
systemctl status customfancontrol.service