from pathlib import Path
import datetime
import torch
import json
import numpy as np
import cv2
from tkinter import Tk, Canvas, Button, PhotoImage, messagebox, Label
from PIL import Image, ImageTk
import os
import multiprocessing as mp
import queue
import math
import tkinter as tk
import time
import gc

from feature_bank import FeatureBank
from camera_logic import CameraLogic
from correction_window import CorrectionWindow
from inference_worker import inference_worker
from expert_system_manager import ExpertSystemManager

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

def cosine_similarity(v1, v2):
    """Menghitung cosine similarity antara dua vektor."""
    if v1 is None or v2 is None:
        return 0.0
    # Pastikan v1 dan v2 adalah numpy array dan normalisasikan
    v1 = np.array(v1, dtype=np.float32)
    v2 = np.array(v2, dtype=np.float32)
    
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0 # Hindari pembagian dengan nol
        
    return np.dot(v1, v2) / (norm_v1 * norm_v2)

# === Konstanta untuk Tracking ===
EMA_ALPHA = 0.7
MAX_FRAMES_TO_LIVE = 5
SIMILARITY_THRESHOLD = 0.8
BBOX_EMA_ALPHA = 0.3

# === Konfigurasi Global ===
# --- Konfigurasi Input Video ---
# Ganti dengan sumber video Anda (0, 1, 2 untuk kamera, atau path ke file video)
# SOURCES = [
#     'output_videos/camera_1.mp4',
#     'output_videos/camera_2.mp4',
#     'output_videos/camera_3.mp4',
# ]

SOURCES = [ #3
    2,
    1,
]

# --- Konfigurasi Model ---
MODEL_PATH = "best.pt" # Ganti dengan model Anda
IMG_SIZE = 640
CONFIDENCE = 0.6
IOU = 0.5
MASK_ALPHA = 0.4
DEVICE = 0 if torch.cuda.is_available() else "cpu"  # Menggunakan CPU untuk performa yang lebih konsisten
print(f"[GUI] Using device: {DEVICE}")

# --- Konfigurasi UI ---
# CLASS_NAMES = ["Kue Lapis", "Kue Mangkok", "Lemper", "Pastel", "Wajik"]
CLASS_NAMES = ["Lemper", "Pastel", "Kue Lapis", "Kue Mangkok", "Wajik"]
PRICES = {"Lemper": 2500, "Pastel": 10000, "Kue Lapis": 15000, "Kue Mangkok": 3000, "Wajik": 8000}
BASE_PATH = Path(__file__).parent
ASSETS_PATH = BASE_PATH / "assets" / "frame0"

# --- Fungsi Utilitas ---
def relative_to_assets(fn: str) -> str:
    return str(ASSETS_PATH / fn)

def format_currency(x: int) -> str:
    return f"IDR {x:,}".replace(",", ".")

