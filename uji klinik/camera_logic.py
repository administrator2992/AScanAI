from typing import List, Dict, Any
import numpy as np

def cosine_similarity(vec1, vec2):
    """Menghitung kemiripan kosinus antara dua vektor."""
    # Pastikan vektor adalah NumPy array
    vec1 = np.asarray(vec1)
    vec2 = np.asarray(vec2)
    
    dot_product = np.dot(vec1, vec2)
    norm_vec1 = np.linalg.norm(vec1)
    norm_vec2 = np.linalg.norm(vec2)
    
    # Hindari pembagian dengan nol
    if norm_vec1 == 0 or norm_vec2 == 0:
        return 0.0
        
    return dot_product / (norm_vec1 * norm_vec2)

def combine_detections(detection_buffer: Dict[int, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Menggabungkan deteksi dari beberapa kamera berdasarkan logika yang ditentukan,
    memastikan ID objek konsisten.
    """
    SIMILARITY_THRESHOLD = 0.95  # Ambang batas yang sama dengan pelacakan

    # 1. Kumpulkan semua deteksi dari buffer dan tambahkan ID kamera asalnya
    all_detections_with_cam_id = []
    for cam_id, detections in detection_buffer.items():
        for det in detections:
            det['cam_id'] = cam_id
            all_detections_with_cam_id.append(det)

    if not all_detections_with_cam_id:
        return []

    # 2. Kelompokkan deteksi berdasarkan objek fisik menggunakan kemiripan fitur
    object_groups = []
    remaining_detections = list(all_detections_with_cam_id)
    while remaining_detections:
        base_det = remaining_detections.pop(0)
        current_group = [base_det]
        
        matches = []
        for other_det in remaining_detections:
            # Periksa apakah kelasnya sama untuk efisiensi
            if other_det['cls_idx'] == base_det['cls_idx']:
                similarity = cosine_similarity(base_det.get('feature_vector', []), other_det.get('feature_vector', []))
                if similarity > SIMILARITY_THRESHOLD:
                    matches.append(other_det)
        
        current_group.extend(matches)
        
        # Buang deteksi yang sudah dicocokkan dari daftar sisa.
        # Kita menggunakan id() untuk menghindari ValueError saat membandingkan kamus
        # yang berisi array NumPy.
        matched_ids = {id(m) for m in matches}
        remaining_detections = [d for d in remaining_detections if id(d) not in matched_ids]
        
        object_groups.append(current_group)

    # 3. Pilih deteksi terbaik dari setiap kelompok berdasarkan aturan
    final_detections = []
    for group in object_groups:
        d1 = next((d for d in group if d.get('cam_id') == 1), None)
        d2 = next((d for d in group if d.get('cam_id') == 2), None)
        d3 = next((d for d in group if d.get('cam_id') == 3), None)

        c1 = d1['conf'] if d1 else -1.0
        c2 = d2['conf'] if d2 else -1.0
        c3 = d3['conf'] if d3 else -1.0

        best_det = None
        # Aturan: Jika kamera 1 tidak lebih baik dari gabungan kamera 2 dan 3,
        # ambil dari perbandingan kamera 2 dan 3 mana yang lebih baik.
        # Jika tidak, sisanya ambil dari kamera 1.
        if c1 < max(c2, c3):
            if c2 >= c3:
                best_det = d2
            else:
                best_det = d3
        else:
            best_det = d1 # Termasuk kasus jika d1 ada dan d2/d3 tidak ada

        if best_det:
            final_detections.append(best_det)
    
    return final_detections 