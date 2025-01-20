#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import os
import requests
import xml.etree.ElementTree as ET
from io import BytesIO
import logging
import time
from PIL import Image
import traceback
import threading

picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_epd import epd7in3e

class EpaperPhotoFrame:
    def __init__(self):
        logging.info("Initialisiere E-Paper Photoframe")
        self.epd = epd7in3e.EPD()
        self.epd.init()
        self.epd.Clear()
        
        self.enable_resize = True
        self.enable_rotation = True
        self.display_interval = 30
        self.feed_url = ""
        self.running = False
        self.last_url = None
    
    def set_running(self, state):
        """Erlaubt das Setzen des Running-Status von aussen"""
        self.running = state
        logging.info(f"Frame running status: {state}")
    
    def get_image_urls(self):
        if not self.feed_url:
            logging.warning("Keine Feed-URL konfiguriert")
            return []
            
        logging.info(f"Rufe Feed ab: {self.feed_url}")
        attempts = 3
        for attempt in range(attempts):
            try:
                response = requests.get(self.feed_url, timeout=30)
                logging.info(f"Feed-Status: {response.status_code}")
                root = ET.fromstring(response.content)
                
                urls = []
                for item in root.findall('.//item'):
                    link = item.find('link').text
                    urls.append(link)
                
                logging.info(f"Gefundene Bild-URLs: {len(urls)}")
                return urls
            except Exception as e:
                if attempt < attempts - 1:
                    logging.warning(f"Versuch {attempt + 1} fehlgeschlagen, versuche erneut...")
                    time.sleep(5)
                else:
                    logging.error(f"Fehler beim Abrufen des Feeds: {e}")
        return []

    def display_image(self, image_url, timeout=30):
        logging.info(f"Lade Bild: {image_url}")
        try:
            if os.path.isfile(image_url):
                image = Image.open(image_url)
            else:
                response = requests.get(image_url, timeout=timeout)
                image = Image.open(BytesIO(response.content))
            
            logging.info(f"Urspruengliche Bildgroesse: {image.size}")
            
            # Wenn PNG mit Transparenz, weissen Hintergrund hinzufuegen
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                bg = Image.new('RGB', image.size, 'white')
                if image.mode == 'P':
                    image = image.convert('RGBA')
                bg.paste(image, (0, 0), image)
                image = bg
            
            if self.enable_resize:
                image = self.resize_image(image)
                logging.info(f"Angepasste Bildgroesse: {image.size}")
            
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            display_thread = threading.Thread(target=self._display_buffer, args=(image,))
            display_thread.start()
            display_thread.join(timeout=timeout)
            
            if display_thread.is_alive():
                logging.error("Timeout bei der Bildanzeige")
                return False
                
            logging.info("Bild erfolgreich angezeigt")
            return True
            
        except Exception as e:
            logging.error(f"Fehler beim Anzeigen des Bildes: {e}")
            return False

    def _display_buffer(self, image):
        try:
            self.epd.display(self.epd.getbuffer(image))
        except Exception as e:
            logging.error(f"Fehler beim Anzeigen des Buffers: {e}")

    def resize_image(self, image):
        orig_width, orig_height = image.size
        is_portrait = orig_height > orig_width
        
        display_width = self.epd.width
        display_height = self.epd.height
        
        if self.enable_rotation and is_portrait:
            image = image.rotate(90, expand=True)
            orig_width, orig_height = image.size
        
        image_ratio = orig_width / orig_height
        display_ratio = display_width / display_height
        
        if display_ratio > image_ratio:
            height = display_height
            width = int(height * image_ratio)
        else:
            width = display_width
            height = int(width / image_ratio)
            
        image = image.resize((width, height), Image.LANCZOS)
        
        new_image = Image.new('RGB', (display_width, display_height), self.epd.WHITE)
        paste_x = (display_width - width) // 2
        paste_y = (display_height - height) // 2
        new_image.paste(image, (paste_x, paste_y))
        
        return new_image

    def run(self):
        """Eine einzelne Iteration des Feed-Checks durchfuehren"""
        if not self.running:
            logging.info("Frame ist nicht im running state")
            return

        try:
            image_urls = self.get_image_urls()
            
            if image_urls and len(image_urls) > 0:
                url = image_urls[0]
                if url != self.last_url:  # Nur anzeigen wenn es ein neues Bild ist
                    if self.display_image(url):
                        logging.info(f"Bild erfolgreich angezeigt: {url}")
                        self.last_url = url
                    else:
                        logging.warning("Fehler beim Anzeigen des Bildes")
                else:
                    logging.info("Bild bereits angezeigt, ueberspringe")
                
        except Exception as e:
            logging.error(f"Fehler in der Frame-Hauptschleife: {e}")
            time.sleep(5)