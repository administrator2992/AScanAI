import cv2
import queue
import numpy as np
from feature_extractor import FeatureExtractor
import os
import time
import torch
from ultralytics import YOLO
import threading
from collections import deque
import uuid
import json
from pathlib import Path

# --- Worker Configuration ---
# CLASS_NAMES = ["Kue Lapis", "Kue Mangkok", "Lemper", "Pastel", "Wajik"]
CLASS_NAMES = ["Lemper", "Pastel", "Kue Lapis", "Kue Mangkok", "Wajik"]
BOX_COLORS = {
    "Lemper": "#00FF00", "Pastel": "#D2B48C", "Kue Lapis": "#FFFFFF",
    "Kue Mangkok": "#FFC0CB", "Wajik": "#654321"
}

FILTERING_THRESHOLDS = {
    1: { # Camera 1 - Filtering lebih ketat untuk mengurangi background noise
        "min_area_ratio": 0.005, "max_area_ratio": 0.3,  # Lebih ketat untuk background
        "min_aspect_ratio": 0.4, "max_aspect_ratio": 2.5,  # Lebih ketat untuk bentuk aneh
    },
    2: { # Camera 2 - Filtering lebih ketat untuk mengurangi background noise
        "min_area_ratio": 0.005, "max_area_ratio": 0.3,  # Lebih ketat untuk background
        "min_aspect_ratio": 0.4, "max_aspect_ratio": 2.5,  # Lebih ketat untuk bentuk aneh
    },
    3: { # Camera 3 - Filtering lebih ketat untuk mengurangi background noise
        "min_area_ratio": 0.005, "max_area_ratio": 0.3,  # Lebih ketat untuk background
        "min_aspect_ratio": 0.4, "max_aspect_ratio": 2.5,  # Lebih ketat untuk bentuk aneh
    }
}



