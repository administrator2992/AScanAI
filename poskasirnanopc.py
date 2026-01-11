import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import firebase_admin
from firebase_admin import credentials, db, storage
from tkinter import filedialog
import os
from PIL import Image, ImageTk
import numpy as np
import cv2

# 🔥 Init Firebase
cred = credentials.Certificate("assets/poskasir-develop-firebase-adminsdk-fbsvc-dbdeeb4379.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://poskasir-develop-default-rtdb.firebaseio.com/',
    'storageBucket': 'poskasir-develop.firebasestorage.app'
})

current_user_id = None
current_user_name = "User"
diskontotal = 0
# === 🖼️ UI Setup ===
root = tk.Tk()
root.title("POS Kasir")
root.attributes('-fullscreen', True)  # Set window to fullscreen
root.configure(bg="#f0f2f5")

# === Frame atas (header) ===
header = tk.Frame(root, bg="white", height=60)
header.pack(side="top", fill="x")
header.pack_propagate(False)

# Logo di kiri (sesuaikan logo di sini)
original_image = Image.open("assets/logodoang.png")  # pastikan filenya benar
resized_image = original_image.resize((60, 50))  # ukuran disesuaikan
tk_image = ImageTk.PhotoImage(resized_image)

# Tampilkan gambar yang sudah di-resize
logo_label = tk.Label(header, image=tk_image, bg="white")
logo_label.pack(side="left", padx=5)

# Simpan referensi ke image agar tidak terhapus oleh garbage collector
logo_label.image = tk_image

# Tanggal di tengah kiri
tanggal_label = tk.Label(header, text="", font=("Segoe UI", 12, "bold"), bg="white", fg="#5B708B")
tanggal_label.pack(side="left", padx=10)

# Hi, <user> + avatar
user_label = tk.Label(header, text="Hi, Emma", font=("Segoe UI", 12, "bold"), bg="white", fg="#5B708B")
user_label.pack(side="left", padx=10)

# Nama halaman di kanan
halaman_label = tk.Label(header, text="Inventory List", font=("Segoe UI", 12, "bold"), bg="white", fg="#5B708B")
halaman_label.pack(side="right", padx=20)

def update_header(user="Emma", halaman="Home"):
    from datetime import datetime
    tanggal_label.config(text=datetime.now().strftime("%a, %d %B %Y"))
    user_label.config(text=f"Hi, {user}")
    halaman_label.config(text=halaman)

update_header()  # panggil saat login, atau tiap ganti halaman

body = tk.Frame(root, bg="white")
body.pack(fill="both", expand=True)

# Sidebar
sidebar = tk.Frame(body, bg="#57708c", width=70)
sidebar.pack(side="left", fill="y")
sidebar.pack_propagate(False)

# Main area (berisi frame halaman)
main_area = tk.Frame(body, bg="white")
main_area.pack(side="left", fill="both", expand=True)

frames = {}
nav_buttons = {}
is_updating_frame = False

# === Fungsi Navigasi ===
def logout():
    show_frame("Login")
    set_nav_state(False)
    messagebox.showinfo("Logout", "Anda telah logout.")

def show_frame(name):
    global is_updating_frame
    for f in frames.values():
        f.pack_forget()

    # Tampilkan main_area jika frame yang akan ditampilkan ada di dalamnya
    if name in frames:
        target_frame = frames[name]
        parent = target_frame.master  # ambil parent frame-nya

        if parent != root:
            main_area.pack(fill="both", expand=True)
        else:
            main_area.pack_forget()

        target_frame.pack(fill="both", expand=True)

        print(f"[DEBUG] Menampilkan frame: {name}")
        set_active(name)
    else:
        print(f"[DEBUG] Frame {name} tidak ditemukan")

    update_header(user=current_user_name, halaman=name)  # Tambahkan ini!
    if name == "Login":
        set_nav_state(False)
    else:
        set_nav_state(True)

    if name == "Home2":
        is_updating_frame = True
        update_frame()
        update_header(user=current_user_name, halaman="Transaksi")
        tampilkan_kategori(canvas)
    else:
        is_updating_frame = False

    if name == "Tambah":
        tampilkan_kategori_kotak2()

    if name == "Setting":
        load_tax()

def set_active(active_name):
    for name, btn in nav_buttons.items():
        color = "#4B5E75" if name == active_name else "#5B708B"
        btn.config(bg=color)

def set_nav_state(enabled=True):
    for btn in nav_buttons.values():
        for child in btn.winfo_children():
            try:
                child.config(state="normal" if enabled else "disabled")
            except:
                pass

# === Fungsi buat tombol sidebar ===
def create_nav_button(name, icon_text, command):
    btn_frame = tk.Frame(sidebar, bg="#5B708B", height=50)
    btn_frame.pack(fill="x", pady=5)
    btn_frame.pack_propagate(False)

    btn = tk.Button(btn_frame, text=icon_text, font=("Segoe UI", 18), fg="white",
                    bg="#5B708B", bd=0, command=command, activebackground="#4B5E75")
    btn.pack(expand=True)
    nav_buttons[name] = btn_frame
    return btn_frame

# ----------------------------------------------------------------------------------------------------

# List Frame/Page (Kalau mau nambah page/frame baru taro di sini )

# === Buat Tombol Navigasi ===
create_nav_button("Home", "🏠", lambda: show_frame("Home"))
create_nav_button("Home2", "🛒", lambda: show_frame("Home2"))
create_nav_button("Tambah", "➕", lambda: show_frame("Tambah"))
# create_nav_button("Transaksi", "🛒", lambda: show_frame("Transaksi"))
create_nav_button("Inventaris", "🍰", lambda: show_frame("Inventory List"))
create_nav_button("Riwayat", "📜", lambda: show_frame("Riwayat"))

# Spacer biar tombol bawah di bawah
tk.Label(sidebar, bg="#5B708B").pack(expand=True, fill="both")

# Setting dan Logout
create_nav_button("Setting", "⚙️", lambda: show_frame("Setting"))
create_nav_button("Logout", "🔒", logout)

tambah = tk.Frame(main_area, bg="white")
frames["Tambah"] = tambah

edit = tk.Frame(main_area, bg="white")
frames["Edit"] = edit

riw = tk.Frame(main_area, bg="white")
frames["Riwayat"] = riw

home2 = tk.Frame(main_area, bg="white")
frames["Home2"] = home2

home2pay = tk.Frame(main_area, bg="white")
frames["Home2pay"] = home2pay

edit2 = tk.Frame(main_area, bg="white")
frames["Edit2"] = edit2

detail_frame4 = tk.Frame(main_area, bg="white")
frames["DetailFrame"] = detail_frame4

# ----------------------------------------------------------------------------------------------------

# LOGIN PAGE START

# === Setup Frame ===
login_frame = tk.Frame(main_area, bg="#f0f2f5")  # Warna latar belakang lembut
frames["Login"] = login_frame

# === Style Setup ===
style = ttk.Style()
style.configure("TLabel", font=("Segoe UI", 12), background="#f0f2f5")
style.configure("TEntry", padding=5)
style.configure("TButton", font=("Segoe UI", 11), padding=(10, 5))

# === Container untuk form ===
form_frame = tk.Frame(login_frame, bg="#ffffff", bd=1, relief="solid")
form_frame.place(relx=0.5, rely=0.5, anchor="center", width=350, height=300)

# === Judul ===
tk.Label(form_frame, text="Login Kasir", font=("Segoe UI", 16, "bold"), bg="#ffffff").pack(pady=(20, 10))

# === Input Fields ===
ttk.Label(form_frame, text="Nama", background="#ffffff").pack(anchor="w", padx=30, pady=(0, 5))
entry_nama = ttk.Entry(form_frame, width=30)
entry_nama.pack(padx=30, pady=(0, 10))

ttk.Label(form_frame, text="Password", background="#ffffff").pack(anchor="w", padx=30, pady=(0, 5))
entry_pass = ttk.Entry(form_frame, show="*", width=30)
entry_pass.pack(padx=30, pady=(0, 20))

# === Fungsi Login ===
def do_login():
    global current_user_id, current_user_name
    nama = entry_nama.get().strip()
    pw = entry_pass.get().strip()
    ref = db.reference("users")
    users = ref.get()

    for uid, u in (users or {}).items():
        if u["nama"] == nama and u["password"] == pw:
            current_user_id = uid
            current_user_name = u["nama"]
            messagebox.showinfo("Sukses", "Login berhasil!")
            welcome_name_label.config(text=f"{current_user_name} ")
            show_frame("Home")
            return
    messagebox.showerror("Gagal", "Nama atau password salah!")

# === Tombol ===
btn_frame = tk.Frame(form_frame, bg="#ffffff")
btn_frame.pack(pady=(10, 0))

ttk.Button(btn_frame, text="Login", command=do_login).pack(padx=10)

# LOGIN PAGE END

# ----------------------------------------------------------------------------------------------------

# SETTING PAGE START
tax_frame = tk.Frame(main_area, bg="white")
frames["Setting"] = tax_frame

# ====== Isi UI ======
tk.Label(tax_frame, text="Edit Tax", font=("Segoe UI", 18, "bold"), bg="white").pack(pady=20)

tax_var = tk.StringVar(value="0")

form_tax = tk.Frame(tax_frame, bg="white")
form_tax.pack(pady=10)

tk.Label(form_tax, text="Tax (%) :", font=("Segoe UI", 12), bg="white").grid(row=0, column=0, sticky="w", padx=10, pady=10)
tax_entry = tk.Entry(form_tax, textvariable=tax_var, font=("Segoe UI", 12), width=20)
tax_entry.grid(row=0, column=1, pady=10)

# ====== Fungsi Load dan Simpan ======
def load_tax():
    try:
        ref = db.reference("setting/tax")
        nilai_tax = ref.get()
        if nilai_tax is None:
            nilai_tax = 0
        tax_var.set(str(nilai_tax))
    except Exception as e:
        print("Gagal memuat tax:", e)
        tax_var.set("0")

def simpan_tax():
    try:
        nilai = float(tax_var.get())
        ref = db.reference("setting/tax")
        ref.set(nilai)
        messagebox.showinfo("Berhasil", f"Tax berhasil diperbarui menjadi {nilai}%")
    except ValueError:
        messagebox.showerror("Error", "Tax harus berupa angka.")
    except Exception as e:
        messagebox.showerror("Error", f"Gagal menyimpan tax: {e}")

# ====== Tombol Simpan ======
simpan_btn = tk.Button(tax_frame, text="Simpan Tax", font=("Segoe UI", 12, "bold"),
                       bg="#4CAF50", fg="white", padx=20, pady=10, command=simpan_tax)
simpan_btn.pack(pady=20)

# SETTING PAGE END

# ----------------------------------------------------------------------------------------------------

# === 🏠 HOME PAGE START ===
home = tk.Frame(main_area, bg="white")
frames["Home"] = home

# === Area Utama Center ===
home_container = tk.Frame(home, bg="white")
home_container.place(relx=0.5, rely=0.4, anchor="center")

# === Logo / Emoji ===
tk.Label(home_container, text="🛒", font=("Segoe UI", 60), bg="white").pack(pady=(10, 0))

# === Judul ===
tk.Label(home_container, text="POS KASIR", font=("Segoe UI", 22, "bold"), bg="white", fg="#2c3e50").pack(pady=(10, 5))

# === Selamat Datang dengan Nama User ===
welcome_name_label = tk.Label(home_container, text="Selamat datang!", font=("Segoe UI", 14), bg="white", fg="#34495e")
welcome_name_label.pack(pady=(5, 15))

# === Tombol Mulai Transaksi ===
def mulai_transaksi():
    show_frame("Home2")  # pastikan kamu punya fungsi show_frame(name)

ttk.Button(home_container, text="💼 Mulai Transaksi", command=mulai_transaksi).pack(pady=10)

# === Jam Real Time ===
jam_label = tk.Label(home_container, text="", font=("Segoe UI", 10), bg="white", fg="#95a5a6")
jam_label.pack(pady=(10, 0))

def update_jam():
    from datetime import datetime
    jam_label.config(text=datetime.now().strftime("%A, %d %B %Y - %H:%M:%S"))
    jam_label.after(1000, update_jam)

update_jam()

# === 🏠 HOME PAGE END ===

# ----------------------------------------------------------------------------------------------------

# === 📦 INVENTARIS PAGE START ===

inv = tk.Frame(main_area, bg="white")
frames["Inventory List"] = inv

# === Frame Horizontal untuk Kategori ===
kategori_scroll_frame = tk.Frame(inv, bg="white")
kategori_scroll_frame.pack(fill="x", padx=20, pady=(10, 0))

kategori_canvas = tk.Canvas(kategori_scroll_frame, height=130, bg="white", highlightthickness=0)
kategori_scrollbar = ttk.Scrollbar(kategori_scroll_frame, orient="horizontal", command=kategori_canvas.xview)

kategori_inner_frame = tk.Frame(kategori_canvas, bg="white")
kategori_inner_frame.bind("<Configure>", lambda e: kategori_canvas.configure(scrollregion=kategori_canvas.bbox("all")))
kategori_canvas.create_window((0, 0), window=kategori_inner_frame, anchor="nw")

kategori_canvas.configure(xscrollcommand=kategori_scrollbar.set)
kategori_canvas.pack(side="top", fill="x", expand=True)
kategori_scrollbar.pack(side="bottom", fill="x")

# === SCROLLABLE CANVAS ===
canvas_frame = tk.Frame(inv)
canvas_frame.pack(fill="both", expand=True, padx=20, pady=10)

canvas = tk.Canvas(canvas_frame, bg="white")
scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
scrollable_frame = tk.Frame(canvas, bg="white")

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(
        scrollregion=canvas.bbox("all")
    )
)

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# Simpan gambar agar tidak terhapus oleh garbage collector
inventaris_images = []
import threading

def load_card_image_async(url, label, index):
    def worker():
        try:
            print(f"🔄 (Thread {index}) Load gambar: {url}")
            response = requests.get(url, timeout=5)
            img_data = Image.open(BytesIO(response.content))
            img_data.thumbnail((100, 100), Image.Resampling.LANCZOS)
            img_tk = ImageTk.PhotoImage(img_data)

            label.after(0, lambda: update_inventaris_image(label, img_tk, index))
        except Exception as e:
            print(f"❌ Gagal load gambar di thread {index}: {e}")
            label.after(0, lambda: label.config(text="[Gagal Load]"))

    threading.Thread(target=worker).start()


def update_inventaris_image(label, img, index):
    inventaris_images.append(img)  # Simpan referensi agar tidak hilang
    label.config(image=img, text="")
    label.image = img

