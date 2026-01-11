from pathlib import Path
import datetime
import numpy as np
import cv2
from tkinter import Tk, Canvas, Button, PhotoImage, messagebox, Label
from PIL import Image, ImageTk
import sys
import os
import multiprocessing as mp
import queue
import math

# Tambahkan path untuk import modul dari direktori lain
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from validation_system import ValidationSystem, ValidationInterface
from validation_gui import ValidationIntegration
from inference_worker import inference_worker
from camera_logic import combine_detections, cosine_similarity

# === Konfigurasi Global ===
# --- Konfigurasi Input Video ---
# Ganti dengan sumber video Anda (0, 1, 2 untuk kamera, atau path ke file video)
# SOURCES = [
#     'assets/Video_Makanan_Berputar_Derajat.mp4',
#     'assets/Video_Makanan_Berputar_Derajat.mp4',
#     'assets/Video_Makanan_Berputar_Derajat.mp4',
# ]

SOURCES = [
    3,
    1,
    5,
]

# --- Konfigurasi Model ---
MODEL_PATH = "../Hasil/yolo11n-seg(v1)/weights/best_rknn_model" # Ganti dengan model Anda
IMG_SIZE = 640
CONFIDENCE = 0.5
IOU = 0.45
MASK_ALPHA = 0.4