# === Kelas Orkestrator Utama ===
class MainApp:
    def __init__(self, window):
        self.window = window
        self.root = window  # Tambahkan referensi untuk konsistensi
        self.window.geometry("1024x768")
        self.window.configure(bg="#FFFAF2")
        self.window.resizable(False, False)

        # Inisialisasi antrian untuk komunikasi antar proses dengan ukuran terbatas
        self.display_queue = mp.Queue(maxsize=50)  # Increased back to 50 for better throughput
        self.control_queues = [mp.Queue() for _ in SOURCES]

        self.processes = []
        
        # Performance monitoring
        self.last_performance_check = time.time()
        self.frame_count = 0
        self.performance_interval = 10.0  # Check performance setiap 10 detik
        
        # --- Variabel untuk Pelacakan Objek ---
        # Menggunakan dictionary dengan location_id sebagai kunci untuk pelacakan yang robust.
        self.tracked_objects = {} # Key: location_id, Value: detection_dict
        self.detection_buffer = {}  # Buffer for detections from each camera
        self.raw_data_buffer = {}   # Buffer for raw data for validation
        self.frame_buffer = {}      # Buffer for the original frames for saving
        
        # --- Variabel untuk Koreksi Kelas dengan Penundaan 150ms ---
        self.class_conflict_buffer = {}  # Key: location_id, Value: {pending_class, timestamp, original_class}
        self.class_correction_delay = 0.1  # 100ms delay untuk koreksi kelas (dipercepat dari 150ms)
        
        # --- Toggle untuk Automatic Correction ---
        self.automatic_correction_enabled = True  # Default aktif
        
        # --- Variabel untuk Sinkronisasi Kamera ---
        self.camera_sync_buffer = {}  # Buffer untuk sinkronisasi frame dari semua kamera
        self.camera_timestamps = {}   # Timestamp untuk setiap kamera
        self.sync_window_ms = 50      # Window sinkronisasi 50ms (lebih ketat untuk real-time)
        self.expected_cameras = set(range(1, len(SOURCES) + 1))  # Set kamera yang diharapkan
        self.max_wait_time = 100      # Maksimal tunggu 100ms untuk kamera lain (lebih cepat)
        
        # ID unik global untuk setiap objek fisik yang terdeteksi.
        self.next_global_id = 0

        # Inisialisasi CameraLogic sebagai pusat koordinator
        # Initialize the core logic components
        self.feature_bank = FeatureBank()
        self.expert_system = ExpertSystemManager(self.feature_bank)
        self.camera_logic = CameraLogic(self.feature_bank)
        
        # Start expert system background thread
        self.expert_system.start()
        print("[GUI] Expert system started in background")

        self.setup_ui()
        self.start_inference_processes()
        self.update_gui()

    def setup_ui(self):
        self.canvas = Canvas(self.window, width=1024, height=768, bg="#FFFAF2", bd=0, highlightthickness=0)
        self.canvas.place(x=0, y=0)
        
        # Load aset gambar
        self.bg1 = PhotoImage(file=relative_to_assets("image_1.png"))
        self.canvas.create_image(512, 384, image=self.bg1)

        # === Tata Letak Bingkai Video ===
        # Kamera Utama (60%)
        self.video_label_1 = Label(self.window, bg="black")
        self.video_label_1.place(x=30, y=90, width=500, height=225)
        # Kamera Bawah (20% x 2)
        self.video_label_2 = Label(self.window, bg="black")
        self.video_label_2.place(x=30, y=325, width=245, height=140)
        self.video_label_3 = Label(self.window, bg="black")
        self.video_label_3.place(x=285, y=325, width=245, height=140)
        
        # Simpan referensi label untuk pembaruan
        self.video_labels = {1: self.video_label_1, 2: self.video_label_2, 3: self.video_label_3}
        self.tk_image_refs = {1: None, 2: None, 3: None}

        # Sisa UI (keranjang, tombol, dll.)
        self.setup_cart_ui()

        # Inisialisasi ulang semua elemen UI yang hilang
        self.bg2 = PhotoImage(file=relative_to_assets("image_2.png"))
        self.ci = PhotoImage(file=relative_to_assets("image_9.png"))
        self.btn_img = PhotoImage(file=relative_to_assets("button_1.png"))
        self.colom_count_img = PhotoImage(file=relative_to_assets("image_11.png"))
        payment_icons = [PhotoImage(file=relative_to_assets(fn)) for fn in ["image_4.png","image_5.png","image_6.png","image_7.png","image_8.png"]]

        self.canvas.create_image(512, 45, image=self.bg2)
        self.canvas.create_text(60, 578, anchor="nw", text="Pilih Metode Pembayaran:", fill="#745540", font=("Heebo Medium", -20))
        for (x, y), img in zip([(92,644),(201,644),(321,644),(91,708),(201,708)], payment_icons):
            self.canvas.create_image(x, y, image=img)

        self.canvas.create_rectangle(577, 90, 1024, 768, fill="#553526", outline="")
        self.canvas.create_image(769, 120, image=self.ci)
        self.canvas.create_text(800, 105, anchor="nw", text="Cart", fill="#DBA576", font=("FamiljenGrotesk Bold", -24))

        self.current_order_id = 1
        self.order_id_text = self.canvas.create_text(645, 155, anchor="nw", text=f"Order #[{self.current_order_id:04d}] --:--:--", fill="#FFFFFF", font=("microsoft sans serif", -20))

        checkout_button = Button(self.window, image=self.btn_img, bd=0, highlightthickness=0, relief="flat", command=self.on_checkout)
        checkout_button.place(x=394, y=629, width=136, height=47)
        checkout_button.bind("<Enter>", lambda e: checkout_button.config(cursor="hand2"))

        self.count_id_text = self.canvas.create_text(60, 534, anchor="nw", text="Jumlah Item: [0]", fill="#745540", font=("Heebo Medium", -20))
        footer_y = 710
        self.canvas.create_text(590, footer_y, anchor="nw", text="Total", fill="#FFFFFF", font=("microsoft sans serif", -30))
        self.price_id_text = self.canvas.create_text(1010, footer_y, anchor="ne", text="IDR 0", fill="#FFFFFF", font=("microsoft sans serif", -32))
        self.cart_item_ids = []

        # Button to open the new correction window
        self.validate_button = tk.Button(
            self.window,
            text="Correct Detections",
            command=self.open_correction_window,
            bg="#e67e22", fg="white", font=("Inter", 12, "bold")
        )
        self.validate_button.place(x=10, y=670, width=250, height=40)
        
        # Toggle button untuk automatic correction
        self.auto_correction_button = tk.Button(
            self.window,
            text="Auto Correction: ON",
            command=self.toggle_automatic_correction,
            bg="#27ae60", fg="white", font=("Inter", 10, "bold")
        )
        self.auto_correction_button.place(x=270, y=670, width=180, height=40)

        self.window.resizable(False, False)

    def setup_cart_ui(self):
        # Fungsi ini sekarang digabungkan ke dalam setup_ui
        pass

    def start_inference_processes(self):
        for i, source in enumerate(SOURCES):
            camera_id = i + 1
            args = (
                camera_id, source, self.display_queue, self.control_queues[i], 
                IMG_SIZE, MODEL_PATH, CONFIDENCE, IOU, DEVICE
            )
            process = mp.Process(target=inference_worker, args=args)
            process.start()
            self.processes.append(process)
            print(f"Started process {process.pid} for camera {camera_id}")

    def update_gui(self):
        """Loop GUI utama dengan sinkronisasi kamera. Mengambil frame, menampilkannya, dan menjalankan pelacakan."""
        import time
        current_time = time.time() * 1000  # Konversi ke milidetik
        
        # Ambil data dari antrian dengan batasan untuk mencegah blocking
        new_data_received = False
        processed_count = 0
        max_process_per_cycle = 40  # Increased from 20 to 40 to handle higher throughput
        
        while processed_count < max_process_per_cycle:
            try:
                camera_id, frame, simple_results, raw_data = self.display_queue.get_nowait()
                
                # Simpan data dengan timestamp untuk sinkronisasi
                self.camera_sync_buffer[camera_id] = {
                    'frame': frame,
                    'simple_results': simple_results,
                    'raw_data': raw_data,
                    'timestamp': current_time
                }
                self.camera_timestamps[camera_id] = current_time
                new_data_received = True
                processed_count += 1
                
                # Display frame segera untuk responsivitas UI
                # Inisialisasi frame counter per kamera jika belum ada
                if not hasattr(self, 'camera_frame_counters'):
                    self.camera_frame_counters = {}
                if camera_id not in self.camera_frame_counters:
                    self.camera_frame_counters[camera_id] = 0
                
                self.camera_frame_counters[camera_id] += 1
                
                # Tampilkan setiap frame kedua per kamera untuk performance
                if self.camera_frame_counters[camera_id] % 2 == 0:
                    self.display_frame(camera_id, frame)
            
            except queue.Empty:
                break
        
        # Proses sinkronisasi kamera - tunggu semua kamera dalam window waktu yang sama
        synchronized_data = self._get_synchronized_camera_data(current_time)
        
        if synchronized_data:
            # Reset buffer kamera untuk data yang sudah diproses
            for cam_id in synchronized_data.keys():
                if cam_id in self.camera_sync_buffer:
                    del self.camera_sync_buffer[cam_id]
            
            # Update deteksi dari semua kamera yang tersinkronisasi
            self.camera_logic.all_camera_detections.clear()  # Reset deteksi lama
            
            for cam_id, data in synchronized_data.items():
                # Buffer data untuk snapshot
                self.frame_buffer[cam_id] = data['frame']
                self.raw_data_buffer[cam_id] = data['raw_data']
                
                # Update deteksi ke camera logic
                if data['simple_results']:
                    self.camera_logic.update_detections(cam_id, data['simple_results'])
            
            # Jalankan konsensus hanya setelah semua kamera tersinkronisasi
            final_detections, should_save_snapshot = self.camera_logic.process_and_get_consensus()

            # Skip snapshot saving untuk realtime performance
            # Snapshot operations terlalu berat untuk realtime
            # if should_save_snapshot:
            #     self._save_snapshot_for_review()

            # Update tracking dan keranjang
            if final_detections:
                self.track_and_update_cart(final_detections)
        
        # Skip heavy performance monitoring untuk realtime
        # Hanya lakukan cleanup ringan jika diperlukan
        if len(self.camera_sync_buffer) > 100:  # Simple cleanup threshold
            self.camera_sync_buffer.clear()
        
        # Monitor expert system stats setiap 5 detik
        stats_time = time.time()
        if hasattr(self, 'last_expert_stats_time'):
            if stats_time - self.last_expert_stats_time > 5.0:  # 5 detik
                stats = self.expert_system.get_stats()
                print(f"[Expert] Stats - Processed: {stats['processed_count']}, Queue: {stats['queue_size']}, Cache: {stats['cache_size']}, Running: {stats['is_running']}")
                self.last_expert_stats_time = stats_time
        else:
            self.last_expert_stats_time = stats_time
        
        # Jadwalkan pembaruan GUI berikutnya dengan interval realtime
        # Gunakan interval 10ms (~100 FPS) untuk maksimal realtime performance
        self.root.after(10, self.update_gui)

    def _get_synchronized_camera_data(self, current_time):
        """
        Mengambil data kamera yang tersinkronisasi dalam window waktu yang sama.
        Mengembalikan data dari kamera yang memiliki timestamp dalam window sinkronisasi.
        """
        if not self.camera_sync_buffer:
            return None
        
        # Cari timestamp terlama dalam buffer
        oldest_timestamp = min(data['timestamp'] for data in self.camera_sync_buffer.values())
        
        # Cek apakah ada data dari semua kamera dalam window sinkronisasi
        synchronized_cameras = {}
        cameras_in_window = set()
        
        for cam_id, data in self.camera_sync_buffer.items():
            time_diff = abs(data['timestamp'] - oldest_timestamp)
            if time_diff <= self.sync_window_ms:
                cameras_in_window.add(cam_id)
                synchronized_cameras[cam_id] = data
        
        # Strategi sinkronisasi:
        # 1. Jika semua kamera tersedia dalam window, gunakan semua
        # 2. Jika minimal 2 kamera tersedia dan window sudah cukup lama, proses
        # 3. Jika hanya 1 kamera dan sudah timeout, proses tetap
        
        time_since_oldest = current_time - oldest_timestamp
        
        # Kondisi untuk memproses data (lebih responsif untuk real-time):
        should_process = False
        
        if len(cameras_in_window) == len(self.expected_cameras):
            # Semua kamera tersedia - proses segera
            should_process = True
        elif len(cameras_in_window) >= 2 and time_since_oldest > self.max_wait_time:
            # Minimal 2 kamera dan sudah melewati batas maksimal - proses
            should_process = True
        elif len(cameras_in_window) >= 1 and time_since_oldest > self.max_wait_time * 1.2:
            # Minimal 1 kamera dan sudah timeout - proses lebih cepat (dikurangi dari 1.5 ke 1.2)
            should_process = True
        
        if should_process:
            # Clear processed data from buffer
            for cam_id in list(synchronized_cameras.keys()):
                if cam_id in self.camera_sync_buffer:
                    del self.camera_sync_buffer[cam_id]
            return synchronized_cameras
        
        return None

    def track_and_update_cart(self, final_detections):
        """
        Melakukan pelacakan objek berdasarkan lokasi fisik yang stabil.
        - Memberikan ID unik pada objek yang muncul di lokasi baru.
        - Memperbarui kelas objek jika berubah di lokasi yang sama.
        - Menghitung jumlah objek per lokasi berdasarkan kelas yang berbeda.
        - Tetap melacak objek meski ada kamera offline.
        """
        # Kelompokkan deteksi berdasarkan location_id
        detections_by_location = {}
        for det in final_detections:
            loc_id = det['location_id']
            if loc_id not in detections_by_location:
                detections_by_location[loc_id] = []
            detections_by_location[loc_id].append(det)
        
        current_location_ids = set(detections_by_location.keys())
        tracked_location_ids = set(self.tracked_objects.keys())
        
        # Inisialisasi timestamp untuk logika penundaan
        import time
        current_time = time.time()

        # --- Langkah 1: Update objek di lokasi yang terdeteksi ---
        for loc_id, detections in detections_by_location.items():
            if loc_id not in self.tracked_objects:
                self.tracked_objects[loc_id] = {}
            
            # Kelompokkan deteksi berdasarkan kelas di lokasi ini
            detections_by_class = {}
            for det in detections:
                if det.get('cls_idx', -1) == -1:
                    continue # Lewati deteksi 'unknown'
                cls_idx = det['cls_idx']
                if cls_idx not in detections_by_class:
                    detections_by_class[cls_idx] = []
                detections_by_class[cls_idx].append(det)
            
            # Update atau tambah objek berdasarkan kelas dengan logika penundaan koreksi
            for cls_idx, class_detections in detections_by_class.items():
                # Ambil deteksi dengan confidence tertinggi untuk kelas ini
                best_detection = max(class_detections, key=lambda x: x['conf'])
                
                # Cari objek yang sudah ada di lokasi ini (tidak peduli kelas)
                existing_obj_key = None
                existing_obj = None
                for obj_key, obj in self.tracked_objects[loc_id].items():
                    existing_obj_key = obj_key
                    existing_obj = obj
                    break  # Ambil objek pertama di lokasi ini
                
                if existing_obj_key:
                    # Ada objek di lokasi ini
                    if existing_obj['cls_idx'] == cls_idx:
                        # Kelas sama - update langsung
                        if best_detection['conf'] > existing_obj['conf']:
                            existing_obj.update(best_detection)
                            existing_obj['id'] = existing_obj['id']  # Pertahankan ID
                        # Hapus konflik yang mungkin ada karena kelas sudah cocok
                        if loc_id in self.class_conflict_buffer:
                            del self.class_conflict_buffer[loc_id]
                    else:
                        # Kelas berbeda - implementasi logika penundaan 250ms
                        self._handle_class_conflict(loc_id, existing_obj, best_detection, current_time)
                else:
                    # Tidak ada objek di lokasi ini - tambah objek baru
                    self.next_global_id += 1
                    obj_id = f"item-{self.next_global_id}"
                    best_detection['id'] = obj_id
                    self.tracked_objects[loc_id][obj_id] = best_detection

        # --- Langkah 2: Hapus lokasi yang tidak terdeteksi dalam waktu lama ---
        # Implementasi timeout untuk menghapus objek yang hilang
        
        # Tambahkan timestamp untuk objek baru
        for loc_id in current_location_ids:
            if loc_id in self.tracked_objects:
                for obj_id, obj in self.tracked_objects[loc_id].items():
                    obj['last_seen'] = current_time
        
        # Hapus objek yang tidak terlihat lebih dari 10 detik
        locations_to_remove = []
        for loc_id in tracked_location_ids:
            if loc_id not in current_location_ids:
                # Cek apakah ada objek yang sudah lama tidak terlihat
                objects_to_remove = []
                if loc_id in self.tracked_objects:
                    for obj_id, obj in self.tracked_objects[loc_id].items():
                        if current_time - obj.get('last_seen', current_time) > 30:  # 30 detik timeout (diperpanjang dari 10 detik)
                            objects_to_remove.append(obj_id)
                    
                    # Hapus objek yang timeout
                    for obj_id in objects_to_remove:
                        del self.tracked_objects[loc_id][obj_id]
                    
                    # Hapus lokasi jika kosong
                    if not self.tracked_objects[loc_id]:
                        locations_to_remove.append(loc_id)
        
        for loc_id in locations_to_remove:
            del self.tracked_objects[loc_id]
        
        # --- Langkah 3: Proses konflik kelas yang tertunda ---
        self._process_pending_class_conflicts(current_time)

        self.update_cart_ui()
    
    def _handle_class_conflict(self, loc_id, existing_obj, new_detection, current_time):
        """
        Menangani konflik kelas di lokasi yang sama dengan penundaan 250ms.
        Jika lokasi sama tapi kelas berbeda, tunggu 250ms sebelum koreksi.
        """
        if loc_id not in self.class_conflict_buffer:
            # Konflik baru - mulai penundaan
            self.class_conflict_buffer[loc_id] = {
                'pending_class': new_detection['cls_idx'],
                'pending_detection': new_detection.copy(),
                'timestamp': current_time,
                'original_class': existing_obj['cls_idx'],
                'original_obj_id': existing_obj['id']
            }
            pass
        else:
            # Konflik sudah ada - update deteksi pending jika confidence lebih tinggi
            conflict_data = self.class_conflict_buffer[loc_id]
            if new_detection['conf'] > conflict_data['pending_detection']['conf']:
                conflict_data['pending_detection'] = new_detection.copy()
                conflict_data['pending_class'] = new_detection['cls_idx']
    
    def _process_pending_class_conflicts(self, current_time):
        """
        Memproses konflik kelas yang sudah menunggu lebih dari 250ms.
        Jika masih berbeda setelah 250ms, lakukan koreksi kelas.
        """
        conflicts_to_resolve = []
        
        for loc_id, conflict_data in self.class_conflict_buffer.items():
            time_elapsed = current_time - conflict_data['timestamp']
            
            if time_elapsed >= self.class_correction_delay:
                conflicts_to_resolve.append(loc_id)
        
        for loc_id in conflicts_to_resolve:
            conflict_data = self.class_conflict_buffer[loc_id]
            
            # Cek apakah objek masih ada di lokasi ini
            if loc_id in self.tracked_objects:
                for obj_id, obj in self.tracked_objects[loc_id].items():
                    if obj['id'] == conflict_data['original_obj_id']:
                        # Koreksi kelas objek dengan deteksi yang pending
                        pending_detection = conflict_data['pending_detection']
                        old_class = obj['cls_idx']
                        new_class = pending_detection['cls_idx']
                        
                        # Update objek dengan kelas baru
                        obj.update(pending_detection)
                        obj['id'] = conflict_data['original_obj_id']  # Pertahankan ID asli
                        
                        pass
                        break
            
            # Hapus konflik yang sudah diproses
            del self.class_conflict_buffer[loc_id]

    def update_cart_ui(self):
        """Fungsi terpisah untuk hanya menggambar ulang UI keranjang."""
        # Hapus item keranjang lama
        for iid in self.cart_item_ids:
            self.canvas.delete(iid)
        self.cart_item_ids.clear()
        
        # Kelompokkan objek berdasarkan kelas - HITUNG SEMUA OBJEK TERDETEKSI
        class_counts = {}  # {cls_idx: {'name': str, 'qty': int, 'best_conf': float, 'locations': set}}
        total_items = 0
        
        for loc_id, objects_dict in self.tracked_objects.items():
            for obj_id, obj in objects_dict.items():
                cls_idx = obj['cls_idx']
                conf = obj.get('conf', 0)
                
                if cls_idx not in class_counts:
                    class_counts[cls_idx] = {
                        'name': CLASS_NAMES[cls_idx] if cls_idx < len(CLASS_NAMES) else 'Unknown',
                        'qty': 0,  # Mulai dari 0, akan ditambah per objek
                        'best_conf': conf,
                        'locations': set(),
                        'best_obj_id': obj['id']
                    }
                
                # Tambah qty untuk setiap objek yang terdeteksi
                class_counts[cls_idx]['qty'] += 1
                class_counts[cls_idx]['locations'].add(loc_id)
                
                # Simpan objek dengan confidence tertinggi untuk setiap kelas
                if conf > class_counts[cls_idx]['best_conf']:
                    class_counts[cls_idx]['best_conf'] = conf
                    class_counts[cls_idx]['best_obj_id'] = obj['id']
        
        # Total items = jumlah semua objek yang terdeteksi
        total_items = sum(class_data['qty'] for class_data in class_counts.values())
        
        # Perbarui jumlah item total
        self.canvas.itemconfigure(self.count_id_text, text=f"Jumlah Item: [{total_items}]")
    
        total_price = 0
        y0, dy = 200, 80
        
        # Tampilkan item berdasarkan kelas yang dikelompokkan
        for i, (cls_idx, class_data) in enumerate(class_counts.items()):
            name = class_data['name']
            qty = class_data['qty']
            unit = PRICES.get(name, 0)
            price = qty * unit
            total_price += price
            y = y0 + i * dy
            
            # Tampilkan informasi lokasi dan confidence terbaik
            locations_str = ', '.join([f"Loc-{loc}" for loc in sorted(class_data['locations'])])
            conf_info = f"Conf: {class_data['best_conf']:.2f}"
            display_name = f"{name} ({locations_str}) - {conf_info}"

            self.cart_item_ids += [
                self.canvas.create_text(590, y, anchor="nw", text=display_name, fill="#ffffff", font=("microsoft sans serif", -16)),
                self.canvas.create_text(590, y+22, anchor="nw", text=format_currency(unit), fill="#ffffff", font=("microsoft sans serif", -18)),
                self.canvas.create_image(825, y+22, image=self.colom_count_img),
                self.canvas.create_text(817.5, y+10, anchor="nw", text=str(qty), fill="#ffffff", font=("microsoft sans serif", -20)),
                self.canvas.create_text(1010, y+10, anchor="ne", text=format_currency(price), fill="#ffffff", font=("microsoft sans serif", -18))
            ]
        self.canvas.itemconfigure(self.price_id_text, text=format_currency(total_price))



    def display_frame(self, camera_id, frame):
        """Menampilkan sebuah frame pada label video yang sesuai dengan optimasi performance."""
        target_label = self.video_labels.get(camera_id)
        if target_label:
            try:
                w, h = target_label.winfo_width(), target_label.winfo_height()
                if w > 1 and h > 1:
                    # Optimasi: resize dengan interpolasi yang lebih cepat
                    frame_resized = cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)
                    
                    # Optimasi: konversi color yang lebih efisien
                    img_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(img_rgb)
                    
                    # Cleanup referensi lama untuk mencegah memory leak
                    old_ref = self.tk_image_refs.get(camera_id)
                    if old_ref:
                        del old_ref
                    
                    imgtk = ImageTk.PhotoImage(image=img)
                    target_label.configure(image=imgtk)
                    self.tk_image_refs[camera_id] = imgtk
                    
                    pass
                else:
                    pass
            except Exception as e:
                 print(f"[GUI] Error displaying frame for camera {camera_id}: {e}")
        else:
            pass

    def _check_performance_and_cleanup(self):
        """Monitor performance dan lakukan cleanup untuk mencegah memory leak."""
        current_time = time.time()
        self.frame_count += 1
        
        if current_time - self.last_performance_check > self.performance_interval:
            fps = self.frame_count / self.performance_interval
            queue_size = self.display_queue.qsize() if hasattr(self.display_queue, 'qsize') else 0
            
            # Cleanup memory jika diperlukan
            if queue_size > 80:  # Jika queue hampir penuh
                gc.collect()
            
            # Reset counters
            self.last_performance_check = current_time
            self.frame_count = 0
            
            # Cleanup old tracked objects (objek yang tidak terdeteksi > 30 detik)
            objects_to_remove = []
            for loc_id, objects_dict in self.tracked_objects.items():
                if not objects_dict:  # Jika dictionary kosong
                    objects_to_remove.append(loc_id)
            
            for loc_id in objects_to_remove:
                del self.tracked_objects[loc_id]

    def _save_snapshot_for_review(self):
        """Saves the frames and detection data from the last processed cycle for user review."""
        import uuid
        # Use the data stored in the buffers from the last cycle
        if not self.frame_buffer or not self.raw_data_buffer:
            return

        snapshot_id = str(uuid.uuid4())
        snapshot_dir = Path("validation_data") / snapshot_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # This will now save a multi-camera snapshot
        all_detections_for_json = []
        for cam_id, frame in self.frame_buffer.items():
            # Save the frame from this camera's perspective
            cv2.imwrite(str(snapshot_dir / f"frame_cam_{cam_id}.jpg"), frame)

            # Add this camera's detections to the list
            if cam_id in self.raw_data_buffer:
                for det in self.raw_data_buffer[cam_id]:
                    det_copy = det.copy()
                    det_copy['feature'] = det_copy['feature'].tolist()
                    det_copy['detection_id'] = f"cam{cam_id}_{uuid.uuid4().hex[:6]}"
                    det_copy['camera_id'] = cam_id # Add camera_id to each detection
                    all_detections_for_json.append(det_copy)

        # Also save current tracked objects data
        tracked_objects_data = []
        for loc_id, objects_dict in self.tracked_objects.items():
            for obj_id, obj in objects_dict.items():
                # Konversi numpy types ke Python native types untuk JSON serialization
                bbox = obj.get('bbox', [])
                if hasattr(bbox, 'tolist'):
                    bbox = bbox.tolist()
                elif isinstance(bbox, (list, tuple)):
                    bbox = [float(x) if hasattr(x, 'item') else x for x in bbox]
                
                confidence = obj['conf']
                if hasattr(confidence, 'item'):
                    confidence = confidence.item()
                
                cls_idx = obj['cls_idx']
                if hasattr(cls_idx, 'item'):
                    cls_idx = cls_idx.item()
                
                tracked_objects_data.append({
                    'id': obj['id'],
                    'location_id': loc_id,
                    'class_idx': int(cls_idx),
                    'class_name': CLASS_NAMES[int(cls_idx)] if int(cls_idx) < len(CLASS_NAMES) else 'Unknown',
                    'bbox': bbox,
                    'confidence': float(confidence)
                })

        snapshot_data = {
            'snapshot_id': snapshot_id,
            'detections': all_detections_for_json,
            'tracked_objects': tracked_objects_data
        }

        with open(snapshot_dir / "detections.json", "w") as f:
            json.dump(snapshot_data, f, indent=4)

        pass
        # Clear buffers after saving to prevent re-saving the same data
        self.frame_buffer.clear()
        self.raw_data_buffer.clear()

    def on_checkout(self):
        """Fungsi yang dipanggil saat tombol checkout ditekan."""
        self.current_order_id += 1
        now = datetime.datetime.now().strftime("%d %b %Y %H:%M:%S")
        self.canvas.itemconfigure(self.order_id_text, text=f"Order #[{self.current_order_id:04d}] {now}")
        messagebox.showinfo("Transaksi", f"Order #{self.current_order_id:04d} Berhasil", parent=self.window)

    def open_correction_window(self):
        """Opens the new user correction window.""" 
        try:
            # Pass the main window and the feature bank instance
            CorrectionWindow(self.window, self.feature_bank)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open correction window: {e}", parent=self.window)
            print(f"[ERROR] Failed to open CorrectionWindow: {e}")
    
    def toggle_automatic_correction(self):
        """Toggle automatic correction on/off untuk mengurangi beban komputasi."""
        self.automatic_correction_enabled = not self.automatic_correction_enabled
        
        # Update tampilan tombol
        if self.automatic_correction_enabled:
            self.auto_correction_button.config(
                text="Auto Correction: ON",
                bg="#27ae60"  # Hijau untuk aktif
            )
            print("[GUI] Automatic correction enabled")
        else:
            self.auto_correction_button.config(
                text="Auto Correction: OFF",
                bg="#e74c3c"  # Merah untuk nonaktif
            )
            print("[GUI] Automatic correction disabled")
        
        # Update camera logic dengan status toggle
        if hasattr(self, 'camera_logic'):
            self.camera_logic.set_automatic_correction(self.automatic_correction_enabled)


    def on_closing_without_confirmation(self):
        """Helper to clean up and destroy without asking for confirmation."""
        print("Stopping child processes...")
        
        # Force save feature bank sebelum shutdown
        if hasattr(self, 'feature_bank'):
            self.feature_bank.force_save()
            print("[GUI] Feature bank force saved")
        
        # Stop expert system first
        if hasattr(self, 'expert_system'):
            self.expert_system.stop()
            print("[GUI] Expert system stopped")
        
        for q in self.control_queues:
            q.put('STOP')
        for p in self.processes:
            p.join(timeout=2) # Tunggu proses selesai
            if p.is_alive():
                p.terminate() # Paksa berhenti jika macet
        self.window.destroy()

    def on_closing(self):
        # Sementara hapus protocol handler untuk mencegah masalah re-entry
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing_without_confirmation)

        if messagebox.askokcancel("Keluar", "Apakah Anda ingin keluar dari aplikasi?"):
            # Jika pengguna mengonfirmasi, lanjutkan dengan menghentikan proses dan menghancurkan jendela
            self.on_closing_without_confirmation()
        else:
            # Jika pengguna membatalkan, ikat kembali protocol handler asli
            self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

if __name__ == "__main__":
    mp.set_start_method('spawn', force=True)
    root = Tk()
    app = MainApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