from functools import partial
import urllib.request
import io
def open_edit(item_data, kategori):
    for widget in edit2.winfo_children():
        widget.destroy()

    tk.Label(edit2, text="Edit Barang", font=("Segoe UI", 14, "bold"), bg="white").pack(pady=10)

    nama_var = tk.StringVar(value=item_data.get("nama", ""))
    harga_var = tk.StringVar(value=str(item_data.get("harga", 0)))
    stok_var = tk.StringVar(value=str(item_data.get("stok", 0)))
    diskon_var = tk.StringVar(value=str(item_data.get("discount", 0)))
    gambar_var = tk.StringVar(value=item_data.get("gambar", ""))
    local_gambar_path = [None]  # Mutable container to track file path

    form = tk.Frame(edit2, bg="white")
    form.pack(pady=10)

    def add_row(label, var, row):
        tk.Label(form, text=label, bg="white").grid(row=row, column=0, sticky="e", padx=10, pady=5)
        tk.Entry(form, textvariable=var, width=40).grid(row=row, column=1, padx=10, pady=5)

    add_row("Nama", nama_var, 0)
    add_row("Harga", harga_var, 1)
    add_row("Stok", stok_var, 2)
    add_row("Discount", diskon_var, 3)

    # === Gambar Preview ===
    gambar_frame = tk.Frame(edit2, bg="white")
    gambar_frame.pack(pady=10)

    gambar_preview = tk.Label(gambar_frame, bg="white")
    gambar_preview.pack()

    def tampilkan_gambar_dari_url(url):
        try:
            with urllib.request.urlopen(url) as u:
                raw_data = u.read()
            img = Image.open(io.BytesIO(raw_data))
            img.thumbnail((200, 200))
            img_tk = ImageTk.PhotoImage(img)
            gambar_preview.config(image=img_tk)
            gambar_preview.image = img_tk
        except:
            gambar_preview.config(image='', text="(Gambar gagal ditampilkan)", fg="red")

    def tampilkan_gambar_dari_file(path):
        try:
            img = Image.open(path)
            img.thumbnail((200, 200))
            img_tk = ImageTk.PhotoImage(img)
            gambar_preview.config(image=img_tk)
            gambar_preview.image = img_tk
        except:
            gambar_preview.config(image='', text="(Gambar gagal ditampilkan)", fg="red")

    if gambar_var.get().startswith("http"):
        tampilkan_gambar_dari_url(gambar_var.get())

    # === Pilih Gambar Baru ===
    def pilih_gambar():
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
        if file_path:
            local_gambar_path[0] = file_path
            tampilkan_gambar_dari_file(file_path)

    tk.Button(gambar_frame, text="📁 Pilih Gambar Baru", command=pilih_gambar,
              bg="#2196F3", fg="white").pack(pady=5)

    # === Simpan Perubahan ===
    def simpan_perubahan():
        ref = db.reference(f"inventaris/{kategori}")
        barang_id = None

        for id_barang, data in ref.get().items():
            if data.get("nama") == item_data.get("nama"):
                barang_id = id_barang
                break

        if not barang_id:
            print("Barang tidak ditemukan!")
            return

        update_ref = ref.child(barang_id)
        new_data = {
            "nama": nama_var.get(),
            "harga": int(harga_var.get() or 0),
            "stok": int(stok_var.get() or 0),
            "discount": int(diskon_var.get() or 0),
        }

        # Upload gambar jika user pilih baru
        if local_gambar_path[0]:
            path = local_gambar_path[0]
            filename = f"barang/{kategori}/{barang_id}.jpg"
            bucket = storage.bucket()
            blob = bucket.blob(filename)
            blob.upload_from_filename(path)
            blob.make_public()  # Biar bisa dilihat via URL
            url = blob.public_url
            new_data["gambar"] = url
        else:
            new_data["gambar"] = gambar_var.get()  # tetap pakai lama

        update_ref.update(new_data)
        kembali_ke_inventaris()

    def kembali_ke_inventaris():
        show_frame("Inventory List")

    btn_frame = tk.Frame(edit2, bg="white")
    btn_frame.pack(pady=15)

    tk.Button(btn_frame, text="💾 Simpan", command=simpan_perubahan,
              bg="#4CAF50", fg="white", width=12).pack(side="left", padx=10)
    tk.Button(btn_frame, text="↩️ Batal", command=kembali_ke_inventaris,
              bg="gray", fg="white", width=12).pack(side="left", padx=10)

    show_frame("Edit2")

def load_inventaris():
    for widget in kategori_inner_frame.winfo_children():
        widget.destroy()
    for widget in scrollable_frame.winfo_children():
        widget.destroy()
    inventaris_images.clear()

    # Ambil data kategori dan inventaris dari Firebase
    ref_kategori = db.reference("daftar_kategori")
    data_kategori = ref_kategori.get() or {}

    ref_inventaris = db.reference("inventaris")
    data_inventaris = ref_inventaris.get() or {}

    if not data_kategori:
        tk.Label(scrollable_frame, text="Tidak ada kategori tersedia.", bg="white").pack(pady=10)
        return

    # Fungsi untuk menampilkan isi item suatu kategori
    def show_kategori_items(nama_kategori):
        for widget in scrollable_frame.winfo_children():
            widget.destroy()

        item_data = data_inventaris.get(nama_kategori, {})
        # headers = ["Gambar", "Nama", "Harga", "Stok", "Discount", "Kategori"]
        headers = ["Gambar", "Nama", "Harga", "Stok", "Discount", "Kategori", "Action"]
        for col, text in enumerate(headers):
            tk.Label(scrollable_frame, text=text, bg="#ddd", relief="ridge", bd=1,
                     width=16, font=("Segoe UI", 10, "bold"), anchor="center").grid(row=0, column=col, sticky="nsew",
                                                                                    padx=1, pady=1)

        row_num = 1
        for item_id, item in item_data.items():
            def update_stok(delta, item_id=item_id, kategori=nama_kategori, label_ref=None):
                ref = db.reference(f"inventaris/{kategori}/{item_id}/stok")
                stok_lama = ref.get() or 0
                stok_baru = stok_lama + delta
                if stok_baru < 0:
                    return
                ref.set(stok_baru)
                label_ref.config(text=stok_baru)

            def update_discount(delta, item_id=item_id, kategori=nama_kategori, label_ref=None):
                ref = db.reference(f"inventaris/{kategori}/{item_id}/discount")
                diskon_lama = ref.get()
                if diskon_lama is None:
                    diskon_lama = 0
                try:
                    diskon_lama = int(diskon_lama)
                except ValueError:
                    diskon_lama = 0

                diskon_baru = max(0, diskon_lama + delta)  # Pastikan tidak negatif
                ref.set(diskon_baru)
                label_ref.config(text=diskon_baru)

            nama = item.get("nama", "-")
            harga = item.get("harga", 0)
            stok = item.get("stok", 0)
            discount = item.get("discount", 0)
            gambar = item.get("gambar", "")

            img_item = tk.Label(scrollable_frame, text="Loading...", bg="white", relief="ridge", bd=1)
            img_item.grid(row=row_num, column=0, sticky="nsew", padx=1, pady=1)
            if gambar:
                load_card_image_async(gambar, img_item, f"{nama_kategori}-{row_num}")
            else:
                img_item.config(text="[No Image]")

            tk.Label(scrollable_frame, text=nama, bg="white", anchor="center", relief="ridge", bd=1).grid(row=row_num,
                                                                                                          column=1,
                                                                                                          sticky="nsew",
                                                                                                          padx=1,
                                                                                                          pady=1)
            tk.Label(scrollable_frame, text=f"Rp {harga:,}", bg="white", anchor="center", relief="ridge", bd=1).grid(
                row=row_num, column=2, sticky="nsew", padx=1, pady=1)

            # === Stok ===
            frame_qty = tk.Frame(scrollable_frame, bg="white", relief="ridge", bd=1)
            frame_qty.grid(row=row_num, column=3, sticky="nsew", padx=1, pady=1)

            label_qty = tk.Label(frame_qty, text=stok, width=5, bg="white", anchor="center")

            tk.Button(frame_qty, text="-", width=2,
                      command=partial(update_stok, -1, item_id=item_id, kategori=nama_kategori,
                                      label_ref=label_qty)).pack(side="left", padx=2)

            label_qty.pack(side="left", padx=2)

            tk.Button(frame_qty, text="+", width=2,
                      command=partial(update_stok, 1, item_id=item_id, kategori=nama_kategori,
                                      label_ref=label_qty)).pack(side="left", padx=2)

            # === Discount ===
            frame_discount = tk.Frame(scrollable_frame, bg="white", relief="ridge", bd=1)
            frame_discount.grid(row=row_num, column=4, sticky="nsew", padx=1, pady=1)

            label_discount = tk.Label(frame_discount, text=discount, width=5, bg="white", anchor="center")

            tk.Button(frame_discount, text="-", width=2,
                      command=partial(update_discount, -1, item_id=item_id, kategori=nama_kategori,
                                      label_ref=label_discount)).pack(side="left", padx=2)

            label_discount.pack(side="left", padx=2)

            tk.Button(frame_discount, text="+", width=2,
                      command=partial(update_discount, 1, item_id=item_id, kategori=nama_kategori,
                                      label_ref=label_discount)).pack(side="left", padx=2)

            # === Kategori ===
            tk.Label(scrollable_frame, text=nama_kategori, bg="white", anchor="center", relief="ridge", bd=1).grid(
                row=row_num, column=5, sticky="nsew", padx=1, pady=1)

            # === Action ===
            frame_action = tk.Frame(scrollable_frame, bg="white", relief="ridge", bd=1)
            frame_action.grid(row=row_num, column=6, sticky="nsew", padx=1, pady=1)

            btn_edit = tk.Button(frame_action, text="✏️", bg="white", relief="flat", bd=0,
                                 command=lambda item_data=item, kategori=nama_kategori: open_edit(item_data, kategori))
            btn_edit.pack(side="left", padx=(5, 2))

            def delete_item(kat=nama_kategori, id=item_id):
                if tk.messagebox.askyesno("Konfirmasi", f"Yakin ingin menghapus '{nama}' dari kategori '{kat}'?"):
                    db.reference(f"inventaris/{kat}/{id}").delete()
                    show_kategori_items(kat)  # Refresh list setelah hapus

            btn_delete = tk.Button(frame_action, text="🗑️", bg="white", relief="flat", bd=0,
                                   command=delete_item)
            btn_delete.pack(side="left", padx=(2, 5))

            row_num += 1

    # Untuk menyimpan referensi button kategori supaya bisa di-highlight
    kategori_buttons = {}

    for idx, (nama_kategori, info) in enumerate(data_kategori.items()):
        gambar_url = info.get("gambar", "")

        # Frame utama kategori (tanpa border)
        kategori_btn = tk.Frame(kategori_inner_frame, bg="white", cursor="hand2")
        kategori_btn.pack(side="left", padx=5, pady=5)

        # Frame gambar dengan border (hanya sekeliling gambar)
        frame_gambar = tk.Frame(kategori_btn, bg="white", bd=2, relief="solid")
        frame_gambar.pack(padx=5, pady=(5, 2))
        kategori_buttons[nama_kategori] = kategori_btn

        # Label gambar
        img_label = tk.Label(frame_gambar, text="Loading...", bg="white")
        img_label.pack()
        if gambar_url:
            load_card_image_async(gambar_url, img_label, f"kateg-{idx}")
        else:
            img_label.config(text="[No Image]")

        # Label nama
        jumlah_item = len(data_inventaris.get(nama_kategori, {}))
        nama_tampil = f"{nama_kategori} ({jumlah_item})"
        tk.Label(kategori_btn, text=nama_tampil, bg="white", font=("Segoe UI", 10)).pack(pady=(0, 5))

        # Fungsi klik
        def on_click_kategori(nama=nama_kategori):
            show_kategori_items(nama)
            # Reset semua kategori jadi putih
            for btn in kategori_buttons.values():
                btn.config(bg="white")
            kategori_buttons[nama].config(bg="#cce")  # highlight biru muda

        kategori_btn.bind("<Button-1>", lambda e, nama=nama_kategori: on_click_kategori(nama))
        img_label.bind("<Button-1>", lambda e, nama=nama_kategori: on_click_kategori(nama))

    # Auto pilih kategori pertama jika ada
    if data_kategori:
        nama_pertama = list(data_kategori.keys())[0]
        show_kategori_items(nama_pertama)
        kategori_buttons[nama_pertama].config(bg="#cce")


# Panggil saat frame Inventaris ditampilkan
inv.bind("<Visibility>", lambda e: load_inventaris())

# === 📦 INVENTARIS PAGE END ===

# ----------------------------------------------------------------------------------------------------

# === 🧾 TRANSAKSI PAGE (NOT USED) START ===

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import requests
from io import BytesIO

trx_frame = tk.Frame(main_area, bg="white")
frames["Transaksi"] = trx_frame

tk.Label(trx_frame, text="Transaksi Barang", font=("Segoe UI", 18, "bold"), bg="white").pack(pady=10)

# === Container Tengah ===
trx_center = tk.Frame(trx_frame, bg="white")
trx_center.pack(expand=True, fill="both")

main_area = tk.Frame(trx_center, bg="white")
main_area.place(relx=0.5, rely=0.5, anchor="center")

# === KIRI: Panel Checkout & Keranjang ===
checkout_left = tk.Frame(main_area, bg="white")
checkout_left.pack(side="left", padx=30, pady=10)

tk.Label(checkout_left, text="📋 Checkout Pembeli", font=("Segoe UI", 12), bg="white").pack(pady=(5, 2))
pembeli_cb = ttk.Combobox(checkout_left, width=35)
pembeli_cb.pack(pady=(0, 5))

ttk.Button(checkout_left, text="🔄 Muat Keranjang", command=lambda: load_checkout_pembeli()).pack(pady=(5, 10))

tk.Label(checkout_left, text="🧺 Keranjang Belanja", font=("Segoe UI", 14, "bold"), bg="white").pack(anchor="w", pady=(5, 2))

# === Scrollable Keranjang Card View ===
canvas_keranjang = tk.Canvas(checkout_left, bg="white", width=400, height=320, highlightthickness=0)
scroll_keranjang = ttk.Scrollbar(checkout_left, orient="vertical", command=canvas_keranjang.yview)
scroll_keranjang_frame = tk.Frame(canvas_keranjang, bg="white")

canvas_keranjang.create_window((0, 0), window=scroll_keranjang_frame, anchor="nw")
canvas_keranjang.configure(yscrollcommand=scroll_keranjang.set)
scroll_keranjang_frame.bind("<Configure>", lambda e: canvas_keranjang.configure(scrollregion=canvas_keranjang.bbox("all")))

canvas_keranjang.pack(side="left", fill="both", expand=True)
scroll_keranjang.pack(side="right", fill="y")

# === Bawah Kiri ===
ttk.Button(checkout_left, text="🗑️ Hapus Semua", command=lambda: hapus_semua_keranjang()).pack(pady=5)
label_total_trx = ttk.Label(checkout_left, text="Total: Rp 0", font=("Segoe UI", 12, "bold"), background="white")
label_total_trx.pack(pady=5)
ttk.Button(checkout_left, text="Pembayaran", command=lambda: simpan_transaksi_multi()).pack(pady=5)

