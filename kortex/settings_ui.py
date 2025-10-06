import yaml
import os
import json
import math
import requests
import zipfile
import shutil
import ollama
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, 
                             QStackedWidget, QPushButton, QComboBox, QSplitter,
                             QListWidgetItem, QFrame, QProgressBar, QGroupBox,
                             QLineEdit, QCheckBox, QSpinBox)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QColor

STYLESHEET = """
QWidget {
    background-color: #ffffff;
    font-family: "Segoe UI", "SF Pro Text", "Arial", sans-serif;
    color: #1d1d1f;
}
QListWidget#navList {
    background-color: #f2f2f7;
    border: none;
    outline: 0;
    padding-top: 15px;
    border-right: 1px solid #e0e0e0;
}
QListWidget#navList::item {
    padding: 12px 20px;
    border-radius: 8px;
    margin: 4px 10px;
    color: #333;
}
QListWidget#navList::item:selected {
    background-color: #007aff;
    color: white;
}
QListWidget#navList::item:hover:!selected {
    background-color: #dcdce1;
}
QLabel#titleLabel {
    font-size: 24px;
    font-weight: 600;
    padding-bottom: 10px;
    margin-left: 5px;
}
QGroupBox {
    background-color: #f7f7f7;
    border: none;
    border-radius: 12px;
    margin-top: 1em;
    padding: 20px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 10px;
    margin-left: 10px;
    font-size: 16px;
    font-weight: 600;
}
QPushButton {
    background-color: #007aff;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 500;
}
QPushButton:hover { background-color: #005ecb; }
QPushButton:disabled { background-color: #e5e5ea; color: #8e8e93; }
QComboBox, QSpinBox {
    border: 1px solid #dcdce1;
    border-radius: 8px;
    padding: 8px 12px;
    background-color: #ffffff;
    font-size: 14px;
}
QComboBox:hover, QSpinBox:hover { border-color: #b0b0b0; }
QComboBox::drop-down { border: none; }
QLineEdit {
    border: 1px solid #dcdce1;
    border-radius: 8px;
    padding: 8px 12px;
    background-color: #ffffff;
    font-size: 14px;
}
QLineEdit:focus { border-color: #007aff; }
QListWidget {
    border-radius: 8px;
    border: 1px solid #e0e0e0;
}
QProgressBar {
    height: 12px;
    border: none;
    border-radius: 6px;
    text-align: center;
    background-color: #e5e5ea;
    color: #1d1d1f;
}
QProgressBar::chunk {
    background-color: #007aff;
    border-radius: 6px;
}
QLabel[status="neutral"] { color: #6e6e73; }
QLabel[status="error"]   { color: #d93025; }
QLabel[status="success"] { color: #34c759; }
"""

class VoskModelDownloader(QThread):
    progress = pyqtSignal(int); finished = pyqtSignal(bool, str)
    def __init__(self, url, dest_folder, model_name):
        super().__init__(); self.url = url; self.dest_folder = dest_folder; self.model_name = model_name
    def run(self):
        try:
            os.makedirs(self.dest_folder, exist_ok=True); zip_path = os.path.join(self.dest_folder, f"{self.model_name}.zip")
            with requests.get(self.url, stream=True) as r:
                r.raise_for_status(); total_size = int(r.headers.get('content-length', 0)); downloaded_size = 0
                with open(zip_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk); downloaded_size += len(chunk)
                        if total_size > 0: self.progress.emit(int(100 * downloaded_size / total_size))
            self.progress.emit(100); self.finished.emit(True, "Download complete. Unzipping...")
            with zipfile.ZipFile(zip_path, 'r') as z: z.extractall(self.dest_folder)
            extracted_path = os.path.join(self.dest_folder, self.model_name)
            if not os.path.exists(extracted_path):
                 extracted_folders = [d for d in os.listdir(self.dest_folder) if os.path.isdir(os.path.join(self.dest_folder, d))]
                 if extracted_folders: os.rename(os.path.join(self.dest_folder, extracted_folders[0]), extracted_path)
            os.remove(zip_path)
            self.finished.emit(True, f"Model '{self.model_name}' installed successfully.")
        except Exception as e: self.finished.emit(False, f"Error: {e}")

