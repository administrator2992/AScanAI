import numpy as np
import json
from pathlib import Path
import threading
import time

# --- Constants ---
BANK_FILE = 'feature_bank.json'
SIMILARITY_THRESHOLD = 0.85 # Cosine similarity threshold for a confident match

class FeatureBank:
    """Manages the storage and retrieval of validated feature vectors for each class."""

    def __init__(self, bank_file=BANK_FILE):
        """Initializes the FeatureBank, loading existing data from the file."""
        self.bank_file = Path(bank_file)
        self.bank = self._load_bank()
        self._lock = threading.Lock()  # Lock untuk mencegah concurrent writing
        self._pending_saves = 0  # Counter untuk pending saves
        self._last_save_time = time.time()
        self._save_interval = 30.0  # Save setiap 30 detik untuk mengurangi I/O
        self._batch_threshold = 10  # Minimum 10 features sebelum save
        print(f"[FeatureBank] Loaded {sum(len(v) for v in self.bank.values())} features for {len(self.bank)} classes.")

    def _load_bank(self):
        """Loads the feature bank from a JSON file."""
        if not self.bank_file.exists():
            return {}
        try:
            with open(self.bank_file, 'r') as f:
                # Convert lists back to numpy arrays
                json_data = json.load(f)
                bank = {k: [np.array(v_item) for v_item in v] for k, v in json_data.items()}
                return bank
        except (json.JSONDecodeError, IOError) as e:
            print(f"[FeatureBank] Error loading bank file: {e}. Starting with an empty bank.")
            return {}

    def save_bank(self, force=False):
        """Saves the current feature bank to a JSON file with thread safety."""
        if not force and self._pending_saves == 0:
            return  # Tidak ada perubahan untuk disimpan
            
        with self._lock:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Write to temporary file first
                    temp_file = self.bank_file.with_suffix('.tmp')
                    with open(temp_file, 'w') as f:
                        # Convert numpy arrays to lists for JSON serialization
                        json_data = {k: [v_item.tolist() for v_item in v] for k, v in self.bank.items()}
                        json.dump(json_data, f, indent=4)
                    
                    # Atomic rename to prevent corruption
                    temp_file.replace(self.bank_file)
                    if self._pending_saves > 0:
                        print(f"[FeatureBank] Batch saved {self._pending_saves} features to {self.bank_file}")
                    return
                except IOError as e:
                    print(f"[FeatureBank] Error saving bank file (attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(0.1)  # Wait before retry
                    else:
                        print(f"[FeatureBank] Failed to save after {max_retries} attempts")

    def force_save(self):
        """Forces immediate save of all pending changes."""
        if self._pending_saves > 0:
            self.save_bank(force=True)
            self._pending_saves = 0
            self._last_save_time = time.time()

    def add_feature(self, class_name, feature_vector):
        """Adds a new, validated feature vector to the bank."""
        if not isinstance(feature_vector, np.ndarray):
            feature_vector = np.array(feature_vector)
        
        if class_name not in self.bank:
            self.bank[class_name] = []
        
        self.bank[class_name].append(feature_vector)
        print(f"[FeatureBank] Added new feature for '{class_name}'. Total features for class: {len(self.bank[class_name])}")
        
        # Optimized saving: batch save berdasarkan threshold dan interval
        self._pending_saves += 1
        current_time = time.time()
        
        # Save jika mencapai batch threshold ATAU sudah lewat interval waktu
        should_save = (self._pending_saves >= self._batch_threshold or 
                      current_time - self._last_save_time >= self._save_interval)
        
        if should_save:
            self.save_bank()
            self._pending_saves = 0
            self._last_save_time = current_time

    def get_best_match(self, feature_vector):
        """
        Compares a new feature vector against all vectors in the bank.

        Returns:
            A tuple (best_class_name, best_similarity_score) if a match is found.
            (None, 0.0) if no confident match is found.
        """
        if not isinstance(feature_vector, np.ndarray):
            feature_vector = np.array(feature_vector)
        
        # Validasi feature_vector
        if feature_vector.size == 0 or feature_vector.ndim == 0:
            print(f"[FeatureBank] Invalid feature vector: empty or scalar")
            return None, 0.0
        
        # Flatten jika multi-dimensional
        if feature_vector.ndim > 1:
            feature_vector = feature_vector.flatten()

        best_match = None
        highest_similarity = -1.0

        try:
            # Normalize the input vector once for cosine similarity calculation
            norm_vector = feature_vector / np.linalg.norm(feature_vector)
        except Exception as e:
            print(f"[FeatureBank] Error normalizing input vector: {e}")
            return None, 0.0

        for class_name, vectors in self.bank.items():
            if not vectors:
                continue
            
            # Handle vectors with potentially different dimensions
            similarities = []
            for bank_vector in vectors:
                try:
                    # Validasi bank_vector
                    if not isinstance(bank_vector, np.ndarray):
                        bank_vector = np.array(bank_vector)
                    
                    if bank_vector.size == 0 or bank_vector.ndim == 0:
                        continue
                    
                    # Flatten jika multi-dimensional
                    if bank_vector.ndim > 1:
                        bank_vector = bank_vector.flatten()
                    
                    if len(bank_vector) == len(feature_vector):
                        # Normalize bank vector
                        norm_bank = bank_vector / np.linalg.norm(bank_vector)
                        # Calculate cosine similarity
                        similarity = np.dot(norm_bank, norm_vector)
                        similarities.append(similarity)
                except Exception as e:
                    print(f"[FeatureBank] Error processing bank vector for {class_name}: {e}")
                    continue
            
            if similarities:
                max_sim_for_class = max(similarities)
            else:
                max_sim_for_class = 0.0

            if max_sim_for_class > highest_similarity:
                highest_similarity = max_sim_for_class
                best_match = class_name

        if highest_similarity >= SIMILARITY_THRESHOLD:
            return best_match, highest_similarity
        else:
            return None, highest_similarity
