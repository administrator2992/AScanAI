import cv2
import numpy as np

# ---------- STEP 1: Load gambar ----------
img1 = cv2.imread("cam1.jpg")
img2 = cv2.imread("cam2.jpg")

points_img1 = []
points_img2 = []
collecting_for = 1  # mulai dari gambar pertama

def click_event(event, x, y, flags, param):
    global collecting_for
    if event == cv2.EVENT_LBUTTONDOWN:
        if collecting_for == 1:
            points_img1.append([x, y])
            print(f"Point on img1: {x}, {y}")
        else:
            points_img2.append([x, y])
            print(f"Point on img2: {x}, {y}")

# ---------- STEP 2: Pilih titik pada img1 ----------
print("Klik minimal 4 titik di Gambar 1 (misalnya sudut meja/kursi). Tekan 'q' kalau sudah.")
cv2.imshow("Image 1", img1)
cv2.setMouseCallback("Image 1", click_event)

while True:
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
cv2.destroyAllWindows()

# ---------- STEP 3: Pilih titik pada img2 ----------
collecting_for = 2
print("Sekarang klik titik yang sama di Gambar 2 dengan urutan sama. Tekan 'q' kalau sudah.")
cv2.imshow("Image 2", img2)
cv2.setMouseCallback("Image 2", click_event)

while True:
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
cv2.destroyAllWindows()

# ---------- STEP 4: Hitung homography ----------
pts1 = np.array(points_img1, dtype=np.float32)
pts2 = np.array(points_img2, dtype=np.float32)

H, _ = cv2.findHomography(pts2, pts1, cv2.RANSAC)

# ---------- STEP 5: Warp & Stitch ----------
height, width, _ = img1.shape
result = cv2.warpPerspective(img2, H, (width + img2.shape[1], height))
result[0:img1.shape[0], 0:img1.shape[1]] = img1

cv2.imshow("Panorama", result)
cv2.waitKey(0)
cv2.destroyAllWindows()

# ---------- STEP 6: Simpan hasil ----------
cv2.imwrite("panorama_result.jpg", result)
