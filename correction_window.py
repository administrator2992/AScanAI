import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import json
from PIL import Image, ImageTk
import cv2
import numpy as np

from feature_bank import FeatureBank

CLASS_NAMES = ["Lemper", "Pastel", "Kue Lapis", "Kue Mangkok", "Wajik"]

class CorrectionWindow:
    def __init__(self, parent, feature_bank):
        self.parent = parent
        self.feature_bank = feature_bank
        self.snapshot_dir = Path("validation_data")
        self.snapshot_paths = []
        self.current_snapshot_index = -1

        self.window = tk.Toplevel(parent)
        self.window.title("User Correction")
        self.window.geometry("1000x800")

        self.canvas = tk.Canvas(self.window, bg="#2c3e50")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.load_snapshots()
        if not self.snapshot_paths:
            messagebox.showinfo("Info", "No snapshots found for correction.", parent=self.window)
            self.window.destroy()
            return
        
        self.load_next_snapshot()

        # --- UI Controls ---
        btn_frame = tk.Frame(self.window)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        self.save_button = ttk.Button(btn_frame, text="Save & Next", command=self.save_corrections_and_next)
        self.save_button.pack(side=tk.LEFT, expand=True, padx=20)

        self.skip_button = ttk.Button(btn_frame, text="Skip", command=self.load_next_snapshot)
        self.skip_button.pack(side=tk.RIGHT, expand=True, padx=20)

    def load_snapshots(self):
        """Load all available snapshot directories."""
        self.snapshot_paths = sorted([p for p in self.snapshot_dir.iterdir() if p.is_dir()])
        print(f"[Correction] Found {len(self.snapshot_paths)} snapshots to correct.")

    def load_next_snapshot(self):
        """Load and display the next available snapshot for correction."""
        self.current_snapshot_index += 1
        if self.current_snapshot_index >= len(self.snapshot_paths):
            messagebox.showinfo("Complete", "All snapshots have been corrected!", parent=self.window)
            self.window.destroy()
            return

        self.clear_canvas()
        snapshot_path = self.snapshot_paths[self.current_snapshot_index]
        self.display_snapshot(snapshot_path)

    def display_snapshot(self, snapshot_path):
        """Display the image and detection data from a single snapshot."""
        try:
            image_path = snapshot_path / "frame.jpg"
            detections_path = snapshot_path / "detections.json"

            if not image_path.exists() or not detections_path.exists():
                print(f"[Correction] Skipping invalid snapshot: {snapshot_path.name}")
                self.load_next_snapshot()
                return

            # Load image
            frame = cv2.imread(str(image_path))
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            self.photo = ImageTk.PhotoImage(image=img)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

            # Load detections
            with open(detections_path, 'r') as f:
                self.current_snapshot_data = json.load(f)

            self.detection_widgets = []
            for det in self.current_snapshot_data['detections']:
                x1, y1, x2, y2 = det['box_xyxy']
                original_class = det['class_name']

                # Draw bounding box
                self.canvas.create_rectangle(x1, y1, x2, y2, outline="#1abc9c", width=2)

                # Create dropdown for class correction
                class_var = tk.StringVar(value=original_class)
                dropdown = ttk.Combobox(self.window, textvariable=class_var, values=CLASS_NAMES, state='readonly')
                self.canvas.create_window(x1, y1 - 30, anchor=tk.NW, window=dropdown)

                self.detection_widgets.append({
                    'dropdown': dropdown,
                    'original_class': original_class,
                    'feature': np.array(det['feature'])
                })

        except Exception as e:
            print(f"[Correction] Error loading snapshot {snapshot_path.name}: {e}")
            self.load_next_snapshot()

    def clear_canvas(self):
        """Clear all items from the canvas."""
        self.canvas.delete("all")

    def save_corrections_and_next(self):
        """Save the user's corrections to the feature bank and load the next snapshot."""
        for widget_info in self.detection_widgets:
            selected_class = widget_info['dropdown'].get()
            original_class = widget_info['original_class']

            if selected_class != original_class:
                feature_vector = widget_info['feature']
                self.feature_bank.add_feature(selected_class, feature_vector)
                print(f"[Correction] Feature for '{original_class}' moved to '{selected_class}'.")
        
        # Clean up the processed snapshot directory (optional, but good practice)
        snapshot_path = self.snapshot_paths[self.current_snapshot_index]
        try:
            for file in snapshot_path.iterdir():
                file.unlink()
            snapshot_path.rmdir()
        except Exception as e:
            print(f"[Correction] Could not clean up snapshot {snapshot_path.name}: {e}")

        self.load_next_snapshot()
