# E-paper display control

Eine einfache, webbasierte Software zur Anzeige von Bildern aus einem RSS-Feeds auf einem RaspberryPi und einem e-Ink-Display.
![image](https://github.com/user-attachments/assets/3992d382-a7c0-49ac-8e02-60ed7cf0a7af)

# Features
- Darstellung von Bildern auf e-Ink-Display
-   Abruf der Bilder über RSS-Feed oder Bereitstellung über einfachen Upload
- Konfigurierbarer Bildwechsel-Intervall (aktualisert alle n-Sekunden das Bild) 
- Automatische Bildrotation und -anpassung
- Start/Stop-Steuerung des RSS-Feeds

# Hardware
- RaspberryPi, ab Version 3
- Raspberry Pi - offizielles Netzteil für Raspberry Pi 4 Model B, USB-C, 5.1V, 3A weiß
- Adapter USB C auf Micro
- SD-Karte

## Installation
1. Raspberry Pi Imager herunterladen und installieren https://www.raspberrypi.com/software/
2. Raspberri Pi OS (Empfehlung: Raspberry Pi OS Lite (64 Bit)) auf SD-Karte schreiben.
Wichtig: SSH-Zugriff aktivieren
![image](https://github.com/user-attachments/assets/a5599abd-8c44-4f04-8971-a423e5ebd253)
3. Updates  durchführen
```
sudo apt update && apt upgrade
```
4. SPI Interface aktivieren (3. Interfacing Options -> I4 SPI -> Yes Enable SPI interface)
```
sudo raspi-config
```
5. Reboot
```
sudo reboot
```
7. Prüfen, ob firmware/config.txt korrekt beschrieben und ob dtparam=spi=on aktiviert ist
```
nano /boot/firmware/config.txt
```
![image](https://github.com/user-attachments/assets/a97e0484-e8ad-4f15-9963-ac2e0024c390)
7b. Bei 13.3 Zoll Display zusätzlich config.txt ergänzen:
```
sudo nano /boot/firmware/config.txt
```
Am Ende der Datei ergänzen
```
gpio=7=op,dl
gpio=8=op,dl
```

8. Python Bibliotheken & Flask installieren
```
sudo apt-get install python3-pip
sudo apt-get install python3-pil
sudo apt-get install python3-numpy
sudo apt install python3-spidev
sudo apt-get install python3-flask
```

9. photoframe-Verzeichnis kopieren
10. Test durchführen
```
cd photoframe
python epaper_display.py
```

11. Autostart installieren
```
sudo python toggle_autostart.py
```
![image](https://github.com/user-attachments/assets/5dc9a641-764d-41c9-846d-d3b8a3d532e7)

### Service starten / stoppen
```
sudo systemctl start epaper-frame.service
sudo systemctl stop epaper-frame.service
```
