# e_paper_display
## E-paper display control

Eine einfache, webbasierte Software zur Anzeige von Bildern aus einem RSS-Feeds auf einem RaspberryPi und einem e-Ink-Display.
![image](https://github.com/user-attachments/assets/3992d382-a7c0-49ac-8e02-60ed7cf0a7af)

### Features
- Darstellung von Bildern auf e-Ink-Display
-   Abruf der Bilder über RSS-Feed oder Bereitstellung über einfachen Upload
- Konfigurierbarer Bildwechsel-Intervall (aktualisert alle n-Sekunden das Bild) 
- Automatische Bildrotation und -anpassung
- Start/Stop-Steuerung des RSS-Feeds

### Hardware
- RaspberryPi, ab Version 3
- Raspberry Pi - offizielles Netzteil für Raspberry Pi 4 Model B, USB-C, 5.1V, 3A weiß
- Adapter USB C auf Micro
- SD-Karte

### Service starten / stoppen
```
sudo systemctl start epaper-frame.service
sudo systemctl stop epaper-frame.service
```
