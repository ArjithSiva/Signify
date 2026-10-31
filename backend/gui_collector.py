"""
Signify - Desktop GUI for Wired ESP32 Data Collection & Live Testing
--------------------------------------------------------------------
Features:
  - Real-time COM port detection & connection over USB cable.
  - Live visual feedback for all 5 flex sensors (Thumb, Index, Middle, Ring, Pinky).
  - Quick-select buttons for A-Z and 0-9 gestures, plus custom label entry.
  - One-click / Spacebar data recording into `gesture_data.csv`.
  - Built-in instant classifier mode: test gestures live as soon as data is recorded!
"""

import os
import sys
import json
import csv
import math
import time
import threading
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    messagebox.showerror(
        "Missing Dependency",
        "pyserial is required. Install it using:\npip install pyserial"
    )
    sys.exit(1)

CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gesture_data.csv")
FIELDS = ["thumb", "index", "middle", "ring", "pinky"]


class SignifyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Signify - ESP32 Wired Glove Studio")
        self.root.geometry("880x740")
        self.root.minsize(820, 680)

        # Serial state
        self.ser = None
        self.serial_thread = None
        self.is_connected = False
        self.stop_thread = threading.Event()

        # Current sensor readings: [thumb, index, middle, ring, pinky]
        self.current_readings = [0, 0, 0, 0, 0]
        self.recording = False
        self.recorded_samples = []

        # Local dataset cache for live prediction & stats
        self.dataset = []  # list of (features_list, label)
        self.load_existing_dataset()
        self.last_web_forward = 0
        self.last_forwarded_label = ""

        # Style & UI
        self.setup_styles()
        self.build_ui()

        # Keyboard shortcuts
        self.root.bind("<space>", lambda e: self.trigger_record_shortcut())

        # Start periodic GUI updater (50ms)
        self.update_gui_loop()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Configure custom colors
        self.bg_color = "#1e1e2e"
        self.card_bg = "#282a36"
        self.text_color = "#f8f8f2"
        self.accent_color = "#50fa7b"
        self.warn_color = "#ff5555"

        self.root.configure(bg=self.bg_color)

    def build_ui(self):
        # Header / Title
        header_frame = tk.Frame(self.root, bg="#181825", pady=10, padx=15)
        header_frame.pack(fill=tk.X)

        title = tk.Label(
            header_frame,
            text="SIGNIFY — ESP32 GLOVE STUDIO",
            font=("Segoe UI", 16, "bold"),
            fg="#89b4fa",
            bg="#181825"
        )
        title.pack(side=tk.LEFT)

        subtitle = tk.Label(
            header_frame,
            text="USB Wired Mode • 5 Flex Sensors • 12-bit (0-4095)",
            font=("Segoe UI", 9),
            fg="#a6adc8",
            bg="#181825"
        )
        subtitle.pack(side=tk.LEFT, padx=15, pady=4)

        # Main horizontal container: Left pane (Controls & Sensors), Right pane (Dataset & Predictor)
        main_panes = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=self.bg_color, sashwidth=4)
        main_panes.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        left_frame = tk.Frame(main_panes, bg=self.bg_color)
        right_frame = tk.Frame(main_panes, bg=self.bg_color)
        main_panes.add(left_frame, minsize=420)
        main_panes.add(right_frame, minsize=380)

        # ----------------- LEFT PANE -----------------
        # 1. Connection Card
        conn_card = tk.LabelFrame(
            left_frame, text=" 1. Serial Port Connection ",
            font=("Segoe UI", 10, "bold"), fg="#cdd6f4", bg=self.card_bg, padx=10, pady=8
        )
        conn_card.pack(fill=tk.X, pady=5)

        port_row = tk.Frame(conn_card, bg=self.card_bg)
        port_row.pack(fill=tk.X)

        tk.Label(port_row, text="COM Port:", fg="#cdd6f4", bg=self.card_bg).pack(side=tk.LEFT, padx=4)
        self.port_combobox = ttk.Combobox(port_row, width=15, state="readonly")
        self.port_combobox.pack(side=tk.LEFT, padx=5)

        refresh_btn = tk.Button(
            port_row, text="🔄 Refresh", command=self.refresh_ports,
            bg="#45475a", fg="#ffffff", relief=tk.FLAT, padx=6
        )
        refresh_btn.pack(side=tk.LEFT, padx=4)

        self.connect_btn = tk.Button(
            port_row, text="Connect", command=self.toggle_connection,
            bg="#a6e3a1", fg="#11111b", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=12
        )
        self.connect_btn.pack(side=tk.RIGHT, padx=4)

        self.conn_status_label = tk.Label(
            conn_card, text="Status: Disconnected. Connect ESP32 via USB.",
            font=("Segoe UI", 9, "italic"), fg="#f38ba8", bg=self.card_bg
        )
        self.conn_status_label.pack(anchor="w", pady=(6, 0))

        # 2. Live Sensors Monitor
        sensor_card = tk.LabelFrame(
            left_frame, text=" 2. Live Flex Sensors (0 - 4095) ",
            font=("Segoe UI", 10, "bold"), fg="#cdd6f4", bg=self.card_bg, padx=10, pady=8
        )
        sensor_card.pack(fill=tk.X, pady=6)

        self.sensor_bars = {}
        self.sensor_val_labels = {}
        finger_colors = ["#f38ba8", "#fab387", "#f9e2af", "#a6e3a1", "#89dceb"]

        for idx, finger in enumerate(["Thumb (32)", "Index (33)", "Middle (34)", "Ring (35)", "Pinky (36)"]):
            key = FIELDS[idx]
            f_row = tk.Frame(sensor_card, bg=self.card_bg)
            f_row.pack(fill=tk.X, pady=3)

            lbl = tk.Label(f_row, text=finger, width=12, anchor="w", fg="#cdd6f4", bg=self.card_bg, font=("Segoe UI", 9))
            lbl.pack(side=tk.LEFT)

            # Progress bar
            pbar = ttk.Progressbar(f_row, orient="horizontal", length=180, mode="determinate", maximum=4095)
            pbar.pack(side=tk.LEFT, padx=8, expand=True, fill=tk.X)
            self.sensor_bars[key] = pbar

            # Numerical value label
            v_lbl = tk.Label(f_row, text="0", width=6, fg=finger_colors[idx], bg=self.card_bg, font=("Consolas", 10, "bold"))
            v_lbl.pack(side=tk.RIGHT)
            self.sensor_val_labels[key] = v_lbl

        # 3. Data Collection Controls
        record_card = tk.LabelFrame(
            left_frame, text=" 3. Data Collection & Training ",
            font=("Segoe UI", 10, "bold"), fg="#cdd6f4", bg=self.card_bg, padx=10, pady=8
        )
        record_card.pack(fill=tk.BOTH, expand=True, pady=6)

        label_row = tk.Frame(record_card, bg=self.card_bg)
        label_row.pack(fill=tk.X, pady=4)

        tk.Label(label_row, text="Current Sign / Label:", font=("Segoe UI", 10, "bold"), fg="#cdd6f4", bg=self.card_bg).pack(side=tk.LEFT, padx=4)
        self.label_entry = tk.Entry(label_row, width=10, font=("Segoe UI", 12, "bold"), justify="center", bg="#313244", fg="#ffffff", insertbackground="white")
        self.label_entry.insert(0, "A")
        self.label_entry.pack(side=tk.LEFT, padx=8)

        # Quick select buttons for Alphabet and Numbers
        quick_frame = tk.Frame(record_card, bg=self.card_bg)
        quick_frame.pack(fill=tk.X, pady=6)

        tk.Label(quick_frame, text="Quick Select:", font=("Segoe UI", 9), fg="#bac2de", bg=self.card_bg).pack(anchor="w")

        # Alphabet row 1: A-M
        row_am = tk.Frame(quick_frame, bg=self.card_bg)
        row_am.pack(fill=tk.X, pady=2)
        for char in "ABCDEFGHIJKLM":
            b = tk.Button(row_am, text=char, width=2, relief=tk.FLAT, bg="#45475a", fg="#ffffff",
                          command=lambda c=char: self.set_label(c))
            b.pack(side=tk.LEFT, padx=1)

        # Alphabet row 2: N-Z
        row_nz = tk.Frame(quick_frame, bg=self.card_bg)
        row_nz.pack(fill=tk.X, pady=2)
        for char in "NOPQRSTUVWXYZ":
            b = tk.Button(row_nz, text=char, width=2, relief=tk.FLAT, bg="#45475a", fg="#ffffff",
                          command=lambda c=char: self.set_label(c))
            b.pack(side=tk.LEFT, padx=1)

        # Numbers row: 0-9
        row_num = tk.Frame(quick_frame, bg=self.card_bg)
        row_num.pack(fill=tk.X, pady=2)
        for num in "0123456789":
            b = tk.Button(row_num, text=num, width=2, relief=tk.FLAT, bg="#585b70", fg="#cba6f7",
                          command=lambda c=num: self.set_label(c))
            b.pack(side=tk.LEFT, padx=1)

        # Record action
        rec_action_frame = tk.Frame(record_card, bg=self.card_bg, pady=8)
        rec_action_frame.pack(fill=tk.X)

        self.record_btn = tk.Button(
            rec_action_frame,
            text="🔴 RECORD SAMPLES  [Spacebar]",
            font=("Segoe UI", 11, "bold"),
            bg="#f38ba8", fg="#11111b",
            relief=tk.FLAT, padx=15, pady=8,
            command=self.start_recording
        )
        self.record_btn.pack(fill=tk.X)

        self.rec_status_label = tk.Label(
            rec_action_frame,
            text="Hold the sign pose steady, then click Record or press Spacebar.",
            font=("Segoe UI", 9), fg="#a6adc8", bg=self.card_bg, pady=4
        )
        self.rec_status_label.pack()

        self.rec_progress = ttk.Progressbar(rec_action_frame, orient="horizontal", mode="determinate")
        self.rec_progress.pack(fill=tk.X, pady=2)

        # ----------------- RIGHT PANE -----------------
        # 1. Dataset stats card
        dataset_card = tk.LabelFrame(
            right_frame, text=" Dataset Summary (gesture_data.csv) ",
            font=("Segoe UI", 10, "bold"), fg="#cdd6f4", bg=self.card_bg, padx=10, pady=8
        )
        dataset_card.pack(fill=tk.BOTH, expand=True, pady=5)

        stats_top = tk.Frame(dataset_card, bg=self.card_bg)
        stats_top.pack(fill=tk.X)

        self.total_samples_lbl = tk.Label(
            stats_top, text="Total Samples: 0", font=("Segoe UI", 10, "bold"),
            fg="#89b4fa", bg=self.card_bg
        )
        self.total_samples_lbl.pack(side=tk.LEFT)

        undo_btn = tk.Button(
            stats_top, text="🗑️ Clear Last Added", relief=tk.FLAT, bg="#585b70", fg="#f38ba8",
            font=("Segoe UI", 8), command=self.undo_last_sample
        )
        undo_btn.pack(side=tk.RIGHT)

        # List of labels and sample counts
        list_frame = tk.Frame(dataset_card, bg=self.card_bg)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=6)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.classes_listbox = tk.Listbox(
            list_frame, bg="#181825", fg="#cdd6f4", font=("Consolas", 10),
            selectbackground="#45475a", yscrollcommand=scrollbar.set, relief=tk.FLAT
        )
        self.classes_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.classes_listbox.yview)

        # 2. Live Prediction / Testing Box
        predict_card = tk.LabelFrame(
            right_frame, text=" Live Gesture Prediction (Instant Test) ",
            font=("Segoe UI", 10, "bold"), fg="#cdd6f4", bg=self.card_bg, padx=10, pady=8
        )
        predict_card.pack(fill=tk.X, pady=6)

        self.predict_active = tk.BooleanVar(value=True)
        pred_check = tk.Checkbutton(
            predict_card, text="Enable Live Prediction", variable=self.predict_active,
            fg="#cdd6f4", bg=self.card_bg, selectcolor="#181825", activebackground=self.card_bg
        )
        pred_check.pack(anchor="w")

        self.pred_display = tk.Label(
            predict_card, text="--", font=("Segoe UI", 36, "bold"),
            fg="#a6e3a1", bg="#181825", height=2
        )
        self.pred_display.pack(fill=tk.X, pady=6)

        self.pred_confidence = tk.Label(
            predict_card, text="Confidence: Collect at least 2 signs to activate",
            font=("Segoe UI", 9, "italic"), fg="#a6adc8", bg=self.card_bg
        )
        self.pred_confidence.pack()

        # Initial populate
        self.refresh_ports()
        self.update_dataset_stats()

    def set_label(self, label_char):
        self.label_entry.delete(0, tk.END)
        self.label_entry.insert(0, label_char)

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [p.device for p in ports]
        self.port_combobox["values"] = port_list
        if port_list:
            # If an ESP32 is already selected or default to the first one
            self.port_combobox.current(0)
            self.conn_status_label.config(text=f"Found {len(port_list)} port(s). Select one and click Connect.", fg="#89b4fa")
        else:
            self.conn_status_label.config(text="No COM ports found. Plug in ESP32 via USB.", fg="#fab387")

    def toggle_connection(self):
        if not self.is_connected:
            port = self.port_combobox.get()
            if not port:
                messagebox.showwarning("No Port", "Please select a COM port first.")
                return

            try:
                self.ser = serial.Serial(port, 115200, timeout=1)
                time.sleep(1.0)  # Wait for ESP32 reboot / serial stabilization
                self.ser.reset_input_buffer()
                
                self.stop_thread.clear()
                self.serial_thread = threading.Thread(target=self.serial_reader_worker, daemon=True)
                self.serial_thread.start()

                self.is_connected = True
                self.connect_btn.config(text="Disconnect", bg="#f38ba8")
                self.conn_status_label.config(text=f"Connected to {port} at 115200 baud.", fg="#a6e3a1")
                self.port_combobox.config(state="disabled")
            except Exception as e:
                messagebox.showerror("Connection Error", f"Could not open {port}:\n{e}")
        else:
            self.disconnect_serial()

    def disconnect_serial(self):
        self.stop_thread.set()
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
        self.is_connected = False
        self.connect_btn.config(text="Connect", bg="#a6e3a1")
        self.conn_status_label.config(text="Disconnected.", fg="#f38ba8")
        self.port_combobox.config(state="readonly")

    def serial_reader_worker(self):
        while not self.stop_thread.is_set():
            if not self.ser or not self.ser.is_open:
                break
            try:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                # Handle JSON format: {"thumb":3200,"index":3100,...}
                if line.startswith("{") and line.endswith("}"):
                    try:
                        data = json.loads(line)
                        if all(k in data for k in FIELDS):
                            vals = [int(data[k]) for k in FIELDS]
                            self.current_readings = vals
                            if self.recording:
                                self.recorded_samples.append(vals)
                    except Exception:
                        pass
                # Also accept CSV fallback: 3200,3100,2800,2900,3000
                elif "," in line:
                    parts = line.split(",")
                    if len(parts) >= 5:
                        try:
                            vals = [int(float(p.strip())) for p in parts[:5]]
                            self.current_readings = vals
                            if self.recording:
                                self.recorded_samples.append(vals)
                        except Exception:
                            pass
            except Exception:
                break
        self.is_connected = False

    def trigger_record_shortcut(self):
        # Trigger recording only if not currently recording
        if not self.recording:
            self.start_recording()

    def start_recording(self):
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to the ESP32 first.")
            return

        label = self.label_entry.get().strip()
        if not label:
            messagebox.showwarning("Missing Label", "Please enter a sign label (e.g. 'A', '1').")
            return

        self.recording = True
        self.recorded_samples = []
        self.record_btn.config(state="disabled", text=f"RECORDING '{label}'...", bg="#fab387")
        self.rec_status_label.config(text=f"Recording '{label}'... Hold sign steady!", fg="#fab387")
        
        # Start a thread to count down 3.0 seconds of capture
        threading.Thread(target=self.record_countdown_worker, args=(label,), daemon=True).start()

    def record_countdown_worker(self, label):
        duration = 3.0
        start_time = time.time()
        
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            pct = int((elapsed / duration) * 100)
            self.rec_progress["value"] = pct
            time.sleep(0.05)

        self.recording = False
        self.rec_progress["value"] = 100

        # Save to CSV
        samples_to_save = list(self.recorded_samples)
        if samples_to_save:
            with open(CSV_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                for row in samples_to_save:
                    writer.writerow(row + [label])
                    self.dataset.append((row, label))

        # Update UI back in main thread
        self.root.after(0, lambda: self.finish_recording(label, len(samples_to_save)))

    def finish_recording(self, label, count):
        self.record_btn.config(state="normal", text="🔴 RECORD SAMPLES  [Spacebar]", bg="#f38ba8")
        self.rec_status_label.config(text=f"✅ Saved {count} samples for '{label}' to gesture_data.csv!", fg="#a6e3a1")
        self.rec_progress["value"] = 0
        self.update_dataset_stats()

    def load_existing_dataset(self):
        self.dataset = []
        if os.path.exists(CSV_FILE):
            try:
                with open(CSV_FILE, "r") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) >= 6:
                            try:
                                feats = [float(x) for x in row[:5]]
                                lbl = str(row[5]).strip()
                                self.dataset.append((feats, lbl))
                            except ValueError:
                                pass
            except Exception as e:
                print(f"Error loading CSV: {e}")

    def update_dataset_stats(self):
        self.total_samples_lbl.config(text=f"Total Samples: {len(self.dataset)}")
        self.classes_listbox.delete(0, tk.END)

        counts = {}
        for _, lbl in self.dataset:
            counts[lbl] = counts.get(lbl, 0) + 1

        for lbl in sorted(counts.keys()):
            self.classes_listbox.insert(tk.END, f"  Sign [{lbl:^3}]  :  {counts[lbl]:4d} samples")

    def undo_last_sample(self):
        if not os.path.exists(CSV_FILE) or not self.dataset:
            messagebox.showinfo("Empty", "Dataset is empty.")
            return

        # Find the last label
        last_label = self.dataset[-1][1]
        if messagebox.askyesno("Undo Last", f"Remove recent samples for sign '{last_label}'?"):
            # Remove all contiguous trailing samples of last_label
            while self.dataset and self.dataset[-1][1] == last_label:
                self.dataset.pop()

            # Rewrite CSV
            with open(CSV_FILE, "w", newline="") as f:
                writer = csv.writer(f)
                for row, lbl in self.dataset:
                    writer.writerow(row + [lbl])

            self.update_dataset_stats()
            self.rec_status_label.config(text=f"Removed samples for '{last_label}'.", fg="#fab387")

    def predict_knn(self, features, k=5):
        """Pure Python fast K-Nearest Neighbors classifier (No scikit-learn required)."""
        if len(self.dataset) < 5:
            return None, 0.0

        # Calculate Euclidean distances
        distances = []
        for x, label in self.dataset:
            dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(features, x)))
            distances.append((dist, label))

        # Sort by distance
        distances.sort(key=lambda item: item[0])
        nearest = distances[:k]

        # Vote
        votes = {}
        for _, lbl in nearest:
            votes[lbl] = votes.get(lbl, 0) + 1

        winner = max(votes, key=votes.get)
        confidence = (votes[winner] / k) * 100.0
        return winner, confidence

    def forward_to_web(self, label, conf, sensors):
        now = time.time()
        # Only forward if label changed or after 1.5 seconds cooldown
        if label != self.last_forwarded_label or (now - self.last_web_forward > 1.5):
            self.last_forwarded_label = label
            self.last_web_forward = now

            def _send():
                try:
                    payload = json.dumps({
                        "label": label,
                        "confidence": int(conf),
                        "sensors": sensors
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        "http://127.0.0.1:5000/api/predict",
                        data=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    urllib.request.urlopen(req, timeout=0.4)
                except Exception:
                    pass

            threading.Thread(target=_send, daemon=True).start()

    def update_gui_loop(self):
        # Update progress bars and numeric labels
        for idx, key in enumerate(FIELDS):
            val = self.current_readings[idx]
            self.sensor_bars[key]["value"] = val
            self.sensor_val_labels[key].config(text=str(val))

        # Live prediction if enabled and connected
        if self.is_connected and self.predict_active.get() and len(self.dataset) >= 5:
            pred_label, conf = self.predict_knn(self.current_readings, k=5)
            if pred_label:
                self.pred_display.config(text=str(pred_label))
                self.pred_confidence.config(
                    text=f"Prediction: '{pred_label}' ({conf:.0f}% confidence)",
                    fg="#a6e3a1" if conf >= 80 else "#fab387"
                )
                self.forward_to_web(pred_label, conf, self.current_readings)
        elif not self.is_connected:
            self.pred_display.config(text="--")
            self.pred_confidence.config(text="Connect ESP32 to test signs", fg="#a6adc8")

        # Schedule next update
        self.root.after(50, self.update_gui_loop)


def main():
    root = tk.Tk()
    app = SignifyGUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.disconnect_serial(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
