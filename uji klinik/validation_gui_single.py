import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
import json
import glob
from typing import Dict, List, Any
from datetime import datetime

class SingleCameraValidationGUI:
    def __init__(self, validation_system):
        self.validation_system = validation_system
        self.current_batch_id = None
        self.current_predictions = {}
        self.batch_files = []
        self.current_batch_index = 0
        
        # GUI elements
        self.root = None
        self.image_label = None
        self.item_tree = None
        self.batch_label = None
        self.navigation_frame = None
        
    def open_validation_window(self):
        if self.root is not None:
            self.root.lift()
            return
        
        self.root = tk.Toplevel()
        self.root.title("Single Camera Validation")
        self.root.geometry("1000x700")
        
        self.setup_ui()
        self.load_available_batches()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Single Camera Validation", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Image display frame
        image_frame = ttk.LabelFrame(main_frame, text="Camera Image")
        image_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.image_label = ttk.Label(image_frame, text="No image loaded")
        self.image_label.pack(expand=True, padx=10, pady=10)
        
        # Batch navigation
        nav_frame = ttk.Frame(main_frame)
        nav_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(nav_frame, text="Batch:").pack(side=tk.LEFT, padx=(0, 5))
        self.batch_label = ttk.Label(nav_frame, text="No batches available")
        self.batch_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.prev_button = ttk.Button(nav_frame, text="Previous", 
                                     command=self.previous_batch)
        self.prev_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.next_button = ttk.Button(nav_frame, text="Next", 
                                     command=self.next_batch)
        self.next_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Detection list frame
        detection_frame = ttk.LabelFrame(main_frame, text="Detections")
        detection_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Treeview for detections
        columns = ("ID", "Class", "Confidence", "Status")
        self.item_tree = ttk.Treeview(detection_frame, columns=columns, show="headings")
        
        for col in columns:
            self.item_tree.heading(col, text=col)
            self.item_tree.column(col, width=100)
        
        self.item_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Bind selection event
        self.item_tree.bind("<<TreeviewSelect>>", self.on_item_select)
        
        # Validation buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(button_frame, text="Mark as Correct", 
                  command=self.mark_as_correct).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Mark as Incorrect", 
                  command=self.mark_as_incorrect).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Save Validation", 
                  command=self.save_validation).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Refresh", 
                  command=self.refresh_batches).pack(side=tk.LEFT, padx=(0, 5))
        
    def load_available_batches(self):
        try:
            # Find all JSON files in validation_data/predictions
            json_pattern = "validation_data/predictions/*.json"
            self.batch_files = glob.glob(json_pattern)
            self.batch_files.sort()
            
            if self.batch_files:
                self.current_batch_index = 0
                self.load_batch(self.batch_files[0])
            else:
                self.batch_label.config(text="No batches available")
                
        except Exception as e:
            print(f"Error loading batches: {e}")
            messagebox.showerror("Error", f"Could not load batches: {e}")
    
    def load_batch(self, json_path):
        try:
            with open(json_path, 'r') as f:
                batch_data = json.load(f)
            
            self.current_batch_id = batch_data.get('batch_id')
            self.current_predictions = batch_data.get('camera_predictions', {})
            
            # Update batch label
            batch_name = os.path.basename(json_path)
            self.batch_label.config(text=f"{batch_name} ({self.current_batch_index + 1}/{len(self.batch_files)})")
            
            # Load and display image
            image_paths = batch_data.get('image_paths', {})
            if '1' in image_paths:
                image_path = image_paths['1']
                self.display_camera_image(image_path)
            else:
                self.image_label.config(text="No image available")
            
            # Populate detection tree
            self.populate_item_tree()
            
        except Exception as e:
            print(f"Error loading batch {json_path}: {e}")
            messagebox.showerror("Error", f"Could not load batch: {e}")
    
    def display_camera_image(self, image_path):
        try:
            # Try multiple possible paths
            possible_paths = [
                image_path,
                os.path.join(os.getcwd(), image_path),
                os.path.abspath(image_path)
            ]
            
            image = None
            used_path = None
            
            for test_path in possible_paths:
                if os.path.exists(test_path):
                    image = cv2.imread(test_path)
                    if image is not None:
                        used_path = test_path
                        break
            
            if image is not None:
                print(f"[DEBUG] ✅ Loaded image: {used_path}")
                
                # Resize image to fit display
                height, width = image.shape[:2]
                max_size = 600
                
                if width > max_size or height > max_size:
                    scale = max_size / max(width, height)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    image = cv2.resize(image, (new_width, new_height))
                
                # Convert to RGB and display
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                image_pil = Image.fromarray(image_rgb)
                image_tk = ImageTk.PhotoImage(image_pil)
                
                self.image_label.configure(image=image_tk)
                self.image_label.image = image_tk
                
            else:
                print(f"[DEBUG] ❌ Failed to load image")
                print(f"[DEBUG] Tried paths: {possible_paths}")
                self.image_label.config(text="Failed to load image")
                
        except Exception as e:
            print(f"Error displaying image: {e}")
            self.image_label.config(text=f"Error loading image: {e}")
    
    def populate_item_tree(self):
        # Clear existing items
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
        
        # Add detections from camera 1
        if '1' in self.current_predictions:
            detections = self.current_predictions['1']
            for i, detection in enumerate(detections):
                class_name = detection.get('class_name', 'Unknown')
                confidence = detection.get('confidence', 0)
                
                item_id = self.item_tree.insert("", "end", values=(
                    i,
                    class_name,
                    f"{confidence:.3f}",
                    "Pending"
                ))
    
    def on_item_select(self, event):
        selection = self.item_tree.selection()
        if selection:
            item = self.item_tree.item(selection[0])
            print(f"Selected detection: {item['values']}")
    
    def mark_as_correct(self):
        selection = self.item_tree.selection()
        if selection:
            for item in selection:
                self.item_tree.set(item, "Status", "Correct")
    
    def mark_as_incorrect(self):
        selection = self.item_tree.selection()
        if selection:
            for item in selection:
                self.item_tree.set(item, "Status", "Incorrect")
    
    def save_validation(self):
        # Collect validation results
        validation_results = {}
        for item in self.item_tree.get_children():
            values = self.item_tree.item(item)['values']
            item_id = values[0]
            status = values[3]
            validation_results[item_id] = status
        
        # Save validation results
        try:
            validation_file = f"validation_data/validations/{self.current_batch_id}_validation.json"
            os.makedirs(os.path.dirname(validation_file), exist_ok=True)
            
            validation_data = {
                "batch_id": self.current_batch_id,
                "timestamp": datetime.now().isoformat(),
                "validation_results": validation_results
            }
            
            with open(validation_file, 'w') as f:
                json.dump(validation_data, f, indent=2)
            
            messagebox.showinfo("Success", "Validation results saved!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not save validation: {e}")
    
    def previous_batch(self):
        if self.batch_files and self.current_batch_index > 0:
            self.current_batch_index -= 1
            self.load_batch(self.batch_files[self.current_batch_index])
    
    def next_batch(self):
        if self.batch_files and self.current_batch_index < len(self.batch_files) - 1:
            self.current_batch_index += 1
            self.load_batch(self.batch_files[self.current_batch_index])
    
    def refresh_batches(self):
        self.load_available_batches()

# Update validation_system.py to use single camera validation GUI
class ValidationInterface:
    def __init__(self, validation_system):
        self.validation_system = validation_system
        self.validation_gui = SingleCameraValidationGUI(validation_system)
    
    def add_validation_controls(self, parent):
        # Add validation controls to parent window
        pass
    
    def open_validation_window(self):
        self.validation_gui.open_validation_window() 