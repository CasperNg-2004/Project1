"""
gui.py — Tkinter GUI for the voice chatbot

Dark terminal-inspired theme. Mic button toggles recording.
"""

import threading
import tkinter as tk
from tkinter import font as tkfont, ttk, messagebox


# ── Colour palette ────────────────────────────────────────────────────────────
BG        = "#0f1117"   # near-black background
SURFACE   = "#1a1d27"   # card / input surface
BORDER    = "#2a2d3d"   # subtle borders
ACCENT    = "#7c6af7"   # violet accent (mic active, user bubble)
ACCENT2   = "#4ecdc4"   # teal accent (assistant bubble)
TEXT_PRI  = "#e8e8f0"   # primary text
TEXT_SEC  = "#7a7a9d"   # secondary / placeholder
RED       = "#f26b5b"   # stop / error


class ChatBubble(tk.Frame):
    """A single chat message bubble."""

    def __init__(self, parent, role: str, text: str, **kwargs):
        super().__init__(parent, bg=BG, **kwargs)
        is_user = role == "user"

        bubble_color = ACCENT if is_user else SURFACE
        text_color   = "#ffffff" if is_user else TEXT_PRI
        align        = tk.E if is_user else tk.W
        label_text   = "You" if is_user else "Assistant"
        label_color  = ACCENT if is_user else ACCENT2

        # role label
        lbl = tk.Label(self, text=label_text, bg=BG,
                       fg=label_color, font=("Courier New", 9, "bold"))
        lbl.pack(anchor=align, padx=12, pady=(4, 0))

        # bubble
        bubble = tk.Frame(self, bg=bubble_color,
                          highlightbackground=BORDER,
                          highlightthickness=1)
        bubble.pack(anchor=align, padx=12, pady=(0, 6), fill=tk.NONE)

        msg = tk.Label(bubble, text=text, bg=bubble_color, fg=text_color,
                       font=("Courier New", 11), wraplength=480,
                       justify=tk.LEFT, padx=12, pady=8)
        msg.pack()


