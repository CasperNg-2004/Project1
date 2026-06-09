"""
tts.py — pyttsx3 text-to-speech

Runs speech synthesis in a background thread so it doesn't block the GUI.
"""

import threading
import pyttsx3


class TextToSpeech:
    def __init__(self, rate: int = 175, volume: float = 1.0):
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", rate)
        self._engine.setProperty("volume", volume)
        self._lock = threading.Lock()
        self._stop_flag = False

    def set_voice(self, voice_id: str):
        self._engine.setProperty("voice", voice_id)

    def list_voices(self):
        return self._engine.getProperty("voices")

    def speak(self, text: str, on_done=None):
        """Speak text in a background thread. Calls on_done() when finished."""
        def _run():
            with self._lock:
                if not self._stop_flag:
                    self._engine.say(text)
                    self._engine.runAndWait()
            if on_done:
                on_done()

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def stop(self):
        """Interrupt current speech."""
        self._stop_flag = True
        self._engine.stop()
        self._stop_flag = False

    def close(self):
        self._engine.stop()