import tkinter as tk
from tkinter import messagebox
import cv2
from PIL import Image, ImageTk
import multiprocessing as mp
import queue
import torch
import json
import numpy as np
from inference_worker import inference_worker # Re-use the worker for detection

# --- Global Configuration ---
SOURCES = [3, 2, 1] # Use the same camera sources as the main app
IMG_SIZE = 640
CALIBRATION_FILE = 'calibration_map.json'
MODEL_PATH = 'best_8625.pt'  # Path to YOLO model
CONFIDENCE = 0.5  # Detection confidence threshold
IOU = 0.5  # IoU threshold for NMS
DEVICE = 0 if torch.cuda.is_available() else "cpu"
print(f"[CalibrationApp] Using device: {DEVICE}")

class CalibrationApp:
    def __init__(self, window):
        self.window = window
        self.window.title("ScanAI - Camera Calibration Tool")
        self.window.geometry("1200x800")
        self.window.configure(bg="#2c3e50")

        # --- State and Data ---
        self.calibration_points = []
        self.frame_buffer = {}
        self.latest_detections = {}

        # --- Multiprocessing Queues ---
        self.display_queue = mp.Queue()
        self.control_queues = [mp.Queue() for _ in SOURCES]
        self.processes = []

        self.setup_ui()
        self.start_workers()
        self.update_frames()

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        # Main frame
        main_frame = tk.Frame(self.window, bg="#2c3e50")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Video frame
        video_frame = tk.Frame(main_frame, bg="#34495e")
        video_frame.pack(fill=tk.BOTH, expand=True)

        self.video_labels = {}
        for i, cam_id in enumerate(SOURCES):
            label = tk.Label(video_frame, text=f'Camera {cam_id}\n(Waiting for feed...)', bg='black', fg='white', font=("Arial", 14))
            label.grid(row=0, column=i, padx=5, pady=5, sticky="nsew")
            self.video_labels[i + 1] = label # Key by camera_id (1, 2, 3)
        video_frame.grid_columnconfigure(list(range(len(SOURCES))), weight=1)
        video_frame.grid_rowconfigure(0, weight=1)

        # Controls frame
        controls_frame = tk.Frame(main_frame, bg="#2c3e50")
        controls_frame.pack(fill=tk.X, pady=10)

        self.capture_button = tk.Button(controls_frame, text="Capture Point", font=("Arial", 14, "bold"), bg="#27ae60", fg="white", command=self.capture_point)
        self.capture_button.pack(side=tk.LEFT, padx=10, pady=5)

        self.save_button = tk.Button(controls_frame, text="Save Calibration File", font=("Arial", 14, "bold"), bg="#2980b9", fg="white", command=self.save_calibration)
        self.save_button.pack(side=tk.LEFT, padx=10, pady=5)

        self.status_label = tk.Label(controls_frame, text="Place a single object in view of all cameras and press 'Capture Point'.", bg="#2c3e50", fg="white", font=("Arial", 12))
        self.status_label.pack(side=tk.RIGHT, padx=10)

    def start_workers(self):
        for i, source in enumerate(SOURCES):
            camera_id = i + 1
            args = (camera_id, source, self.display_queue, self.control_queues[i], IMG_SIZE, MODEL_PATH, CONFIDENCE, IOU, DEVICE)
            process = mp.Process(target=inference_worker, args=args)
            process.start()
            self.processes.append(process)
            print(f"[CALIBRATION] Started process for camera {camera_id}")

    def update_frames(self):
        try:
            while not self.display_queue.empty():
                camera_id, frame, simple_results, _ = self.display_queue.get_nowait()
                self.frame_buffer[camera_id] = frame
                if simple_results:
                    # Store only the most confident detection for calibration
                    if len(simple_results) > 0:
                        best_det = max(simple_results, key=lambda r: r['conf'])
                        self.latest_detections[camera_id] = best_det

            for cam_id_index, label in self.video_labels.items():
                frame = self.frame_buffer.get(cam_id_index)
                if frame is not None:
                    # Draw the latest detection on the frame
                    draw_frame = frame.copy()
                    if cam_id_index in self.latest_detections:
                        det = self.latest_detections[cam_id_index]
                        x1, y1, x2, y2 = det['bbox']
                        center_x, center_y = int((x1 + x2) / 2), int((y1 + y2) / 2)
                        cv2.rectangle(draw_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.circle(draw_frame, (center_x, center_y), 5, (0, 0, 255), -1)
                        cv2.putText(draw_frame, f"Center: ({center_x}, {center_y})", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                    img = cv2.cvtColor(draw_frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(img)
                    img_tk = ImageTk.PhotoImage(image=img)
                    label.config(image=img_tk)
                    label.image = img_tk

        except queue.Empty:
            pass
        finally:
            self.window.after(30, self.update_frames)

    def capture_point(self):
        if len(self.latest_detections) != len(SOURCES):
            messagebox.showwarning("Capture Error", f"Could not detect an object in all {len(SOURCES)} cameras. Please ensure the object is clearly visible in all feeds.")
            return

        point_data = {}
        for cam_id, det in self.latest_detections.items():
            x1, y1, x2, y2 = det['bbox']
            center_x, center_y = int((x1 + x2) / 2), int((y1 + y2) / 2)
            point_data[f'cam_{cam_id}'] = {'coords': [center_x, center_y]}
        
        self.calibration_points.append(point_data)
        num_points = len(self.calibration_points)
        self.status_label.config(text=f"Captured Point {num_points}. Move the object to a new location or save the file.")
        messagebox.showinfo("Point Captured", f"Successfully captured Point #{num_points}.\nData: {json.dumps(point_data)}")

    def save_calibration(self):
        if not self.calibration_points:
            messagebox.showerror("Save Error", "No calibration points have been captured. Please capture at least one point before saving.")
            return

        try:
            with open(CALIBRATION_FILE, 'w') as f:
                json.dump(self.calibration_points, f, indent=4)
            messagebox.showinfo("Save Successful", f"Calibration data for {len(self.calibration_points)} points saved to {CALIBRATION_FILE}")
            self.on_closing()
        except Exception as e:
            messagebox.showerror("Save Error", f"An error occurred while saving the file: {e}")

    def on_closing(self):
        print("[CALIBRATION] Closing application...")
        for q in self.control_queues:
            q.put("STOP")
        for p in self.processes:
            p.join(timeout=2)
            if p.is_alive():
                p.terminate()
        self.window.destroy()

if __name__ == '__main__':
    try:
        mp.set_start_method('spawn', force=True)
    except RuntimeError:
        pass
    
    root = tk.Tk()
    app = CalibrationApp(root)
    root.mainloop()