# === KANAN: Tambah Barang ===
form_right = tk.Frame(main_area, bg="white")
form_right.pack(side="left", padx=30, pady=10)

tk.Label(form_right, text="Tambah Barang ke Keranjang", font=("Segoe UI", 14, "bold"), bg="white").pack(anchor="w")
form_area = tk.Frame(form_right, bg="white")
form_area.pack(pady=10)

ttk.Label(form_area, text="Pilih Barang:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
barang_cb = ttk.Combobox(form_area, width=30)
barang_cb.grid(row=0, column=1, padx=5, pady=5)

ttk.Label(form_area, text="Jumlah:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
jumlah_entry = ttk.Entry(form_area, width=10)
jumlah_entry.grid(row=1, column=1, padx=5, pady=5)

tk.Label(checkout_left, text="💳 Metode Pembayaran", font=("Segoe UI", 12), bg="white").pack(anchor="w", pady=(10, 0))
metode_var = tk.StringVar()
metode_cb = ttk.Combobox(checkout_left, textvariable=metode_var, values=["Tunai", "QRIS", "Debit"], state="readonly", width=32)
metode_cb.pack(pady=(0, 5))


ttk.Button(form_area, text="+ Tambah ke Keranjang", command=lambda: tambah_keranjang()).grid(row=2, column=0, columnspan=2, pady=10)

# === Variabel & Fungsi ===
keranjang = []
gambar_refs = {}
user_id_to_name = {}   # pembeli_1 → Nama Asli
user_name_to_id = {}   # Nama Asli → pembeli_1

def load_keranjang_image_async(gambar_url, label, nama):
    def worker():
        try:
            response = requests.get(gambar_url, timeout=5)
            img_data = Image.open(BytesIO(response.content))
            img_data.thumbnail((100, 100), Image.Resampling.LANCZOS)
            img_tk = ImageTk.PhotoImage(img_data)

            label.after(0, lambda: update_keranjang_image(label, img_tk, nama))
        except Exception as e:
            print(f"❌ Gagal load gambar {nama}: {e}")
            label.after(0, lambda: label.config(text="[No Image]"))

    threading.Thread(target=worker).start()

def update_keranjang_image(label, img_tk, nama):
    gambar_refs[nama] = img_tk
    label.config(image=img_tk, text="")
    label.image = img_tk

def find_item_index(nama):
    for i, item in enumerate(keranjang):
        if item["nama"] == nama:
            return i
    return -1

def kembali():
    payment_frame.pack_forget()
    checkout_left.pack(side="left", padx=30, pady=10)
    form_right.pack(side="left", padx=30, pady=10)
def load_daftar_checkout():
    checkout_data = db.reference("checkout").get()
    if checkout_data:
        pembeli_cb["values"] = list(checkout_data.keys())  # ['pembeli_1', 'pembeli_2']

def load_checkout_pembeli():
    global keranjang
    keranjang.clear()
    for widget in scroll_keranjang_frame.winfo_children():
        widget.destroy()

    user_id = pembeli_cb.get()
    if not user_id:
        return

    data = db.reference("checkout").child(user_id).child("items").get()
    if not data:
        messagebox.showwarning("Kosong", "Data checkout kosong.")
        return

    for nama, item in data.items():
        add_card_keranjang(nama, item["jumlah"], item["harga"], item.get("gambar", ""))
        keranjang.append(item)

    update_total_trx()


def tambah_keranjang():
    nama = barang_cb.get()
    if not nama:
        return
    try:
        jumlah = int(jumlah_entry.get())
        if jumlah <= 0:
            return

        ref = db.reference("inventaris")
        data_inventaris = ref.get() or {}

        for kategori_data in data_inventaris.values():
            for item in kategori_data.values():
                if item.get("nama") == nama:
                    harga = item.get("harga", 0)
                    gambar_url = item.get("gambar", "")
                    add_card_keranjang(nama, jumlah, harga, gambar_url)
                    keranjang.append({"nama": nama, "jumlah": jumlah, "harga": harga})
                    update_total_trx()
                    jumlah_entry.delete(0, tk.END)
                    return  # Keluar setelah ketemu
    except Exception as e:
        print(f"Error tambah_keranjang: {e}")

def update_total_trx():
    total = sum(item['jumlah'] * item['harga'] for item in keranjang)
    label_total_trx.config(text=f"Total: Rp {total:,}")

def add_card_keranjang(nama, jumlah, harga, gambar_url):
    card = tk.Frame(scroll_keranjang_frame, bg="white", bd=1, relief="solid", padx=8, pady=8)
    card.pack(fill="x", pady=5, padx=5)
    card._nama = nama  # Tambahkan properti untuk identifikasi saat update

    # Gambar (async biar gak lemot)
    img_label = tk.Label(card, text="Loading...", bg="white")
    img_label.pack(side="left", padx=5)
    if gambar_url:
        load_keranjang_image_async(gambar_url, img_label, nama)
    else:
        img_label.config(text="[No Image]")

    # Info Frame
    info = tk.Frame(card, bg="white")
    info.pack(side="left", expand=True, fill="x")

    nama_label = tk.Label(info, text=nama, font=("Segoe UI", 11, "bold"), bg="white")
    nama_label.pack(anchor="w")
    jumlah_label = tk.Label(info, text=f"Jumlah: {jumlah}", bg="white")
    jumlah_label.pack(anchor="w")
    subtotal_label = tk.Label(info, text=f"Subtotal: Rp {jumlah * harga:,}", bg="white")
    subtotal_label.pack(anchor="w")

    # Tombol ➕➖
    control = tk.Frame(card, bg="white")
    control.pack(side="right")

    def tambah():
        for item in keranjang:
            if item["nama"] == nama:
                item["jumlah"] += 1
                jumlah_label.config(text=f"Jumlah: {item['jumlah']}")
                subtotal_label.config(text=f"Subtotal: Rp {item['jumlah'] * harga:,}")
                update_total_trx()
                break

    def kurang():
        for item in keranjang:
            if item["nama"] == nama:
                item["jumlah"] -= 1
                if item["jumlah"] <= 0:
                    keranjang.remove(item)
                    card.destroy()
                else:
                    jumlah_label.config(text=f"Jumlah: {item['jumlah']}")
                    subtotal_label.config(text=f"Subtotal: Rp {item['jumlah'] * harga:,}")
                update_total_trx()
                break

    tk.Button(control, text="+", width=2, command=tambah, bg="#2ecc71", fg="white").pack(pady=2)
    tk.Button(control, text="-", width=2, command=kurang, bg="#e67e22", fg="white").pack(pady=2)

    # Tombol Hapus Langsung
    tk.Button(control, text="❌", width=2, command=lambda: [card.destroy(), hapus_item(nama)], bg="#e74c3c", fg="white").pack(pady=2)


def hapus_item(nama):
    global keranjang
    keranjang = [item for item in keranjang if item["nama"] != nama]
    update_total_trx()

def hapus_semua_keranjang():
    for widget in scroll_keranjang_frame.winfo_children():
        widget.destroy()
    keranjang.clear()
    update_total_trx()

from reportlab.lib.pagesizes import A6
from reportlab.pdfgen import canvas as pdf_canvas
from datetime import datetime

def tampilkan_struk_di_payment_frame(trx_id, total, metode, items):
    # Bersihkan payment_frame
    for widget in payment_frame.winfo_children():
        widget.destroy()

    wrapper = tk.Frame(payment_frame, bg="white")
    wrapper.pack(padx=30, pady=20, fill="both", expand=True)

    tk.Label(wrapper, text="✅ Pembayaran Berhasil", font=("Segoe UI", 14, "bold"), fg="green", bg="white").pack(pady=(0, 10))
    tk.Label(wrapper, text=f"ID Transaksi: {trx_id}", bg="white").pack()
    tk.Label(wrapper, text=f"Metode: {metode}", bg="white").pack()
    tk.Label(wrapper, text=f"Total: Rp {total:,}", bg="white").pack(pady=(0, 10))

    tk.Label(wrapper, text="Catatan (opsional):", bg="white").pack(anchor="w")
    note_entry = tk.Text(wrapper, height=5, width=50)
    note_entry.pack(pady=5)

    def simpan_catatan():
        note_text = note_entry.get("1.0", "end").strip()

        if note_text:
            db.reference("transaksi").child(trx_id).update({"catatan": note_text})

        simpan_struk_pdf(trx_id, metode, total, items, catatan=note_text)
        messagebox.showinfo("Selesai", f"Struk disimpan sebagai: {trx_id}.pdf")

    ttk.Button(wrapper, text="💾 Simpan Struk", command=simpan_catatan).pack(pady=10)


def simpan_struk_pdf(trx_id, metode, total, items, catatan=""):
    filename = f"{trx_id}.pdf"
    c = pdf_canvas.Canvas(filename, pagesize=A6)
    width, height = A6
    y = height - 20

    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, y, "TOKO KASIR ANDA")
    y -= 15
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, y, "Jl. Contoh No. 123, Indonesia")
    y -= 10
    c.drawString(10, y, "=" * 35)
    y -= 12

    c.drawString(10, y, f"ID Transaksi : {trx_id}")
    y -= 10
    c.drawString(10, y, f"Tanggal      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 10
    c.drawString(10, y, f"Metode Bayar : {metode}")
    y -= 12
    c.drawString(10, y, "-" * 35)
    y -= 10

    c.drawString(10, y, "Barang        Qty   Harga   Subtotal")
    y -= 10

    for item in items:
        if y < 40:  # avoid writing past the bottom
            c.showPage()
            y = height - 20

        nama = item["nama"][:10].ljust(10)
        qty = str(item["jumlah"]).rjust(3)
        harga = str(item["harga"]).rjust(6)
        subtotal = str(item["jumlah"] * item["harga"]).rjust(8)
        c.drawString(10, y, f"{nama}  {qty}  {harga}  {subtotal}")
        y -= 10

    c.drawString(10, y, "-" * 35)
    y -= 12
    c.drawString(10, y, f"TOTAL BAYAR : Rp {total:,}".replace(",", "."))
    y -= 14
    c.drawString(10, y, "=" * 35)
    y -= 12

    if catatan.strip():
        c.drawString(10, y, "Catatan:")
        y -= 10
        for line in catatan.strip().split("\n"):
            if y < 30:
                c.showPage()
                y = height - 20
            c.drawString(10, y, line.strip())
            y -= 10

    c.drawString(10, y, "=" * 35)
    y -= 14
    c.drawCentredString(width / 2, y, "Terima kasih telah berbelanja!")
    c.save()

    return filename

def show_struk(trx_id, total, metode, items):
    note_win = tk.Toplevel()
    note_win.title("Struk Pembelian")
    note_win.geometry("400x300")

    tk.Label(note_win, text="Struk Pembelian", font=("Segoe UI", 14, "bold")).pack(pady=10)
    tk.Label(note_win, text=f"ID Transaksi: {trx_id}").pack(pady=2)
    tk.Label(note_win, text=f"Metode: {metode}").pack(pady=2)
    tk.Label(note_win, text=f"Total: Rp {total:,}").pack(pady=2)

    tk.Label(note_win, text="Catatan (opsional):").pack(pady=(10, 0))
    note_entry = tk.Text(note_win, height=5, width=40)
    note_entry.pack(pady=5)

    def simpan_catatan():
        note_text = note_entry.get("1.0", "end").strip()

        # Simpan ke Firebase
        if note_text:
            db.reference("transaksi").child(trx_id).update({"catatan": note_text})

        # Simpan ke PDF
        simpan_struk_pdf(trx_id, metode, total, items, catatan=note_text)

        note_win.destroy()
        messagebox.showinfo("Selesai", f"Struk disimpan sebagai: {trx_id}.pdf")

    ttk.Button(note_win, text="Simpan Catatan", command=simpan_catatan).pack(pady=10)


payment_frame = tk.Frame(main_area, bg="white")
payment_frame.pack_forget()  # Disembunyikan dulu

def simpan_transaksi_multi():
    if not keranjang:
        messagebox.showwarning("Kosong", "Keranjang kosong")
        return

    total = sum(item['jumlah'] * item['harga'] for item in keranjang)
    metode_pilihan = metode_var.get()
    if not metode_pilihan:
        messagebox.showwarning("Pilih Metode", "Silakan pilih metode pembayaran terlebih dahulu.")
        return

    checkout_left.pack_forget()
    form_right.pack_forget()

    for widget in payment_frame.winfo_children():
        widget.destroy()

    inner = tk.Frame(payment_frame, bg="white")
    inner.pack(padx=30, pady=20, fill="both", expand=True)

    tk.Label(inner, text="💰 Masukkan Pembayaran", font=("Segoe UI", 14, "bold"), bg="white").pack(pady=(0, 10))
    tk.Label(inner, text=f"Total Belanja: Rp {total:,}", font=("Segoe UI", 12), bg="white").pack(pady=(0, 10))

    # Input bayar (readonly)
    bayar_var = tk.StringVar(value="")
    bayar_entry = ttk.Entry(inner, textvariable=bayar_var, font=("Segoe UI", 14), justify="right", state="readonly", width=20)
    bayar_entry.pack(pady=(0, 10))

    # Label kembalian
    kembalian_label = ttk.Label(inner, text="", font=("Segoe UI", 11), background="white", foreground="green")
    kembalian_label.pack(pady=5)

    # === Numeric Pad Kasir ===
    pad_frame = tk.Frame(inner, bg="white")
    pad_frame.pack()

    pad_buttons = [
        ["7", "8", "9", "100000", "50000"],
        ["4", "5", "6", "20000", "10000"],
        ["1", "2", "3", "5000", "2000"],
        ["0", "00", "000", "1000", "⌫"]
    ]

    def update_bayar(val):
        current_val = bayar_var.get()
        try:
            current = int(current_val or "0")
        except ValueError:
            current = 0

        if val == "⌫":
            bayar_var.set(current_val[:-1])
        elif val in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "00", "000"]:
            # Angka biasa → string append
            bayar_var.set(current_val + val)
        else:
            # Tombol nominal cepat → tambahkan ke integer total bayar
            try:
                bayar_var.set(str(current + int(val)))
            except:
                pass

        # Update kembalian
        try:
            dibayar = int(bayar_var.get())
            kembalian = dibayar - total
            if kembalian >= 0:
                kembalian_label.config(text=f"Kembalian: Rp {kembalian:,}", foreground="green")
            else:
                kembalian_label.config(text=f"Kurang: Rp {abs(kembalian):,}", foreground="red")
        except:
            kembalian_label.config(text="")

    # Render tombol pad seperti tabel 4 baris x 5 kolom
    for row in pad_buttons:
        row_frame = tk.Frame(pad_frame, bg="white")
        row_frame.pack()
        for val in row:
            display = val
            if val == "⌫":
                btn = tk.Button(row_frame, text="⌫", font=("Segoe UI", 14), width=6, height=2,
                                command=lambda v=val: update_bayar(v))
            elif val.isdigit():
                # Format untuk angka besar
                if int(val) >= 1000:
                    display = f"{int(val):,}".replace(",", ".")
                btn = tk.Button(row_frame, text=display, font=("Segoe UI", 12, "bold"), width=6, height=2,
                                command=lambda v=val: update_bayar(v))
            else:
                btn = tk.Button(row_frame, text=display, font=("Segoe UI", 12), width=6, height=2,
                                command=lambda v=val: update_bayar(v))
            btn.pack(side="left", padx=3, pady=3)

    # === Tombol Aksi ===
    def kembali():
        payment_frame.pack_forget()
        checkout_left.pack(side="left", padx=30, pady=10)
        form_right.pack(side="left", padx=30, pady=10)

    def proses_pembayaran():
        try:
            jumlah_bayar = int(bayar_var.get())
        except ValueError:
            messagebox.showerror("Error", "Masukkan jumlah bayar yang valid")
            return

        if jumlah_bayar < total:
            messagebox.showwarning("Kurang", "Jumlah bayar kurang dari total belanja.")
            return

        kembalian = jumlah_bayar - total

        # Validasi stok
        ref = db.reference("inventaris")
        for item in keranjang:
            items = ref.order_by_child("nama").equal_to(item["nama"]).get()
            for key, val in items.items():
                if val["stok"] < item["jumlah"]:
                    messagebox.showerror("Stok Kurang", f"Stok {item['nama']} tidak cukup")
                    kembali()
                    return

        # Kurangi stok
        for item in keranjang:
            items = ref.order_by_child("nama").equal_to(item["nama"]).get()
            for key, val in items.items():
                ref.child(key).update({"stok": val["stok"] - item["jumlah"]})

        # Simpan transaksi
        from datetime import datetime
        trx_id = "trx_" + datetime.now().strftime("%Y%m%d%H%M%S")
        pembeli_id = pembeli_cb.get() if pembeli_cb.get() else "Umum"
        db.reference("transaksi").child(trx_id).set({
            "barang": keranjang,
            "total": total,
            "dibayar": jumlah_bayar,
            "kembalian": kembalian,
            "waktu": datetime.now().isoformat(),
            "pembeli": pembeli_id,
            "metode": metode_pilihan
        })

        if pembeli_cb.get():
            db.reference("checkout").child(pembeli_id).delete()
            pembeli_cb.set("")

        items_copy = keranjang.copy()
        hapus_semua_keranjang()
        update_barang_cb()
        kembali()
        show_struk(trx_id, total, metode_pilihan, items_copy)

    button_frame = tk.Frame(inner, bg="white")
    button_frame.pack(pady=15)

    ttk.Button(button_frame, text="✅ Proses Pembayaran", command=proses_pembayaran).pack(side="left", padx=10)
    ttk.Button(button_frame, text="❌ Batal", command=kembali).pack(side="left", padx=10)

    payment_frame.pack(side="left", padx=30, pady=10, fill="both", expand=True)