class PiperVoiceDownloader(QThread):
    progress = pyqtSignal(int); finished = pyqtSignal(bool, str)
    def __init__(self, files_to_download, dest_folder):
        super().__init__(); self.files_to_download = files_to_download; self.dest_folder = dest_folder
    def run(self):
        try:
            os.makedirs(self.dest_folder, exist_ok=True); total_size = sum(f['size'] for f in self.files_to_download); downloaded_size = 0
            for file_info in self.files_to_download:
                with requests.get(file_info['url'], stream=True) as r:
                    r.raise_for_status()
                    with open(file_info['path'], 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk); downloaded_size += len(chunk)
                            if total_size > 0: self.progress.emit(int(100 * downloaded_size / total_size))
            self.finished.emit(True, "Voice installed successfully.")
        except Exception as e: self.finished.emit(False, f"Error: {e}")

class SettingsWindow(QWidget):
    def __init__(self, config_path="kortex/config.yaml"):
        super().__init__(); self.config_path = config_path; self.config = self.load_config()
        self.vosk_models_data = self.load_json("models/models.json"); self.piper_voices_data = self.load_json("tools/piper/voices.json")
        self.setWindowTitle("Kortex Settings"); self.setMinimumSize(800, 600); self.setStyleSheet(STYLESHEET)
        
        main_layout = QHBoxLayout(self); main_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal); main_layout.addWidget(splitter)
        self.nav_list = QListWidget(); self.nav_list.setObjectName("navList"); self.nav_list.setMaximumWidth(240); self.nav_list.setIconSize(QSize(20, 20))
        splitter.addWidget(self.nav_list)
        self.pages_widget = QStackedWidget(); splitter.addWidget(self.pages_widget); splitter.setSizes([240, 560])

        self.init_ui(); self.nav_list.currentRowChanged.connect(self.pages_widget.setCurrentIndex); self.nav_list.setCurrentRow(0)

    def init_ui(self):
        self.pages_widget.addWidget(self.create_stt_page()); self.pages_widget.addWidget(self.create_llm_page()); self.pages_widget.addWidget(self.create_tts_page())
        self.pages_widget.addWidget(self.create_services_page()); self.pages_widget.addWidget(self.create_accounts_page())

        self.nav_list.addItem(QListWidgetItem(self._create_icon("#007aff"), "Speech-to-Text")); self.nav_list.addItem(QListWidgetItem(self._create_icon("#34c759"), "Language Model")); self.nav_list.addItem(QListWidgetItem(self._create_icon("#ff9500"), "Text-to-Speech"))
        self.nav_list.addItem(QListWidgetItem(self._create_icon("#8e8e93"), "Services")); self.nav_list.addItem(QListWidgetItem(self._create_icon("#5856d6"), "Accounts"))

        self.update_stt_page_state(); self.populate_ollama_models(); self.update_tts_page_state(); self.update_services_page_state(); self.update_accounts_page_state()

    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config if isinstance(config, dict) else {}
        except (FileNotFoundError, yaml.YAMLError) as e:
            print(f"CRITICAL: Could not load or parse config file '{self.config_path}'. Using an empty configuration. Any saves will fail until this is resolved. Error: {e}")
            return {}

    def load_json(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}

    def save_config(self):
        if not isinstance(self.config, dict) or 'ollama_model' not in self.config:
            print("CRITICAL: Config is incomplete or wasn't loaded correctly. Aborting save to prevent data loss.")
            self._set_status_label(self.services_status_label, "Error: Config not loaded, save aborted.", "error")
            self._set_status_label(self.accounts_status_label, "Error: Config not loaded, save aborted.", "error")
            return
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)

    def _set_status_label(self, label, text, status="neutral"):
        label.setText(text)
        label.setProperty("status", status)
        label.style().unpolish(label)
        label.style().polish(label)

    def _create_icon(self, color):
        pixmap = QPixmap(24, 24); pixmap.fill(Qt.transparent); painter = QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing); painter.setBrush(QColor(color)); painter.setPen(Qt.NoPen); painter.drawEllipse(2, 2, 20, 20); painter.end()
        return QIcon(pixmap)
    def _format_bytes(self, size_bytes):
        if size_bytes <= 0: return "0B"; size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.log(size_bytes, 1024)); p = math.pow(1024, i); s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    def create_stt_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setAlignment(Qt.AlignTop); layout.setContentsMargins(30, 25, 30, 25); layout.setSpacing(20)
        title = QLabel("Speech-to-Text Models (Vosk)"); title.setObjectName("titleLabel")
        active_group = QGroupBox("Active Model"); active_layout = QHBoxLayout(active_group)
        self.stt_model_combo = QComboBox(); self.stt_model_combo.currentIndexChanged.connect(self.set_active_stt_model)
        self.stt_delete_button = QPushButton("Delete"); self.stt_delete_button.clicked.connect(self.delete_stt_model)
        active_layout.addWidget(self.stt_model_combo); active_layout.addWidget(self.stt_delete_button)
        available_group = QGroupBox("Available Models for Download"); available_layout = QVBoxLayout(available_group)
        self.vosk_model_list = QListWidget(); self.vosk_model_list.itemSelectionChanged.connect(self.update_stt_details)
        self.vosk_desc_label = QLabel("Description: Select a model to see details."); self.vosk_desc_label.setWordWrap(True)
        self.vosk_size_label = QLabel("Size: ")
        self.stt_download_button = QPushButton("Download Model"); self.stt_download_button.clicked.connect(self.start_stt_download)
        self.stt_download_progress = QProgressBar(); self.stt_download_progress.hide()
        available_layout.addWidget(self.vosk_model_list); available_layout.addWidget(self.vosk_desc_label); available_layout.addWidget(self.vosk_size_label); available_layout.addWidget(self.stt_download_button); available_layout.addWidget(self.stt_download_progress)
        self.stt_status_label = QLabel(""); self.stt_status_label.setProperty("status", "neutral")
        layout.addWidget(title); layout.addWidget(active_group); layout.addWidget(available_group); layout.addWidget(self.stt_status_label)
        return page

    def update_stt_page_state(self):
        self.vosk_model_list.clear()
        for lang, models in self.vosk_models_data.items():
            lang_item = QListWidgetItem(lang); lang_item.setFont(QFont("Segoe UI", 10, QFont.Bold)); lang_item.setFlags(lang_item.flags() & ~Qt.ItemIsSelectable); self.vosk_model_list.addItem(lang_item)
            for model in models: list_item = QListWidgetItem(f"  {model['name']}"); list_item.setData(Qt.UserRole, model); self.vosk_model_list.addItem(list_item)
        self.stt_model_combo.clear(); models_dir = "models"
        if not os.path.exists(models_dir): os.makedirs(models_dir)
        downloaded = [d for d in os.listdir(models_dir) if os.path.isdir(os.path.join(models_dir, d))]
        self.stt_model_combo.addItems(downloaded)
        current_model = os.path.basename(self.config.get('stt_model_path', ''))
        if current_model in downloaded: self.stt_model_combo.setCurrentText(current_model)
        self.stt_delete_button.setEnabled(bool(downloaded))
        self.update_stt_details()

    def update_stt_details(self):
        selected = self.vosk_model_list.selectedItems()
        if not selected or not selected[0].data(Qt.UserRole): self.stt_download_button.setEnabled(False); return
        model_data = selected[0].data(Qt.UserRole); self.vosk_desc_label.setText(f"Description: {model_data['desc']}"); self.vosk_size_label.setText(f"Size: {model_data['size']}")
        is_downloaded = os.path.exists(os.path.join("models", model_data['name'])); self.stt_download_button.setEnabled(not is_downloaded); self.stt_download_button.setText("Model Installed" if is_downloaded else "Download Model")

    def start_stt_download(self):
        model_data = self.vosk_model_list.selectedItems()[0].data(Qt.UserRole); url = f"https://alphacephei.com/vosk/models/{model_data['url_name']}.zip"
        self.stt_download_progress.show(); self.stt_download_progress.setValue(0); self._set_status_label(self.stt_status_label, f"Downloading {model_data['name']}...")
        self.stt_download_button.setEnabled(False)
        self.stt_worker = VoskModelDownloader(url, "models", model_data['name']); self.stt_worker.progress.connect(self.stt_download_progress.setValue); self.stt_worker.finished.connect(self.on_stt_download_finished); self.stt_worker.start()

    def on_stt_download_finished(self, success, message):
        self._set_status_label(self.stt_status_label, message, "success" if success else "error")
        self.stt_download_progress.hide();
        if success: self.update_stt_page_state()

    def set_active_stt_model(self):
        self.config['stt_model_path'] = f"models/{self.stt_model_combo.currentText()}"; self.save_config()
        self._set_status_label(self.stt_status_label, "Settings saved. Restart Kortex to apply.", "success")

    def delete_stt_model(self):
        model_to_delete = self.stt_model_combo.currentText()
        if not model_to_delete: return
        if model_to_delete == os.path.basename(self.config.get('stt_model_path', '')):
            self._set_status_label(self.stt_status_label, "Cannot delete the currently active model.", "error")
            return
        try:
            shutil.rmtree(os.path.join("models", model_to_delete))
            self._set_status_label(self.stt_status_label, f"Model '{model_to_delete}' deleted.", "success")
            self.update_stt_page_state()
        except Exception as e:
            self._set_status_label(self.stt_status_label, f"Error deleting model: {e}", "error")

    def create_llm_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setAlignment(Qt.AlignTop); layout.setContentsMargins(30, 25, 30, 25); layout.setSpacing(20)
        title = QLabel("Language Model (Ollama)"); title.setObjectName("titleLabel")
        group = QGroupBox("Active Model"); group_layout = QHBoxLayout(group)
        self.ollama_model_combo = QComboBox(); self.ollama_model_combo.currentIndexChanged.connect(self.save_ollama_selection)
        self.llm_status_label = QLabel(""); self.llm_status_label.setProperty("status", "neutral")
        group_layout.addWidget(QLabel("Select Model:")); group_layout.addWidget(self.ollama_model_combo)
        layout.addWidget(title); layout.addWidget(group); layout.addWidget(self.llm_status_label)
        return page

    def populate_ollama_models(self):
        try:
            client = ollama.Client(timeout=5); models_data = client.list().get('models', []); model_names = [m.get('name') for m in models_data if m.get('name')]
            self.ollama_model_combo.clear(); self.ollama_model_combo.addItems(model_names)
            current_model = self.config.get('ollama_model')
            if current_model in model_names: self.ollama_model_combo.setCurrentText(current_model)
            self._set_status_label(self.llm_status_label, "Ollama connection successful.", "success")
        except requests.exceptions.ConnectionError:
            self._set_status_label(self.llm_status_label, "Could not connect to Ollama. Please ensure it is running.", "error")
        except Exception as e:
            self._set_status_label(self.llm_status_label, f"An Ollama error occurred: {e}", "error")

    def save_ollama_selection(self):
        self.config['ollama_model'] = self.ollama_model_combo.currentText(); self.save_config()
        self._set_status_label(self.llm_status_label, "Active LLM updated. Restart Kortex to apply.", "success")

    def create_tts_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setAlignment(Qt.AlignTop); layout.setContentsMargins(30, 25, 30, 25); layout.setSpacing(20)
        title = QLabel("Text-to-Speech Voices (Piper)"); title.setObjectName("titleLabel")
        active_group = QGroupBox("Default Voice"); active_layout = QHBoxLayout(active_group)
        self.tts_voice_combo = QComboBox(); self.tts_voice_combo.currentIndexChanged.connect(self.set_active_tts_voice)
        self.tts_delete_button = QPushButton("Delete"); self.tts_delete_button.clicked.connect(self.delete_tts_voice)
        active_layout.addWidget(self.tts_voice_combo); active_layout.addWidget(self.tts_delete_button)
        available_group = QGroupBox("Available Voices for Download"); available_layout = QVBoxLayout(available_group)
        self.piper_voice_list = QListWidget(); self.piper_voice_list.itemSelectionChanged.connect(self.update_tts_details)
        self.piper_desc_label = QLabel("Description: Select a voice to see details."); self.piper_desc_label.setWordWrap(True)
        self.piper_size_label = QLabel("Size: ")
        self.tts_download_button = QPushButton("Download Voice"); self.tts_download_button.clicked.connect(self.start_tts_download)
        self.tts_download_progress = QProgressBar(); self.tts_download_progress.hide()
        available_layout.addWidget(self.piper_voice_list); available_layout.addWidget(self.piper_desc_label); available_layout.addWidget(self.piper_size_label); available_layout.addWidget(self.tts_download_button); available_layout.addWidget(self.tts_download_progress)
        self.tts_status_label = QLabel(""); self.tts_status_label.setProperty("status", "neutral")
        layout.addWidget(title); layout.addWidget(active_group); layout.addWidget(available_group); layout.addWidget(self.tts_status_label)
        return page

    def update_tts_page_state(self):
        self.piper_voice_list.clear(); voices_by_lang = {}
        for key, data in self.piper_voices_data.items():
            lang = data['language']['name_english']
            if lang not in voices_by_lang: voices_by_lang[lang] = []
            voices_by_lang[lang].append(data)
        for lang in sorted(voices_by_lang.keys()):
            lang_item = QListWidgetItem(lang); lang_item.setFont(QFont("Segoe UI", 10, QFont.Bold)); lang_item.setFlags(lang_item.flags() & ~Qt.ItemIsSelectable); self.piper_voice_list.addItem(lang_item)
            for voice_data in sorted(voices_by_lang[lang], key=lambda x: x['name']):
                item_text = f"  {voice_data['name']} ({voice_data['quality']})"; list_item = QListWidgetItem(item_text); list_item.setData(Qt.UserRole, voice_data); self.piper_voice_list.addItem(list_item)
        
        tts_config = self.config.get('tts', {})
        downloaded = tts_config.get('voices', {}).keys()
        current_voice = tts_config.get('default_voice', '')
        
        self.tts_voice_combo.clear(); self.tts_voice_combo.addItems(downloaded)
        if current_voice in downloaded: self.tts_voice_combo.setCurrentText(current_voice)
        self.tts_delete_button.setEnabled(bool(list(downloaded)))
        self.update_tts_details()

    def update_tts_details(self):
        selected = self.piper_voice_list.selectedItems()
        if not selected or not selected[0].data(Qt.UserRole): self.tts_download_button.setEnabled(False); return
        voice_data = selected[0].data(Qt.UserRole); total_size = sum(f.get('size_bytes', 0) for f in voice_data['files'].values())
        self.piper_desc_label.setText(f"Description: {voice_data['language']['name_english']} - {voice_data['name']} ({voice_data['quality']})"); self.piper_size_label.setText(f"Size: {self._format_bytes(total_size)}")
        onnx_filename = f"{voice_data['key']}.onnx"; is_downloaded = os.path.exists(os.path.join("tools/piper", onnx_filename))
        self.tts_download_button.setEnabled(not is_downloaded); self.tts_download_button.setText("Voice Installed" if is_downloaded else "Download Voice")

    def start_tts_download(self):
        voice_data = self.piper_voice_list.selectedItems()[0].data(Qt.UserRole)
        self.tts_download_progress.show(); self.tts_download_progress.setValue(0); self._set_status_label(self.tts_status_label, f"Downloading {voice_data['name']}...")
        self.tts_download_button.setEnabled(False)
        base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"; files_to_download = []
        for file_key, file_info in voice_data['files'].items():
            if file_key.endswith(('.onnx', '.onnx.json')): files_to_download.append({'url': base_url + file_key, 'path': os.path.join("tools/piper", os.path.basename(file_key)), 'size': file_info.get('size_bytes', 0)})
        self.tts_worker = PiperVoiceDownloader(files_to_download, "tools/piper"); self.tts_worker.progress.connect(self.tts_download_progress.setValue)
        self.tts_worker.finished.connect(lambda s, m: self.on_tts_download_finished(s, m, voice_data)); self.tts_worker.start()

    def on_tts_download_finished(self, success, message, voice_data):
        self._set_status_label(self.tts_status_label, message, "success" if success else "error")
        self.tts_download_progress.hide()
        if success:
            if 'tts' not in self.config: self.config['tts'] = {}
            if 'voices' not in self.config['tts']: self.config['tts']['voices'] = {}
            
            voice_name = f"{voice_data['name']}"; onnx_path = f"tools/piper/{voice_data['key']}.onnx"
            self.config['tts']['voices'][voice_name] = onnx_path
            self.save_config(); self.update_tts_page_state()

    def set_active_tts_voice(self):
        if 'tts' not in self.config: self.config['tts'] = {}
        self.config['tts']['default_voice'] = self.tts_voice_combo.currentText()
        self.save_config()
        self._set_status_label(self.tts_status_label, "Settings saved. Restart Kortex to apply.", "success")

    def delete_tts_voice(self):
        voice_to_delete = self.tts_voice_combo.currentText()
        if not voice_to_delete: return
        
        tts_config = self.config.get('tts', {})
        if voice_to_delete == tts_config.get('default_voice'):
            self._set_status_label(self.tts_status_label, "Cannot delete the active default voice.", "error")
            return
        
        try:
            voice_path = tts_config.get('voices', {}).get(voice_to_delete)
            if voice_path and os.path.exists(voice_path):
                os.remove(voice_path)
                json_path = voice_path + ".json"
                if os.path.exists(json_path): os.remove(json_path)
            
            if 'voices' in tts_config and voice_to_delete in tts_config['voices']:
                del self.config['tts']['voices'][voice_to_delete]

            self.save_config()
            self._set_status_label(self.tts_status_label, f"Voice '{voice_to_delete}' deleted.", "success")
            self.update_tts_page_state()
        except Exception as e:
            self._set_status_label(self.tts_status_label, f"Error deleting voice: {e}", "error")
            
    def create_services_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setAlignment(Qt.AlignTop); layout.setContentsMargins(30, 25, 30, 25); layout.setSpacing(20)
        title = QLabel("Integrations & Services"); title.setObjectName("titleLabel")
        
        weather_group = QGroupBox("Meteosource Weather"); weather_layout = QVBoxLayout(weather_group)
        self.weather_enable_checkbox = QCheckBox("Enable Weather Tool")
        self.weather_enable_checkbox.stateChanged.connect(self.save_settings)
        weather_layout.addWidget(self.weather_enable_checkbox)
        self.weather_api_key_input = QLineEdit(); self.weather_api_key_input.setPlaceholderText("Enter Meteosource API Key")
        self.weather_api_key_input.setEchoMode(QLineEdit.Password); self.weather_api_key_input.editingFinished.connect(self.save_settings)
        weather_layout.addWidget(self.weather_api_key_input)
        info_label1 = QLabel("Get a free API key from <a href='https://www.meteosource.com'>meteosource.com</a>."); info_label1.setOpenExternalLinks(True)
        weather_layout.addWidget(info_label1)

        currency_group = QGroupBox("Currency Conversion (CurrencyFreaks)"); currency_layout = QVBoxLayout(currency_group)
        self.currency_enable_checkbox = QCheckBox("Enable Currency Conversion Tool")
        self.currency_enable_checkbox.stateChanged.connect(self.save_settings)
        currency_layout.addWidget(self.currency_enable_checkbox)
        self.currency_api_key_input = QLineEdit(); self.currency_api_key_input.setPlaceholderText("Enter CurrencyFreaks API Key")
        self.currency_api_key_input.setEchoMode(QLineEdit.Password); self.currency_api_key_input.editingFinished.connect(self.save_settings)
        currency_layout.addWidget(self.currency_api_key_input)
        info_label2 = QLabel("Get a free API key from <a href='https://currencyfreaks.com/'>currencyfreaks.com</a>."); info_label2.setOpenExternalLinks(True)
        currency_layout.addWidget(info_label2)

        location_group = QGroupBox("Location Services (IPLocate.io)"); location_layout = QVBoxLayout(location_group)
        self.location_enable_checkbox = QCheckBox("Enable Location-based Tools")
        self.location_enable_checkbox.stateChanged.connect(self.save_settings)
        location_layout.addWidget(self.location_enable_checkbox)
        self.location_api_key_input = QLineEdit(); self.location_api_key_input.setPlaceholderText("Enter IPLocate.io API Key")
        self.location_api_key_input.setEchoMode(QLineEdit.Password); self.location_api_key_input.editingFinished.connect(self.save_settings)
        location_layout.addWidget(self.location_api_key_input)
        info_label3 = QLabel("Get a free API key from <a href='https://iplocate.io/'>iplocate.io</a>."); info_label3.setOpenExternalLinks(True)
        location_layout.addWidget(info_label3)
        
        self.services_status_label = QLabel(""); self.services_status_label.setProperty("status", "neutral")
        
        layout.addWidget(title); layout.addWidget(weather_group); layout.addWidget(currency_group); layout.addWidget(location_group)
        layout.addStretch(); layout.addWidget(self.services_status_label)
        return page
        
    def update_services_page_state(self):
        services = self.config.get('services', {})
        weather = services.get('weather', {})
        currency = services.get('currency_conversion', {})
        location = services.get('location', {})

        self.weather_enable_checkbox.setChecked(weather.get('enabled', False))
        self.weather_api_key_input.setText(weather.get('api_key', ''))
        self.weather_api_key_input.setEnabled(weather.get('enabled', False))
        
        self.currency_enable_checkbox.setChecked(currency.get('enabled', False))
        self.currency_api_key_input.setText(currency.get('api_key', ''))
        self.currency_api_key_input.setEnabled(currency.get('enabled', False))

        self.location_enable_checkbox.setChecked(location.get('enabled', False))
        self.location_api_key_input.setText(location.get('iplocate_api_key', ''))
        self.location_api_key_input.setEnabled(location.get('enabled', False))
        
    def create_accounts_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setAlignment(Qt.AlignTop); layout.setContentsMargins(30, 25, 30, 25); layout.setSpacing(20)
        title = QLabel("Accounts"); title.setObjectName("titleLabel")

        email_group = QGroupBox("Email Account (SMTP)"); email_layout = QVBoxLayout(email_group)
        self.email_enable_checkbox = QCheckBox("Enable Email Tool"); self.email_enable_checkbox.stateChanged.connect(self.save_settings)
        email_layout.addWidget(self.email_enable_checkbox)
        self.email_address_input = QLineEdit(); self.email_address_input.setPlaceholderText("your-email@example.com"); self.email_address_input.editingFinished.connect(self.save_settings)
        self.email_password_input = QLineEdit(); self.email_password_input.setPlaceholderText("App Password"); self.email_password_input.setEchoMode(QLineEdit.Password); self.email_password_input.editingFinished.connect(self.save_settings)
        self.email_smtp_server_input = QLineEdit(); self.email_smtp_server_input.setPlaceholderText("smtp.example.com"); self.email_smtp_server_input.editingFinished.connect(self.save_settings)
        self.email_smtp_port_input = QSpinBox(); self.email_smtp_port_input.setRange(1, 65535); self.email_smtp_port_input.setValue(587); self.email_smtp_port_input.editingFinished.connect(self.save_settings)
        
        email_layout.addWidget(QLabel("Email Address:"))
        email_layout.addWidget(self.email_address_input)
        email_layout.addWidget(QLabel("App Password (recommended):"))
        email_layout.addWidget(self.email_password_input)
        email_layout.addWidget(QLabel("SMTP Server:"))
        email_layout.addWidget(self.email_smtp_server_input)
        email_layout.addWidget(QLabel("SMTP Port:"))
        email_layout.addWidget(self.email_smtp_port_input)

        self.accounts_status_label = QLabel(""); self.accounts_status_label.setProperty("status", "neutral")
        layout.addWidget(title); layout.addWidget(email_group); layout.addStretch(); layout.addWidget(self.accounts_status_label)
        return page

    def update_accounts_page_state(self):
        email_config = self.config.get('services', {}).get('email', {})
        email_enabled = email_config.get('enabled', False)
        self.email_enable_checkbox.setChecked(email_enabled)
        self.email_address_input.setText(email_config.get('email_address', ''))
        self.email_password_input.setText(email_config.get('app_password', ''))
        self.email_smtp_server_input.setText(email_config.get('smtp_server', ''))
        self.email_smtp_port_input.setValue(email_config.get('smtp_port', 587))
        
        for widget in [self.email_address_input, self.email_password_input, self.email_smtp_server_input, self.email_smtp_port_input]:
            widget.setEnabled(email_enabled)
            
    def save_settings(self):
        if 'services' not in self.config: self.config['services'] = {}
        # Services Page
        if 'weather' not in self.config['services']: self.config['services']['weather'] = {}
        if 'currency_conversion' not in self.config['services']: self.config['services']['currency_conversion'] = {}
        if 'location' not in self.config['services']: self.config['services']['location'] = {}

        weather_enabled = self.weather_enable_checkbox.isChecked()
        self.config['services']['weather']['enabled'] = weather_enabled
        self.config['services']['weather']['api_key'] = self.weather_api_key_input.text()
        self.weather_api_key_input.setEnabled(weather_enabled)

        currency_enabled = self.currency_enable_checkbox.isChecked()
        self.config['services']['currency_conversion']['enabled'] = currency_enabled
        self.config['services']['currency_conversion']['api_key'] = self.currency_api_key_input.text()
        self.currency_api_key_input.setEnabled(currency_enabled)

        location_enabled = self.location_enable_checkbox.isChecked()
        self.config['services']['location']['enabled'] = location_enabled
        self.config['services']['location']['iplocate_api_key'] = self.location_api_key_input.text()
        self.location_api_key_input.setEnabled(location_enabled)

        # Accounts Page
        if 'email' not in self.config['services']: self.config['services']['email'] = {}
        email_enabled = self.email_enable_checkbox.isChecked()
        self.config['services']['email']['enabled'] = email_enabled
        self.config['services']['email']['email_address'] = self.email_address_input.text()
        self.config['services']['email']['app_password'] = self.email_password_input.text()
        self.config['services']['email']['smtp_server'] = self.email_smtp_server_input.text()
        self.config['services']['email']['smtp_port'] = self.email_smtp_port_input.value()

        for widget in [self.email_address_input, self.email_password_input, self.email_smtp_server_input, self.email_smtp_port_input]:
            widget.setEnabled(email_enabled)

        self.save_config()
        self._set_status_label(self.services_status_label, "Settings updated.", "success")
        self._set_status_label(self.accounts_status_label, "Settings updated.", "success")