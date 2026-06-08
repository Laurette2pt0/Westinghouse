#Calibration + correctionh d'une image 

import cv2
import numpy as np
import glob
 
# region callibration/distortion
# Taille du damier (coins INTERNES)
pattern_size = (8, 5)
 
# Préparation des points 3D (grille réelle)
objp = np.zeros((pattern_size[0]*pattern_size[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
 
objpoints = []  # points réels
imgpoints = []  # points image
 
images = glob.glob("*.jpg")
 
# 🔍 Détection des coins (version robuste)
for fname in images:
    img = cv2.imread(fname)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
 
    # Méthode robuste
    ret, corners = cv2.findChessboardCornersSB(gray, pattern_size)
 
    if ret:
        # objpoints.append(objp)
        # imgpoints.append(corners)
        
        objpoints.append(objp.reshape(-1,1,3))
        imgpoints.append(corners.reshape(-1,1,2))

        # Affichage (pour vérifier)
        cv2.drawChessboardCorners(img, pattern_size, corners, ret)
        cv2.imshow(f"Corners_{fname}", img)
        cv2.waitKey(200)
 
        print(fname, "-> OK ✅")
    else:
        print(fname, "-> ECHEC ❌")
 
# ✅ Vérification
if len(objpoints) < 5:
    print("Pas assez d'images valides ❌")
    exit()
 
# 📏 Récupération taille image
img = cv2.imread(images[0])
h, w = img.shape[:2]
print (f"damier : h={h} et w={w}")

# 🔧 Initialisation matrices
K = np.zeros((3, 3))
D = np.zeros((4, 1))  # modèle fisheye = 4 coeff
 
# flags fisheye
flags = cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC + \
        cv2.fisheye.CALIB_CHECK_COND + \
        cv2.fisheye.CALIB_FIX_SKEW
 
# 🎯 Calibration FISHEYE
rms, K, D, rvecs, tvecs = cv2.fisheye.calibrate(
    objpoints,
    imgpoints,
    (w, h),
    K,
    D,
    None,
    None,
    flags,
    (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6)
)
 
print("\n📷 Matrice intrinsèque K :")
print(K)

print("\n🔵 Coefficients de distorsion D :")
print(D)
print("\n✅ Calibration réussie")
print("RMS erreur :", rms)

# region image traitée
# Charger une image NORMALE (sans damier)
img = cv2.imread("image/plaque metal 105mm.jpg")#"image/plaque impression 3d 105mm.jpg"
hi, wi = img.shape[:2]
print (f"image : h={h} et w={w}")

# region Recalibrer la taille de l'image
scale_x = wi / w
scale_y = hi / h

#adapter K
K_scaled = K.copy()

K_scaled[0, 0] *= scale_x  # fx
K_scaled[1, 1] *= scale_y  # fy
K_scaled[0, 2] *= scale_x  # cx
K_scaled[1, 2] *= scale_y  # c

map1, map2 = cv2.fisheye.initUndistortRectifyMap(
    K_scaled, D, np.eye(3), K, (w, h), cv2.CV_32FC1
)

undistorted = cv2.remap(img, map1, map2, cv2.INTER_LINEAR)

# region Affichage
# cv2.imshow("Original", img)
# cv2.imshow("Corrigee", undistorted)


cv2.namedWindow("Original", cv2.WINDOW_NORMAL)
cv2.namedWindow("Corrigee", cv2.WINDOW_NORMAL)

cv2.imshow("Original", img)
cv2.imshow("Corrigee", undistorted)

cv2.resizeWindow("Original", 1200, 800)
cv2.resizeWindow("Corrigee", 1200, 800)

cv2.waitKey(0)
cv2.destroyAllWindows()