trx_frame.bind("<Visibility>", lambda e: load_daftar_checkout())

# === 🧾 TRANSAKSI PAGE (NOT USED) END ===

# ----------------------------------------------------------------------------------------------------

# === 📜 RIWAYAT TRANSAKSI PAGE START ===

from datetime import datetime, timedelta

# === FRAME DETAIL TRANSAKSI YANG DIBARUI ===
tk.Label(detail_frame4, text="🧾 Detail Transaksi", font=("Segoe UI", 18, "bold"), bg="white", fg="#333").pack(pady=15)

# Scrollable area
canvas4 = tk.Canvas(detail_frame4, bg="white", highlightthickness=0)
scrollbar4 = tk.Scrollbar(detail_frame4, orient="vertical", command=canvas4.yview)
scrollable_frame4 = tk.Frame(canvas4, bg="white")

scrollable_frame4.bind(
    "<Configure>",
    lambda e: canvas4.configure(scrollregion=canvas4.bbox("all"))
)

canvas4.create_window((0, 0), window=scrollable_frame4, anchor="nw")
canvas4.configure(yscrollcommand=scrollbar4.set)

canvas4.pack(side="left", fill="both", expand=True)
scrollbar4.pack(side="right", fill="y")

# === BAGIAN HEADER ===
info_frame = tk.Frame(scrollable_frame4, bg="white")
info_frame.pack(padx=20, pady=10, anchor="w")

labels_info = {
    "ID Transaksi": "-",
    "Waktu": "-",
    "Pembeli": "-",
    "Tipe Transaksi": "-",
    "Metode Pembayaran": "-"
}
label_refs = {}

for i, (k, v) in enumerate(labels_info.items()):
    tk.Label(info_frame, text=k + ":", font=("Segoe UI", 11, "bold"), bg="white").grid(row=i, column=0, sticky="w", pady=2)
    val_label = tk.Label(info_frame, text=v, font=("Segoe UI", 11), bg="white", fg="#555")
    val_label.grid(row=i, column=1, sticky="w", padx=10, pady=2)
    label_refs[k] = val_label

# === TABEL BARANG ===
table_frame = tk.Frame(scrollable_frame4, bg="white")
table_frame.pack(padx=20, pady=(10, 5), anchor="w")

headers = ["Nama", "Jumlah", "Harga", "Total"]
for col, head in enumerate(headers):
    tk.Label(table_frame, text=head, font=("Segoe UI", 10, "bold"), bg="#f1f1f1", padx=10, pady=6, relief="ridge").grid(row=0, column=col, sticky="nsew")

harga_awal_label = tk.Label(scrollable_frame4, text="", font=("Segoe UI", 11), bg="white", fg="#222")
harga_awal_label.pack(padx=20, fill='x', expand=True, anchor="center")

diskon_label = tk.Label(scrollable_frame4, text="", font=("Segoe UI", 11), bg="white", fg="#222")
diskon_label.pack(padx=20, fill='x', expand=True, anchor="center")

pajak_label = tk.Label(scrollable_frame4, text="", font=("Segoe UI", 11), bg="white", fg="#222")
pajak_label.pack(padx=20, fill='x', expand=True, anchor="center")

subtotal_label = tk.Label(scrollable_frame4, text="", font=("Segoe UI", 11, "bold"), bg="white", fg="#222")
subtotal_label.pack(padx=20, pady=(10, 0), fill='x', expand=True, anchor="center")


# === TOMBOL KEMBALI ===
tk.Button(scrollable_frame4, text="⬅ Kembali", command=lambda: show_frame("Riwayat"),
          bg="#e0e0e0", font=("Segoe UI", 10), padx=10, pady=5).pack(pady=20)

# === FUNGSI TAMPILKAN ===
def tampilkan_detail_di_frame4(trx_id4):
    trx_data4 = db.reference("transaksi").child(trx_id4).get()
    if not trx_data4:
        label_refs["ID Transaksi"].config(text="Data tidak ditemukan")
        return show_frame("DetailFrame")

    # Ambil data
    waktu4 = trx_data4.get("waktu", "-")
    totalsemua4 = trx_data4.get("total", "-")
    pembeli4 = trx_data4.get("pembeli", "Umum")
    tipe4 = trx_data4.get("tipe_transaksi", "-")
    metode4 = trx_data4.get("metode", "-")
    barang_list4 = trx_data4.get("barang", [])
    total_simpan4 = trx_data4.get("hargaawal", 0)
    diskon4 = trx_data4.get("diskon", 0)  # Pastikan ini disimpan saat transaksi
    pajak4 = trx_data4.get("tax", 0)  # Pajak juga

    try:
        from datetime import datetime
        waktu4 = datetime.fromisoformat(waktu4).strftime("%d %B %Y %H:%M:%S")
    except:
        pass

    # Update header
    label_refs["ID Transaksi"].config(text=trx_id4)
    label_refs["Waktu"].config(text=waktu4)
    label_refs["Pembeli"].config(text=pembeli4)
    label_refs["Tipe Transaksi"].config(text=tipe4)
    label_refs["Metode Pembayaran"].config(text=metode4)

    # Bersihkan tabel
    for widget in table_frame.winfo_children():
        if int(widget.grid_info()["row"]) > 0:
            widget.destroy()

    # Tampilkan tabel isi barang
    for i, item4 in enumerate(barang_list4, start=1):
        nama = item4.get("nama", "-")
        jumlah = item4.get("jumlah", 0)
        harga = item4.get("harga", 0)
        total = item4.get("total", harga * jumlah)

        tk.Label(table_frame, text=nama, bg="white", font=("Segoe UI", 10), padx=10, pady=5).grid(row=i, column=0, sticky="nsew")
        tk.Label(table_frame, text=jumlah, bg="white", font=("Segoe UI", 10)).grid(row=i, column=1, sticky="nsew")
        tk.Label(table_frame, text=f"Rp {harga:,}", bg="white", font=("Segoe UI", 10)).grid(row=i, column=2, sticky="nsew")
        tk.Label(table_frame, text=f"Rp {total:,}", bg="white", font=("Segoe UI", 10)).grid(row=i, column=3, sticky="nsew")

    subtotal_label.config(text=f"Subtotal: Rp {int(totalsemua4):,}")
    harga_awal_label.config(text=f"Harga Awal: Rp {total_simpan4:,}")
    diskon_label.config(text=f"Diskon: Rp {diskon4:,}")
    pajak_label.config(text=f"Tax: Rp {pajak4:,}")
    show_frame("DetailFrame")

# Frame utama
tk.Label(riw, text="Riwayat Transaksi", font=("Segoe UI", 18), bg="white").pack(pady=10)

# Frame filter di atas kanan
riw_filter_frame = tk.Frame(riw, bg="white")
riw_filter_frame.pack(fill="x", padx=20, pady=(0, 5), anchor="e")

tk.Label(riw_filter_frame, text="Filter Mingguan:", bg="white").pack(side="left")

# Buat daftar minggu (Senin - Minggu)
def generate_week_options():
    today = datetime.today()
    weeks = []
    for i in range(10):
        start = today - timedelta(days=today.weekday() + i * 7)
        end = start + timedelta(days=6)
        weeks.append((start, end))
    return [f"{start.strftime('%Y-%m-%d')} - {end.strftime('%Y-%m-%d')}" for start, end in weeks]


week_var = tk.StringVar()
week_dropdown = ttk.Combobox(riw_filter_frame, textvariable=week_var, state="readonly", width=30)
week_dropdown['values'] = generate_week_options()
if week_dropdown['values']:
    week_dropdown.current(0)
week_dropdown.pack(side="left", padx=10)
week_dropdown.current(0)

# Frame utama dua kolom
riw_main = tk.Frame(riw, bg="white")
riw_main.pack(fill="both", expand=True, padx=20, pady=10)

# === TABEL SCROLLABLE SEBELAH KIRI ===
riw_table_frame = tk.Frame(riw_main, bg="white")
riw_table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

# Canvas + Scrollbar
canvas = tk.Canvas(riw_table_frame, bg="white")
scroll_y = tk.Scrollbar(riw_table_frame, orient="vertical", command=canvas.yview)
scroll_frame = tk.Frame(canvas, bg="white")

scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
canvas.configure(yscrollcommand=scroll_y.set)

canvas.pack(side="left", fill="both", expand=True)
scroll_y.pack(side="right", fill="y")

riw_image_refs = {}

def konfirmasi_hapus_transaksi(trx_id):
    from tkinter import messagebox
    confirm = messagebox.askyesno("Konfirmasi", f"Yakin ingin menghapus transaksi\n{trx_id}?")
    if confirm:
        db.reference("transaksi").child(trx_id).delete()
        load_riwayat()


# === LOAD RIWAYAT ===
def load_riwayat():
    for widget in scroll_frame.winfo_children():
        widget.destroy()

    ref = db.reference("transaksi")
    data = ref.get()
    if not data:
        return

    sorted_data = sorted(data.items(), key=lambda x: x[1]["waktu"], reverse=True)

    selected_range = week_var.get()
    try:
        start_str, end_str = selected_range.split(" - ")
        start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d").date()
    except:
        start_date = end_date = None

    BG_COLOR = "#e9f3fc"
    FONT = ("Segoe UI", 10)

    headers = ["Order ID", "Order Date", "Transaction", "Cashier", "Payment", "Action"]
    for col, text in enumerate(headers):
        tk.Label(scroll_frame, text=text, font=("Segoe UI", 10, "bold"), bg="white", fg="#556677", padx=8, pady=6).grid(row=0, column=col, sticky="nsew")

    row_idx = 1
    for trx_id, val in sorted_data:
        waktu_str = val.get("waktu")
        if not waktu_str:
            continue

        try:
            waktu_obj = datetime.fromisoformat(waktu_str)
        except:
            continue

        if start_date and end_date:
            if not (start_date <= waktu_obj.date() <= end_date):
                continue

        tanggal = waktu_obj.strftime('%d %B %Y')
        pembeli = val.get("pembeli", "Umum")
        tipe = val.get("tipe_transaksi", "-")
        metode = val.get("metode", "-")
        kasir = val.get("kasir", "-")  # Jika ada field kasir

        cells = [trx_id, tanggal, tipe, kasir, metode]
        for col, val in enumerate(cells):
            tk.Label(scroll_frame, text=val, bg=BG_COLOR, font=FONT, padx=6, pady=4).grid(row=row_idx, column=col, sticky="nsew")

        # Kolom Aksi
        aksi_frame = tk.Frame(scroll_frame, bg=BG_COLOR)
        aksi_frame.grid(row=row_idx, column=5, sticky="nsew")

        btn_edit = tk.Button(aksi_frame, text="✏️", font=FONT, bd=0, bg=BG_COLOR, command=lambda tid=trx_id: tampilkan_detail_di_frame4(tid))
        btn_edit.pack(side="left", padx=2)

        btn_hapus = tk.Button(aksi_frame, text="🗑️", font=FONT, bd=0, fg="red", bg=BG_COLOR, command=lambda tid=trx_id: konfirmasi_hapus_transaksi(tid))
        btn_hapus.pack(side="left", padx=2)

        row_idx += 1


week_dropdown.bind("<<ComboboxSelected>>", lambda e: load_riwayat())

def update_barang_cb():
    data = db.reference("inventaris").get()
    print("Data inventaris dari Firebase:")
    print(data)  # Log semua isi dari 'inventaris'

    all_nama = []

    if data:
        for kategori_key, kategori_items in data.items():
            print(f"\nKategori: {kategori_key}")  # Log nama kategori, misalnya "Ayam", "Minuman"

            if isinstance(kategori_items, dict):
                for item_id, item in kategori_items.items():
                    print(f"  ID Barang: {item_id}")  # Log ID barang misal "ID001"
                    print(f"  Data Barang: {item}")  # Log isi dict barang

                    if isinstance(item, dict) and 'nama' in item:
                        print(f"    Nama ditemukan: {item['nama']}")  # Log nama barang yang ditambahkan
                        all_nama.append(item['nama'])
                    else:
                        print("    Tidak ada kunci 'nama' dalam item.")

    print("\nSemua nama yang ditemukan:", all_nama)

    barang_cb['values'] = all_nama

