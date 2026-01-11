import onnxruntime as ort
import numpy as np
import cv2

class FeatureExtractor:
    def __init__(self, model_path="assets/osnet_x0_25_msmt17.onnx"):
        """
        Inisialisasi model OSNet dari file ONNX lokal untuk ekstraksi fitur.
        """
        print(f"[FeatureExtractor] Loading ONNX model from: {model_path}")
        
        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        
        # Ambil ukuran batch yang diharapkan dari model, misal: 16
        self.batch_size = self.input_shape[0]
        self.input_height = self.input_shape[2]
        self.input_width = self.input_shape[3]

        print(f"[FeatureExtractor] ONNX model loaded. Expected batch size: {self.batch_size}, Input shape: {self.input_shape}")

    def _preprocess(self, crop_image_np):
        """
        Pra-pemrosesan satu gambar agar sesuai dengan input model ONNX, tanpa menambahkan dimensi batch.
        """
        resized_img = cv2.resize(crop_image_np, (self.input_width, self.input_height))
        rgb_img = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB)
        chw_img = rgb_img.transpose(2, 0, 1)
        
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        
        normalized_img = (chw_img / 255.0 - mean[:, np.newaxis, np.newaxis]) / std[:, np.newaxis, np.newaxis]
        
        return normalized_img.astype(np.float32)

    def extract_features_batch(self, crop_images_np: list):
        """
        Mengekstrak vektor fitur dari batch potongan gambar objek (crops).
        Akan menangani padding jika jumlah gambar kurang dari ukuran batch yang diharapkan model.
        """
        if not crop_images_np:
            return np.array([])

        num_actual_images = len(crop_images_np)

        # Jika jumlah crop melebihi ukuran batch model, proses dalam beberapa chunk (kasus jarang terjadi)
        if num_actual_images > self.batch_size:
            print(f"[FeatureExtractor-WARNING] Number of crops ({num_actual_images}) exceeds model batch size ({self.batch_size}). Will process in chunks.")
            all_vectors = []
            for i in range(0, num_actual_images, self.batch_size):
                chunk = crop_images_np[i:i+self.batch_size]
                all_vectors.extend(self.extract_features_batch(chunk))
            return np.array(all_vectors)

        # Pra-pemrosesan semua gambar dalam list
        preprocessed_batch = [self._preprocess(img) for img in crop_images_np]
        input_batch = np.stack(preprocessed_batch, axis=0)

        # Buat batch final dengan padding jika perlu
        if num_actual_images < self.batch_size:
            padding_shape = (self.batch_size - num_actual_images,) + input_batch.shape[1:]
            padding = np.zeros(padding_shape, dtype=np.float32)
            final_batch = np.concatenate([input_batch, padding], axis=0)
        else:
            final_batch = input_batch
        
        # Jalankan inferensi
        outputs = self.session.run(None, {self.input_name: final_batch})
        feature_vectors_batch = outputs[0]
        
        # Ambil hanya fitur dari gambar asli (bukan dari padding)
        actual_feature_vectors = feature_vectors_batch[:num_actual_images]
        
        # Normalisasi setiap vektor (L2 normalization)
        norms = np.linalg.norm(actual_feature_vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1e-6 # Hindari pembagian dengan nol
        normalized_vectors = actual_feature_vectors / norms
        
        return normalized_vectors 