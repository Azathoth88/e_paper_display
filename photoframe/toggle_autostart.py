#!/usr/bin/python3
import os
import sys

def get_service_content():
    return """[Unit]
Description=E-Paper Photo Frame Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/photoframe/app.py
WorkingDirectory=/home/pi/photoframe
User=pi
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

def toggle_autostart():
    service_name = "epaper-frame.service"
    service_path = f"/etc/systemd/system/{service_name}"
    
    if os.path.exists(service_path):
        print("Deaktiviere Autostart...")
        os.system(f"sudo systemctl stop {service_name}")
        os.system(f"sudo systemctl disable {service_name}")
        os.system(f"sudo rm {service_path}")
        print("Autostart deaktiviert.")
    else:
        print("Aktiviere Autostart...")
        with open("temp_service", "w") as f:
            f.write(get_service_content())
        os.system(f"sudo mv temp_service {service_path}")
        os.system(f"sudo systemctl daemon-reload")
        os.system(f"sudo systemctl enable {service_name}")
        os.system(f"sudo systemctl start {service_name}")
        print("Autostart aktiviert.")

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Dieses Script muss mit sudo ausgefuehrt werden!")
        sys.exit(1)
    toggle_autostart()