# === 📜 RIWAYAT TRANSAKSI PAGE END ===

# ----------------------------------------------------------------------------------------------------

# === ✏️ EDIT BARANG PAGE START ===

tk.Label(edit, text="Edit Barang", font=("Segoe UI", 18, "bold"), bg="white").pack(pady=10)

form3 = tk.Frame(edit, bg="white")
form3.pack(pady=20)

# === Komponen ===
edit_cb = ttk.Combobox(form3, width=40)
new_stok = ttk.Entry(form3, width=40)
new_harga = ttk.Entry(form3, width=40)

ttk.Label(form3, text="Pilih Barang:", background="white").grid(row=0, column=0, padx=10, pady=5, sticky="e")
edit_cb.grid(row=0, column=1, padx=10, pady=5)

ttk.Label(form3, text="Stok Baru:", background="white").grid(row=1, column=0, padx=10, pady=5, sticky="e")
new_stok.grid(row=1, column=1, padx=10, pady=5)

ttk.Label(form3, text="Harga Baru:", background="white").grid(row=2, column=0, padx=10, pady=5, sticky="e")
new_harga.grid(row=2, column=1, padx=10, pady=5)

# === Gambar Baru ===
gambar_edit_frame = tk.Frame(form3, bg="white")
gambar_edit_frame.grid(row=3, column=1, sticky="w", padx=10, pady=10)

gambar_edit_path = None
preview_label = tk.Label(gambar_edit_frame, text="[Preview Gambar]", bg="white")
preview_label.pack(side="left", padx=(0, 10))

def pilih_gambar_edit():
    global gambar_edit_path
    from tkinter import filedialog
    path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
    if path:
        gambar_edit_path = path
        from PIL import Image, ImageTk
        img = Image.open(path).resize((60, 60))
        img_tk = ImageTk.PhotoImage(img)
        preview_label.config(image=img_tk, text="")
        preview_label.image = img_tk

ttk.Button(gambar_edit_frame, text="Pilih Gambar Baru", command=pilih_gambar_edit).pack(side="left")

# === Aksi Update ===
def update_barang():
    global gambar_edit_path
    try:
        nama = edit_cb.get()
        stok = int(new_stok.get())
        harga = int(new_harga.get())

        ref = db.reference("inventaris")
        data_inventaris = ref.get() or {}

        item_ditemukan = False

        for kategori_key, kategori_data in data_inventaris.items():
            for item_key, item in kategori_data.items():
                if item.get("nama") == nama:
                    gambar_url = item.get("gambar", "")

                    # Upload gambar baru jika ada
                    if gambar_edit_path:
                        bucket = storage.bucket()
                        blob = bucket.blob(f'Gambar Barang/{item_key}_{os.path.basename(gambar_edit_path)}')
                        blob.upload_from_filename(gambar_edit_path)
                        blob.make_public()
                        gambar_url = blob.public_url

                    ref.child(f"{kategori_key}/{item_key}").update({
                        "stok": stok,
                        "harga": harga,
                        "gambar": gambar_url
                    })

                    messagebox.showinfo("Sukses", "Barang berhasil diperbarui.")
                    gambar_edit_path = None
                    preview_label.config(image="", text="[Preview Gambar]")
                    update_barang_cb()
                    item_ditemukan = True
                    return

        if not item_ditemukan:
            messagebox.showerror("Error", "Barang tidak ditemukan.")
    except Exception as e:
        messagebox.showerror("Error", str(e))


ttk.Button(form3, text="Update Barang", command=update_barang).grid(row=4, column=0, columnspan=2, pady=20)

def isi_data_barang(event=None):
    try:
        nama = edit_cb.get()
        print(f"[INFO] Nama dipilih dari ComboBox: {nama}")
        ref = db.reference("inventaris")
        data_inventaris = ref.get() or {}

        print("[DEBUG] Data inventaris diambil:")
        print(data_inventaris)

        # Telusuri tiap kategori
        for kategori_nama, kategori_data in data_inventaris.items():
            print(f"[TRACE] Kategori: {kategori_nama}")
            if isinstance(kategori_data, dict):
                # Telusuri tiap item dalam kategori
                for item_id, item_info in kategori_data.items():
                    print(f"  [TRACE] Cek item ID: {item_id} -> nama: {item_info.get('nama')}")
                    if isinstance(item_info, dict) and item_info.get("nama") == nama:
                        print("[SUCCESS] Barang ditemukan!")
                        print(item_info)

                        # Update stok dan harga
                        new_stok.delete(0, tk.END)
                        new_harga.delete(0, tk.END)
                        new_stok.insert(0, str(item_info.get("stok", 0)))
                        new_harga.insert(0, str(item_info.get("harga", 0)))

                        # Tampilkan gambar jika ada
                        img_url = item_info.get("gambar", "")
                        if img_url:
                            from urllib.request import urlopen
                            img = Image.open(BytesIO(urlopen(img_url).read())).resize((60, 60))
                            img_tk = ImageTk.PhotoImage(img)
                            preview_label.config(image=img_tk, text="")
                            preview_label.image = img_tk
                        else:
                            preview_label.config(image="", text="[Preview Gambar]")
                        return  # Barang ditemukan

        # Jika tidak ditemukan
        print("[WARNING] Barang tidak ditemukan dalam database.")
        preview_label.config(image="", text="[Barang tidak ditemukan]")
        new_stok.delete(0, tk.END)
        new_harga.delete(0, tk.END)

    except Exception as e:
        print(f"[ERROR] Gagal tampilkan data: {e}")



edit_cb.bind("<<ComboboxSelected>>", isi_data_barang)

# Auto-load saat frame muncul
edit.bind("<Visibility>", lambda e: update_barang_cb())

# === ✏️ EDIT BARANG PAGE END ===

# ----------------------------------------------------------------------------------------------------

# ===  TAMBAH BARANG PAGE START ===

gambar_path = None  # Global path
preview_img = None  # Global preview image agar tidak hilang dari memori
kategori_refs2 = []

def pilih_gambar():
    global gambar_path, preview_img
    path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg;*.jpeg;*.png")])
    if path:
        gambar_path = path
        img = Image.open(gambar_path).resize((100, 100))
        preview_img = ImageTk.PhotoImage(img)

        if hasattr(pilih_gambar, 'preview_label'):
            pilih_gambar.preview_label.config(image=preview_img)
            pilih_gambar.preview_label.image = preview_img
        else:
            pilih_gambar.preview_label = tk.Label(gambar_frame, image=preview_img, bg="white")
            pilih_gambar.preview_label.pack(side="left", padx=10)

        lbl_gambar.config(text="")  # Ganti dari pack_forget jadi update teks

kategori_terpilih = tk.StringVar()

def ambil_daftar_kategori():
    ref = db.reference("kategori")
    data = ref.get()
    return list(data.values()) if data else []

tk.Label(tambah, text="Tambah Barang Baru", font=("Segoe UI", 18, "bold"), bg="white").pack(pady=15)

kategori_frame = tk.Frame(tambah, bg="white")
kategori_frame.pack(pady=(0, 10))

tk.Label(kategori_frame, text="Pilih Kategori:", background="white", font=("Segoe UI", 12)).pack(side="left", padx=5)

# === Frame Kategori Kotak (horizontal scrollable) ===
kategori_scroll_frame2 = tk.Frame(tambah, bg="white")
kategori_scroll_frame2.pack(fill="x", padx=20, pady=(0, 10))

kategori_canvas2 = tk.Canvas(kategori_scroll_frame2, height=130, bg="white", highlightthickness=0)
kategori_scrollbar2 = ttk.Scrollbar(kategori_scroll_frame2, orient="horizontal", command=kategori_canvas2.xview)

kategori_inner_frame2 = tk.Frame(kategori_canvas2, bg="white")
kategori_inner_frame2.bind("<Configure>", lambda e: kategori_canvas2.configure(scrollregion=kategori_canvas2.bbox("all")))
kategori_canvas2.create_window((0, 0), window=kategori_inner_frame2, anchor="nw")

kategori_canvas2.configure(xscrollcommand=kategori_scrollbar2.set)
kategori_canvas2.pack(side="top", fill="x", expand=True)
kategori_scrollbar2.pack(side="bottom", fill="x")

def kategori_dipilih_dari_kotak2(nama):
    kategori_terpilih.set(nama)
    form_kategori_baru.pack_forget()
    form_tambah.pack()


kategori_images2 = []  # untuk menyimpan gambar agar tidak hilang
kategori_buttons2 = {}

def kategori_dipilih_dengan_highlight(nama):
    kategori_terpilih.set(nama)
    form_kategori_baru.pack_forget()
    form_tambah.pack()

    # Update tampilan visual (highlight selected)
    for frame, nm in kategori_refs2:
        if nm == nama:
            frame.config(bg="#a7c7e7")  # biru muda
        else:
            frame.config(bg="white")  # normal

def tampilkan_kategori_kotak2():
    for widget in kategori_inner_frame2.winfo_children():
        widget.destroy()
    kategori_images2.clear()
    kategori_buttons2.clear()

    daftar_kategori = ambil_daftar_kategori()

    for idx, nama_kategori in enumerate(daftar_kategori):
        # === RENDER UI DULU (kosong) ===
        kategori_btn = tk.Frame(kategori_inner_frame2, bg="white", cursor="hand2")
        kategori_btn.pack(side="left", padx=5, pady=5)

        frame_gambar = tk.Frame(kategori_btn, bg="white", bd=2, relief="solid")
        frame_gambar.pack(padx=5, pady=(5, 2))

        img_label = tk.Label(frame_gambar, text="Loading...", bg="white")
        img_label.pack()

        label_nama = tk.Label(kategori_btn, text=f"{nama_kategori} (...)", bg="white", font=("Segoe UI", 10))
        label_nama.pack(pady=(0, 5))

        kategori_buttons2[nama_kategori] = kategori_btn

        def load_detail_kategori(nama=nama_kategori, label_img=img_label, label_nama=label_nama, idx=idx):
            try:
                data = db.reference("daftar_kategori").child(nama).get()
                gambar_url = data.get("gambar", "")
                jumlah_item = len(db.reference("inventaris").child(nama).get() or {})
                nama_tampil = f"{nama} ({jumlah_item})"

                label_nama.config(text=nama_tampil)

                if gambar_url:
                    response = requests.get(gambar_url, stream=True, timeout=5)
                    img_data = Image.open(response.raw).convert("RGBA").resize((120, 60))
                    img_tk = ImageTk.PhotoImage(img_data)
                    label_img.config(image=img_tk, text="")
                    label_img.image = img_tk
                    kategori_images2.append(img_tk)
                else:
                    label_img.config(text="[No Image]")
            except Exception as e:
                print(f"[Load Error] {nama} | {e}")
                label_img.config(text="❌", font=("Arial", 14), image="", compound="top")

        # 🔁 Load data + gambar async
        threading.Thread(target=load_detail_kategori).start()

        # Event klik
        def on_click_kategori(nama=nama_kategori):
            kategori_terpilih.set(nama)
            form_kategori_baru.pack_forget()
            form_tambah.pack()
            for btn in kategori_buttons2.values():
                btn.config(bg="white")
            kategori_buttons2[nama].config(bg="#cce")

        kategori_btn.bind("<Button-1>", lambda e, nama=nama_kategori: on_click_kategori(nama))
        img_label.bind("<Button-1>", lambda e, nama=nama_kategori: on_click_kategori(nama))


# Form tambah kategori baru (sembunyikan default)
form_kategori_baru = tk.Frame(tambah, bg="white", bd=1, relief="solid", padx=10, pady=10)
form_kategori_baru.pack(pady=5)
form_kategori_baru.pack_forget()  # sembunyikan dulu

tk.Label(form_kategori_baru, text="Nama Kategori Baru:", background="white").grid(row=0, column=0, sticky="e", padx=5, pady=5)
entry_nama_kategori = ttk.Entry(form_kategori_baru, width=30)
entry_nama_kategori.grid(row=0, column=1, padx=5, pady=5)

def pilih_gambar_kategori():
    global kategori_gambar_path, kategori_preview_img
    kategori_gambar_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg;*.jpeg;*.png")])
    if kategori_gambar_path:
        img = Image.open(kategori_gambar_path).resize((60, 60))
        kategori_preview_img = ImageTk.PhotoImage(img)
        kategori_img_preview.config(image=kategori_preview_img)
        kategori_img_preview.image = kategori_preview_img

kategori_gambar_path = None
kategori_preview_img = None

tk.Label(form_kategori_baru, text="Gambar Kategori:", background="white").grid(row=1, column=0, sticky="e", padx=5, pady=5)
kategori_gambar_btn = ttk.Button(form_kategori_baru, text="Pilih Gambar", command=pilih_gambar_kategori)
kategori_gambar_btn.grid(row=1, column=1, sticky="w", padx=5, pady=5)
kategori_img_preview = tk.Label(form_kategori_baru, bg="white")
kategori_img_preview.grid(row=1, column=2, padx=5)


def buat_kategori_baru():
    kategori_terpilih.set("")  # Kosongkan combo box
    form_kategori_baru.pack()  # Tampilkan form
    form_tambah.pack_forget()  # Sembunyikan form barang


ttk.Button(kategori_frame, text="Buat Kategori Baru", command=buat_kategori_baru).pack(side="left", padx=5)

form_tambah = tk.Frame(tambah, bg="white", bd=1, relief="solid", padx=20, pady=20)
form_tambah.pack(pady=10)

# === INPUT FIELDS ===
ttk.Label(form_tambah, text="Nama Barang:", background="white").grid(row=0, column=0, sticky="e", padx=10, pady=5)
tambah_nama = ttk.Entry(form_tambah, width=40)
tambah_nama.grid(row=0, column=1, padx=10, pady=5)

ttk.Label(form_tambah, text="Stok Awal:", background="white").grid(row=1, column=0, sticky="e", padx=10, pady=5)
tambah_stok = ttk.Entry(form_tambah, width=40)
tambah_stok.grid(row=1, column=1, padx=10, pady=5)

ttk.Label(form_tambah, text="Harga Satuan:", background="white").grid(row=2, column=0, sticky="e", padx=10, pady=5)
tambah_harga = ttk.Entry(form_tambah, width=40)
tambah_harga.grid(row=2, column=1, padx=10, pady=5)

# === PILIH GAMBAR + PREVIEW ===
ttk.Label(form_tambah, text="Gambar Barang:", background="white").grid(row=3, column=0, sticky="ne", padx=10, pady=10)
gambar_frame = tk.Frame(form_tambah, bg="white")
gambar_frame.grid(row=3, column=1, sticky="w")

btn_gambar = ttk.Button(gambar_frame, text="Pilih Gambar", command=pilih_gambar)
btn_gambar.pack(side="left", padx=(0, 10))

