import subprocess
import yaml
import os
import tempfile
import winsound


class TextToSpeech:
    def __init__(self, config_path="kortex/config.yaml"):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.piper_path = config['tts']['piper_path']
        self.voices = config['tts']['voices']
        self.default_voice_id = config['tts']['default_voice']
        
        if self.default_voice_id not in self.voices:
            raise ValueError(f"Default voice '{self.default_voice_id}' not found in config voices.")
        
        print("TTS Engine Initialized with voices:", list(self.voices.keys()))

    def speak(self, text: str, voice_id: str = None):
        if not text:
            return
        
        selected_voice_id = voice_id if voice_id in self.voices else self.default_voice_id
        voice_path = self.voices[selected_voice_id]
        
        print(f"Kortex ({selected_voice_id}): {text}")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
            output_path = tmpfile.name

        command = [self.piper_path, '-m', voice_path, '-f', output_path]
        
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        process.communicate(input=text.encode('utf-8'))

        if process.returncode != 0:
            print(f"Error running Piper TTS: {process.stderr.decode()}")
            os.remove(output_path)
            return

        try:
            flags = winsound.SND_FILENAME | winsound.SND_NODEFAULT
            winsound.PlaySound(output_path, flags)
        except Exception as e:
            print(f"Error playing audio file with winsound: {e}")
        finally:
            os.remove(output_path)