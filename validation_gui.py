import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
from typing import Dict, List, Optional, Any
from validation_system import ValidationSystem, ValidationInterface
import cv2
import numpy as np
from PIL import Image, ImageTk
import os # Added for file existence check

class ValidationWindow:
    """Validation window for manual review of food detection results"""
    
    def __init__(self, parent, validation_interface: ValidationInterface):
        self.parent = parent
        self.validation_interface = validation_interface
        self.window = None
        self.current_image = None
        self.current_predictions = None
        self.current_batch_id = None
        self.validation_items = []
        
    def show_validation_window(self):
        """Display the validation window"""
        if self.window is not None:
            self.window.lift()
            return
            
        self.window = tk.Toplevel(self.parent)
        self.window.title("Food Detection Validation")
        self.window.geometry("1200x800")
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
        
        self.setup_validation_ui()
        self.load_pending_validations()
        
    def setup_validation_ui(self):
        """Setup the validation user interface"""
        # Main container
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel - Image and controls
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Image display - Sekarang untuk 3 kamera
        self.image_frame = ttk.LabelFrame(left_frame, text="Detection Results - Multi Camera")
        self.image_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Kamera Utama (60%)
        self.image_label_1 = ttk.Label(self.image_frame, text="Camera 1")
        self.image_label_1.pack(expand=True, fill=tk.BOTH, pady=5)
        
        # Kamera Bawah (20% x 2)
        bottom_frame = ttk.Frame(self.image_frame)
        bottom_frame.pack(fill=tk.X, pady=5)
        
        self.image_label_2 = ttk.Label(bottom_frame, text="Camera 2")
        self.image_label_2.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 5))
        
        self.image_label_3 = ttk.Label(bottom_frame, text="Camera 3")
        self.image_label_3.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=(5, 0))
        
        # Simpan referensi label untuk pembaruan
        self.image_labels = {1: self.image_label_1, 2: self.image_label_2, 3: self.image_label_3}
        self.tk_image_refs = {1: None, 2: None, 3: None}
        
        # Control buttons
        control_frame = ttk.Frame(left_frame)
        control_frame.pack(fill=tk.X)
        
        ttk.Button(control_frame, text="Load Next Batch", 
                  command=self.load_next_batch).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(control_frame, text="Complete Batch", 
                  command=self.complete_current_batch).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(control_frame, text="Statistics", 
                  command=self.show_statistics).pack(side=tk.LEFT)
        
        # Right panel - Validation controls
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_frame.config(width=400)
        
        # Validation queue
        queue_frame = ttk.LabelFrame(right_frame, text="Validation Queue")
        queue_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.queue_listbox = tk.Listbox(queue_frame, height=6)
        self.queue_listbox.pack(fill=tk.X, padx=5, pady=5)
        self.queue_listbox.bind('<<ListboxSelect>>', self.on_batch_select)
        
        # Item validation
        item_frame = ttk.LabelFrame(right_frame, text="Item Validation")
        item_frame.pack(fill=tk.BOTH, expand=True)
        
        # Item list
        ttk.Label(item_frame, text="Detected Items:").pack(anchor=tk.W, padx=5, pady=(5, 0))
        
        self.item_tree = ttk.Treeview(item_frame, columns=('Class', 'Confidence'), show='tree headings', height=8)
        self.item_tree.heading('#0', text='Item')
        self.item_tree.heading('Class', text='Class')
        self.item_tree.heading('Confidence', text='Confidence')
        self.item_tree.column('#0', width=60)
        self.item_tree.column('Class', width=100)
        self.item_tree.column('Confidence', width=80)
        self.item_tree.pack(fill=tk.X, padx=5, pady=5)
        self.item_tree.bind('<<TreeviewSelect>>', self.on_item_select)
        
        # Validation controls
        validation_control_frame = ttk.Frame(item_frame)
        validation_control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Validation type
        ttk.Label(validation_control_frame, text="Validation Type:").pack(anchor=tk.W)
        self.validation_type = tk.StringVar(value="confirm")
        
        validation_types = [
            ("Confirm Correct", "confirm"),
            ("Correct Class", "correct"),
            ("False Positive", "false_positive"),
            ("Add Missing Item", "add_missing")
        ]
        
        for text, value in validation_types:
            ttk.Radiobutton(validation_control_frame, text=text, 
                           variable=self.validation_type, value=value).pack(anchor=tk.W)
        
        # Class correction
        ttk.Label(validation_control_frame, text="Correct Class (if applicable):").pack(anchor=tk.W, pady=(10, 0))
        self.correct_class = ttk.Combobox(validation_control_frame, 
                                         values=["Lemper", "Pastel", "Kue Lapis", "Kue Mangkok", "Wajik"])
        self.correct_class.pack(fill=tk.X, pady=(0, 5))
        
        # Confidence rating
        ttk.Label(validation_control_frame, text="Confidence Rating (1-5):").pack(anchor=tk.W)
        self.confidence_rating = tk.Scale(validation_control_frame, from_=1, to=5, orient=tk.HORIZONTAL)
        self.confidence_rating.set(5)
        self.confidence_rating.pack(fill=tk.X)
        
        # Notes
        ttk.Label(validation_control_frame, text="Notes:").pack(anchor=tk.W, pady=(5, 0))
        self.notes_text = tk.Text(validation_control_frame, height=3)
        self.notes_text.pack(fill=tk.X)
        
        # Submit validation
        ttk.Button(validation_control_frame, text="Submit Validation", 
                  command=self.submit_validation).pack(pady=(10, 0))
        
    def load_pending_validations(self):
        """Load pending validation batches"""
        pending_batches = self.validation_interface.get_validation_queue()
        
        self.queue_listbox.delete(0, tk.END)
        for batch in pending_batches:
            display_text = f"Batch {batch['batch_id'][:8]} - {batch['total_items']} items (Conf: {batch['avg_confidence']:.2f})"
            self.queue_listbox.insert(tk.END, display_text)
            
    def on_batch_select(self, event):
        """Handle batch selection from queue"""
        selection = self.queue_listbox.curselection()
        if not selection:
            return
            
        # Get pending batches and select the chosen one
        pending_batches = self.validation_interface.get_validation_queue()
        if selection[0] < len(pending_batches):
            self.load_batch(pending_batches[selection[0]])
            
    def load_batch(self, batch_data: Dict):
        """Load a specific batch for validation"""
        print(f"[DEBUG] Loading batch: {batch_data.get('batch_id', 'unknown')}")
        print(f"[DEBUG] Image paths: {batch_data.get('image_paths', {})}")
        
        self.current_batch_id = batch_data['batch_id']
        self.current_predictions = batch_data.get('camera_predictions', {})  # Sekarang dictionary per kamera
        
        # Load and display images for all cameras
        image_paths = batch_data.get('image_paths', {})
        
        for cam_id in [1, 2, 3]:
            try:
                image_path = image_paths.get(cam_id)
                if image_path:
                    # Solusi langsung: coba semua kemungkinan path tanpa "uji klinik"
                    possible_paths = [
                        image_path,  # Path asli dari JSON
                        os.path.join(os.getcwd(), image_path),  # Path absolut
                        os.path.abspath(image_path)  # Path absolut lengkap
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
                        print(f"[DEBUG] ✅ Loaded image for camera {cam_id}: {used_path}")
                        self.display_camera_image_with_detections(cam_id, image, self.current_predictions.get(cam_id, []))
                    else:
                        print(f"[DEBUG] ❌ Failed to load image for camera {cam_id}")
                        print(f"[DEBUG] Tried paths: {possible_paths}")
                        self.image_labels[cam_id].configure(text=f"Camera {cam_id}: Failed to load image")
                else:
                    print(f"[DEBUG] No image path for camera {cam_id}")
                    self.image_labels[cam_id].configure(text=f"Camera {cam_id}: No image available")
            except Exception as e:
                print(f"[DEBUG] Error loading camera {cam_id}: {e}")
                self.image_labels[cam_id].configure(text=f"Camera {cam_id}: Error - {str(e)}")
        
        self.populate_item_tree()
            
    def display_camera_image_with_detections(self, camera_id: int, image: np.ndarray, predictions: List[Dict]):
        """Display image with detection overlays for a specific camera"""
        if image is None:
            return
            
        # Define a fixed display area size
        display_width = 350
        display_height = 200

        # Create a working copy of the image
        img_to_process = image.copy()
        
        # Get original image dimensions for scaling calculations
        orig_h, orig_w = img_to_process.shape[:2]

        # Resize the base image
        display_image = cv2.resize(img_to_process, (display_width, display_height), interpolation=cv2.INTER_AREA)

        # Calculate new scaling ratios
        if orig_w == 0 or orig_h == 0:
            print(f"[ERROR] Camera {camera_id}: Original image has zero width or height.")
            return
            
        ratio_w = display_width / orig_w
        ratio_h = display_height / orig_h
        
        # Draw detection results, scaled to the new display_image
        for i, prediction in enumerate(predictions):
            class_name = prediction['class_name']
            confidence = prediction['confidence']
            bgr = (0, 255, 0) if confidence > 0.7 else (0, 255, 255) # Green/Yellow

            # Draw polygon if it exists, scaled to the new display size
            if 'segmentation_polygon' in prediction and prediction['segmentation_polygon'] is not None:
                poly_orig = np.array(prediction['segmentation_polygon'], dtype=np.int32)
                poly_scaled = poly_orig.copy().astype(np.float32)
                poly_scaled[:, 0] *= ratio_w
                poly_scaled[:, 1] *= ratio_h
                
                overlay = display_image.copy()
                cv2.fillPoly(overlay, [poly_scaled.astype(np.int32)], bgr)
                display_image = cv2.addWeighted(overlay, 0.4, display_image, 0.6, 0)

            # Scale and draw bounding box
            bbox_orig = prediction['bounding_box']
            x1_s = int(bbox_orig[0] * ratio_w)
            y1_s = int(bbox_orig[1] * ratio_h)
            x2_s = int(bbox_orig[2] * ratio_w)
            y2_s = int(bbox_orig[3] * ratio_h)
            cv2.rectangle(display_image, (x1_s, y1_s), (x2_s, y2_s), bgr, 2)
            
            # Draw the label
            label = f"{class_name} {confidence:.2f}"
            font_scale = 0.4
            thickness = 1
            (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
            
            # Draw a filled rectangle behind the text for better visibility
            cv2.rectangle(display_image, (x1_s, y1_s - text_h - 5), (x1_s + text_w, y1_s), bgr, -1)
            cv2.putText(display_image, label, (x1_s, y1_s - 4), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness, cv2.LINE_AA)
        
        # Convert to PhotoImage and display
        display_image = cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(display_image)
        
        photo = ImageTk.PhotoImage(pil_image)
        self.image_labels[camera_id].configure(image=photo, text="")
        self.tk_image_refs[camera_id] = photo  # Keep a reference
        
    def display_image_with_detections(self):
        """Display image with detection overlays - DEPRECATED, use display_camera_image_with_detections"""
        # Fungsi ini dipertahankan untuk kompatibilitas tapi tidak digunakan lagi
        pass
        
    def populate_item_tree(self):
        """Populate the item tree with current predictions from all cameras"""
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
            
        # Gabungkan semua prediksi dari semua kamera
        all_predictions = []
        for cam_id, predictions in self.current_predictions.items():
            for i, prediction in enumerate(predictions):
                prediction_copy = prediction.copy()
                prediction_copy['camera_id'] = cam_id
                prediction_copy['item_id'] = f"Cam{cam_id}_Item{i+1}"
                all_predictions.append(prediction_copy)
        
        for i, prediction in enumerate(all_predictions):
            item_id = prediction['item_id']
            class_name = prediction['class_name']
            confidence = f"{prediction['confidence']:.3f}"
            camera_id = prediction['camera_id']
            
            # Color code by confidence
            tags = ('low_conf',) if prediction['confidence'] < 0.7 else ('high_conf',)
            
            self.item_tree.insert('', 'end', text=item_id, 
                                 values=(f"{class_name} (Cam{camera_id})", confidence), tags=tags)
        
        # Configure tags
        self.item_tree.tag_configure('low_conf', background='#ffeeee')
        self.item_tree.tag_configure('high_conf', background='#eeffee')
        
    def on_item_select(self, event):
        """Handle item selection in tree"""
        selection = self.item_tree.selection()
        if not selection:
            return
            
        # Get selected item index
        item = self.item_tree.selection()[0]
        item_index = self.item_tree.index(item)
        
        # Gabungkan semua prediksi dari semua kamera (sama seperti di populate_item_tree)
        all_predictions = []
        for cam_id, predictions in self.current_predictions.items():
            for i, prediction in enumerate(predictions):
                prediction_copy = prediction.copy()
                prediction_copy['camera_id'] = cam_id
                prediction_copy['item_id'] = f"Cam{cam_id}_Item{i+1}"
                all_predictions.append(prediction_copy)
        
        # Pre-fill validation form with current prediction
        if item_index < len(all_predictions):
            prediction = all_predictions[item_index]
            self.correct_class.set(prediction['class_name'])
            
    def submit_validation(self):
        """Submit validation for selected item"""
        selection = self.item_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an item to validate")
            return
            
        item_index = self.item_tree.index(selection[0])
        validation_type = self.validation_type.get()
        validated_class = self.correct_class.get() if validation_type == "correct" else None
        confidence_rating = self.confidence_rating.get()
        notes = self.notes_text.get("1.0", tk.END).strip()
        
        success = self.validation_interface.submit_validation(
            item_index, validation_type, validated_class, confidence_rating, notes
        )
        
        if success:
            # Mark item as validated in tree
            item = self.item_tree.selection()[0]
            self.item_tree.set(item, 'Class', f"{self.item_tree.set(item, 'Class')} ✓")
            messagebox.showinfo("Success", "Validation submitted successfully")
            
            # Clear form
            self.notes_text.delete("1.0", tk.END)
        else:
            messagebox.showerror("Error", "Failed to submit validation")
            
    def load_next_batch(self):
        """Load the next batch for validation"""
        self.load_pending_validations()
        if self.queue_listbox.size() > 0:
            self.queue_listbox.selection_set(0)
            self.on_batch_select(None)
        else:
            messagebox.showinfo("Info", "No pending validations available")
            
    def complete_current_batch(self):
        """Mark current batch as completed"""
        if self.current_batch_id:
            self.validation_interface.complete_batch_validation()
            messagebox.showinfo("Success", "Batch marked as completed")
            self.current_batch_id = None
            self.current_predictions = None
            self.load_pending_validations()
        else:
            messagebox.showwarning("Warning", "No batch currently loaded")
            
    def show_statistics(self):
        """Show validation statistics"""
        stats = self.validation_interface.get_validation_stats()
        
        stats_window = tk.Toplevel(self.window)
        stats_window.title("Validation Statistics")
        stats_window.geometry("400x300")
        
        stats_text = tk.Text(stats_window, wrap=tk.WORD)
        stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        stats_content = f"""Validation System Statistics

Total Predictions: {stats['total_predictions']}
Pending Validations: {stats['pending_validations']}
Completed Validations: {stats['completed_validations']}
Active Sessions: {stats['active_sessions']}

Validation Progress: {stats['completed_validations']}/{stats['total_predictions']} ({(stats['completed_validations']/max(stats['total_predictions'], 1)*100):.1f}%)
"""
        
        stats_text.insert(tk.END, stats_content)
        stats_text.config(state=tk.DISABLED)
        
    def close_window(self):
        """Close the validation window"""
        self.window.destroy()
        self.window = None

class ValidationIntegration:
    """Integration class for adding validation to existing GUI"""
    
    def __init__(self, main_gui):
        self.main_gui = main_gui
        # Use the validation_data directory in the current working directory
        self.validation_system = ValidationSystem("validation_data")
        self.validation_interface = ValidationInterface(self.validation_system)
        self.validation_window = None
        self.validation_mode = None  # Will be set in add_validation_controls
        
        # Start validation session
        self.validation_interface.start_validation_session()
        
    def add_validation_controls(self, parent_window):
        """Add validation controls to existing GUI"""
        validation_frame = tk.Frame(parent_window, bg='#2c3e50', width=176, height=768)
        validation_frame.place(x=1024, y=0)
        validation_frame.pack_propagate(False)
        
        # Validation mode toggle
        self.validation_mode = tk.BooleanVar()
        validation_toggle = tk.Checkbutton(
            validation_frame, text="Validation Mode", 
            variable=self.validation_mode,
            bg='#2c3e50', fg='white', selectcolor='#34495e',
            command=self.toggle_validation_mode
        )
        validation_toggle.pack(pady=5)
        
        # Open validation window button
        validation_btn = tk.Button(
            validation_frame, text="Open Validation",
            command=self.open_validation_window,
            bg='#e74c3c', fg='white', font=('Arial', 10, 'bold')
        )
        validation_btn.pack(pady=5)
        
        # Quick validation stats
        self.stats_label = tk.Label(
            validation_frame, text="Stats: Loading...",
            bg='#2c3e50', fg='white', font=('Arial', 8)
        )
        self.stats_label.pack(pady=5)
        
        # Update stats periodically
        self.update_stats_display()
        
    def is_validation_mode_active(self) -> bool:
        """Check if validation mode is currently active."""
        # Pastikan self.validation_mode sudah diinisialisasi
        if hasattr(self, 'validation_mode'):
            return self.validation_mode.get()
        return False

    def toggle_validation_mode(self):
        """Toggle validation mode on/off"""
        self.validation_interface.validation_mode = self.validation_mode.get()
        
    def open_validation_window(self):
        """Open the validation window"""
        if self.validation_window is None:
            self.validation_window = ValidationWindow(self.main_gui, self.validation_interface)
        self.validation_window.show_validation_window()
        
    def process_all_camera_detections_for_validation(self, camera_data: Dict[int, Dict[str, Any]]):
        """Process detection results from all cameras for validation."""
        if self.is_validation_mode_active():
            # Panggil metode di ValidationInterface yang sudah kita ubah
            batch_id = self.validation_interface.process_multicamera_detection_results(
                camera_data
            )
            return batch_id
        return None
        
    def update_stats_display(self):
        """Update the stats display"""
        try:
            stats = self.validation_interface.get_validation_stats()
            stats_text = f"Pending: {stats['pending_validations']}\nCompleted: {stats['completed_validations']}"
            self.stats_label.config(text=stats_text)
        except Exception as e:
            # More detailed error handling
            print(f"Stats error: {str(e)}")
            self.stats_label.config(text="Stats: Error")
        
        # Schedule next update
        self.main_gui.after(5000, self.update_stats_display)  # Update every 5 seconds