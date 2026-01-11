import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import threading
import time
import os
import sys
import json
import uuid
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from inference_worker import InferenceWorker
from validation_system import ValidationSystem
from validation_gui_single import ValidationInterface

class SingleCameraGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ScanAI - Single Camera Detection")
        self.root.geometry("1200x800")
        
        # Video capture
        self.cap = None
        self.is_running = False
        
        # Detection data
        self.current_detections = []
        self.detection_buffer = []
        
        # Validation system
        self.validation_system = ValidationSystem()
        self.validation_interface = ValidationInterface(self.validation_system)
        
        # GUI elements
        self.video_label = None
        self.status_label = None
        self.detection_label = None
        self.validation_button = None
        
        # Inference worker
        self.inference_worker = None
        self.display_queue = None
        
        self.setup_ui()
        self.setup_validation_controls()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="ScanAI - Single Camera Detection", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Video display frame
        video_frame = ttk.Frame(main_frame)
        video_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Video label
        self.video_label = ttk.Label(video_frame, text="No camera connected", 
                                    font=("Arial", 12))
        self.video_label.pack(expand=True)
        
        # Control frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Camera selection
        camera_frame = ttk.LabelFrame(control_frame, text="Camera Settings")
        camera_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(camera_frame, text="Camera Source:").pack(side=tk.LEFT, padx=(10, 5))
        self.camera_var = tk.StringVar(value="0")
        camera_combo = ttk.Combobox(camera_frame, textvariable=self.camera_var, 
                                   values=["0", "1", "2", "3"], width=10)
        camera_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        # Start/Stop button
        self.start_button = ttk.Button(camera_frame, text="Start Camera", 
                                      command=self.toggle_camera)
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Status label
        self.status_label = ttk.Label(camera_frame, text="Status: Ready")
        self.status_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Detection info frame
        detection_frame = ttk.LabelFrame(main_frame, text="Detection Information")
        detection_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.detection_label = ttk.Label(detection_frame, text="No detections")
        self.detection_label.pack(padx=10, pady=5)
        
        # Validation button
        self.validation_button = ttk.Button(main_frame, text="Open Validation Window", 
                                          command=self.open_validation_window)
        self.validation_button.pack(pady=(0, 10))
        
    def setup_validation_controls(self):
        try:
            self.validation_interface.add_validation_controls(self.root)
        except Exception as e:
            print(f"Warning: Could not setup validation controls: {e}")
    
    def toggle_camera(self):
        if not self.is_running:
            self.start_camera()
        else:
            self.stop_camera()
    
    def start_camera(self):
        try:
            camera_id = int(self.camera_var.get())
            self.cap = cv2.VideoCapture(camera_id)
            
            if not self.cap.isOpened():
                messagebox.showerror("Error", f"Could not open camera {camera_id}")
                return
            
            self.is_running = True
            self.start_button.config(text="Stop Camera")
            self.status_label.config(text="Status: Running")
            
            # Start inference worker
            self.start_inference_worker()
            
            # Start GUI update
            self.update_gui()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start camera: {e}")
    
    def stop_camera(self):
        self.is_running = False
        self.start_button.config(text="Start Camera")
        self.status_label.config(text="Status: Stopped")
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        if self.inference_worker:
            self.inference_worker.stop()
            self.inference_worker = None
    
    def start_inference_worker(self):
        try:
            from multiprocessing import Queue
            self.display_queue = Queue()
            
            self.inference_worker = InferenceWorker(
                camera_id=int(self.camera_var.get()),
                display_queue=self.display_queue
            )
            self.inference_worker.start()
            
        except Exception as e:
            print(f"Error starting inference worker: {e}")
    
    def update_gui(self):
        if not self.is_running:
            return
        
        # Check for new data from inference worker
        if self.display_queue and not self.display_queue.empty():
            try:
                data = self.display_queue.get_nowait()
                
                if 'frame' in data:
                    # Display frame
                    frame = data['frame']
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_pil = Image.fromarray(frame_rgb)
                    frame_tk = ImageTk.PhotoImage(frame_pil)
                    
                    self.video_label.configure(image=frame_tk)
                    self.video_label.image = frame_tk
                
                if 'detections' in data:
                    # Update detections
                    self.current_detections = data['detections']
                    self.update_detection_display()
                
                if 'raw_validation_data' in data:
                    # Process validation data
                    self.process_validation_data(data['raw_validation_data'])
                
            except Exception as e:
                print(f"Error processing inference data: {e}")
        
        # Schedule next update
        self.root.after(30, self.update_gui)
    
    def update_detection_display(self):
        if not self.current_detections:
            self.detection_label.config(text="No detections")
            return
        
        detection_text = f"Detected {len(self.current_detections)} objects:\n"
        for i, detection in enumerate(self.current_detections):
            class_name = detection.get('class_name', 'Unknown')
            confidence = detection.get('confidence', 0)
            detection_text += f"{i+1}. {class_name} ({confidence:.2f})\n"
        
        self.detection_label.config(text=detection_text)
    
    def process_validation_data(self, raw_data):
        try:
            # Save prediction batch for validation
            batch_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            # Extract data for single camera
            image = raw_data.get('image')
            detections = raw_data.get('detections', [])
            
            if image is not None:
                # Save image
                image_path = f"validation_data/predictions/{batch_id}_cam_1.jpg"
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                cv2.imwrite(image_path, image)
                
                # Save prediction data
                prediction_data = {
                    "batch_id": batch_id,
                    "timestamp": timestamp,
                    "image_paths": {"1": image_path},
                    "model_version": "yolo11n-seg(v1)",
                    "camera_predictions": {"1": detections}
                }
                
                json_path = f"validation_data/predictions/{batch_id}.json"
                with open(json_path, 'w') as f:
                    json.dump(prediction_data, f, indent=2)
                
                print(f"Saved validation batch: {batch_id}")
                
        except Exception as e:
            print(f"Error processing validation data: {e}")
    
    def open_validation_window(self):
        try:
            self.validation_interface.open_validation_window()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open validation window: {e}")
    
    def on_closing(self):
        self.stop_camera()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = SingleCameraGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main() 