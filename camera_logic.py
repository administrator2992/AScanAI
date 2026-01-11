import numpy as np
import json
from collections import defaultdict
from feature_bank import FeatureBank
from scipy.spatial.distance import cdist
from location_matcher import LocationMatcher # Import the new expert

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

# This list must be kept in sync with the one in gui.py and inference_worker.py
CLASS_NAMES = ['Lemper', 'Pastel', 'Kue Lapis', 'Kue Mangkok', 'Wajik']

# --- Constants ---
SAVE_CONFIDENCE_THRESHOLD = 0.6   # Flag for saving if final confidence is below this (lebih ketat untuk mengurangi noise)
CONFLICT_VOTE_THRESHOLD = 0.7     # If winning class gets < this % of total votes, it's a conflict (lebih ketat)
MIN_CAMERAS_FOR_CONSENSUS = 1     # Minimum kamera yang diperlukan untuk consensus (mendukung kamera offline)
MIN_DETECTION_CONFIDENCE = 0.5  # Naikkan threshold untuk mengurangi false positive    # Minimum confidence untuk menerima deteksi YOLO (reduced from 0.4)

class CameraLogic:
    """Manages detections from multiple cameras to create a unified, consensus-based result."""

    def __init__(self, feature_bank):
        """Initializes the CameraLogic system with a shared feature bank."""
        self.feature_bank = feature_bank
        self.all_camera_detections = defaultdict(list)
        # Instantiate the location expert
        self.location_matcher = LocationMatcher(calibration_file='calibration_map.json')
        # Toggle untuk automatic correction
        self.automatic_correction_enabled = True
        # Expert system bounding boxes untuk koordinat yang terukur sama
        self.expert_bounding_boxes = {}
        self.expert_predictions_by_location = {}
        print("[CameraLogic] Initialized with Location Matcher and Expert System Integration.")
    
    def set_automatic_correction(self, enabled):
        """Set status automatic correction untuk mengontrol beban komputasi."""
        self.automatic_correction_enabled = enabled
        print(f"[CameraLogic] Automatic correction {'enabled' if enabled else 'disabled'}")

    def update_detections(self, camera_id, detections):
        """
        Receives a new list of detections from a specific camera worker.
        Filters out low-confidence detections to reduce YOLO false positives.

        Args:
            camera_id (int): The ID of the camera providing the detections.
            detections (list): A list of detection dictionaries from the worker.
        """
        # Filter deteksi berdasarkan confidence minimum untuk mengurangi false positive
        filtered_detections = [
            det for det in detections 
            if det.get('conf', 0) >= MIN_DETECTION_CONFIDENCE
        ]
        
        # Log jika ada deteksi yang difilter
        if len(filtered_detections) < len(detections):
            filtered_count = len(detections) - len(filtered_detections)
            print(f"[CameraLogic] Filtered {filtered_count} low-confidence detections from camera {camera_id}")
        
        self.all_camera_detections[camera_id] = filtered_detections

    def _group_detections(self):
        """Groups detections using the LocationMatcher expert instead of IoU."""
        # Delegate the entire grouping logic to our new expert system.
        # This is more robust as it's based on calibrated physical locations.
        return self.location_matcher.group_detections_by_location(self.all_camera_detections)

    def _resolve_group_conflict(self, group):
        """
        Resolves classification conflict based on a new voting logic:
        1.  **Majority Rule**: The class detected by the most cameras wins.
        2.  **Highest Confidence Tie-Breaker**: If there's a tie in camera count,
            the class with the highest single detection confidence wins.
        3.  **Unknown Priority**: If an "unknown" detection is present, it is only chosen
            if no other valid class is detected.

        The final bounding box and other details are taken from the single, 
        highest-confidence detection of the winning class.
        """
        if not group:
            return None, False

        # Separate real detections from "unknown" placeholders.
        real_detections = [d for d in group if d['class_name'] != 'unknown']
        unknown_detections = [d for d in group if d['class_name'] == 'unknown']

        # If there are no real detections, return the first "unknown" as the result.
        if not real_detections:
            if unknown_detections:
                # Return a unified "unknown" detection.
                unknown_det = unknown_detections[0].copy()
                unknown_det['source_cameras'] = [d.get('camera_id') for d in unknown_detections]
                unknown_det['original_group_size'] = len(unknown_detections)
                return unknown_det, False
            return None, False # Should not happen if grouping logic is correct.

        # 1. Tally votes for each class based on camera count.
        votes = defaultdict(int)
        # Store the highest confidence detection for each class.
        best_detection_per_class = {}

        for det in real_detections:
            class_name = det['class_name']
            votes[class_name] += 1
            # Keep track of the detection with the highest confidence for each class.
            if class_name not in best_detection_per_class or det['conf'] > best_detection_per_class[class_name]['conf']:
                best_detection_per_class[class_name] = det

        # 2. Determine the winning class based on the new rules.
        winning_class = None
        # Find the maximum number of votes any class received.
        max_votes = 0
        if votes:
            max_votes = max(votes.values())

        # Identify all classes that have the maximum number of votes.
        top_classes = [cls for cls, num_votes in votes.items() if num_votes == max_votes]

        if len(top_classes) == 1:
            # A single class has the most votes.
            winning_class = top_classes[0]
        elif len(top_classes) > 1:
            # Tie in vote count, use highest confidence as a tie-breaker.
            highest_conf = -1
            for cls in top_classes:
                if best_detection_per_class[cls]['conf'] > highest_conf:
                    highest_conf = best_detection_per_class[cls]['conf']
                    winning_class = cls

        # 3. Create the final unified detection.
        if winning_class:
            # The winning detection is the one with the highest confidence from the winning class.
            final_detection = best_detection_per_class[winning_class].copy()
            
            # Log the decision process.
            print(f"[Voting] Winner: '{winning_class}' (Votes: {votes[winning_class]}, Conf: {final_detection['conf']:.3f})")

            # Populate metadata for the final detection.
            final_detection['source_cameras'] = [d.get('camera_id') for d in group]
            final_detection['original_group_size'] = len(group)
            final_detection['is_conflict'] = len(top_classes) > 1 # Mark if there was a tie

            return final_detection, (original_class != winning_class if 'original_class' in locals() else False)

        # Fallback: this should ideally not be reached if there are real detections.
        # If for some reason no winner is chosen, return the highest confidence detection from the group.
        if real_detections:
            return max(real_detections, key=lambda x: x['conf']), False
        
        return None, False
        
        # 8. Calculate average feature vector untuk expert system learning
        # Hanya lakukan jika ada feature vectors yang valid
        avg_feature_vector = None
        valid_features = [det['feature_vector'] for det in group if det.get('feature_vector') is not None]
        if valid_features:
            try:
                # Weighted average berdasarkan confidence
                weights = [det['conf'] for det in group if det.get('feature_vector') is not None]
                if len(weights) == len(valid_features):
                    weighted_sum = np.zeros_like(valid_features[0])
                    total_weight = 0
                    for feature, weight in zip(valid_features, weights):
                        weighted_sum += feature * weight
                        total_weight += weight
                    if total_weight > 0:
                        avg_feature_vector = weighted_sum / total_weight
                        # Normalize hasil averaging
                        norm = np.linalg.norm(avg_feature_vector)
                        if norm > 0:
                            avg_feature_vector = avg_feature_vector / norm
            except Exception as e:
                print(f"[Expert] Feature averaging error: {e}")
                avg_feature_vector = None

        unified_detection['bbox'] = avg_box
        unified_detection['feature_vector'] = avg_feature_vector
        unified_detection['original_group_size'] = len(group)
        unified_detection['source_cameras'] = list(set(det.get('camera_id', 'unknown') for det in group))

        # 9. Check for conflict: if the winning class didn't have a clear majority, flag it.
        total_votes = sum(votes.values()) + sum(bank_votes.values())
        winner_score = (bank_votes.get(best_class, 0) * 3) + (votes.get(best_class, 0) * 2)
        had_conflict = (winner_score / max(total_votes, 1)) < CONFLICT_VOTE_THRESHOLD if total_votes > 0 else False

        return unified_detection, had_conflict

    def process_and_get_consensus(self):
        """
        Core logic to group detections, resolve conflicts, and return a unified result.
        Mengintegrasikan expert system untuk mengotakkan objek dengan koordinat terukur sama.
        """
        if not self.all_camera_detections:
            return [], False

        # Log total detections sebelum grouping
        total_detections = sum(len(dets) for dets in self.all_camera_detections.values())
        print(f"[SYNC] Total detections before grouping: {total_detections}")

        # Step 0: Integrasikan prediksi expert system dengan deteksi kamera
        if self.automatic_correction_enabled:
            self.all_camera_detections = self.integrate_expert_predictions(self.all_camera_detections)
            print(f"[Expert] Integrated expert predictions with camera detections")

        # Step 1: Group detections by physical location. This now returns a dict.
        # { location_id_1: [detection_group_1], location_id_2: [detection_group_2] }
        detection_groups_by_location = self._group_detections()
        print(f"[SYNC] Created {len(detection_groups_by_location)} location groups")

        # Step 2: Resolve conflicts in each group and tag with its location ID.
        unified_detections = []
        should_save_snapshot = False
        
        # Simpan data original sebelum grouping untuk auto-save logic
        original_detections_by_camera = {}
        for cam_id, cam_detections in self.all_camera_detections.items():
            original_detections_by_camera[cam_id] = [det.copy() for det in cam_detections]
        
        for location_id, group in detection_groups_by_location.items():
            print(f"\n[CameraLogic DEBUG] Processing group for location_id={location_id}: {json.dumps(group, indent=2, cls=NumpyEncoder)}")
            if group:
                resolved_detection, had_conflict = self._resolve_group_conflict(group)
                
                # *** CRITICAL: Add the physical location ID to the final object ***
                resolved_detection['location_id'] = location_id
                
                unified_detections.append(resolved_detection)
                
                # Expert System: Buat bounding boxes untuk koordinat yang terukur sama
                if self.automatic_correction_enabled and location_id < len(self.location_matcher.calibration_map):
                    self.create_expert_bounding_boxes(location_id, group)
                
                # Flag for saving if confidence is low OR there was a notable conflict
                if resolved_detection['conf'] < SAVE_CONFIDENCE_THRESHOLD or had_conflict:
                    should_save_snapshot = True

        # Auto-save high-confidence consensus results to feature bank for learning
        # Hanya lakukan jika automatic correction aktif
        if self.automatic_correction_enabled:
            for detection in unified_detections:
                # Simpan ke bank jika confidence tinggi dan tidak ada konflik untuk deteksi ini
                detection_had_conflict = detection['conf'] < SAVE_CONFIDENCE_THRESHOLD
                if detection['conf'] > 0.8 and not detection_had_conflict:
                    # Cek apakah ada perbedaan klasifikasi dari prediksi original
                    location_id = detection['location_id']
                    original_classes = set()
                    
                    # Kumpulkan kelas original dari semua kamera untuk lokasi ini
                    for cam_id, orig_detections in original_detections_by_camera.items():
                        for orig_det in orig_detections:
                            # Cari deteksi yang sesuai dengan location_id ini
                            # (setelah grouping, location_id ditambahkan ke deteksi)
                            if detection.get('source_cameras') and cam_id in detection.get('source_cameras', []):
                                original_classes.add(orig_det['class_name'])
                    
                    # Simpan jika sistem melakukan koreksi dan ada feature vector yang valid
                    if (len(original_classes) > 1 or (len(original_classes) == 1 and 
                        detection['class_name'] not in original_classes)) and detection.get('feature_vector') is not None:
                        self.add_validated_feature(
                            detection['class_name'], 
                            detection['feature_vector']
                        )
                        print(f"[Expert] Auto-saved consensus feature for '{detection['class_name']}' (conf: {detection['conf']:.3f})")
                    elif detection.get('feature_vector') is None:
                        print(f"[Expert] Skipped auto-save for '{detection['class_name']}' - no feature vector available")
        else:
            print("[Expert] Automatic correction disabled - skipping auto-save to feature bank")

        # Log hasil akhir
        print(f"[SYNC] Final unified detections: {len(unified_detections)}")
        for i, det in enumerate(unified_detections):
            print(f"[SYNC] Detection {i+1}: {det['class_name']} (conf: {det['conf']:.3f}, cameras: {det.get('source_cameras', [])}, predicted: {det.get('is_predicted', False)})")

        # Clear detections for the next processing cycle
        self.all_camera_detections.clear()
        
        # Clear expert bounding boxes untuk cycle berikutnya (opsional, bisa dipertahankan untuk persistence)
        # self.clear_expert_bounding_boxes()

        return unified_detections, should_save_snapshot

    def add_validated_feature(self, class_name, feature_vector):
        """Interface to add a new validated feature to the bank."""
        self.feature_bank.add_feature(class_name, feature_vector)
    
    def create_expert_bounding_boxes(self, location_id, detection_group):
        """Membuat bounding box expert system untuk koordinat yang terukur sama."""
        try:
            if not detection_group:
                return
            
            # Ambil template detection dengan confidence tertinggi
            template_detection = max(detection_group, key=lambda x: x['conf'])
            
            # Buat expert bounding box untuk setiap kamera berdasarkan calibration map
            expert_boxes = {}
            calibration_point = self.location_matcher.calibration_map[location_id] if location_id < len(self.location_matcher.calibration_map) else None
            
            if calibration_point:
                for cam_key, cam_data in calibration_point.items():
                    cam_id = int(cam_key.split('_')[1])  # Extract camera ID dari 'cam_X'
                    coords = cam_data['coords']
                    
                    # Buat bounding box berdasarkan koordinat kalibrasi
                    template_bbox = template_detection['bbox']
                    bbox_width = template_bbox[2] - template_bbox[0]
                    bbox_height = template_bbox[3] - template_bbox[1]
                    
                    # Posisikan bbox dengan center di koordinat kalibrasi
                    center_x, center_y = coords
                    expert_bbox = [
                        int(center_x - bbox_width / 2),
                        int(center_y - bbox_height / 2),
                        int(center_x + bbox_width / 2),
                        int(center_y + bbox_height / 2)
                    ]
                    
                    expert_boxes[cam_id] = {
                        'bbox': expert_bbox,
                        'class_name': template_detection['class_name'],
                        'conf': template_detection['conf'] * 0.9,  # Sedikit kurangi confidence untuk expert prediction
                        'location_id': location_id,
                        'is_expert_prediction': True,
                        'source_detection': template_detection['camera_id']
                    }
                
                self.expert_bounding_boxes[location_id] = expert_boxes
                print(f"[Expert] Created bounding boxes for location {location_id} across {len(expert_boxes)} cameras")
                
        except Exception as e:
            print(f"[Expert] Error creating bounding boxes for location {location_id}: {e}")
    
    def get_expert_predictions_for_camera(self, camera_id):
        """Mendapatkan prediksi expert system untuk kamera tertentu."""
        predictions = []
        
        for location_id, expert_boxes in self.expert_bounding_boxes.items():
            if camera_id in expert_boxes:
                expert_box = expert_boxes[camera_id].copy()
                expert_box['camera_id'] = camera_id
                predictions.append(expert_box)
        
        return predictions
    
    def integrate_expert_predictions(self, camera_detections):
        """Mengintegrasikan prediksi expert system dengan deteksi kamera."""
        integrated_detections = camera_detections.copy()
        
        for cam_id, detections in camera_detections.items():
            # Dapatkan prediksi expert untuk kamera ini
            expert_predictions = self.get_expert_predictions_for_camera(cam_id)
            
            for expert_pred in expert_predictions:
                # Cek apakah sudah ada deteksi real di lokasi yang sama
                has_real_detection = False
                expert_bbox = expert_pred['bbox']
                
                for real_det in detections:
                    real_bbox = real_det['bbox']
                    # Hitung IoU untuk melihat overlap
                    iou = self._calculate_iou(expert_bbox, real_bbox)
                    if iou > 0.3:  # Threshold untuk overlap
                        has_real_detection = True
                        break
                
                # Jika tidak ada deteksi real, tambahkan prediksi expert
                if not has_real_detection:
                    integrated_detections[cam_id].append(expert_pred)
                    print(f"[Expert] Added prediction for camera {cam_id} at location {expert_pred['location_id']}")
        
        return integrated_detections
    
    def _calculate_iou(self, box1, box2):
        """Menghitung Intersection over Union (IoU) antara dua bounding box."""
        try:
            x1_1, y1_1, x2_1, y2_1 = box1
            x1_2, y1_2, x2_2, y2_2 = box2
            
            # Hitung area intersection
            x1_inter = max(x1_1, x1_2)
            y1_inter = max(y1_1, y1_2)
            x2_inter = min(x2_1, x2_2)
            y2_inter = min(y2_1, y2_2)
            
            if x2_inter <= x1_inter or y2_inter <= y1_inter:
                return 0.0
            
            intersection = (x2_inter - x1_inter) * (y2_inter - y1_inter)
            
            # Hitung area union
            area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
            area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
            union = area1 + area2 - intersection
            
            return intersection / union if union > 0 else 0.0
            
        except Exception:
             return 0.0
    
    def get_expert_bounding_boxes_for_display(self):
        """Mendapatkan semua expert bounding boxes untuk ditampilkan di GUI."""
        display_boxes = {}
        
        for location_id, expert_boxes in self.expert_bounding_boxes.items():
            for cam_id, box_data in expert_boxes.items():
                if cam_id not in display_boxes:
                    display_boxes[cam_id] = []
                
                display_box = {
                    'bbox': box_data['bbox'],
                    'class_name': box_data['class_name'],
                    'conf': box_data['conf'],
                    'location_id': location_id,
                    'is_expert_prediction': True,
                    'color': 'blue'  # Warna khusus untuk expert predictions
                }
                display_boxes[cam_id].append(display_box)
        
        return display_boxes
    
    def clear_expert_bounding_boxes(self):
        """Membersihkan expert bounding boxes untuk cycle berikutnya."""
        self.expert_bounding_boxes.clear()
        self.expert_predictions_by_location.clear()
        print("[Expert] Cleared expert bounding boxes for next cycle")
    
    def get_expert_system_stats(self):
        """Mendapatkan statistik expert system."""
        total_expert_boxes = sum(len(boxes) for boxes in self.expert_bounding_boxes.values())
        active_locations = len(self.expert_bounding_boxes)
        
        return {
            'total_expert_boxes': total_expert_boxes,
            'active_locations': active_locations,
            'automatic_correction_enabled': self.automatic_correction_enabled
        }