def hex_to_bgr(hex_color):
    """Converts hex color to a BGR tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (4, 2, 0))

def is_likely_background(box, frame_shape, camera_id):
    """Filters detections based on bounding box properties."""
    frame_h, frame_w = frame_shape
    thresh = FILTERING_THRESHOLDS.get(camera_id, FILTERING_THRESHOLDS[1])

    x1, y1, x2, y2 = box
    box_w, box_h = x2 - x1, y2 - y1
    if box_w <= 0 or box_h <= 0: return True

    frame_area = frame_w * frame_h
    box_area = box_w * box_h
    area_ratio = box_area / frame_area
    if not (thresh["min_area_ratio"] < area_ratio < thresh["max_area_ratio"]):
        return True

    aspect_ratio = box_w / box_h
    if not (thresh["min_aspect_ratio"] < aspect_ratio < thresh["max_aspect_ratio"]):
        return True
    
    # Filter tambahan untuk deteksi background:
    # 1. Deteksi yang terlalu dekat dengan tepi frame (kemungkinan background)
    edge_threshold = 0.05  # 5% dari ukuran frame
    if (x1 < frame_w * edge_threshold or y1 < frame_h * edge_threshold or 
        x2 > frame_w * (1 - edge_threshold) or y2 > frame_h * (1 - edge_threshold)):
        return True
    
    # 2. Deteksi yang terlalu kecil (noise)
    min_pixel_size = 20  # Minimal 20x20 pixel
    if box_w < min_pixel_size or box_h < min_pixel_size:
        return True
    
    # 3. Deteksi yang terlalu besar (kemungkinan background)
    max_pixel_ratio = 0.25  # Maksimal 25% dari frame
    if area_ratio > max_pixel_ratio:
        return True

    return False

def draw_detections(frame, results, scale_x, scale_y):
    """Draws detections on the frame."""
    if not (results and results.boxes):
        return

    for i, box_coords in enumerate(results.boxes.xyxy):
        x1, y1, x2, y2 = [int(c) for c in box_coords]
        cls_id = int(results.boxes.cls[i])
        class_name = CLASS_NAMES[cls_id] if 0 <= cls_id < len(CLASS_NAMES) else "Unknown"
        color = hex_to_bgr(BOX_COLORS.get(class_name, "#FF0000"))

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"{class_name} {results.boxes.conf[i]:.2f}"
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, y1 - h - 5), (x1 + w, y1), color, -1)
        cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

def yolo_inference_thread(camera_id, frames_q, results_q, stop_event, img_size, model_path, confidence, iou, device):
    """Dedicated thread for running Ultralytics YOLO inference."""
    # Load the YOLO model. This is done once per thread.
    try:
        model = YOLO(model_path)
        print(f"[InferThread-{camera_id}] YOLO model loaded successfully from {model_path}")
    except Exception as e:
        print(f"[InferThread-{camera_id}] FATAL: Failed to load YOLO model: {e}")
        return # Stop the thread if the model can't be loaded

    print(f"[InferThread-{camera_id}] Starting...")
    while not stop_event.is_set():
        try:
            frame_id, frame_to_process = frames_q.get(timeout=1)
        except queue.Empty:
            continue

        yolo_results = None
        try:
            # Run inference using the Ultralytics model with settings from the GUI
            results = model.predict(frame_to_process, imgsz=img_size, conf=confidence, iou=iou, verbose=False, device=device)
            # We only expect one image in, so we take the first result object.
            if results:
                yolo_results = results[0]

        except Exception as e:
            print(f"[InferThread-{camera_id}] Error during inference: {e}")
            time.sleep(2) # Avoid spamming on persistent errors

        if yolo_results:
            results_q.put((frame_id, yolo_results))
    print(f"[InferThread-{camera_id}] Stopped.")

def inference_worker(camera_id, video_source, display_queue, control_queue, img_size, model_path, confidence, iou, device):
    """Main worker process for video capture, processing, and display."""
    print(f"[Worker-{camera_id}] Initializing with device: {device}, source: {video_source}")
    feature_extractor = FeatureExtractor()
    stop_event = threading.Event()
    frames_q = queue.Queue(maxsize=30)
    results_q = queue.Queue(maxsize=30)
    thread = threading.Thread(target=yolo_inference_thread, 
                             args=(camera_id, frames_q, results_q, stop_event, img_size, model_path, confidence, iou, device))
    thread.start()

    cap = cv2.VideoCapture(video_source)
    
    # Konfigurasi optimasi untuk OpenCV untuk semua device
    if isinstance(video_source, int):
        try:
            # Konfigurasi buffer dan FPS untuk optimasi performa
            cap.set(cv2.CAP_PROP_FPS, 30)  # Set FPS eksplisit
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Set resolusi optimal
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            print(f"[Worker-{camera_id}] Camera optimizations applied for camera {video_source}")
        except Exception as e:
            print(f"[Worker-{camera_id}] Warning: Could not apply camera optimizations: {e}")
    
    if not cap.isOpened():
        print(f"[Worker-{camera_id}] Error: Cannot open video source {video_source}")
        stop_event.set()
        thread.join()
        return

    frame_id, last_processed_id = 0, -1
    frame_buffer, results_buffer = {}, {}
    last_frame_time = time.time()
    frame_timeout = 5.0  # 5 detik timeout untuk deteksi frame baru

    while not stop_event.is_set():
        try:
            cmd = control_queue.get_nowait()
            if cmd == 'STOP': break
        except queue.Empty:
            pass

        # Cek apakah kamera membeku (tidak ada frame baru dalam waktu tertentu)
        current_time = time.time()
        if isinstance(video_source, int) and current_time - last_frame_time > frame_timeout:
            print(f"[Worker-{camera_id}] Camera freeze detected. Restarting camera...")
            cap.release()
            time.sleep(0.5)  # Tambah delay sebelum restart untuk stabilitas
            cap = cv2.VideoCapture(video_source)
            
            # Terapkan konfigurasi optimasi lagi saat restart
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                print(f"[Worker-{camera_id}] Camera optimizations reapplied after restart")
            except Exception as e:
                print(f"[Worker-{camera_id}] Warning: Could not reapply camera optimizations: {e}")
            
            last_frame_time = current_time
            if not cap.isOpened():
                print(f"[Worker-{camera_id}] Failed to reopen camera {video_source}")
                time.sleep(1)  # Tunggu lebih lama jika gagal membuka
                continue
            print(f"[Worker-{camera_id}] Camera successfully reopened")
        
        ret, frame = cap.read()
        if not ret:
            # Untuk kamera fisik (integer source), jangan restart terlalu sering
            if isinstance(video_source, int):
                print(f"[Worker-{camera_id}] Camera read failed. Waiting before retry...")
                time.sleep(0.1)  # Tunggu sebentar sebelum mencoba lagi
                continue
            else:
                # Untuk file video, restart seperti biasa
                print(f"[Worker-{camera_id}] End of video. Restarting capture.")
                cap.release()
                cap = cv2.VideoCapture(video_source)
                
                # Terapkan konfigurasi optimasi untuk file video juga jika diperlukan
                if device == 0:
                    try:
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        print(f"[Worker-{camera_id}] Buffer optimization applied to video file")
                    except Exception as e:
                        print(f"[Worker-{camera_id}] Warning: Could not apply buffer optimization: {e}")
                continue
        
        # Update waktu frame terakhir ketika berhasil membaca frame
        last_frame_time = current_time

        frame_id += 1
        frame_buffer[frame_id] = frame
        
        # Optimasi: Drop frame jika queue hampir penuh untuk mencegah blocking
        if frames_q.qsize() < 25:  # Hanya masukkan jika queue tidak hampir penuh
            try:
                # Resize dengan interpolasi yang lebih cepat
                resized_frame = cv2.resize(frame, (img_size, img_size), interpolation=cv2.INTER_LINEAR)
                frames_q.put((frame_id, resized_frame), timeout=0.01)  # Timeout singkat untuk mencegah blocking
            except queue.Full:
                print(f"[Worker-{camera_id}] Frames queue full, dropping frame {frame_id}")
                pass  # Drop frame jika queue penuh

        # Ambil hasil inference dengan batasan untuk mencegah blocking
        results_processed = 0
        max_results_per_cycle = 5  # Batasi pemrosesan hasil per cycle
        
        while results_processed < max_results_per_cycle:
            try:
                res_id, yolo_results = results_q.get_nowait()
                results_buffer[res_id] = yolo_results
                results_processed += 1
            except queue.Empty:
                break

        processed_id = -1
        for f_id in sorted(frame_buffer.keys()):
            if f_id in results_buffer:
                processed_id = f_id
                break
        
        if processed_id > last_processed_id:
            last_processed_id = processed_id
            frame_to_process = frame_buffer.pop(processed_id)
            yolo_results = results_buffer.pop(processed_id)
            orig_h, orig_w = frame_to_process.shape[:2]
            scale_x, scale_y = orig_w / img_size, orig_h / img_size

            filtered_results = None
            # The results from model.predict are already scaled to the original image size
            # when using the `source` argument. However, since we are passing a resized
            # numpy array, we must scale the results back manually.
            scaled_results = None
            if yolo_results and len(yolo_results.boxes) > 0:
                # Scale the boxes from the inference size (img_size) back to the original frame size.
                # Work with numpy arrays to avoid tensor issues
                boxes_np = yolo_results.boxes.xyxy.cpu().numpy().copy()
                boxes_np[:, [0, 2]] *= scale_x
                boxes_np[:, [1, 3]] *= scale_y
                
                # Create a simple container for scaled results
                scaled_results = type('ScaledResults', (), {
                    'boxes': type('ScaledBoxes', (), {
                        'xyxy': boxes_np,
                        'conf': yolo_results.boxes.conf.cpu().numpy(),
                        'cls': yolo_results.boxes.cls.cpu().numpy()
                    })()
                })()
                
                # Use scaled_results instead of yolo_results for further processing
                yolo_results = scaled_results

                # Filter out detections that are likely background noise.
                indices_to_keep = []
                for i, box in enumerate(yolo_results.boxes.xyxy):
                    if not is_likely_background(box, (orig_h, orig_w), camera_id):
                        indices_to_keep.append(i)
                
                # Create filtered results with only the kept detections
                if indices_to_keep:
                    filtered_results = type('FilteredResults', (), {
                        'boxes': type('FilteredBoxes', (), {
                            'xyxy': yolo_results.boxes.xyxy[indices_to_keep],
                            'conf': yolo_results.boxes.conf[indices_to_keep],
                            'cls': yolo_results.boxes.cls[indices_to_keep]
                        })()
                    })()
                else:
                    filtered_results = None

            frame_with_detections = frame_to_process.copy()
            simple_results, raw_validation_data = [], []
            if filtered_results:
                draw_detections(frame_with_detections, filtered_results, 1, 1) # Already scaled

                # Step 1: Collect all valid crops from detections
                crops = []
                valid_detections_indices = []
                for i, b in enumerate(filtered_results.boxes.xyxy):
                    x1, y1, x2, y2 = [int(c) for c in b]
                    if y1 < y2 and x1 < x2: # Ensure the crop is valid
                        crops.append(frame_to_process[y1:y2, x1:x2])
                        valid_detections_indices.append(i)

                # Step 2: Extract features untuk expert system (dijalankan di background)
                # Feature extraction akan diproses di thread terpisah untuk tidak mengganggu realtime
                feature_vectors = []
                if crops:
                    try:
                        # Extract features secara batch untuk efisiensi
                        feature_vectors = feature_extractor.extract_features_batch(crops)
                    except Exception as e:
                        print(f"[Worker-{camera_id}] Feature extraction error: {e}")
                        feature_vectors = [None] * len(crops)
                
                # Step 3: Create results dengan feature vectors untuk expert system
                for i in range(len(filtered_results.boxes.xyxy)):
                    box = filtered_results.boxes.xyxy[i]
                    x1, y1, x2, y2 = [int(c) for c in box]
                    class_name = CLASS_NAMES[int(filtered_results.boxes.cls[i])]
                    confidence = filtered_results.boxes.conf[i]
                    cls_idx = int(filtered_results.boxes.cls[i])
                    
                    # Ambil feature vector jika tersedia
                    feature_vector = None
                    if i < len(feature_vectors) and feature_vectors[i] is not None:
                        feature_vector = feature_vectors[i]

                    simple_results.append({
                        'bbox': (x1, y1, x2, y2),
                        'conf': confidence,
                        'cls_idx': cls_idx,
                        'class_name': class_name,
                        'feature_vector': feature_vector  # Include feature untuk expert system
                    })
                    raw_validation_data.append({'box_xyxy': (x1, y1, x2, y2), 'class_name': class_name, 'feature': feature_vector})

            # Optimasi: Cek ukuran queue dan drop data jika perlu untuk mencegah memory buildup
            if display_queue.qsize() < 40:  # Increased from 20 to 40 to match GUI capacity
                try:
                    display_queue.put((camera_id, frame_with_detections, simple_results, raw_validation_data), timeout=0.01)  # Reduced timeout further
                except queue.Full:
                    # Silent drop to reduce log overhead and improve performance
                    pass
            else:
                # Silent drop when queue is full to reduce log overhead
                pass

        # Cleanup buffers
        for key_to_del in [k for k in frame_buffer if k < last_processed_id - 10]:
            del frame_buffer[key_to_del]
            results_buffer.pop(key_to_del, None)

    print(f"[Worker-{camera_id}] Stopping...")
    stop_event.set()
    thread.join()
    cap.release()
    print(f"[Worker-{camera_id}] Stopped.")