# --- Konfigurasi UI ---
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
        self.window.geometry("1200x768")
        self.window.configure(bg="#FFFAF2")
        self.window.resizable(False, False)

        # Inisialisasi antrian untuk komunikasi antar proses
        self.display_queue = mp.Queue()
        self.control_queues = [mp.Queue() for _ in SOURCES]

        self.processes = []
        
        # --- Variabel untuk Pelacakan Objek ---
        self.tracked_objects = [] # List of dicts, e.g., {"id": "2.1", "cls_idx": 2, ...}
        self.detection_buffer = {} # Buffer untuk menampung deteksi dari setiap kamera
        self.raw_data_buffer = {} # Buffer untuk data mentah validasi

        # Inisialisasi validation integration di awal
        try:
            self.validation_integration = ValidationIntegration(self.window)
        except Exception as e:
            print(f"Warning: Could not initialize validation integration: {e}")
            self.validation_integration = None

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

        # Integrasi Sistem Validasi (akan digunakan nanti)
        # self.validation_integration = ValidationIntegration(self.window)
        # self.validation_integration.add_validation_controls(self.window)
        
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

        # Mengaktifkan kembali integrasi validasi
        if self.validation_integration:
            try:
                self.validation_integration.add_validation_controls(self.window)
            except Exception as e:
                print(f"Warning: Could not add validation controls: {e}")

    def setup_cart_ui(self):
        # Fungsi ini sekarang digabungkan ke dalam setup_ui
        pass

    def start_inference_processes(self):
        for i, source in enumerate(SOURCES):
            camera_id = i + 1
            args = (
                camera_id, source, self.display_queue, self.control_queues[i], 
                MODEL_PATH, IMG_SIZE, CONFIDENCE
            )
            process = mp.Process(target=inference_worker, args=args)
            process.start()
            self.processes.append(process)
            print(f"Started process {process.pid} for camera {camera_id}")

    def update_gui(self):
        """Loop GUI utama. Mengambil frame, menampilkannya, dan menjalankan pelacakan."""
        # Kuras antrian untuk mendapatkan data terbaru
        while not self.display_queue.empty():
            try:
                # Sekarang unpack 4 item
                camera_id, frame, simple_results, raw_data = self.display_queue.get_nowait()
                
                self.display_frame(camera_id, frame)
                
                # Simpan deteksi dan data mentah terbaru untuk kamera ini
                self.detection_buffer[camera_id] = simple_results
                self.raw_data_buffer[camera_id] = raw_data

            except (queue.Empty, ValueError): # ValueError jika unpack gagal
                break
        
        # Jika mode validasi aktif, proses buffer untuk validasi.
        # Kita hanya proses jika buffer sudah terisi untuk semua kamera.
        if self.validation_integration and self.validation_integration.is_validation_mode_active():
            print(f"[DEBUG] Validation mode active. Buffer size: {len(self.raw_data_buffer)}/{len(SOURCES)}")
            if len(self.raw_data_buffer) == len(SOURCES):
                print(f"[DEBUG] Processing validation data for cameras: {list(self.raw_data_buffer.keys())}")
                batch_id = self.validation_integration.process_all_camera_detections_for_validation(self.raw_data_buffer)
                print(f"[DEBUG] Validation batch created: {batch_id}")
                # Kosongkan buffer setelah diproses untuk mencegah pengiriman berulang
                self.raw_data_buffer.clear()

        # Gabungkan deteksi dari buffer menggunakan logika baru
        final_detections = combine_detections(self.detection_buffer)

        # Jalankan logika pelacakan dan perbarui keranjang dengan hasil yang sudah difilter
        self.track_and_update_cart(final_detections)
        
        self.window.after(100, self.update_gui) # Diperlambat karena OSNet butuh waktu

    def track_and_update_cart(self, all_detections):
        """
        Versi OSNet: Algoritma pelacakan berbasis kemiripan fitur visual.
        """
        SIMILARITY_THRESHOLD = 0.85 # Ambang batas kemiripan (bisa disesuaikan)
        
        unmatched_detections = list(all_detections)
        updated_tracked_objects = []
        
        # Coba cocokkan objek yang sudah ada
        for tracked_obj in self.tracked_objects:
            best_match = None
            max_similarity = -1.0
            
            # Cari deteksi dengan fitur paling mirip
            for i, det in enumerate(unmatched_detections):
                if det["cls_idx"] == tracked_obj["cls_idx"]:
                    similarity = cosine_similarity(det["feature_vector"], tracked_obj["feature_vector"])
                    if similarity > max_similarity:
                        max_similarity = similarity
                        best_match = (i, det)
            
            if best_match and max_similarity > SIMILARITY_THRESHOLD:
                match_idx, match_det = best_match
                # Perbarui objek yang sudah ada dengan fitur dan kepercayaan terbaru
                # Ini penting agar "sidik jari" objek bisa beradaptasi sedikit
                if match_det["conf"] > tracked_obj["conf"]:
                    tracked_obj.update(match_det)
                
                updated_tracked_objects.append(tracked_obj)
                del unmatched_detections[match_idx]

        # Deteksi yang tersisa adalah objek baru
        for new_det in unmatched_detections:
            instance_count = sum(1 for o in updated_tracked_objects if o["cls_idx"] == new_det["cls_idx"])
            new_id = f"{new_det['cls_idx']}.{instance_count}"
            
            new_obj = new_det.copy()
            new_obj["id"] = new_id
            updated_tracked_objects.append(new_obj)

        self.tracked_objects = updated_tracked_objects
        
        self.update_cart_ui()

    def update_cart_ui(self):
        """Fungsi terpisah untuk hanya menggambar ulang UI keranjang."""
        # Hapus item keranjang lama
        for iid in self.cart_item_ids:
            self.canvas.delete(iid)
        self.cart_item_ids.clear()
        
        # Perbarui jumlah item
        self.canvas.itemconfigure(self.count_id_text, text=f"Jumlah Item: [{len(self.tracked_objects)}]")
    
        total_price = 0
        y0, dy = 219, 80
        
        for i, obj in enumerate(self.tracked_objects):
            cls_idx = obj["cls_idx"]
            if cls_idx < len(CLASS_NAMES):
                name = CLASS_NAMES[cls_idx]
                qty = 1
                unit = PRICES.get(name, 0)
                price = qty * unit
                total_price += price
                y = y0 + i * dy
                
                display_name = f"{name} (ID: {obj['id']})"

                self.cart_item_ids += [
                    self.canvas.create_text(590, y, anchor="nw", text=display_name, fill="#ffffff", font=("microsoft sans serif", -16)),
                    self.canvas.create_text(590, y+22, anchor="nw", text=format_currency(unit), fill="#ffffff", font=("microsoft sans serif", -18)),
                    self.canvas.create_image(825, y+22, image=self.colom_count_img),
                    self.canvas.create_text(817.5, y+10, anchor="nw", text=str(qty), fill="#ffffff", font=("microsoft sans serif", -20)),
                    self.canvas.create_text(1010, y+10, anchor="ne", text=format_currency(price), fill="#ffffff", font=("microsoft sans serif", -18))
                ]
        self.canvas.itemconfigure(self.price_id_text, text=format_currency(total_price))

    def display_frame(self, camera_id, frame):
        """Menampilkan sebuah frame pada label video yang sesuai."""
        target_label = self.video_labels.get(camera_id)
        if target_label:
            w, h = target_label.winfo_width(), target_label.winfo_height()
            if w > 1 and h > 1:
                frame_resized = cv2.resize(frame, (w, h))
                img = Image.fromarray(cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB))
                imgtk = ImageTk.PhotoImage(image=img)
                target_label.configure(image=imgtk)
                self.tk_image_refs[camera_id] = imgtk

    def on_checkout(self):
        """Fungsi yang dipanggil saat tombol checkout ditekan."""
        self.current_order_id += 1
        now = datetime.datetime.now().strftime("%d %b %Y %H:%M:%S")
        self.canvas.itemconfigure(self.order_id_text, text=f"Order #[{self.current_order_id:04d}] {now}")
        messagebox.showinfo("Transaksi", f"Order #{self.current_order_id:04d} Berhasil", parent=self.window)

    def on_closing(self):
        if messagebox.askokcancel("Keluar", "Apakah Anda ingin keluar dari aplikasi?", parent=self.window):
            print("Stopping child processes...")
            for q in self.control_queues:
                q.put('STOP')
            for p in self.processes:
                p.join(timeout=5) # Tunggu proses selesai
                if p.is_alive():
                    p.terminate() # Paksa berhenti jika macet
            self.window.destroy()

if __name__ == "__main__":
    mp.set_start_method('spawn', force=True)
    root = Tk()
    app = MainApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
