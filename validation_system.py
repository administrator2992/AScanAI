import json
import os
import datetime
import uuid
from typing import Dict, List, Optional, Any
from pathlib import Path
import cv2
import numpy as np

class ValidationSystem:
    """Manual validation system for food detection results"""
    
    def __init__(self, validation_data_dir: str = "validation_data"):
        self.validation_data_dir = Path(validation_data_dir)
        self.validation_data_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for organized data storage
        (self.validation_data_dir / "predictions").mkdir(exist_ok=True)
        (self.validation_data_dir / "validations").mkdir(exist_ok=True)
        (self.validation_data_dir / "sessions").mkdir(exist_ok=True)
        (self.validation_data_dir / "feedback").mkdir(exist_ok=True)
        
        self.class_names = ["Lemper", "Pastel", "Kue Lapis", "Kue Mangkok", "Wajik"]
        

    def _to_serializable(self, obj):
        """Recursively convert numpy arrays/scalars in obj to native Python types."""
        if isinstance(obj, dict):
            return {k: self._to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._to_serializable(v) for v in obj]
        elif hasattr(obj, 'item'):
            return obj.item()
        elif hasattr(obj, 'tolist'):
            return obj.tolist()
        else:
            return obj

    def save_prediction_batch(self, image_paths: Dict[int, str], predictions: Dict[int, List[Dict]], 
                            model_version: str = "yolo11n-seg(v1)", batch_id: Optional[str] = None) -> str:
        """Save a batch of predictions with metadata for multiple cameras"""
        if batch_id is None:
            batch_id = str(uuid.uuid4())
        
        timestamp = datetime.datetime.now().isoformat()

        # Recursively convert all numpy types to native Python types
        serializable_predictions = self._to_serializable(predictions)

        # Total item dihitung dari semua kamera
        total_items = sum(len(preds) for preds in predictions.values())

        prediction_data = {
            "batch_id": batch_id,
            "timestamp": timestamp,
            "image_paths": image_paths, # Path untuk setiap kamera
            "model_version": model_version,
            "camera_predictions": serializable_predictions, # Prediksi dikelompokkan per kamera
            "validation_status": "pending",
            "total_items": total_items
        }

        # Save prediction batch
        prediction_file = self.validation_data_dir / "predictions" / f"{batch_id}.json"
        with open(prediction_file, 'w') as f:
            json.dump(prediction_data, f, indent=2)

        return batch_id
    
    def create_validation_session(self, validator_id: str) -> str:
        """Create a new validation session"""
        session_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().isoformat()
        
        session_data = {
            "session_id": session_id,
            "validator_id": validator_id,
            "start_time": timestamp,
            "status": "active",
            "validated_batches": [],
            "validation_count": 0
        }
        
        session_file = self.validation_data_dir / "sessions" / f"{session_id}.json"
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
            
        return session_id
    
    def get_pending_validations(self, limit: int = 10) -> List[Dict]:
        """Get pending validation batches prioritized by confidence, skipping corrupted files"""
        pending_batches = []
        predictions_dir = self.validation_data_dir / "predictions"

        for prediction_file in predictions_dir.glob("*.json"):
            try:
                with open(prediction_file, 'r') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Warning: Skipping corrupted or invalid JSON file: {prediction_file} ({e})")
                continue

            if data.get("validation_status") == "pending":
                # Calculate average confidence for prioritization
                avg_confidence = sum(p.get("confidence", 0) for p in data.get("predictions", [])) / max(len(data.get("predictions", [])), 1)
                data["avg_confidence"] = avg_confidence
                pending_batches.append(data)

        # Sort by confidence (lowest first for manual review)
        pending_batches.sort(key=lambda x: x["avg_confidence"])
        return pending_batches[:limit]
    
    def validate_item(self, batch_id: str, item_index: int, validation_data: Dict, 
                     session_id: str, validator_id: str) -> bool:
        """Validate a single detected item"""
        validation_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().isoformat()
        
        validation_record = {
            "validation_id": validation_id,
            "batch_id": batch_id,
            "item_index": item_index,
            "session_id": session_id,
            "validator_id": validator_id,
            "timestamp": timestamp,
            "validation_type": validation_data["type"],  # "confirm", "correct", "false_positive", "add_missing"
            "original_prediction": validation_data.get("original_prediction"),
            "validated_class": validation_data.get("validated_class"),
            "confidence_rating": validation_data.get("confidence_rating", 5),
            "notes": validation_data.get("notes", ""),
            "bounding_box": validation_data.get("bounding_box"),
            "segmentation_mask": validation_data.get("segmentation_mask")
        }
        
        # Save validation record
        validation_file = self.validation_data_dir / "validations" / f"{validation_id}.json"
        with open(validation_file, 'w') as f:
            json.dump(validation_record, f, indent=2)
        
        # Update session
        self._update_session(session_id, batch_id)
        
        return True
    
    def _update_session(self, session_id: str, batch_id: str):
        """Update validation session with completed batch"""
        session_file = self.validation_data_dir / "sessions" / f"{session_id}.json"
        
        with open(session_file, 'r') as f:
            session_data = json.load(f)
        
        if batch_id not in session_data["validated_batches"]:
            session_data["validated_batches"].append(batch_id)
            session_data["validation_count"] += 1
            session_data["last_activity"] = datetime.datetime.now().isoformat()
        
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
    
    def mark_batch_validated(self, batch_id: str):
        """Mark a prediction batch as validated"""
        prediction_file = self.validation_data_dir / "predictions" / f"{batch_id}.json"
        
        with open(prediction_file, 'r') as f:
            data = json.load(f)
        
        data["validation_status"] = "validated"
        data["validation_completed_at"] = datetime.datetime.now().isoformat()
        
        with open(prediction_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_validation_statistics(self) -> Dict:
        """Get validation system statistics, skipping corrupted files"""
        stats = {
            "total_predictions": 0,
            "pending_validations": 0,
            "completed_validations": 0,
            "validation_accuracy": 0.0,
            "class_accuracy": {cls: 0.0 for cls in self.class_names},
            "active_sessions": 0
        }

        # Count predictions
        predictions_dir = self.validation_data_dir / "predictions"
        for prediction_file in predictions_dir.glob("*.json"):
            try:
                with open(prediction_file, 'r') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Warning: Skipping corrupted or invalid JSON file in stats: {prediction_file} ({e})")
                continue

            stats["total_predictions"] += 1
            if data.get("validation_status") == "pending":
                stats["pending_validations"] += 1
            elif data.get("validation_status") == "validated":
                stats["completed_validations"] += 1

        # Count active sessions
        sessions_dir = self.validation_data_dir / "sessions"
        for session_file in sessions_dir.glob("*.json"):
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Warning: Skipping corrupted or invalid session JSON file in stats: {session_file} ({e})")
                continue

            if data.get("status") == "active":
                stats["active_sessions"] += 1

        return stats
    
    def generate_feedback_data(self) -> Dict:
        """Generate feedback data for model improvement"""
        feedback_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "corrections": [],
            "confirmations": [],
            "false_positives": [],
            "missed_detections": []
        }
        
        validations_dir = self.validation_data_dir / "validations"
        for validation_file in validations_dir.glob("*.json"):
            with open(validation_file, 'r') as f:
                validation = json.load(f)
            
            validation_type = validation["validation_type"]
            if validation_type == "correct":
                feedback_data["corrections"].append(validation)
            elif validation_type == "confirm":
                feedback_data["confirmations"].append(validation)
            elif validation_type == "false_positive":
                feedback_data["false_positives"].append(validation)
            elif validation_type == "add_missing":
                feedback_data["missed_detections"].append(validation)
        
        # Save feedback data
        feedback_file = self.validation_data_dir / "feedback" / f"feedback_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(feedback_file, 'w') as f:
            json.dump(feedback_data, f, indent=2)
        
        return feedback_data