lbl_gambar = ttk.Label(gambar_frame, text="Belum ada gambar dipilih", background="white")
lbl_gambar.pack(side="left")

def on_kategori_selected(event=None):
    if kategori_terpilih.get():
        form_tambah.pack(pady=10)
        form_kategori_baru.pack_forget()
    else:
        form_tambah.pack_forget()


form_tambah.pack_forget()

def simpan_kategori_baru():
    global kategori_gambar_path
    nama_kategori = entry_nama_kategori.get().strip()

    if not nama_kategori:
        messagebox.showwarning("Peringatan", "Nama kategori tidak boleh kosong.")
        return

    # Upload gambar kategori jika ada
    gambar_url = ""
    if kategori_gambar_path:
        try:
            id_kat = str(int(datetime.now().timestamp()))
            bucket = storage.bucket()
            blob = bucket.blob(f'Gambar Kategori/{id_kat}_{os.path.basename(kategori_gambar_path)}')
            blob.upload_from_filename(kategori_gambar_path)
            blob.make_public()
            gambar_url = blob.public_url
        except Exception as e:
            messagebox.showerror("Error", f"Gagal upload gambar kategori: {e}")
            return

    try:
        db.reference("kategori").push(nama_kategori)  # Tambah ke dropdown
        db.reference("daftar_kategori").child(nama_kategori).set({
            "gambar": gambar_url
        })  # Simpan detail kategori

        tampilkan_kategori_kotak2()

        kategori_terpilih.set(nama_kategori)

        messagebox.showinfo("Sukses", "Kategori berhasil ditambahkan.")
        entry_nama_kategori.delete(0, tk.END)
        kategori_img_preview.config(image='')
        kategori_gambar_path = None
        form_kategori_baru.pack_forget()
        form_tambah.pack()  # Tampilkan form barang

    except Exception as e:
        messagebox.showerror("Error", f"Gagal simpan kategori: {e}")


ttk.Button(form_kategori_baru, text="Simpan Kategori Baru", command=simpan_kategori_baru).grid(
    row=2, column=0, columnspan=3, pady=10
)


def simpan_barang_baru():
    try:
        global gambar_path
        kategori = kategori_terpilih.get().strip()
        nama = tambah_nama.get().strip()
        stok = int(tambah_stok.get())
        harga = int(tambah_harga.get())

        if not kategori:
            messagebox.showwarning("Peringatan", "Silakan pilih kategori terlebih dahulu.")
            return

        if not nama:
            messagebox.showwarning("Peringatan", "Nama barang tidak boleh kosong.")
            return

        # Ambil semua data dari Firebase
        all_barang = db.reference("inventaris").get()

        # Cek apakah nama barang sudah ada
        if all_barang:
            for item in all_barang.values():
                if item.get("nama", "").lower() == nama.lower():
                    messagebox.showerror("Error", f"Barang '{nama}' sudah ada dalam database.")
                    return

        # Generate ID dan simpan data barang (tanpa gambar dulu)
        idbrg = str(int(datetime.now().timestamp()))

        # Upload gambar jika ada
        gambar_url = ""
        if gambar_path:
            bucket = storage.bucket()
            blob = bucket.blob(f'Gambar Barang/{idbrg}_{os.path.basename(gambar_path)}')
            blob.upload_from_filename(gambar_path)
            blob.make_public()
            gambar_url = blob.public_url

        # Simpan ke Firebase di dalam kategori
        db.reference("inventaris").child(kategori).child(idbrg).set({
            "nama": nama,
            "stok": stok,
            "harga": harga,
            "gambar": gambar_url
        })

        messagebox.showinfo("Sukses", "Barang berhasil ditambahkan.")

        tambah_nama.delete(0, tk.END)
        tambah_stok.delete(0, tk.END)
        tambah_harga.delete(0, tk.END)
        lbl_gambar.config(text="Belum ada gambar dipilih")
        gambar_path = None
        update_barang_cb()

    except Exception as e:
        messagebox.showerror("Error", f"Gagal menambahkan barang: {e}")

ttk.Button(form_tambah, text="Tambah Barang", command=simpan_barang_baru).grid(
    row=4, column=0, columnspan=2, pady=20
)

# ===  TAMBAH BARANG PAGE END ===

# ----------------------------------------------------------------------------------------------------

# ===  TRANSAKSI PAGE START (ScanAI + Manual) ===

from pathlib import Path
import numpy as np
import cv2
from ultralytics import YOLO
import torch
from tkinter import Tk, Canvas, Button, PhotoImage, messagebox, Frame, Label, Scrollbar
import random

# === Global Configuration ===
MODEL_PATH = "../Hasil/yolo11n-seg(v1)/weights/best_rknn_model" 
USE_CAMERA = True
USE_STATIC_IMAGE = False
STATIC_IMAGE_PATH = "assets/frame0/image_3.png"
USE_CUDA = False
IMG_SIZE = 896
CONFIDENCE = 0.7
IOU = 0.7
AUGMENT = 0.0
MASK_ALPHA = 0.4  # Transparency factor for masks (0.0 transparent, 1.0 opaque)
# Additional filtering parameters to prevent background detections
MIN_DETECTION_AREA_RATIO = 0.02  # Minimum area ratio (2% of frame) - increased from 1%
MAX_DETECTION_AREA_RATIO = 0.6   # Maximum area ratio (60% of frame) - decreased from 80%
MIN_ASPECT_RATIO = 0.3           # Minimum aspect ratio (width/height) - increased from 0.2
MAX_ASPECT_RATIO = 3.0           # Maximum aspect ratio (width/height) - decreased from 5.0

keranjang_final = {}
def random_hex_color():
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

nama_terdeteksi = set()
def update_keranjang_final():
    # 1. Ambil nama-nama yang sekarang terdeteksi oleh AI
    global nama_terdeteksi
    nama_terdeteksi = set(last_detected_items.keys())

    # 2. Hapus item AI yang sudah tidak terdeteksi lagi
    nama_saat_ini = list(keranjang_final.keys())
    for nama in nama_saat_ini:
        if nama not in nama_terdeteksi:
            item = keranjang_final[nama]
            if item.get("source") == "ai":
                del keranjang_final[nama]

    # 3. Update / tambahkan item dari deteksi terbaru
    for nama, data in last_detected_items.items():
        harga = data["harga"]
        jumlah = data["quantity"]
        total = harga * jumlah
        keranjang_final[nama] = {
            "quantity": jumlah,
            "harga": harga,
            "total": total,
            "source": "ai"  # tandai ini dari AI
        }
def update_keranjang_dari_AI(detected_now):
    global last_detected_items
    last_detected_items.clear()
    last_detected_items.update(detected_now)
    update_keranjang_final()  # Panggil ini setelah update

def get_keranjang_from_deteksi():
    return [
        {
            "nama": name,
            "jumlah": data["quantity"],
            "harga": data["harga"],
            "total": data["total"]
        }
        for name, data in keranjang_final.items()
    ]

payment_frame2 = tk.Frame(home2pay, bg="white")
payment_frame2.pack(fill="both", expand=True)

hargaakhir = 0

def simpan_transaksi_multi2():
    global last_detected_items, hargaakhir, current_user_name, diskontotal, taxtotal, hargaawal, keranjang_final

    keranjang = get_keranjang_from_deteksi()
    if not keranjang:
        messagebox.showwarning("Kosong", "Tidak ada item terdeteksi.")
        return

    final_price = hargaakhir
    metode_pilihan = metode_var.get()
    if not metode_pilihan:
        messagebox.showwarning("Pilih Metode", "Silakan pilih metode pembayaran terlebih dahulu.")
        return

    for widget in payment_frame2.winfo_children():
        widget.destroy()

    inner = tk.Frame(payment_frame2, bg="white")
    inner.pack(padx=30, pady=20, fill="both", expand=True)

    left_frame = tk.Frame(inner, bg="white")
    left_frame.pack(side="left", fill="both", expand=True, padx=(0, 20))

    right_frame = tk.Frame(inner, bg="white")
    right_frame.pack(side="right", fill="y", padx=(20, 0))

    # Entry untuk jumlah bayar
    bayar_var = tk.StringVar(value="")
    bayar_entry = ttk.Entry(left_frame, textvariable=bayar_var, font=("Segoe UI", 18), justify="right", state="readonly", width=20)
    bayar_entry.pack(pady=(0, 20))

    # Frame untuk keypad
    pad_frame = tk.Frame(left_frame, bg="white")
    pad_frame.pack()

    pad_buttons = [
        ["7", "8", "9", "100000", "50000"],
        ["4", "5", "6", "20000", "10000"],
        ["1", "2", "3", "5000", "2000"],
        ["0", "00", "000", "1000", "⌫"]
    ]

    def update_bayar(val):
        current_val = bayar_var.get()
        try:
            current = int(current_val or "0")
        except ValueError:
            current = 0

        if val == "⌫":
            bayar_var.set(current_val[:-1])
        elif val in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "00", "000"]:
            bayar_var.set(current_val + val)
        else:
            try:
                bayar_var.set(str(current + int(val)))
            except:
                pass

        try:
            dibayar = int(bayar_var.get())
            kembalian = dibayar - final_price
            if kembalian >= 0:
                kembalian_label.config(text=f"idr {kembalian:,}".replace(",", "."), foreground="green")
            else:
                kembalian_label.config(text=f"kurang Rp {abs(kembalian):,}", foreground="red")
        except:
            kembalian_label.config(text="")

    for row in pad_buttons:
        row_frame = tk.Frame(pad_frame, bg="white")
        row_frame.pack()
        for val in row:
            display = val
            if val == "⌫":
                btn = tk.Button(row_frame, text="⌫", font=("Segoe UI", 14), width=6, height=2,
                                command=lambda v=val: update_bayar(v))
            elif val.isdigit() and int(val) >= 1000:
                display = f"{int(val):,}".replace(",", ".")
                btn = tk.Button(row_frame, text=display, font=("Segoe UI", 12, "bold"), width=6, height=2,
                                command=lambda v=val: update_bayar(v))
            else:
                btn = tk.Button(row_frame, text=display, font=("Segoe UI", 12), width=6, height=2,
                                command=lambda v=val: update_bayar(v))
            btn.pack(side="left", padx=3, pady=3)

    # Informasi di sisi kanan
    tk.Label(right_frame, text="Total", font=("Segoe UI", 12), bg="white", fg="#6c7a91").pack(anchor="w")
    tk.Label(right_frame, text=f"idr {final_price:,}".replace(",", "."), font=("Segoe UI", 12), bg="white").pack(anchor="w", pady=(0, 10))

    tk.Label(right_frame, text="Paid", font=("Segoe UI", 12), bg="white", fg="#6c7a91").pack(anchor="w")
    tk.Label(right_frame, textvariable=bayar_var, font=("Segoe UI", 12), bg="white").pack(anchor="w", pady=(0, 10))

    tk.Frame(right_frame, height=2, bg="#ccc").pack(fill="x", pady=10)

    tk.Label(right_frame, text="Change", font=("Segoe UI", 12, "bold"), bg="white").pack(anchor="w")
    kembalian_label = tk.Label(right_frame, text="", font=("Segoe UI", 12, "bold"), background="white", foreground="green")
    kembalian_label.pack(anchor="w", pady=5)

    # Tombol Proses & Batal
    def kembali():
        keranjang_final.clear()
        show_frame("Home2")

    def proses_pembayaran():
        try:
            jumlah_bayar = int(bayar_var.get())
        except ValueError:
            messagebox.showerror("Error", "Masukkan jumlah bayar yang valid")
            return

        if jumlah_bayar < final_price:
            messagebox.showwarning("Kurang", "Jumlah bayar kurang dari total belanja.")
            return

        kembalian = jumlah_bayar - final_price

        trx_id = "trx_" + datetime.now().strftime("%Y%m%d%H%M%S")
        pembeli_id = pembeli_cb.get() if pembeli_cb.get() else "Umum"
        tipe_transaksi = transaksi_var2.get()

        for item in keranjang:
            for key in item:
                if isinstance(item[key], (np.integer, np.int64, np.int32)):
                    item[key] = int(item[key])
                elif isinstance(item[key], (np.floating, np.float64, np.float32)):
                    item[key] = float(item[key])

        db.reference("transaksi").child(trx_id).set({
            "barang": keranjang,
            "total": int(final_price),
            "dibayar": int(jumlah_bayar),
            "kembalian": int(kembalian),
            "waktu": datetime.now().isoformat(),
            "pembeli": pembeli_id,
            "metode": metode_pilihan,
            "tipe_transaksi": tipe_transaksi,
            "kasir": current_user_name,
            "tax": int(taxtotal),
            "diskon": int(diskontotal),
            "hargaawal": int(hargaawal)
        })

        # ✅ Update stok inventaris
        inventaris_ref = db.reference("inventaris")
        inventaris_data = inventaris_ref.get()

        for item in keranjang:
            nama_keranjang = item.get("nama")
            jumlah_beli = item.get("jumlah", 0)

            for kategori, items in (inventaris_data or {}).items():
                for item_id, data in items.items():
                    if data.get("nama") == nama_keranjang:
                        stok_lama = data.get("stok", 0)
                        stok_baru = stok_lama - jumlah_beli if stok_lama >= jumlah_beli else 0
                        inventaris_ref.child(f"{kategori}/{item_id}").update({"stok": stok_baru})

        if pembeli_cb.get():
            db.reference("checkout").child(pembeli_id).delete()
            pembeli_cb.set("")

        kembali()
        show_struk(trx_id, final_price, metode_pilihan, keranjang)

    button_frame = tk.Frame(right_frame, bg="white")
    button_frame.pack(pady=15, anchor="w")

    ttk.Button(button_frame, text="✅ Proses Pembayaran", command=proses_pembayaran).pack(side="left", padx=10)
    ttk.Button(button_frame, text="❌ Batal", command=kembali).pack(side="left", padx=10)

    show_frame("Home2pay")


ref_inventaris = db.reference("inventaris")
data_inventaris = ref_inventaris.get() or {}

CLASS_NAMES = []
PRICES = {}
DISCOUNTS = {}
BOX_COLORS = {}

for kategori_data in data_inventaris.values():
    for item in kategori_data.values():
        nama = item.get("nama")
        harga = item.get("harga")
        diskon = item.get("discount", 0)  # Ambil diskon, default ke 0 jika tidak ada

        if nama and nama not in CLASS_NAMES:
            CLASS_NAMES.append(nama)
            PRICES[nama] = harga if harga is not None else 0
            DISCOUNTS[nama] = diskon if diskon is not None else 0
            BOX_COLORS[nama] = random_hex_color()

MASK_COLORS = BOX_COLORS.copy()

# Asset paths
BASE_PATH = Path(__file__).parent
ASSETS_PATH = BASE_PATH / "assets" / "frame0"

def relative_to_assets(fn: str) -> str:
    return str(ASSETS_PATH / fn)

