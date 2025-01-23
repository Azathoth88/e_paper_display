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
from urllib.parse import urlparse, parse_qs
import urllib3
import re

# Logging-Konfiguration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('epaper_display.log')
    ]
)

# Warnung fuer unsichere HTTPS-Requests unterdruecken
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Pfad-Konfiguration
picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_epd import epd7in3e

def clean_xml(xml_string):
    """Bereinigt XML-String und escaped URLs korrekt"""
    try:
        # Entferne alle Zeichen ausserhalb des gueltigen XML-Bereichs
        cleaned = ''.join(char for char in xml_string if ord(char) < 0xD800 or ord(char) > 0xDFFF)
        # Entferne bestimmte Steuerzeichen
        cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned)
        
        # Ersetze Zeilenumbrüche in description Tags durch Leerzeichen
        def clean_description(match):
            content = match.group(1)
            # Ersetze Zeilenumbrüche durch Leerzeichen
            content = re.sub(r'\s+', ' ', content)
            # Stelle sicher, dass & in URLs korrekt escaped sind
            content = content.replace('&', '&amp;')
            # Stelle die ursprünglichen HTML entities wieder her
            content = content.replace('&amp;lt;', '&lt;').replace('&amp;gt;', '&gt;')
            return f'<description>{content}</description>'
            
        cleaned = re.sub(r'<description>(.*?)</description>', clean_description, cleaned, flags=re.DOTALL)
        
        # URLs in <link> Tags finden und & durch &amp; ersetzen
        def fix_url(match):
            url = match.group(1)
            fixed_url = url.replace('&', '&amp;')
            return f'<link>{fixed_url}</link>'
            
        cleaned = re.sub(r'<link>(.*?)</link>', fix_url, cleaned)
        
        # URLs in <guid> Tags finden und & durch &amp; ersetzen
        def fix_guid(match):
            is_permalink = match.group(1)
            url = match.group(2)
            fixed_url = url.replace('&', '&amp;')
            return f'<guid isPermaLink="{is_permalink}">{fixed_url}</guid>'
            
        cleaned = re.sub(r'<guid isPermaLink="(.*?)">(.*?)</guid>', fix_guid, cleaned)
        
        # Debug: Original vs. Cleaned Content
        logging.debug("=== Original Content ===")
        logging.debug(xml_string[:1000])
        logging.debug("=== Cleaned Content ===")
        logging.debug(cleaned[:1000])
        
        return cleaned
    except Exception as e:
        logging.error(f"Fehler beim Bereinigen des XML: {e}")
        logging.error(traceback.format_exc())
        return xml_string

class SynologyImageHandler:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        logging.info("SynologyImageHandler initialisiert")
        
    def is_synology_photos_url(self, url):
        """Prueft ob die URL von der Synology Photos API stammt"""
        try:
            # & durch &amp; ersetzen für das Parsen
            url = url.replace('&amp;', '&')
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            return ('api' in query_params and 
                    query_params['api'][0] == 'SYNO.FotoTeam.Download' and
                    'method' in query_params and 
                    query_params['method'][0] == 'download')
        except Exception as e:
            logging.error(f"Fehler beim Pruefen der Synology URL: {e}")
            return False

    def extract_image_url(self, item):
        """Extrahiert die Bild-URL aus einem Feed-Item"""
        try:
            # Pruefe zuerst den Link
            link = item.find('link')
            if link is not None and link.text:
                url = link.text.replace('&amp;', '&')  # XML-Escaping rückgängig machen
                if self.is_synology_photos_url(url):
                    logging.info("Synology URL in Link gefunden")
                    return url
                    
            # Pruefe dann die Beschreibung
            description = item.find('description')
            if description is not None and description.text:
                try:
                    # Bereinige die description vor dem Parsen
                    desc_text = description.text
                    # Ersetze &amp; zurück zu & in URLs, aber behalte &lt; und &gt;
                    desc_text = re.sub(r'&amp;(?!lt;|gt;)', '&', desc_text)
                    logging.debug(f"Bereinigte Description: {desc_text}")
                    
                    desc_root = ET.fromstring(desc_text)
                    url_elem = desc_root.find('.//url')
                    if url_elem is not None and url_elem.text:
                        url = url_elem.text.replace('&amp;', '&')
                        if self.is_synology_photos_url(url):
                            logging.info("Synology URL in Beschreibung gefunden")
                            return url
                except ET.ParseError as e:
                    logging.error(f"Fehler beim Parsen der Beschreibung: {e}")
                    logging.error(f"Problematische Description: {desc_text}")
                    
        except Exception as e:
            logging.error(f"Fehler beim Extrahieren der URL: {e}")
            logging.error(traceback.format_exc())
            
        return None

    def download_image(self, url, timeout=30):
        """Laedt ein Bild von der Synology Photos API herunter"""
        try:
            logging.info(f"Versuche Download von Synology URL: {url}")
            
            # Request mit angepassten Headern
            headers = {
                'Accept': 'image/jpeg, image/png, image/*',
                'User-Agent': 'Mozilla/5.0 PhotoFrame',
                'Connection': 'keep-alive'
            }
            
            response = self.session.get(url, headers=headers, timeout=timeout)
            
            # Debug-Informationen
            logging.info("=== Synology Response Debug ===")
            logging.info(f"Status Code: {response.status_code}")
            logging.info(f"Headers: {dict(response.headers)}")
            logging.info(f"Content Type: {response.headers.get('content-type', 'Not found')}")
            logging.info(f"Content Length: {len(response.content)}")
            
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                logging.error(f"Unerwarteter Content-Type: {content_type}")
                if response.status_code != 200:
                    logging.error(f"Error Response: {response.text[:500]}")
                raise ValueError(f"Unerwarteter Content-Type: {content_type}")
                
            return response.content
            
        except Exception as e:
            logging.error(f"Fehler beim Download von Synology: {e}")
            logging.error(traceback.format_exc())
            raise