class ValidationInterface:
    """Interface for integrating validation with existing GUI"""
    
    def __init__(self, validation_system: ValidationSystem):
        self.validation_system = validation_system
        self.current_session = None
        self.current_batch = None
        self.validation_mode = False
    
    def start_validation_session(self, validator_id: str = "default_validator"):
        """Start a new validation session"""
        self.current_session = self.validation_system.create_validation_session(validator_id)
        self.validation_mode = True
        return self.current_session
    
    def process_multicamera_detection_results(self, camera_data: Dict[int, Dict[str, Any]]) -> Optional[str]:
        """
        Process detection results from multiple cameras, save their images with a unique name, 
        and store the already-correctly-scaled polygon/box data.
        """
        print(f"[DEBUG] Processing validation data for {len(camera_data)} cameras")
        batch_id = str(uuid.uuid4())
        
        image_dir = self.validation_system.validation_data_dir / "predictions"
        image_dir.mkdir(exist_ok=True)

        # Dictionary untuk menyimpan path gambar dan prediksi per kamera
        image_paths = {}
        all_predictions = {}

        for cam_id, data in camera_data.items():
            print(f"[DEBUG] Processing camera {cam_id}")
            image_data = data["image"]
            masks = data["masks"]
            boxes = data["boxes"]
            classes = data["classes"]
            confidences = data["confidences"]

            image_path = image_dir / f"{batch_id}_cam_{cam_id}.jpg"
            try:
                cv2.imwrite(str(image_path), image_data)
                # Gunakan path yang konsisten tanpa "uji klinik"
                image_paths[cam_id] = f"validation_data/predictions/{batch_id}_cam_{cam_id}.jpg"
                print(f"[DEBUG] Saved image for camera {cam_id}: {image_path}")
            except Exception as e:
                print(f"[ERROR] Could not save validation image for camera {cam_id}: {e}")
                image_paths[cam_id] = None

            predictions = []
            for i, (polygon, box, cls_idx, conf) in enumerate(zip(masks, boxes, classes, confidences)):
                box_scaled = [int(coord) for coord in box]
                polygon_scaled = polygon.astype(np.int32).tolist() if polygon is not None and isinstance(polygon, np.ndarray) else None
                
                prediction = {
                    "item_id": i,
                    "class_index": int(cls_idx),
                    "class_name": self.validation_system.class_names[int(cls_idx)],
                    "confidence": float(conf),
                    "bounding_box": box_scaled,
                    "segmentation_polygon": polygon_scaled,
                    "needs_validation": conf < 0.7
                }
                predictions.append(prediction)
            
            all_predictions[cam_id] = predictions
            print(f"[DEBUG] Camera {cam_id}: {len(predictions)} predictions")

        # Jangan simpan batch jika tidak ada gambar atau prediksi sama sekali
        if not any(image_paths.values()) or not any(all_predictions.values()):
            print(f"[DEBUG] No valid data to save for batch {batch_id}")
            return None

        print(f"[DEBUG] Saving batch {batch_id} with {sum(len(preds) for preds in all_predictions.values())} total predictions")
        self.validation_system.save_prediction_batch(
            image_paths, all_predictions, batch_id=batch_id
        )
        self.current_batch = batch_id
        return batch_id
    
    def get_validation_queue(self) -> List[Dict]:
        """Get items queued for validation"""
        return self.validation_system.get_pending_validations()
    
    def submit_validation(self, item_index: int, validation_type: str, 
                         validated_class: str = None, confidence_rating: int = 5, 
                         notes: str = "") -> bool:
        """Submit validation for a specific item"""
        if not self.current_session or not self.current_batch:
            return False
        
        # Ensure all values are JSON serializable
        validation_data = {
            "type": validation_type,
            "validated_class": validated_class,
            "confidence_rating": int(confidence_rating) if hasattr(confidence_rating, 'item') else confidence_rating,
            "notes": str(notes)
        }
        
        # Convert item_index to native Python int if it's a numpy type
        safe_item_index = int(item_index) if hasattr(item_index, 'item') else item_index
        
        return self.validation_system.validate_item(
            self.current_batch, safe_item_index, validation_data, 
            self.current_session, "default_validator"
        )
    
    def complete_batch_validation(self):
        """Mark current batch as completed"""
        if self.current_batch:
            self.validation_system.mark_batch_validated(self.current_batch)
            self.current_batch = None
    
    def get_validation_stats(self) -> Dict:
        """Get current validation statistics"""
        return self.validation_system.get_validation_statistics()