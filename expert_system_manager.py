import threading
import queue
import time
from feature_bank import FeatureBank
from feature_extractor import FeatureExtractor
import numpy as np

class ExpertSystemManager:
    """
    Mengelola expert system di background thread terpisah untuk tidak mengganggu realtime performance.
    Expert system akan memproses feature extraction dan feature bank operations secara asinkron.
    """
    
    def __init__(self, feature_bank):
        """Initialize expert system manager dengan feature bank."""
        self.feature_bank = feature_bank
        self.feature_extractor = FeatureExtractor()
        
        # Queue untuk komunikasi dengan expert system
        self.expert_queue = queue.Queue(maxsize=100)
        self.result_cache = {}  # Cache hasil expert system
        
        # Threading control
        self.stop_event = threading.Event()
        self.expert_thread = None
        
        # Performance monitoring
        self.processed_count = 0
        self.last_stats_time = time.time()
        
        print("[ExpertSystem] Manager initialized")
    
    def start(self):
        """Start expert system background thread."""
        if self.expert_thread is None or not self.expert_thread.is_alive():
            self.stop_event.clear()
            self.expert_thread = threading.Thread(target=self._expert_worker, daemon=True)
            self.expert_thread.start()
            print("[ExpertSystem] Background thread started")
    
    def stop(self):
        """Stop expert system background thread."""
        self.stop_event.set()
        if self.expert_thread and self.expert_thread.is_alive():
            self.expert_thread.join(timeout=2.0)
            print("[ExpertSystem] Background thread stopped")
    
    def submit_for_analysis(self, detection_data):
        """
        Submit detection data untuk analisis expert system.
        Non-blocking operation - hasil akan tersedia di cache.
        
        Args:
            detection_data: Dict dengan keys: 'crop_image', 'bbox', 'class_name', 'conf', 'camera_id'
        """
        try:
            # Non-blocking submit
            self.expert_queue.put_nowait(detection_data)
        except queue.Full:
            # Drop jika queue penuh untuk menjaga performa realtime
            pass
    
    def get_expert_opinion(self, feature_vector):
        """
        Mendapatkan expert opinion untuk feature vector.
        Menggunakan cache untuk performa yang lebih baik.
        
        Returns:
            Tuple (best_class, similarity_score) atau (None, 0.0)
        """
        if feature_vector is None:
            return None, 0.0
            
        try:
            # Convert ke string untuk cache key
            cache_key = hash(feature_vector.tobytes()) if isinstance(feature_vector, np.ndarray) else None
            
            # Cek cache terlebih dahulu
            if cache_key and cache_key in self.result_cache:
                return self.result_cache[cache_key]
            
            # Konsultasi feature bank
            best_match, similarity = self.feature_bank.get_best_match(feature_vector)
            
            # Simpan ke cache
            if cache_key:
                self.result_cache[cache_key] = (best_match, similarity)
                
                # Bersihkan cache jika terlalu besar
                if len(self.result_cache) > 1000:
                    # Hapus 20% cache terlama
                    keys_to_remove = list(self.result_cache.keys())[:200]
                    for key in keys_to_remove:
                        del self.result_cache[key]
            
            return best_match, similarity
            
        except Exception as e:
            print(f"[ExpertSystem] Error getting expert opinion: {e}")
            return None, 0.0
    
    def _expert_worker(self):
        """Background worker thread untuk expert system processing."""
        print("[ExpertSystem] Worker thread started")
        
        while not self.stop_event.is_set():
            try:
                # Ambil data dari queue dengan timeout
                detection_data = self.expert_queue.get(timeout=1.0)
                
                # Process detection data
                self._process_detection(detection_data)
                self.processed_count += 1
                
                # Print stats setiap 100 deteksi
                if self.processed_count % 100 == 0:
                    current_time = time.time()
                    elapsed = current_time - self.last_stats_time
                    if elapsed > 0:
                        rate = 100 / elapsed
                        print(f"[ExpertSystem] Processed {self.processed_count} detections, rate: {rate:.1f}/sec")
                    self.last_stats_time = current_time
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[ExpertSystem] Worker error: {e}")
                continue
        
        print("[ExpertSystem] Worker thread stopped")
    
    def _process_detection(self, detection_data):
        """
        Process single detection untuk expert system learning.
        
        Args:
            detection_data: Dict dengan detection information
        """
        try:
            crop_image = detection_data.get('crop_image')
            class_name = detection_data.get('class_name')
            confidence = detection_data.get('conf', 0.0)
            
            if crop_image is None or class_name is None:
                return
            
            # Extract feature dari crop image
            feature_vector = self.feature_extractor.extract_features_batch([crop_image])
            
            if feature_vector is not None:
                try:
                    # Validasi yang lebih robust untuk feature vector
                    if isinstance(feature_vector, np.ndarray):
                        # Pastikan bukan scalar dan memiliki ukuran yang valid
                        if (feature_vector.ndim > 0 and 
                            feature_vector.size > 0 and 
                            feature_vector.shape[0] > 0):
                            feature = feature_vector[0]
                            
                            # Auto-save high confidence detections untuk learning (lebih selektif)
                            if confidence > 0.9:  # Naikkan threshold untuk mengurangi I/O
                                self.feature_bank.add_feature(class_name, feature)
                                print(f"[ExpertSystem] Auto-learned feature for '{class_name}' (conf: {confidence:.3f})")
                            
                            # Update cache dengan hasil baru
                            cache_key = hash(feature.tobytes())
                            best_match, similarity = self.feature_bank.get_best_match(feature)
                            self.result_cache[cache_key] = (best_match, similarity)
                        else:
                            print(f"[ExpertSystem] Invalid feature vector: scalar, empty, or invalid shape for '{class_name}'")
                    else:
                        print(f"[ExpertSystem] Invalid feature vector format for '{class_name}': {type(feature_vector)}")
                except Exception as e:
                    print(f"[ExpertSystem] Feature processing error for '{class_name}': {e}")
                
        except Exception as e:
            print(f"[ExpertSystem] Feature extraction error: {e}")
    
    def get_stats(self):
        """Get expert system statistics."""
        return {
            'processed_count': self.processed_count,
            'queue_size': self.expert_queue.qsize(),
            'cache_size': len(self.result_cache),
            'is_running': self.expert_thread and self.expert_thread.is_alive()
        }