import json
import numpy as np
from pathlib import Path

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

class LocationMatcher:
    """
    An expert system that understands the spatial relationship between cameras.
    It uses a calibration map to determine if detections from different cameras
    correspond to the same physical object based on its location.
    """
    def __init__(self, calibration_file='calibration_map.json', max_distance_threshold=100):
        """
        Initializes the LocationMatcher.

        Args:
            calibration_file (str): Path to the JSON file containing calibration points.
            max_distance_threshold (int): The maximum pixel distance to consider a detection
                                          a match for a calibrated point. This defines the
                                          "tightness" of the location matching.
        """
        self.calibration_map = self._load_calibration_map(calibration_file)
        self.max_distance_threshold = 250  # Increased from 150 to 250 to reduce over-filtering
        if not self.calibration_map:
            print("[LocationMatcher] WARNING: Calibration map is empty. Location matching will be disabled.")

    def _load_calibration_map(self, calibration_file):
        """Loads the calibration data from the specified JSON file."""
        cal_path = Path(calibration_file)
        if not cal_path.exists():
            print(f"[LocationMatcher] ERROR: Calibration file not found at {calibration_file}")
            return []
        try:
            with open(cal_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"[LocationMatcher] ERROR: Could not decode JSON from {calibration_file}")
            return []

    def find_best_location_for_detection(self, detection):
        """
        Finds the closest calibrated physical location for a single detection.
        If no exact match within threshold, uses triangulation with 3 nearest points.

        Args:
            detection (dict): A detection dictionary, which must include 'camera_id'
                              and 'bbox'.

        Returns:
            tuple: A tuple containing (location_id, distance). 
                   - location_id (int): The index of the best matching calibrated point.
                   - distance (float): The pixel distance to that point's center.
                   Returns (None, float('inf')) if no match is found.
        """
        if not self.calibration_map:
            return None, float('inf')

        cam_id_str = f"cam_{detection['camera_id']}"
        x1, y1, x2, y2 = detection['bbox']
        detection_center = np.array([(x1 + x2) / 2, (y1 + y2) / 2])

        # Hitung jarak ke semua titik kalibrasi
        distances = []
        for i, cal_point in enumerate(self.calibration_map):
            if cam_id_str in cal_point:
                cal_coords = np.array(cal_point[cam_id_str]['coords'])
                distance = np.linalg.norm(detection_center - cal_coords)
                distances.append((i, distance))
        
        if not distances:
            return None, float('inf')
        
        # Urutkan berdasarkan jarak terdekat
        distances.sort(key=lambda x: x[1])
        
        # Jika titik terdekat dalam threshold, gunakan langsung
        closest_id, closest_distance = distances[0]
        if closest_distance <= self.max_distance_threshold:
            return closest_id, closest_distance
        
        # Jika tidak ada yang dalam threshold, coba interpolasi dengan 3 titik terdekat
        if len(distances) >= 3:
            interpolated_id = self._interpolate_location(detection_center, distances[:3], cam_id_str)
            if interpolated_id is not None:
                # Hitung ulang jarak ke titik interpolasi
                interpolated_distance = self._calculate_interpolated_distance(detection_center, interpolated_id, cam_id_str)
                return interpolated_id, interpolated_distance
        
        # Fallback: gunakan titik terdekat meskipun di luar threshold
        return closest_id, closest_distance

    def group_detections_by_location(self, all_camera_detections):
        """
        Groups detections by their closest calibrated location ID.

        This revised logic ensures that if at least one camera detects an object
        at a calibrated location, a complete group is formed. For any other camera
        that is supposed to see that location but has no detection, a placeholder
        "unknown" detection is proactively created. This guarantees that the logic
        in CameraLogic always receives a full set of detections (or placeholders)
        for every active location.

        Args:
            all_camera_detections (dict): A dictionary where keys are camera_ids
                                          and values are lists of detections.

        Returns:
            dict: A dictionary where keys are location_ids and values are lists of detections,
                  including predicted ones for missing cameras.
        """
        if not self.calibration_map:
            return {}

        print(f"\n[LocationMatcher DEBUG] Input Detections: {json.dumps(all_camera_detections, indent=2, cls=NumpyEncoder)}")
        groups_by_location = {}

        # Step 1: Assign real detections to their closest calibrated location,
        # but only if they are within the distance threshold.
        for cam_id, detections in all_camera_detections.items():
            for det in detections:
                det['camera_id'] = cam_id  # Ensure camera_id is present
                location_id, distance = self.find_best_location_for_detection(det)

                # Only group detections that are reasonably close to a calibrated point.
                # This prevents spurious detections far from any known location from forming a group.
                if location_id is not None and distance <= self.max_distance_threshold:
                    if location_id not in groups_by_location:
                        groups_by_location[location_id] = []
                    groups_by_location[location_id].append(det)

        # Step 2: For each location that has at least one real detection, 
        # create predictions for missing cameras.
        for loc_id, detections in groups_by_location.items():
            if not detections or loc_id >= len(self.calibration_map):
                continue

            detected_cameras = {det['camera_id'] for det in detections}
            cal_point = self.calibration_map[loc_id]
            all_calibrated_cameras = set(int(cam_str.split('_')[1]) for cam_str in cal_point.keys() if cam_str.startswith('cam_'))
            
            missing_cameras = all_calibrated_cameras - detected_cameras
            
            if missing_cameras:
                # Use the highest confidence detection in the group as a template.
                template_detection = max(detections, key=lambda x: x.get('conf', 0))
                
                for missing_cam_id in missing_cameras:
                    predicted_detection = self._predict_detection_for_camera(
                        template_detection, missing_cam_id, loc_id
                    )
                    if predicted_detection:
                        predicted_detection['is_predicted'] = True
                        predicted_detection['predicted_from_camera'] = template_detection['camera_id']
                        detections.append(predicted_detection)
        
        print(f"[LocationMatcher DEBUG] Final Groups: {json.dumps(groups_by_location, indent=2, cls=NumpyEncoder)}")
        return groups_by_location
    
    def _interpolate_location(self, detection_center, nearest_points, cam_id_str):
        """
        Interpolasi lokasi menggunakan triangulasi dengan 3 titik terdekat.
        Menggunakan Euclidean distance untuk akurasi yang lebih baik.
        
        Args:
            detection_center (np.array): Koordinat pusat deteksi
            nearest_points (list): List of (location_id, distance) tuples
            cam_id_str (str): Camera ID string
        
        Returns:
            int: Location ID hasil interpolasi, atau None jika gagal
        """
        try:
            # Ambil 3 titik terdekat
            points = []
            weights = []
            
            for loc_id, distance in nearest_points:
                cal_point = self.calibration_map[loc_id]
                if cam_id_str in cal_point:
                    coords = np.array(cal_point[cam_id_str]['coords'])
                    points.append((loc_id, coords))
                    # Inverse distance weighting (semakin dekat, semakin besar bobotnya)
                    weight = 1.0 / (distance + 1e-6)  # Tambah epsilon untuk menghindari division by zero
                    weights.append(weight)
            
            if len(points) < 3:
                return None
            
            # Normalisasi bobot
            total_weight = sum(weights)
            weights = [w / total_weight for w in weights]
            
            # Hitung weighted centroid untuk menentukan lokasi virtual
            weighted_center = np.zeros(2)
            for i, (loc_id, coords) in enumerate(points):
                weighted_center += weights[i] * coords
            
            # Cari titik kalibrasi yang paling dekat dengan weighted centroid
            min_dist = float('inf')
            best_loc_id = None
            
            for loc_id, coords in points:
                dist = np.linalg.norm(weighted_center - coords)
                if dist < min_dist:
                    min_dist = dist
                    best_loc_id = loc_id
            
            return best_loc_id
            
        except Exception as e:
            print(f"[LocationMatcher] Error in interpolation: {e}")
            return None
    
    def _calculate_interpolated_distance(self, detection_center, location_id, cam_id_str):
        """
        Hitung jarak ke titik hasil interpolasi.
        
        Args:
            detection_center (np.array): Koordinat pusat deteksi
            location_id (int): ID lokasi hasil interpolasi
            cam_id_str (str): Camera ID string
        
        Returns:
            float: Jarak ke titik interpolasi
        """
        try:
            cal_point = self.calibration_map[location_id]
            if cam_id_str in cal_point:
                cal_coords = np.array(cal_point[cam_id_str]['coords'])
                return np.linalg.norm(detection_center - cal_coords)
            return float('inf')
        except:
            return float('inf')
    
    def _predict_detection_for_camera(self, template_detection, target_camera_id, location_id):
        """
        Memprediksi deteksi objek untuk kamera yang tidak mendeteksi berdasarkan
        template dari kamera lain dan peta kalibrasi.
        
        Args:
            template_detection (dict): Deteksi template dari kamera lain
            target_camera_id (int): ID kamera target untuk prediksi
            location_id (int): ID lokasi fisik objek
        
        Returns:
            dict: Deteksi yang diprediksi atau None jika gagal
        """
        try:
            if location_id >= len(self.calibration_map):
                return None
                
            cal_point = self.calibration_map[location_id]
            target_cam_str = f"cam_{target_camera_id}"
            
            if target_cam_str not in cal_point:
                return None
            
            # Ambil koordinat kalibrasi untuk kamera target
            target_coords = cal_point[target_cam_str]['coords']
            
            # Buat prediksi deteksi berdasarkan template
            predicted_detection = template_detection.copy()
            
            # Update informasi kamera
            predicted_detection['camera_id'] = target_camera_id
            
            # Prediksi bounding box langsung dari data kalibrasi
            predicted_bbox = cal_point[target_cam_str].get('bbox')
            
            # Jika bbox tidak ada di kalibrasi, fallback ke metode lama (meskipun tidak ideal)
            if not predicted_bbox:
                template_bbox = template_detection['bbox']
                bbox_width = template_bbox[2] - template_bbox[0]
                bbox_height = template_bbox[3] - template_bbox[1]
                center_x, center_y = cal_point[target_cam_str]['coords']
                predicted_bbox = [
                    int(center_x - bbox_width / 2),
                    int(center_y - bbox_height / 2),
                    int(center_x + bbox_width / 2),
                    int(center_y + bbox_height / 2)
                ]

            
            predicted_detection['bbox'] = predicted_bbox
            
            # Atur kelas ke "unknown" dan confidence rendah agar tidak menang voting
            predicted_detection['class_name'] = "unknown"
            predicted_detection['cls_idx'] = -1 # Tandai sebagai unknown
            predicted_detection['conf'] = 0.1  # Confidence rendah untuk "unknown"
            predicted_detection['feature_vector'] = None # Tidak ada fitur untuk prediksi

            return predicted_detection
            
        except Exception as e:
            print(f"[LocationMatcher] Error predicting detection for camera {target_camera_id}: {e}")
            return None