class EpaperPhotoFrame:
    def __init__(self):
        logging.info("Initialisiere E-Paper Photoframe")
        try:
            self.epd = epd7in3e.EPD()
            self.epd.init()
            self.epd.Clear()
            logging.info("E-Paper Display initialisiert und geloescht")
            
            self.enable_resize = True
            self.enable_rotation = True
            self.display_interval = 30
            self.feed_url = ""
            self.running = False
            self.last_url = None
            self.synology_handler = SynologyImageHandler()
        except Exception as e:
            logging.error(f"Fehler bei der Initialisierung: {e}")
            raise
    
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
                
                # Debug: Original Feed Content
                content = response.content.decode('utf-8', errors='replace')
                logging.debug("=== Original Feed Content ===")
                logging.debug(content[:1000])
                
                # XML bereinigen
                content = clean_xml(content)
                logging.debug("=== Cleaned Feed Content ===")
                logging.debug(content[:1000])
                
                try:
                    root = ET.fromstring(content)
                    
                    urls = []
                    for item in root.findall('.//item'):
                        # Versuche zuerst die Synology-spezifische URL zu extrahieren
                        url = self.synology_handler.extract_image_url(item)
                        if url:
                            urls.append(url)
                        else:
                            # Fallback auf den normalen Link
                            link = item.find('link')
                            if link is not None and link.text:
                                urls.append(link.text.replace('&amp;', '&'))
                    
                    logging.info(f"Gefundene Bild-URLs: {len(urls)}")
                    for url in urls:
                        logging.info(f"URL gefunden: {url}")
                    return urls
                    
                except ET.ParseError as e:
                    logging.error(f"XML Parse Error: {str(e)}")
                    # Zeige die problematische Zeile
                    lines = content.splitlines()
                    if len(lines) >= e.position[0]:
                        problem_line = lines[e.position[0] - 1]
                        logging.error(f"Problematic line {e.position[0]}:")
                        logging.error(problem_line)
                        logging.error(" " * (e.position[1] - 1) + "^")
                    raise
                    
            except Exception as e:
                if attempt < attempts - 1:
                    logging.warning(f"Versuch {attempt + 1} fehlgeschlagen, versuche erneut...")
                    time.sleep(5)
                else:
                    logging.error(f"Fehler beim Abrufen des Feeds: {e}")
                    logging.error(traceback.format_exc())
        return []

    def display_image(self, image_url, timeout=30):
        logging.info(f"Lade Bild: {image_url}")
        try:
            if os.path.isfile(image_url):
                image = Image.open(image_url)
                logging.info("Lokale Datei geladen")
            else:
                if self.synology_handler.is_synology_photos_url(image_url):
                    logging.info("Verarbeite Synology Photos URL")
                    image_data = self.synology_handler.download_image(image_url, timeout)
                    image = Image.open(BytesIO(image_data))
                    logging.info("Synology Bild erfolgreich geladen")
                else:
                    logging.info("Verwende Standard Download")
                    response = requests.get(image_url, timeout=timeout)
                    response.raise_for_status()
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
            logging.error(traceback.format_exc())
            return False

    def _display_buffer(self, image):
        try:
            self.epd.display(self.epd.getbuffer(image))
        except Exception as e:
            logging.error(f"Fehler beim Anzeigen des Buffers: {e}")
            logging.error(traceback.format_exc())

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
            logging.error(traceback.format_exc())
            time.sleep(5)

# Test-Code wenn die Datei direkt ausgefuehrt wird
if __name__ == "__main__":
    try:
        logging.info("Starte E-Paper Display Test")
        frame = EpaperPhotoFrame()
        logging.info("E-Paper Display erfolgreich initialisiert")
        
        # Test mit einer lokalen Datei, falls vorhanden
        test_image = "test.jpg"
        if os.path.exists(test_image):
            logging.info(f"Teste Anzeige mit lokaler Datei: {test_image}")
            frame.display_image(test_image)
        
        # Optional: Test mit Feed
        #frame.feed_url = "IHRE-TEST-URL"
        #frame.set_running(True)
        #frame.run()
        
        logging.info("Test abgeschlossen")
        
    except Exception as e:
        logging.error(f"Fehler beim Testen: {e}")
        logging.error(traceback.format_exc())
