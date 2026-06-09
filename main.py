"""
main.py — entry point for the local voice chatbot
"""

import tkinter as tk
from tkinter import messagebox

from stt import SpeechToText
from tts import TextToSpeech
from ollama_client import OllamaClient
from gui import VoiceChatGUI

DEFAULT_MODEL = "llama3"   # change to any model you have pulled, e.g. "mistral"


def main():
    root = tk.Tk()
    root.withdraw()          # hide until everything is loaded

    # ── initialise TTS (fast) ──────────────────────────────────────────────
    tts = TextToSpeech(rate=175)

    # ── initialise STT (may download model on first run) ──────────────────
    splash = tk.Toplevel(root)
    splash.title("Loading…")
    splash.configure(bg="#0f1117")
    splash.resizable(False, False)
    msg_var = tk.StringVar(value="Initialising speech recogniser…")
    tk.Label(splash, textvariable=msg_var, bg="#0f1117", fg="#e8e8f0",
             font=("Courier New", 11), padx=30, pady=20).pack()
    splash.update()

    try:
        stt = SpeechToText(progress_cb=lambda m: (msg_var.set(m), splash.update()))
    except Exception as e:
        messagebox.showerror("STT Error",
                             f"Could not initialise Vosk:\n{e}\n\n"
                             "Make sure PyAudio is installed and a microphone is connected.")
        root.destroy()
        return

    splash.destroy()

    # ── initialise Ollama client ──────────────────────────────────────────
    llm = OllamaClient(model=DEFAULT_MODEL)

    # ── launch GUI ────────────────────────────────────────────────────────
    root.deiconify()
    app = VoiceChatGUI(root, stt=stt, tts=tts, ollama=llm)

    def on_close():
        tts.close()
        stt.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()