class VoiceChatGUI:
    def __init__(self, root: tk.Tk, stt, tts, ollama):
        self.root  = root
        self.stt   = stt
        self.tts   = tts
        self.llm   = ollama

        self._recording    = False
        self._stop_rec     = threading.Event()
        self._speaking     = False

        self._build_ui()
        self._refresh_models()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        self.root.title("Voice Chatbot")
        self.root.configure(bg=BG)
        self.root.minsize(560, 640)

        self._build_header()
        self._build_chat_area()
        self._build_status_bar()
        self._build_controls()

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=SURFACE,
                       highlightbackground=BORDER, highlightthickness=1)
        hdr.pack(fill=tk.X)

        tk.Label(hdr, text="🎙  Voice Chatbot", bg=SURFACE, fg=TEXT_PRI,
                 font=("Courier New", 14, "bold"), padx=16, pady=10).pack(side=tk.LEFT)

        # model selector
        right = tk.Frame(hdr, bg=SURFACE)
        right.pack(side=tk.RIGHT, padx=12, pady=6)

        tk.Label(right, text="Model:", bg=SURFACE, fg=TEXT_SEC,
                 font=("Courier New", 9)).pack(side=tk.LEFT, padx=(0, 4))

        self._model_var = tk.StringVar(value=self.llm.model)
        self._model_cb  = ttk.Combobox(right, textvariable=self._model_var,
                                        width=18, state="readonly")
        self._model_cb.pack(side=tk.LEFT)
        self._model_cb.bind("<<ComboboxSelected>>", self._on_model_change)

        tk.Button(right, text="⟳", bg=SURFACE, fg=ACCENT, bd=0,
                  activebackground=SURFACE, activeforeground=TEXT_PRI,
                  font=("Courier New", 11),
                  command=self._refresh_models).pack(side=tk.LEFT, padx=4)

        # clear history
        tk.Button(hdr, text="Clear", bg=SURFACE, fg=TEXT_SEC, bd=0,
                  activebackground=SURFACE, activeforeground=TEXT_PRI,
                  font=("Courier New", 9),
                  command=self._clear_chat).pack(side=tk.RIGHT, padx=8)

    def _build_chat_area(self):
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        self._canvas = tk.Canvas(frame, bg=BG, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL,
                                  command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._chat_inner = tk.Frame(self._canvas, bg=BG)
        self._window_id  = self._canvas.create_window(
            (0, 0), window=self._chat_inner, anchor=tk.NW)

        self._chat_inner.bind("<Configure>", self._on_inner_resize)
        self._canvas.bind("<Configure>",    self._on_canvas_resize)

    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=SURFACE,
                       highlightbackground=BORDER, highlightthickness=1)
        bar.pack(fill=tk.X)

        self._status_dot = tk.Label(bar, text="●", bg=SURFACE,
                                     fg=TEXT_SEC, font=("Courier New", 10))
        self._status_dot.pack(side=tk.LEFT, padx=(12, 4), pady=4)

        self._status_lbl = tk.Label(bar, text="Ready", bg=SURFACE,
                                     fg=TEXT_SEC, font=("Courier New", 10))
        self._status_lbl.pack(side=tk.LEFT)

        # live partial transcript
        self._partial_lbl = tk.Label(bar, text="", bg=SURFACE,
                                      fg=ACCENT, font=("Courier New", 9, "italic"),
                                      anchor=tk.W)
        self._partial_lbl.pack(side=tk.LEFT, padx=8)

    def _build_controls(self):
        ctrl = tk.Frame(self.root, bg=SURFACE,
                        highlightbackground=BORDER, highlightthickness=1)
        ctrl.pack(fill=tk.X, pady=(0, 0))

        # text input row
        inp_row = tk.Frame(ctrl, bg=SURFACE)
        inp_row.pack(fill=tk.X, padx=12, pady=(8, 4))

        self._text_input = tk.Entry(
            inp_row, bg=BORDER, fg=TEXT_PRI, insertbackground=TEXT_PRI,
            font=("Courier New", 11), relief=tk.FLAT,
            highlightbackground=ACCENT, highlightthickness=1)
        self._text_input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 8))
        self._text_input.bind("<Return>", lambda _: self._on_send_text())

        send_btn = tk.Button(
            inp_row, text="Send", bg=ACCENT, fg="#ffffff",
            activebackground=ACCENT2, activeforeground="#ffffff",
            font=("Courier New", 10, "bold"), relief=tk.FLAT,
            padx=14, pady=6, command=self._on_send_text)
        send_btn.pack(side=tk.LEFT)

        # mic row
        mic_row = tk.Frame(ctrl, bg=SURFACE)
        mic_row.pack(pady=(0, 10))

        self._mic_btn = tk.Button(
            mic_row, text="🎙  Click to Speak",
            bg=BORDER, fg=TEXT_PRI, activebackground=RED,
            font=("Courier New", 11, "bold"), relief=tk.FLAT,
            padx=20, pady=10,
            command=self._toggle_recording)
        self._mic_btn.pack(side=tk.LEFT, padx=8)

        stop_btn = tk.Button(
            mic_row, text="■  Stop TTS",
            bg=BORDER, fg=TEXT_SEC, activebackground=BORDER,
            font=("Courier New", 10), relief=tk.FLAT,
            padx=14, pady=10,
            command=self._stop_tts)
        stop_btn.pack(side=tk.LEFT, padx=4)

    # ── Event handlers ─────────────────────────────────────────────────────

    def _toggle_recording(self):
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self._recording = True
        self._stop_rec.clear()
        self._mic_btn.config(text="⏹  Stop Recording", bg=RED, fg="#ffffff")
        self._set_status("Listening…", ACCENT)
        threading.Thread(target=self._record_thread, daemon=True).start()

    def _stop_recording(self):
        self._stop_rec.set()
        self._recording = False
        self._mic_btn.config(text="🎙  Click to Speak", bg=BORDER, fg=TEXT_PRI)
        self._set_status("Processing…", ACCENT2)

    def _record_thread(self):
        transcript = self.stt.listen(
            on_partial=lambda p: self.root.after(0, self._show_partial, p),
            stop_event=self._stop_rec,
        )
        self.root.after(0, self._partial_lbl.config, {"text": ""})
        if self._recording:          # user didn't stop manually
            self._stop_recording()
        if transcript:
            self.root.after(0, self._submit_message, transcript)
        else:
            self.root.after(0, self._set_status, "No speech detected.", TEXT_SEC)

    def _on_send_text(self):
        text = self._text_input.get().strip()
        if text:
            self._text_input.delete(0, tk.END)
            self._submit_message(text)

    def _submit_message(self, text: str):
        self._add_bubble("user", text)
        self._set_status("Thinking…", ACCENT2)
        threading.Thread(target=self._llm_thread, args=(text,), daemon=True).start()

    def _llm_thread(self, text: str):
        # Create a streaming bubble so the user sees tokens arrive live
        self.root.after(0, self._start_streaming_bubble)
        tokens = []
        for token in self.llm.stream_chat(text):
            tokens.append(token)
            self.root.after(0, self._append_stream_token, token)

        reply = "".join(tokens)
        self.root.after(0, self._finalise_streaming_bubble, reply)
        self.root.after(0, self._set_status, "Speaking…", ACCENT2)
        self.tts.speak(reply, on_done=lambda: self.root.after(
            0, self._set_status, "Ready", TEXT_SEC))

    def _on_model_change(self, _event=None):
        self.llm.set_model(self._model_var.get())
        self.llm.clear_history()
        self._set_status(f"Model: {self._model_var.get()} — history cleared.", ACCENT2)

    def _refresh_models(self):
        models = self.llm.list_local_models()
        if models:
            self._model_cb["values"] = models
            if self.llm.model not in models:
                self._model_var.set(models[0])
                self.llm.set_model(models[0])
        else:
            self._model_cb["values"] = [self.llm.model]

    def _clear_chat(self):
        for w in self._chat_inner.winfo_children():
            w.destroy()
        self.llm.clear_history()
        self._set_status("Chat cleared.", TEXT_SEC)

    def _stop_tts(self):
        self.tts.stop()
        self._set_status("Ready", TEXT_SEC)

    # ── UI helpers ─────────────────────────────────────────────────────────

    def _start_streaming_bubble(self):
        """Create a live assistant bubble that tokens are appended to."""
        self._stream_bubble_frame = tk.Frame(self._chat_inner, bg=BG)
        self._stream_bubble_frame.pack(fill=tk.X, pady=2)

        lbl = tk.Label(self._stream_bubble_frame, text="Assistant",
                       bg=BG, fg=ACCENT2, font=("Courier New", 9, "bold"))
        lbl.pack(anchor=tk.W, padx=12, pady=(4, 0))

        bubble = tk.Frame(self._stream_bubble_frame, bg=SURFACE,
                          highlightbackground=BORDER, highlightthickness=1)
        bubble.pack(anchor=tk.W, padx=12, pady=(0, 6))

        self._stream_text_var = tk.StringVar(value="")
        self._stream_label = tk.Label(
            bubble, textvariable=self._stream_text_var,
            bg=SURFACE, fg=TEXT_PRI, font=("Courier New", 11),
            wraplength=480, justify=tk.LEFT, padx=12, pady=8)
        self._stream_label.pack()
        self._stream_tokens: list[str] = []

    def _append_stream_token(self, token: str):
        """Append a new token to the live streaming bubble."""
        self._stream_tokens.append(token)
        self._stream_text_var.set("".join(self._stream_tokens))
        self._canvas.update_idletasks()
        self._canvas.yview_moveto(1.0)

    def _finalise_streaming_bubble(self, full_reply: str):
        """
        Replace the streaming bubble with a proper ChatBubble.
        This ensures consistent styling and avoids stale StringVar references.
        """
        if hasattr(self, "_stream_bubble_frame"):
            self._stream_bubble_frame.destroy()
            del self._stream_bubble_frame
        self._add_bubble("assistant", full_reply)

    def _add_bubble(self, role: str, text: str):
        bubble = ChatBubble(self._chat_inner, role=role, text=text)
        bubble.pack(fill=tk.X, pady=2)
        self._canvas.update_idletasks()
        self._canvas.yview_moveto(1.0)

    def _show_partial(self, text: str):
        self._partial_lbl.config(text=text[:60] + ("…" if len(text) > 60 else ""))

    def _set_status(self, msg: str, color: str = TEXT_SEC):
        self._status_dot.config(fg=color)
        self._status_lbl.config(text=msg, fg=color)

    def _on_inner_resize(self, _event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._window_id, width=event.width)