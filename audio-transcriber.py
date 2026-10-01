#!/usr/bin/env python3
"""
Audio Transcriber — Capture système audio → transcription (faster-whisper)
→ résumé (Ollama) → fichier .md

Windows 11, Python 3.11+, Ollama local requis.

Interface : tkinter avec bouton Record/Stop + Sauvegarder.
"""

import json
import os
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
import requests
import sounddevice as sd
import soundfile as sf

# ── CONFIG ────────────────────────────────────────────────────────────────

CONFIG_FILE = Path.home() / ".audio-transcriber-config.json"
DEFAULT_OUTPUT_DIR = Path.home() / "AudioTranscriber"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"          # modèle pour le résumé
WHISPER_MODEL_SIZE = "small"          # tiny / base / small / medium
WHISPER_DEVICE = "cpu"                # cpu ou cuda
SAMPLE_RATE = 16000                   # 16 kHz (parfait pour whisper)
CHANNELS = 1                          # mono pour la transcription

# Bouton unique Start/Stop — pas de bouton séparé « sauvegarder » dédié
# mais directement le résultat s'affiche et on peut l'enregistrer.
# On garde un combo : [🔴 Record] ↔ [⏹ Stop] + [💾 Sauvegarder]


class AudioTranscriberApp:
    """Application tkinter de capture audio → transcription → résumé."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Audio Transcriber")
        self.root.geometry("620x520")
        self.root.resizable(False, False)

        # état
        self.recording = False
        self.audio_buffer: list[np.ndarray] = []
        self.stream: sd.InputStream | None = None
        self.recorded_file: Path | None = None
        self.transcription_text: str = ""
        self.summary_text: str = ""
        self.processing = False

        # thread worker
        self.worker_thread: threading.Thread | None = None

        self.load_config()
        self.build_ui()
        self.refresh_devices()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ── CONFIG ────────────────────────────────────────────────────────

    def load_config(self):
        """Charge la config depuis le JSON utilisateur."""
        self.config: dict = {}
        if CONFIG_FILE.exists():
            try:
                self.config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.config = {}

    def save_config(self):
        """Persiste la config."""
        # sauvegarde l'ID numérique du device, pas le libellé
        device_id = self._device_map.get(self.device_var.get())
        if device_id is not None:
            self.config["device_id"] = device_id
        self.config["whisper_model"] = self.whisper_var.get()
        self.config["ollama_model"] = self.ollama_var.get()
        self.config["output_dir"] = str(self.output_dir)
        try:
            CONFIG_FILE.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        except OSError:
            pass

    # ── INTERFACE ─────────────────────────────────────────────────────

    def build_ui(self):
        root = self.root

        # -- Périphérique audio
        f1 = ttk.LabelFrame(root, text="🎤 Périphérique audio", padding=8)
        f1.pack(fill="x", padx=12, pady=(8, 2))

        dev_row = ttk.Frame(f1)
        dev_row.pack(fill="x")
        self.device_var = tk.StringVar()
        self.device_menu = ttk.Combobox(dev_row, textvariable=self.device_var,
                                        state="readonly", width=50)
        self.device_menu.pack(side="left", padx=(0, 6))
        ttk.Button(dev_row, text="⟳", width=3,
                   command=self.refresh_devices).pack(side="left")

        # -- Options modèle
        f2 = ttk.LabelFrame(root, text="🧠 Modèles", padding=8)
        f2.pack(fill="x", padx=12, pady=2)

        row = ttk.Frame(f2)
        row.pack(fill="x")
        ttk.Label(row, text="Whisper :").pack(side="left")
        self.whisper_var = tk.StringVar(value=self.config.get("whisper_model", WHISPER_MODEL_SIZE))
        self.whisper_menu = ttk.Combobox(row, textvariable=self.whisper_var,
                                          values=["tiny", "base", "small", "medium"],
                                          state="readonly", width=12)
        self.whisper_menu.pack(side="left", padx=(6, 20))
        ttk.Label(row, text="Ollama :").pack(side="left")
        self.ollama_var = tk.StringVar(value=self.config.get("ollama_model", OLLAMA_MODEL))
        self.ollama_entry = ttk.Entry(row, textvariable=self.ollama_var, width=20)
        self.ollama_entry.pack(side="left", padx=6)

        # -- Bouton Record
        f3 = ttk.LabelFrame(root, text="⏺ Contrôle", padding=8)
        f3.pack(fill="x", padx=12, pady=2)

        self.record_btn = ttk.Button(f3, text="🔴 Record",
                                     command=self.toggle_record, width=20)
        self.record_btn.pack(pady=4)
        self.status_label = ttk.Label(f3, text="Prêt", foreground="gray")
        self.status_label.pack()

        # -- Barre de progression
        self.progress = ttk.Progressbar(f3, mode="indeterminate", length=400)
        # (cachée par défaut, montrée pendant le traitement)

        # -- Résultat
        f4 = ttk.LabelFrame(root, text="📝 Résultat", padding=8)
        f4.pack(fill="both", expand=True, padx=12, pady=2)

        txt_frame = ttk.Frame(f4)
        txt_frame.pack(fill="both", expand=True)

        self.result_text = tk.Text(txt_frame, wrap="word", height=10,
                                   font=("Consolas", 10))
        scroll = ttk.Scrollbar(txt_frame, orient="vertical",
                               command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.result_text.pack(side="left", fill="both", expand=True)

        # -- Bouton Sauvegarder
        btn_row = ttk.Frame(root)
        btn_row.pack(fill="x", padx=12, pady=4)
        self.save_btn = ttk.Button(btn_row, text="💾 Sauvegarder .md",
                                   command=self.save_md, state="disabled")
        self.save_btn.pack(side="left", padx=6)
        ttk.Button(btn_row, text="🗑 Effacer", command=self.clear_result).pack(side="left")

        # restaure device depuis config (après refresh_devices)
        self.root.after(100, self._restore_device)

        self.output_dir = Path(self.config.get("output_dir", str(DEFAULT_OUTPUT_DIR)))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _restore_device(self):
        """Restaure le périphérique depuis la config."""
        saved_id = self.config.get("device_id")
        if saved_id is not None and hasattr(self, "_device_map"):
            for label, idx in self._device_map.items():
                if idx == int(saved_id):
                    self.device_var.set(label)
                    return
        # défaut : premier device
        labels = list(getattr(self, "_device_map", {}).keys())
        if labels:
            self.device_var.set(labels[0])

    def refresh_devices(self):
        """Re-scanner les périphériques audio d'entrée."""
        try:
            devices = sd.query_devices()
            input_devices = [
                (i, d["name"], d["max_input_channels"])
                for i, d in enumerate(devices)
                if d["max_input_channels"] > 0
            ]
            labels = [f"{i} — {name} ({ch} canaux)" for i, name, ch in input_devices]
            self.device_menu["values"] = labels
            self._device_map = {f"{i} — {name} ({ch} canaux)": i
                                for i, name, ch in input_devices}
            if labels:
                current = self.device_var.get()
                if current not in labels:
                    for lbl in labels:
                        if lbl.startswith(current.split("—")[0].strip() + " "):
                            self.device_var.set(lbl)
                            break
                    else:
                        self.device_var.set(labels[0])
        except Exception as exc:
            messagebox.showerror("Erreur périphériques", str(exc))

    # ── ENREGISTREMENT ────────────────────────────────────────────────

    def toggle_record(self):
        if self.processing:
            return
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        device_id = self._device_map.get(self.device_var.get())
        if device_id is None:
            messagebox.showwarning("Périphérique", "Choisis un périphérique audio d'abord.")
            return

        self.recording = True
        self.audio_buffer = []
        self.recorded_file = None
        self.transcription_text = ""
        self.summary_text = ""
        self.result_text.delete("1.0", "end")
        self.save_btn.configure(state="disabled")
        self.record_btn.configure(text="⏹ Stop", state="normal")
        self.status_label.configure(text="🎙 Enregistrement…", foreground="green")
        self.progress.pack(pady=2)
        self.progress.start()

        def callback(indata, frames, time_info, status):
            if self.recording:
                self.audio_buffer.append(indata.copy())

        try:
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                device=device_id,
                callback=callback,
                blocksize=1024,
            )
            self.stream.start()
        except Exception as exc:
            self.recording = False
            self.progress.stop()
            self.progress.pack_forget()
            self.status_label.configure(text="Erreur", foreground="red")
            messagebox.showerror("Erreur audio", str(exc))

    def stop_recording(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.recording = False
        self.progress.stop()
        self.progress.pack_forget()
        self.record_btn.configure(text="🔴 Record")
        self.status_label.configure(text="⏳ Transcription…", foreground="orange")

        if not self.audio_buffer:
            self.status_label.configure(text="Aucun audio capturé", foreground="gray")
            return

        # fusion du buffer → fichier WAV
        audio = np.concatenate(self.audio_buffer, axis=0)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.recorded_file = self.output_dir / f"capture_{timestamp}.wav"
        sf.write(str(self.recorded_file), audio, SAMPLE_RATE)
        self.status_label.configure(text=f"💾 {self.recorded_file.name} — Transcription…",
                                    foreground="orange")

        # Transcription en thread
        self.processing = True
        self.worker_thread = threading.Thread(target=self.transcribe_and_summarize,
                                              daemon=True)
        self.worker_thread.start()

    # ── TRANSCRIPTION + RÉSUMÉ ────────────────────────────────────────

    def transcribe_and_summarize(self):
        """Lance la transcription (faster-whisper) puis le résumé (Ollama)."""
        try:
            from faster_whisper import WhisperModel

            model_size = self.whisper_var.get()
            self.status_label.configure(
                text=f"⏳ Chargement whisper {model_size}…", foreground="orange")

            model = WhisperModel(model_size, device=WHISPER_DEVICE,
                                 compute_type="int8" if WHISPER_DEVICE == "cpu" else "float16")

            self.status_label.configure(text=f"🎤 Transcription en cours…", foreground="orange")

            segments, _ = model.transcribe(str(self.recorded_file),
                                           language="fr",
                                           beam_size=3 if model_size in ("medium",) else 5,
                                           vad_filter=True,
                                           vad_parameters=dict(
                                               threshold=0.35,
                                               min_silence_duration_ms=500,
                                           ))

            lines = []
            for seg in segments:
                start = time.strftime("%H:%M:%S", time.gmtime(seg.start))
                end = time.strftime("%H:%M:%S", time.gmtime(seg.end))
                lines.append(f"[{start} → {end}] {seg.text.strip()}")
            self.transcription_text = "\n".join(lines)
            model = None  # libération mémoire

            if not self.transcription_text.strip():
                self.root.after(0, self._on_transcription_done,
                                "⚠️ Aucune parole détectée dans l'enregistrement.")
                return

            # Résumé Ollama
            self.root.after(0, self._show_progress, "🧠 Résumé Ollama…")
            summary = self._summarize(self.transcription_text)
            self.summary_text = summary

            # Assemblage final
            content = self._build_md()
            self.root.after(0, self._on_transcription_done, content)

        except Exception as exc:
            self.root.after(0, self._on_transcription_done,
                            f"❌ Erreur : {exc}")
        finally:
            self.processing = False

    def _summarize(self, text: str) -> str:
        """Envoie la transcription à Ollama pour un résumé structuré."""
        prompt = (
            "Tu es un assistant qui résume des transcriptions audio. "
            "Voici la transcription d'un enregistrement audio.\n\n"
            f"{text}\n\n"
            "Rédige un résumé structuré en français :\n"
            "- **Sujet** : de quoi ça parle ?\n"
            "- **Points clés** : liste des idées principales\n"
            "- **Décisions / actions** : s'il y en a\n\n"
            "Résumé :"
        )
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": self.ollama_var.get(),
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_ctx": 4096, "temperature": 0.3},
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()
        except requests.exceptions.ConnectionError:
            return "⚠️ Ollama inaccessible (http://localhost:11434). Vérifie qu'Ollama est lancé."
        except Exception as exc:
            return f"⚠️ Erreur résumé : {exc}"

    def _build_md(self) -> str:
        """Construit le contenu Markdown final."""
        now = datetime.now()
        lines = [
            f"# 🎧 Transcription audio — {now.strftime('%d/%m/%Y %H:%M')}",
            "",
            f"Fichier source : `{self.recorded_file.name}`",
            f"Modèle whisper : `{self.whisper_var.get()}` · Ollama : `{self.ollama_var.get()}`",
            "",
            "---",
            "",
            "## 🧠 Résumé",
            "",
            self.summary_text,
            "",
            "---",
            "",
            "## 📝 Transcription brute",
            "",
            "```",
            self.transcription_text,
            "```",
            "",
            "---",
            f"_Généré automatiquement par Audio Transcriber le {now.strftime('%Y-%m-%d %H:%M:%S')}_",
            "",
        ]
        return "\n".join(lines)

    # ── CALLBACKS GUI (thread safe via root.after) ────────────────────

    def _show_progress(self, msg: str):
        self.status_label.configure(text=msg, foreground="orange")
        self.progress.pack(pady=2)
        self.progress.start()

    def _on_transcription_done(self, content: str):
        self.progress.stop()
        self.progress.pack_forget()
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", content)
        if content.startswith("❌") or content.startswith("⚠️"):
            self.status_label.configure(text=content[:60], foreground="red")
            self.save_btn.configure(state="disabled")
        else:
            self.status_label.configure(text="✅ Prêt — Résultat complet", foreground="green")
            self.save_btn.configure(state="normal")

    # ── SAUVEGARDE ────────────────────────────────────────────────────

    def save_md(self):
        """Sauvegarde le contenu Markdown dans un fichier."""
        content = self.result_text.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showinfo("Rien à sauvegarder", "Aucun résultat à enregistrer.")
            return

        default_name = f"transcription_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.md"
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Tous", "*.*")],
            initialdir=str(self.output_dir),
            initialfile=default_name,
        )
        if path:
            Path(path).write_text(content, encoding="utf-8")
            messagebox.showinfo("Sauvegardé", f"Fichier enregistré :\n{path}")
            self.status_label.configure(text=f"✅ Sauvegardé → {Path(path).name}",
                                        foreground="green")

    def clear_result(self):
        self.result_text.delete("1.0", "end")
        self.transcription_text = ""
        self.summary_text = ""
        self.save_btn.configure(state="disabled")
        self.status_label.configure(text="Prêt", foreground="gray")

    # ── FERMETURE ─────────────────────────────────────────────────────

    def on_close(self):
        if self.recording:
            self.stop_recording()
        if self.processing:
            messagebox.showwarning("Traitement en cours",
                                   "Attends la fin de la transcription.")
            return
        self.save_config()
        self.root.destroy()


# ── MAIN ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app = AudioTranscriberApp(root)
    root.mainloop()