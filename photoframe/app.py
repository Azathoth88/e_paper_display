# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify
import threading
import json
import os
import time
from werkzeug.utils import secure_filename
import logging
from epaper_display import EpaperPhotoFrame

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class DisplayController:
    def __init__(self):
        self.frame = EpaperPhotoFrame()
        self.running = False
        self.thread = None
        self.config = self.load_config()
        self.frame.feed_url = self.config.get('feed_url', '')
        self.frame.enable_rotation = self.config.get('enable_rotation', True)
        self.frame.enable_resize = self.config.get('enable_resize', True)
        self.frame.display_interval = self.config.get('display_interval', 30)
        if self.config.get('running', False):
            self.start()
    
    def load_config(self):
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            config = {
                'feed_url': '',
                'enable_rotation': True,
                'enable_resize': True,
                'display_interval': 30,
                'running': False
            }
            with open('config.json', 'w') as f:
                json.dump(config, f)
            return config
    
    def save_config(self):
        config = {
            'feed_url': self.frame.feed_url,
            'enable_rotation': self.frame.enable_rotation,
            'enable_resize': self.frame.enable_resize,
            'display_interval': self.frame.display_interval,
            'running': self.running
        }
        with open('config.json', 'w') as f:
            json.dump(config, f)
    
    def start(self):
        if not self.running:
            self.running = True
            self.frame.set_running(True)
            self.thread = threading.Thread(target=self._run_display)
            self.thread.daemon = True
            self.thread.start()
            logging.info("Display-Thread gestartet")
            self.save_config()
    
    def stop(self):
        if self.running:
            self.running = False
            self.frame.set_running(False)
            if self.thread:
                self.thread.join(timeout=5)
                logging.info("Display-Thread gestoppt")
            self.save_config()
    
    def _run_display(self):
        last_run = 0
        while self.running:
            try:
                current_time = time.time()
                if current_time - last_run > self.frame.display_interval:
                    self.frame.run()
                    last_run = current_time
                time.sleep(1)  # Kurze Pause zwischen den Checks
            except Exception as e:
                logging.error(f"Fehler im Display-Thread: {e}")
                time.sleep(5)
                
            if not self.running:
                break

controller = DisplayController()

@app.route('/')
def index():
    return render_template('index.html', 
                         feed_url=controller.frame.feed_url,
                         enable_rotation=controller.frame.enable_rotation,
                         enable_resize=controller.frame.enable_resize,
                         display_interval=controller.frame.display_interval,
                         is_running=controller.running)

@app.route('/api/config', methods=['POST'])
def update_config():
    try:
        data = request.json
        controller.frame.feed_url = data.get('feed_url', controller.frame.feed_url)
        controller.frame.enable_rotation = data.get('enable_rotation', controller.frame.enable_rotation)
        controller.frame.enable_resize = data.get('enable_resize', controller.frame.enable_resize)
        controller.frame.display_interval = data.get('display_interval', controller.frame.display_interval)
        controller.save_config()
        logging.info("Konfiguration aktualisiert")
        return jsonify({'status': 'success'})
    except Exception as e:
        logging.error(f"Fehler beim Aktualisieren der Konfiguration: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/control', methods=['POST'])
def control_display():
    try:
        action = request.json.get('action')
        if action == 'start':
            controller.start()
        elif action == 'stop':
            controller.stop()
        return jsonify({'status': 'success', 'running': controller.running})
    except Exception as e:
        logging.error(f"Fehler bei der Display-Steuerung: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Keine Datei vorhanden'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'Keine Datei ausgewaehlt'})
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Status vor dem Upload merken
            previous_running_state = controller.running
            
            # Falls der Feed laeuft, stoppen
            if previous_running_state:
                controller.stop()
                logging.info("RSS Feed fuer Upload gestoppt")
            
            # Bild anzeigen
            controller.frame.display_image(filepath)
            logging.info(f"Bild {filename} angezeigt")
            
            # Feed nur wieder starten, wenn er vorher lief
            if previous_running_state:
                controller.start()
                logging.info("RSS Feed nach Upload wieder gestartet")
            
            return jsonify({'status': 'success'})
        except Exception as e:
            logging.error(f"Fehler beim Upload/Anzeigen: {e}")
            # Im Fehlerfall auch den vorherigen Zustand wiederherstellen
            if previous_running_state and not controller.running:
                controller.start()
            return jsonify({'status': 'error', 'message': str(e)})
    
    return jsonify({'status': 'error', 'message': 'Ungueltiger Dateityp'})

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)