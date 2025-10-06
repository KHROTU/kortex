import pyaudio
import json
import yaml
import numpy as np
from vosk import Model, KaldiRecognizer


class SpeechToText:
    def __init__(self, config_path="kortex/config.yaml"):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        model_path = config['stt_model_path']
        self.wake_words = config.get('wake_words', ["cortex"])
        
        try:
            self.model = Model(model_path)
        except Exception as e:
            raise e
            
        self.wake_word_recognizer = KaldiRecognizer(self.model, 16000, json.dumps(self.wake_words))
        self.command_recognizer = KaldiRecognizer(self.model, 16000)
        
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=4096
        )
        print("STT Engine Initialized.")
        self.stream.start_stream()

    def process_chunk(self, is_wake_word_detection=False, volume_callback=None):
        recognizer = self.wake_word_recognizer if is_wake_word_detection else self.command_recognizer
        data = self.stream.read(4096, exception_on_overflow=False)

        if volume_callback:
            audio_data = np.frombuffer(data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
            volume_callback(rms)

        if recognizer.AcceptWaveform(data):
            result = json.loads(recognizer.Result())
            if result['text']:
                if volume_callback:
                    volume_callback(0)
                return result['text']
        return None

    def close(self):
        if self.stream.is_active():
            self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        print("STT stream closed.")