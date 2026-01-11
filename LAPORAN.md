### **LAPORAN: PENINGKATAN SISTEM DETEKSI KUE DENGAN FITUR VALIDASI DAN *SELF-LEARNING***

**Tanggal:** 24 Mei 2024 (Diperbarui: 25 Mei 2024)
**Untuk:** Pemangku Kepentingan Proyek Kue
**Dari:** AI Assistant

---

#### **1. Ringkasan Eksekutif**

Laporan ini mengusulkan penambahan fitur ***Self-Learning*** (Pembelajaran Mandiri) pada sistem deteksi kue yang ada. Saat ini, sistem telah dilengkapi dengan modul validasi manual yang komprehensif (`validation_system.py` dan `validation_gui.py`) yang memungkinkan validator untuk mengoreksi hasil deteksi. Usulan ini bertujuan untuk menutup siklus umpan balik (*feedback loop*) dengan cara mengotomatiskan proses pelatihan ulang (*retraining*) model deteksi menggunakan data yang telah divalidasi. Implementasi fitur ini akan membuat sistem menjadi lebih cerdas, akurat, dan adaptif seiring waktu dengan intervensi manual yang minimal.

---

#### **2. Analisis Sistem Saat Ini**

Sistem deteksi kue yang ada telah memiliki infrastruktur validasi manual yang canggih, sebagaimana dijelaskan dalam `VALIDATION_SYSTEM_README.md`.

*   **Komponen Inti:** `validation_system.py` sebagai pengelola data dan `validation_gui.py` sebagai antarmuka validator.
*   **Alur Kerja Validasi:** Sistem mampu menangkap hasil deteksi dari model (misalnya, `yolo11n.pt`), menandai prediksi dengan tingkat kepercayaan rendah, dan menyajikannya kepada validator.
*   **Tipe Validasi:** Validator dapat melakukan empat aksi krusial:
    1.  **Konfirmasi Kebenaran** (*Confirm Correct*)
    2.  **Koreksi Kelas** (*Correct Class*)
    3.  **Menandai Kesalahan Deteksi** (*False Positive*)
    4.  **Menambah Data Terlewat** (*Add Missing Item*)
*   **Output:** Hasil validasi disimpan secara terstruktur dalam direktori `validation_data/`, yang siap untuk dianalisis lebih lanjut.

Saat ini, pemanfaatan data hasil validasi untuk melatih ulang model masih memerlukan proses manual.

---

#### **3. Status Implementasi Terbaru (25 Mei 2024)**

**✅ FITUR YANG TELAH BERHASIL DIIMPLEMENTASI:**

1. **Sistem Multi-Kamera Terintegrasi:**
   - Implementasi logika kombinasi deteksi dari 3 kamera (`camera_logic.py`)
   - Kamera 1 sebagai deteksi utama, kamera 2&3 sebagai deteksi pendamping
   - Sistem otomatis memilih deteksi terbaik berdasarkan confidence score

2. **Validasi Multi-Kamera:**
   - UI validasi menampilkan 3 gambar sekaligus (mirip jendela utama)
   - Validator dapat melihat hasil dari semua kamera dalam satu tampilan
   - Data dari ketiga kamera disimpan dalam satu batch validasi

3. **Alur Data Terintegrasi:**
   - `inference_worker.py` mengirim data lengkap dalam satu paket
   - `gui.py` menangani buffer data dari semua kamera
   - Sistem validasi dapat dipicu saat mode validasi aktif

**❌ BUG YANG DITEMUKAN:**

1. **Masalah Re-Identification (Re-ID):**
   - Ketika 3 kamera mendeteksi objek yang sama, sistem belum memiliki model re-ID yang robust
   - Objek yang sama mungkin mendapat ID berbeda di kamera yang berbeda
   - **Solusi:** Perlu implementasi model re-ID untuk tracking objek antar kamera

2. **Self-Learning Belum Berfungsi Penuh:**
   - Sistem penyimpanan data validasi sudah ada, tetapi belum ada mekanisme retraining otomatis
   - Kompleksitas tinggi karena tidak hanya menyimpan data, tetapi perlu retraining dengan data yang telah divalidasi
   - **Kendala:** NanoPC mungkin tidak sanggup melakukan training dengan data yang banyak

3. **Input Video Dummy:**
   - Saat ini menggunakan video dummy untuk testing
   - View yang dihasilkan tidak persis seperti kasus nyata
   - Perlu testing dengan kondisi real-world

---

#### **4. Usulan Fitur: Otomatisasi Alur Umpan Balik (*Self-Learning*)**

Kami mengusulkan pengembangan sebuah modul baru yang berfungsi sebagai **"Mesin Pelatih Otomatis"** yang menghubungkan hasil validasi langsung ke proses pelatihan model.

**Arsitektur yang Diusulkan:**

```
Deteksi Kue -> [Hasil Prediksi] -> Sistem Validasi Manual -> [Umpan Balik] -> Data Valid Terkumpul
                                                                                    |
                                                                                    V
                                                                        [Memicu Pelatihan Ulang]
                                                                                    |
                                                                                    V
                                                                    +---------------------------+
                                                                    |   Modul Self-Learning     |
                                                                    |---------------------------|
                                                                    | 1. Transformasi Data      |
                                                                    | 2. Pelatihan Ulang Model  |
                                                                    | 3. Evaluasi & Validasi    |
                                                                    +---------------------------+
                                                                                    |
                                                                                    V
                                                                    Model Baru (lebih akurat) -> [Kembali ke Proses Deteksi]
```