# === Model Initialization ===
# device = "cuda" if USE_CUDA else "cpu"
# model = YOLO(MODEL_PATH)
# model.to(device)
device = "cuda" if torch.cuda.is_available() else "cpu"
model = YOLO(MODEL_PATH, task="segment") #.to(device)

# === Video / Static Setup ===
cap = cv2.VideoCapture(1) if USE_CAMERA else None
static_img = None
if USE_STATIC_IMAGE:
    static_img = cv2.imread(STATIC_IMAGE_PATH)
    if static_img is None:
        raise FileNotFoundError(f"Static image not found: {STATIC_IMAGE_PATH}")

# === Utils ===
def format_currency(x: int) -> str:
    return f"IDR {x:,}".replace(",", ".")

def compute_iou(b1, b2):
    x1, y1 = max(b1[0], b2[0]), max(b1[1], b2[1])
    x2, y2 = min(b1[2], b2[2]), min(b1[3], b2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
    area2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0

def is_likely_background(mask, bbox, frame_shape):
    """
    Enhanced filtering to identify and exclude background detections
    based on edge density, mask characteristics, and position.
    """
    x1, y1, x2, y2 = bbox
    h, w = frame_shape[:2]
    
    # Extract the region of interest
    roi = mask[y1:y2, x1:x2]
    if roi.size == 0:
        return True
    
    # Calculate edge density
    edges = cv2.Canny(roi, 50, 150)
    edge_density = np.sum(edges > 0) / roi.size
    
    # Calculate mask density (how much of the bbox is filled)
    mask_density = np.sum(roi > 0) / roi.size
    
    # Calculate position-based filtering
    # Check if detection is too close to frame edges (likely background)
    edge_margin = 20  # pixels from edge
    too_close_to_edge = (x1 < edge_margin or y1 < edge_margin or 
                        x2 > w - edge_margin or y2 > h - edge_margin)
    
    # Check if detection spans too much of the frame
    frame_area = h * w
    detection_area = (x2 - x1) * (y2 - y1)
    area_ratio = detection_area / frame_area
    
    # Enhanced background indicators:
    # 1. Very low edge density (smooth background)
    # 2. Very high mask density (covers most of bbox)
    # 3. Very low mask density (sparse detection)
    # 4. Too close to frame edges
    # 5. Too large relative to frame
    
    if (edge_density < 0.015 or      # Very smooth (increased threshold)
        mask_density > 0.9 or         # Almost completely filled (decreased threshold)
        mask_density < 0.08 or        # Very sparse (increased threshold)
        too_close_to_edge or          # Too close to edges
        area_ratio > 0.5):           # Too large (50% of frame)
        return True
    
    return False

def pilih_metode(nama):
    metode_var.set(nama)
    print("Metode dipilih:", nama)
    for btn in payment_buttons:
        if btn['text'] == nama:
            btn.config(bg="#6aa4d4", activebackground="#6aa4d4")  # tombol aktif
        else:
            btn.config(bg="#c2d2e1", activebackground="#c2d2e1")  # tombol tidak aktif

# === GUI Setup ===
canvas = Canvas(home2, width=1920*0.8, height=1080*0.8, bg="white", bd=0, highlightthickness=0)
canvas.place(x=0, y=0)

default_bg = "#C2D2E1"
active_bg = "#6AA4D4"

# Load assets
bg1 = PhotoImage(file=relative_to_assets("image_1.png"))
# bg2 = PhotoImage(file=relative_to_assets("image_2.png"))
payment_icons = [PhotoImage(file=relative_to_assets(fn)) for fn in ["image_4.png","image_5.png","image_6.png","image_7.png","image_8.png"]]
ci = PhotoImage(file=relative_to_assets("image_9.png"))
btn_img = PhotoImage(file=relative_to_assets("button_1.png"))
icon_cam = PhotoImage(file=relative_to_assets("image_3.png"))
Colom_count = PhotoImage(file=relative_to_assets("image_11.png"))
metode_var = tk.StringVar(value="")
# Static UI elements

canvas.create_rectangle(577, 10, 1024, 708, fill="white", outline="") # dikurangi 30 di atas dan bawah
canvas.create_image(769, 70, image=ci)  # 120 -> 90
canvas.create_text(800, 55, anchor="nw", text="Cart", fill="#DBA576", font=("FamiljenGrotesk Bold", -24))  # 105 -> 75

transaksi_var2 = tk.StringVar(value="Dine-in")

transaksi_label = tk.Label(
    home2,
    text="Tipe Transaksi:",
    font=("Arial", 10, "bold"),
    bg="white",
    fg="#57708c"
)
transaksi_label.place(x=575, y=500)

tx_types = ["Dine-in", "Takeaway", "GoFood"]
tx_buttons = {}
x_start = 690

# Warna
default_bg = "#c2d2e1"
selected_bg = "#6aa4d4"

def on_transaksi_selected(selected_tx):
    transaksi_var2.set(selected_tx)
    for tx, btn in tx_buttons.items():
        btn.configure(bg=selected_bg if tx == selected_tx else default_bg)

for i, tx in enumerate(tx_types):
    btn = Button(
        home2,
        text=tx,
        font=("Arial", 10, "bold"),
        width=10,
        height=1,
        bd=1,
        relief="ridge",
        bg=default_bg,
        activebackground=default_bg,
        command=lambda v=tx: on_transaksi_selected(v)
    )
    btn.place(x=x_start + i * 110, y=500, width=100, height=30)
    tx_buttons[tx] = btn

# Tandai pilihan awal
on_transaksi_selected("Dine-in")

# Order ID and Checkout button
current_order_id = 1
order_id = canvas.create_text(645, 135, anchor="nw", text=f"Order #[{current_order_id:04d}] --:--:--", fill="#000000", font=("microsoft sans serif", -20))

def on_checkout():
    global current_order_id
    current_order_id += 1
    now = datetime.datetime.now().strftime("%d %b %Y %H:%M:%S")
    canvas.itemconfigure(order_id, text=f"Order #[{current_order_id:04d}] {now}")
    messagebox.showinfo("Transaksi", f"Order #{current_order_id:04d} Berhasil")

def get_placeholder_image(size=(60, 60)):
    im = Image.new("RGB", size, (200, 200, 200))
    return ImageTk.PhotoImage(im)
def tambah_ke_keranjang(nama, harga):
    global keranjang_final
    if nama in keranjang_final:
        keranjang_final[nama]["quantity"] += 1
    else:
        keranjang_final[nama] = {"quantity": 1, "harga": harga, "total": harga, "source": "manual"}
    # update_keranjang_final()

def update_total_item():
    total = sum(item["quantity"] for item in keranjang_final.values())
    print(f"Total Items: {total}")  # Debug
    try:
        canvas.itemconfig(count_id, text=f"Total Items: [{total}] Items")
    except:
        pass  # Hindari error jika count_id tidak ada

def tampilkan_popup_item(nama_kategori):
    window = tk.Toplevel()
    window.title(f"Kategori: {nama_kategori}")
    canvas = Canvas(window, width=400, height=400)
    canvas.pack()

    data = db.reference(f"inventaris/{nama_kategori}").get()

    for i, (id_item, item) in enumerate(data.items()):
        nama = item["nama"]
        harga = item["harga"]
        img_url = item["gambar"]

        def buat_tombol(nama_item=nama, harga_item=harga):
            return lambda: tambah_ke_keranjang(nama_item, harga_item)

        frame = tk.Frame(window)
        frame.place(x=20 + (i % 3) * 120, y=20 + (i // 3) * 130)

        placeholder = get_placeholder_image()
        btn = Button(frame, image=placeholder, command=buat_tombol(), bd=0)
        btn.image = placeholder
        btn.pack()

        # Label tanpa background
        label = tk.Label(frame, text=nama, wraplength=100, font=("Segoe UI", 9))
        label.pack(pady=2)

        def update_button_image(photo, b=btn):
            b.configure(image=photo)
            b.image = photo

        load_image_async(img_url, lambda img, b=btn: window.after(0, lambda: update_button_image(img, b)))

def load_image_async(url, callback, size=(60, 60)):
    def task():
        try:
            with urllib.request.urlopen(url) as u:
                raw_data = u.read()
            im = Image.open(io.BytesIO(raw_data))
            im = im.resize(size)
            photo = ImageTk.PhotoImage(im)
            callback(photo)
        except Exception as e:
            print(f"Failed to load {url}: {e}")
    threading.Thread(target=task).start()


kategori_buttons = []


def tampilkan_kategori(parent_frame, y=500):
    global kategori_buttons
    kategori_buttons.clear()

    item_width = 100
    spacing = 20
    height_image = 80
    max_canvas_width = 500  # BATAS LEBAR MAKSIMAL

    offset_y = 50  # Penurunan posisi sebanyak 50px

    # === Tambahkan Label "Add to Cart" di atas canvas ===
    label_add = tk.Label(parent_frame, text="Add to Cart", font=("Segoe UI", 12, "bold"), fg="blue", bg="white")
    label_add.place(x=0, y=y + offset_y - 30)

    # === Canvas + Scrollbar Horizontal ===
    canvas = tk.Canvas(parent_frame, height=height_image + 60, bg="white", width=max_canvas_width)
    canvas.place(x=0, y=y + offset_y)

    scrollbar = tk.Scrollbar(parent_frame, orient="horizontal", command=canvas.xview)
    scrollbar.place(x=0, y=y + offset_y + height_image + 60 - 15, width=max_canvas_width, height=15)

    canvas.configure(xscrollcommand=scrollbar.set)

    inner_frame = tk.Frame(canvas, bg="white")
    canvas.create_window((0, 0), window=inner_frame, anchor="nw")

    def on_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    inner_frame.bind("<Configure>", on_configure)

    # === Isi Kategori ===
    daftar = db.reference("daftar_kategori").get()
    for i, (nama, data) in enumerate(daftar.items()):
        img_url = data.get("gambar")

        frame_item = tk.Frame(inner_frame, width=item_width, height=height_image + 30, bg="white")
        frame_item.pack(side="left", padx=spacing // 2, pady=5)

        # Gambar Placeholder
        placeholder = get_placeholder_image()
        img_btn = Button(frame_item, image=placeholder, command=lambda k=nama: tampilkan_popup_item(k), bd=0)
        img_btn.image = placeholder
        img_btn.pack()

        # Label Nama Kategori
        nama_label = tk.Label(frame_item, text=nama, wraplength=item_width, font=("Segoe UI", 9), bg="white")
        nama_label.pack(pady=2)

        kategori_buttons.append(img_btn)

        def update_btn_img(photo, b=img_btn):
            b.configure(image=photo)
            b.image = photo

        load_image_async(img_url, lambda img, b=img_btn: canvas.after(0, lambda: update_btn_img(img, b)))


# Dynamic UI elements
cam_w, cam_h = icon_cam.width(), icon_cam.height()
# img_id = canvas.create_image(280, 307, image=icon_cam)
img_id = canvas.create_image(280, 227, image=icon_cam)
count_id = canvas.create_text(310, 474, anchor="nw", text="Total Items: [0] Items", fill="#745540", font=("Arial", -20))



footer_y = 540  # Posisi awal

# Baris 1: Total sebelum tax
canvas.create_text(590, footer_y, anchor="nw", text="Subtotal", fill="#000000", font=("microsoft sans serif", -22))
subtotal_id = canvas.create_text(1010, footer_y, anchor="ne", text="IDR 0", fill="#000000", font=("microsoft sans serif", -24))

# Baris 2: Pajak
canvas.create_text(590, footer_y + 30, anchor="nw", text="Tax", fill="#000000", font=("microsoft sans serif", -22))
tax_amount_id = canvas.create_text(1010, footer_y + 30, anchor="ne", text="IDR 0", fill="#000000", font=("microsoft sans serif", -24))

# Baris 3: Diskon
canvas.create_text(590, footer_y + 60, anchor="nw", text="Discount", fill="#000000", font=("microsoft sans serif", -22))
discount_amount_id = canvas.create_text(1010, footer_y + 60, anchor="ne", text="IDR 0", fill="#000000", font=("microsoft sans serif", -24))

# Baris 4: Total akhir
canvas.create_text(590, footer_y + 90, anchor="nw", text="Total", fill="#000000", font=("microsoft sans serif", -22, "bold"))
price_id = canvas.create_text(1010, footer_y + 90, anchor="ne", text="IDR 0", fill="#000000", font=("microsoft sans serif", -24, "bold"))

payment_y_start = footer_y + 130  # setelah Total + Tax

# Warna default & aktif
payment_buttons = []

Label(
    home2,
    text="Payment Method",
    font=("Arial", 10, "bold"),
    bg="white",  # sesuaikan dengan warna background
    fg="#57708c"   # sesuaikan dengan desain
).place(x=600, y=payment_y_start + 5)

metode_var = tk.StringVar(value="")  # default kosong

payment_methods = [
    ("Cash", 720, payment_y_start),
    ("Card", 810, payment_y_start),
    ("QR", 900, payment_y_start),
]

for nama, x, y in payment_methods:
    btn = Button(
        home2,
        text=nama,
        font=("Arial", 10, "bold"),
        width=10,
        height=1,
        bd=1,
        relief="ridge",
        command=lambda n=nama: pilih_metode(n),
        bg=default_bg,
        activebackground=default_bg
    )
    btn.place(x=x, y=y)
    payment_buttons.append(btn)

continue_btn = Button(
    home2,
    text="Continue to payment",
    font=("Arial", 12, "bold"),
    width=20,
    height=1,
    bd=1,
    relief="ridge",
    bg="#6AA4D4",
    fg="white",
    activebackground="#5B92C5",
    command=simpan_transaksi_multi2  # ganti dengan fungsi kamu sendiri
)

# Letakkan di tengah area metode pembayaran
continue_btn.place(x=720, y=payment_y_start + 35)
manual_quantity_overrides = {}
item_ids = []

# === Detection with segmentation, TTA, NMS, clustering ===
def tta_detect(frame):
    preds = []
    orig_h, orig_w = frame.shape[:2]
    scales, flips = [1.0], [False]
    if AUGMENT > 0:
        scales += [1.0 + AUGMENT, max(0.1, 1.0 - AUGMENT)]
        flips += [True]
    
    for s in scales:
        for f in flips:
            # Resize frame for model input
            if s != 1.0:
                model_h, model_w = int(orig_h * s), int(orig_w * s)
                img = cv2.resize(frame, (model_w, model_h))
            else:
                img = frame.copy()
                model_h, model_w = orig_h, orig_w
            
            if f: 
                img = cv2.flip(img, 1)
            
            res = model(img, imgsz=IMG_SIZE, conf=CONFIDENCE, iou=IOU, augment=False)[0]
            if res.masks is None or len(res.boxes) == 0:
                continue
                
            masks = res.masks.data.cpu().numpy()
            boxes = res.boxes.xyxy.cpu().numpy()
            classes = res.boxes.cls.cpu().numpy().astype(int)
            confs = res.boxes.conf.cpu().numpy()
            
            # Get polygon coordinates directly from YOLO output
            if hasattr(res.masks, 'xy'):
                polygon_coords = res.masks.xy  # Already a list, no need for .cpu().numpy()
            else:
                polygon_coords = None
            
            for idx, (m, b, cl, cf) in enumerate(zip(masks, boxes, classes, confs)):
                # Scale bounding box back to original frame size with proper handling
                if s != 1.0:
                    # Scale coordinates back to original frame size
                    b = b / s
                if f:
                    # Flip x coordinates for horizontal flip
                    b[0], b[2] = model_w - b[2], model_w - b[0]
                
                x1, y1, x2, y2 = b.astype(int)
                
                # Skip detections that are too large (likely background)
                detection_area = (x2 - x1) * (y2 - y1)
                frame_area = orig_w * orig_h
                area_ratio = detection_area / frame_area
                
                # Calculate aspect ratio
                width = x2 - x1
                height = y2 - y1
                aspect_ratio = width / height if height > 0 else float('inf')
                
                # Enhanced filtering to prevent background detections
                if (area_ratio < MIN_DETECTION_AREA_RATIO or 
                    area_ratio > MAX_DETECTION_AREA_RATIO or 
                    aspect_ratio < MIN_ASPECT_RATIO or 
                    aspect_ratio > MAX_ASPECT_RATIO or 
                    cf < CONFIDENCE):
                    continue
                
                # Additional position-based filtering
                # Check if detection is in the center area (more likely to be valid object)
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                frame_center_x = orig_w / 2
                frame_center_y = orig_h / 2
                
                # Calculate distance from center
                distance_from_center = np.sqrt((center_x - frame_center_x)**2 + (center_y - frame_center_y)**2)
                max_distance = min(orig_w, orig_h) * 0.4  # 40% of smaller dimension
                
                # Skip if too far from center (likely background)
                if distance_from_center > max_distance:
                    continue
                
                # Use polygon coordinates directly from YOLO output if available
                if polygon_coords is not None and idx < len(polygon_coords):
                    # Get polygon points from YOLO output
                    polygon_points_orig = np.array(polygon_coords[idx]).astype(np.int32)
                    
                    # Calculate scaling factors for proper coordinate transformation
                    if s != 1.0:
                        scale_x = orig_w / (model_w * s)
                        scale_y = orig_h / (model_h * s)
                    else:
                        scale_x = orig_w / model_w
                        scale_y = orig_h / model_h
                    
                    # Apply flip transformation to polygon points if needed
                    if f:
                        # Flip x coordinates for horizontal flip
                        polygon_points_orig[:, 0] = model_w - polygon_points_orig[:, 0]
                    
                    # Scale polygon points to match frame display
                    scaled_polygon_points = (polygon_points_orig * np.array([scale_x, scale_y])).astype(np.int32)
                    
                    # Create binary mask for the scaled polygon
                    object_binary_mask = np.zeros((orig_h, orig_w), dtype=np.uint8)
                    cv2.fillPoly(object_binary_mask, [scaled_polygon_points], 255)
                    
                    # Use the polygon-based mask
                    mask = object_binary_mask
                else:
                    # Fallback to contour-based approach if polygon coordinates not available
                    # Process mask with proper scaling
                    mask = cv2.resize((m * 255).astype(np.uint8), (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
                    if f: 
                        mask = cv2.flip(mask, 1)
                    
                    # Get polygon points from mask for better visualization
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    if contours:
                        # Use the largest contour
                        largest_contour = max(contours, key=cv2.contourArea)
                        polygon_points = largest_contour.reshape(-1, 2).astype(np.int32)
                        
                        # Create binary mask from polygon
                        object_binary_mask = np.zeros((orig_h, orig_w), dtype=np.uint8)
                        cv2.fillPoly(object_binary_mask, [polygon_points], 255)
                        
                        # Use the improved mask
                        mask = object_binary_mask
                    else:
                        # If no contours found, use the original mask with thresholding
                        mask = (mask > 127).astype(np.uint8) * 255
                
                preds.append((mask, b.astype(int), cl, cf))
    
    if not preds:
        return frame.copy(), [], [], [], []
    
    rects, scores = [], []
    for mask, b, cl, cf in preds:
        x1, y1, x2, y2 = b
        # Ensure coordinates are within frame bounds
        x1 = max(0, min(x1, orig_w - 1))
        y1 = max(0, min(y1, orig_h - 1))
        x2 = max(x1 + 1, min(x2, orig_w))
        y2 = max(y1 + 1, min(y2, orig_h))
        rects.append([x1, y1, x2-x1, y2-y1])
        scores.append(float(cf))
    
    idxs = cv2.dnn.NMSBoxes(rects, scores, CONFIDENCE, IOU)
    if idxs is None or len(idxs) == 0:
        return frame.copy(), [], [], [], []
    
    final = [preds[i] for i in idxs.flatten().tolist()]
    out_masks, out_boxes, out_classes, out_confs = [], [], [], []
    taken = set()
    
    for i, (m1, b1, c1, cf1) in enumerate(final):
        if i in taken: continue
        group = [(i, m1, b1, c1, cf1)]
        taken.add(i)
        for j, (m2, b2, c2, cf2) in enumerate(final[i+1:], start=i+1):
            if j in taken: continue
            if compute_iou(b1, b2) > IOU:
                group.append((j, m2, b2, c2, cf2))
                taken.add(j)
        _, m_best, b_best, c_best, cf_best = group[0]
        
        # Ensure final bounding box coordinates are within frame bounds
        x1, y1, x2, y2 = b_best
        x1 = max(0, min(x1, orig_w - 1))
        y1 = max(0, min(y1, orig_h - 1))
        x2 = max(x1 + 1, min(x2, orig_w))
        y2 = max(y1 + 1, min(y2, orig_h))
        b_best = np.array([x1, y1, x2, y2])
        
        out_masks.append(m_best)
        out_boxes.append(b_best)
        out_classes.append(c_best)
        out_confs.append(cf_best)
    
    return frame.copy(), out_masks, np.array(out_boxes), np.array(out_classes), np.array(out_confs)

last_detected_items = {}
# === Main update loop ===
def get_tax_percentage():
    try:
        tax_ref = db.reference('setting/tax')
        tax_value = tax_ref.get()
        return float(tax_value) if tax_value else 10.0
    except Exception as e:
        print("Error reading tax from Firebase:", e)
        return 10.0  # default kalau error

def update_quantity(name, delta):
    if name not in keranjang_final:
        return  # Item tidak ada di keranjang_final, jadi tidak bisa diupdate
    print(f"Update quantity: {name}, delta: {delta}")  # DEBUG LOG
    # Ambil data lama
    current_qty = keranjang_final[name]["quantity"]
    harga = keranjang_final[name]["harga"]

    # Hitung quantity baru, minimal 0
    new_qty = max(0, current_qty + delta)

    if new_qty == 0:
        keranjang_final.pop(name)  # Hapus item dari keranjang jika qty = 0
    else:
        # Update quantity dan total
        keranjang_final[name]["quantity"] = new_qty
        keranjang_final[name]["total"] = new_qty * harga

taxtotal = 0
hargaawal = 0
current_page = 0
items_per_page = 3
def update_frame():
    global cap, item_ids, is_updating_frame, hargaakhir, diskontotal, taxtotal, hargaawal, manual_quantity_overrides, keranjang_final, current_page
    if not is_updating_frame:
        return
    if USE_CAMERA and cap:
        ret, frame = cap.read()
        if not ret:
            cap.release()
            cap = cv2.VideoCapture(1)
            home2.after(1000, update_frame)
            return
    elif USE_STATIC_IMAGE and static_img is not None:
        frame = cv2.resize(static_img, (cam_w, cam_h))
    else:
        frame = 255 * np.ones((cam_h, cam_h, 3), dtype=np.uint8)

    ann, masks, boxes, classes, confs = tta_detect(frame)
    disp = ann.copy()

    for mask, box, cls_idx, conf in zip(masks, boxes, classes, confs):
        # Safety check for class index
        if cls_idx >= len(CLASS_NAMES) or cls_idx < 0:
            continue
            
        name = CLASS_NAMES[cls_idx]
        label = f"{name} {conf:.2f}"
        hexcol = MASK_COLORS[name][1:]
        bgr = tuple(int(hexcol[i:i + 2], 16) for i in (4, 2, 0))
        overlay = disp.copy()
        overlay[mask == 255] = bgr
        disp = cv2.addWeighted(overlay, MASK_ALPHA, disp, 1 - MASK_ALPHA, 0)
        x1, y1, x2, y2 = box
        cv2.rectangle(disp, (x1, y1), (x2, y2), bgr, 3)
        font_scale = 1.2
        thickness = 2
        (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        cv2.rectangle(disp, (x1, y1 - text_h - 10), (x1 + text_w + 6, y1), bgr, -1)
        cv2.putText(disp, label, (x1 + 3, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness,
                    cv2.LINE_AA)

    cnt_map = dict(zip(*np.unique(classes, return_counts=True))) if len(classes) > 0 else {}
    canvas.itemconfigure(count_id, text=f"Total Items: [{sum(cnt_map.values())}] Items")

    def go_next_page():
        global current_page
        max_page = (len(keranjang_final) - 1) // items_per_page
        if current_page < max_page:
            current_page += 1

    def go_prev_page():
        global current_page
        if current_page > 0:
            current_page -= 1

    # last_detected_items.clear()
    detected_now = {}

    for cls_idx in cnt_map.keys():
        # Safety check for class index
        if cls_idx >= len(CLASS_NAMES) or cls_idx < 0:
            continue
            
        name = CLASS_NAMES[cls_idx]
        qty = cnt_map[cls_idx]

        harga = PRICES[name]
        total = qty * harga
        detected_now[name] = {
            "quantity": qty,
            "harga": harga,
            "total": total
        }

    # last_detected_items.update(detected_now)
    update_keranjang_dari_AI(detected_now)

    rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
    imgtk = ImageTk.PhotoImage(Image.fromarray(rgb).resize((cam_w, cam_h)))
    canvas.itemconfigure(img_id, image=imgtk)
    canvas.image = imgtk

    now = datetime.now().strftime("%d %b %Y %H:%M:%S")
    canvas.itemconfigure(order_id, text=f"Order #[{current_order_id:04d}] {now}")

    for iid in item_ids:
        canvas.delete(iid)
    item_ids.clear()

    total_price = 0
    total_discount = 0
    y0, dy = 219, 80

    for widget in home2.place_slaves():
        if hasattr(widget, "is_qty_button") and widget.is_qty_button:
            widget.destroy()

    print("isikeranjang")
    print(keranjang_final)

    keys = list(keranjang_final.keys())
    start = current_page * items_per_page
    end = start + items_per_page
    displayed_items = keys[start:end]

    for i, name in enumerate(displayed_items):
        data = keranjang_final[name]
        qty = data["quantity"]
        unit = data["harga"]
        price = data["total"]
        discount_percent = DISCOUNTS.get(name, 0)
        discount_amount = price * (discount_percent / 100)
        total_discount += discount_amount
        total_price += price
        y = y0 + i * dy

        # Tombol + dan -
        def make_btn(text, offset_x, command):
            btn = Button(
                home2,
                text=text,
                font=("Arial", 10, "bold"),
                width=2,
                command=command,
                bg="#EEE",
                fg="#333",
                bd=1,
                relief="ridge"
            )
            btn.place(x=780 + offset_x, y=y + 10, width=20, height=20)
            btn.is_qty_button = True
            return btn

        btn_minus = make_btn("-", 0, partial(update_quantity, name, -1))
        btn_plus = make_btn("+", 70, partial(update_quantity, name, 1))

        btn_minus.lift()
        btn_plus.lift()

        item_ids += [
            canvas.create_text(590, y, anchor="nw", text=name, fill="#000000", font=("microsoft sans serif", -18)),
            canvas.create_text(590, y + 22, anchor="nw", text=format_currency(unit), fill="#000000",
                               font=("microsoft sans serif", -18)),
            canvas.create_image(825, y + 22, image=Colom_count),
            canvas.create_text(817.5, y + 10, anchor="nw", text=str(qty), fill="#000000",
                               font=("microsoft sans serif", -20)),
            canvas.create_text(1010, y + 10, anchor="ne", text=format_currency(price), fill="#000000",
                               font=("microsoft sans serif", -18))
        ]

    if len(keranjang_final) > items_per_page:
        btn_prev = Button(
            home2, text="<<", font=("Arial", 10),
            command=go_prev_page,  # cukup ini aja
            bg="#DDD", fg="#000", bd=1, relief="ridge"
        )
        btn_prev.place(x=600, y=y + 80, width=40, height=25)
        btn_prev.is_qty_button = True

        btn_next = Button(
            home2, text=">>", font=("Arial", 10),
            command=go_next_page,
            bg="#DDD", fg="#000", bd=1, relief="ridge"
        )
        btn_next.place(x=650, y=y + 80, width=40, height=25)
        btn_next.is_qty_button = True


    keranjang = []
    for name, data in keranjang_final.items():
        harga = data['harga']
        jumlah = data['quantity']
        total = harga * jumlah
        diskon = DISCOUNTS.get(name, 0)
        potongan = total * (diskon / 100)
        keranjang.append({
            'nama': name,
            'jumlah': jumlah,
            'harga': harga,
            'total': total,
            'diskon': diskon,
            'potongan': potongan
        })

    # total_harga = sum(item['total'] for item in keranjang)
    # total_diskon = sum(item['potongan'] for item in keranjang)
    # tax_amount = total_harga * (get_tax_percentage() / 100)
    # final_price = total_harga + tax_amount - total_diskon

    total_harga = sum(item['total'] for item in keranjang)
    total_diskon = sum(item['potongan'] for item in keranjang)
    tax_amount = round(total_harga * (get_tax_percentage() / 100))
    final_price = round(total_harga + tax_amount - total_diskon)
    total_harga = round(total_harga)
    total_diskon = round(total_diskon)

    hargaakhir = final_price
    diskontotal = total_diskon
    taxtotal = tax_amount
    hargaawal = total_harga

    canvas.itemconfigure(subtotal_id, text=format_currency(total_harga))
    canvas.itemconfigure(tax_amount_id, text=format_currency(tax_amount))
    canvas.itemconfigure(discount_amount_id, text=format_currency(total_diskon))
    canvas.itemconfigure(price_id, text=format_currency(final_price))

    manual_quantity_overrides = {
        k: v for k, v in manual_quantity_overrides.items() if k in last_detected_items
    }

    if USE_CUDA:
        torch.cuda.empty_cache()
    home2.after(30, update_frame)

# ===  TRANSAKSI PAGE END (ScanAI + Manual) ===

# ----------------------------------------------------------------------------------------------------

# 🚀 START APP
show_frame("Login")
update_barang_cb()
root.mainloop()

# ----------------------------------------------------------------------------------------------------