**Mekanisme Kerja:**

1.  **Pengumpulan Data:** Modul secara periodik memeriksa direktori `validation_data/`. Jika jumlah data valid baru (koreksi, konfirmasi, dan item tambahan) telah mencapai ambang batas tertentu, proses *self-learning* akan terpicu.
2.  **Transformasi Data:** Data dari format JSON validasi akan diubah menjadi format anotasi yang sesuai untuk pelatihan model deteksi.
3.  **Pelatihan Ulang Otomatis:** Skrip pelatihan akan dijalankan secara otomatis menggunakan data baru untuk menghasilkan versi model yang lebih baik.
4.  **Evaluasi dan Penerapan:** Model baru akan dievaluasi pada set data uji. Jika performanya terbukti lebih unggul dari model yang sedang aktif, model tersebut akan ditetapkan sebagai model produksi yang baru.

---

#### **5. Manfaat dan Keunggulan**

*   **Peningkatan Berkelanjutan:** Model akan menjadi lebih akurat secara otomatis seiring dengan semakin banyaknya data yang divalidasi oleh pengguna.
*   **Adaptasi Cepat:** Sistem dapat dengan cepat mempelajari jenis-jenis kue baru atau memperbaiki kesalahan deteksi yang sistematis.
*   **Efisiensi Operasional:** Mengurangi secara drastis waktu dan tenaga yang dibutuhkan oleh tim developer untuk melakukan siklus *man-in-the-loop* (pelabelan, pelatihan, dan penerapan model).
*   **Skalabilitas:** Sistem dapat terus berkembang dan menangani lebih banyak variasi data tanpa peningkatan beban kerja manual yang linear.

---

#### **6. Langkah-langkah Implementasi**

1.  **Pengembangan Skrip Transformasi Data:** Membuat skrip Python untuk mengonversi data dari `validation_data/` menjadi format dataset yang dibutuhkan untuk pelatihan.
2.  **Otomatisasi Pipeline Pelatihan:** Membuat skrip Python yang dapat dieksekusi secara otomatis untuk melatih ulang model.
3.  **Pembuatan Modul *Model Manager*:** Mengembangkan komponen yang bertanggung jawab untuk memicu pelatihan, mengevaluasi model baru, dan mengganti model produksi jika diperlukan.
4.  **Integrasi:** Mengintegrasikan modul *self-learning* ke dalam alur kerja sistem yang ada.

---

#### **7. Rencana Debugging dan Pengembangan (Besok)**

**Prioritas 1: Debugging Sistem Multi-Kamera**
- Perbaiki masalah re-ID untuk tracking objek antar kamera
- Optimasi logika kombinasi deteksi
- Testing dengan kondisi real-world

**Prioritas 2: Implementasi Self-Learning**
- Analisis kapasitas NanoPC untuk training
- Implementasi incremental learning (pelatihan bertahap)
- Optimasi penggunaan memori dan CPU

**Prioritas 3: Optimasi Performa**
- Profiling sistem untuk mengidentifikasi bottleneck
- Optimasi alur data antar proses
- Implementasi caching untuk data yang sering diakses

---

#### **8. Kesimpulan**

Penambahan fitur *self-learning* adalah langkah evolusi yang logis dan strategis untuk proyek deteksi kue ini. Dengan memanfaatkan fondasi sistem validasi yang sudah solid, kita dapat menciptakan sebuah sistem deteksi yang tidak hanya canggih, tetapi juga mampu belajar dan beradaptasi secara mandiri. Hal ini akan memastikan keunggulan kompetitif dan relevansi teknologi dalam jangka panjang.

**Status Saat Ini:** Sistem multi-kamera sudah berfungsi dengan baik, namun masih memerlukan perbaikan pada re-ID dan self-learning untuk mencapai performa optimal.

---

### **Tugas Tambahan & Perbaikan (Untuk Besok)**

**1. Perbaikan *Bug* Kritis pada Integrasi Validasi:**

*   **Masalah:** Saat mode validasi diaktifkan pada input video, aplikasi mengalami crash dengan error `TypeError: ValidationInterface.process_detection_results() got multiple values for argument 'image_path'`.
*   **Akar Masalah:** Terdapat ketidakcocokan pada pemanggilan fungsi `process_detection_results` di file `uji klinik/gui.py`. Objek `results` dari model YOLOv8 diteruskan secara langsung, padahal fungsi tersebut mengharapkan data deteksi (seperti *masks*, *boxes*, *classes*, dan *confidences*) dibongkar dan diteruskan sebagai argumen terpisah.
*   **Tindakan:** Modifikasi pemanggilan fungsi di `uji klinik/gui.py` untuk membongkar objek `results` dan memetakan datanya ke parameter yang benar dari fungsi `process_detection_results` di `validation_system.py`.

**2. Implementasi Model Re-ID:**
*   **Masalah:** Objek yang sama terdeteksi di kamera berbeda mendapat ID berbeda
*   **Solusi:** Implementasi model re-identification untuk tracking objek antar kamera
*   **Prioritas:** Tinggi - diperlukan untuk sistem multi-kamera yang robust

**3. Optimasi Self-Learning:**
*   **Masalah:** NanoPC tidak sanggup training dengan data besar
*   **Solusi:** Implementasi incremental learning dan optimasi resource usage
*   **Prioritas:** Sedang - dapat diimplementasikan secara bertahap 