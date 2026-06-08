#calibration et analyse par segment sur une image qui prend toute la place
#gérer segment que horizontale pour la calibration puis n'importe comment pour le reste des mesures 
#faire des cercles et des segments

import dearpygui.dearpygui as dpg
import cv2
import numpy as np
import math
import os
import glob

# ─────────────────────────────────────────
# region VARIABLES GLOBALES
# ─────────────────────────────────────────
chemin_image_actuelle = None
texture_tag = None
cercles = []
segments = []
mode_dessin_cercle = False
mode_dessin_segment = False
point1_temp = None #coordonnée de dépard du segment 

# CALIBRATION
DIAMETRE_ETALON_MM = 60.0
ratio_px_mm = None
segment_etalon_idx = None
calibration = False
idx_segments = None

# Initialisation matrices
K = np.zeros((3, 3))
D = np.zeros((4, 1))  # modèle fisheye = 4 coeff

# DIMENSIONS IMAGE
W = 1630
H = 970

#Dimension damier
h, w = 0, 0

# ─────────────────────────────────────────
# region AFFICHAGE
# ─────────────────────────────────────────
def format_diametre(r):
    if ratio_px_mm:
        return f"{(r * 2) / ratio_px_mm:.2f} mm"
    else:
        return f"{int(r * 2)} px"

def update_display():
    if not dpg.does_item_exist("drawlist_principal"):
        return
    dpg.delete_item("drawlist_principal", children_only=True)

    if texture_tag and dpg.does_item_exist(texture_tag):
        dpg.draw_image(texture_tag, (0, 0), (W, H), parent="drawlist_principal")
    else:
        dpg.draw_rectangle((0, 0), (W, H), fill=(40, 40, 40), parent="drawlist_principal")
        dpg.draw_text((W//2 - 180, H//2),
                      "Chargez une image pour commencer",
                      color=(130, 130, 130), size=18, parent="drawlist_principal")

    #Cercles dessinés
    for i, (cx, cy, r) in enumerate(cercles):
        dpg.draw_circle((cx, cy), r, color=(0, 255, 0, 255), thickness=2, parent="drawlist_principal")
        # Ligne diamètre en rouge
        dpg.draw_line((cx - r, cy), (cx + r, cy), color=(255, 0, 0, 255),
                      thickness=2, parent="drawlist_principal")
        # Points extrêmes
        dpg.draw_circle((cx - r, cy), 4, color=(255, 0, 0, 255), fill=(255, 0, 0, 200), parent="drawlist_principal")
        dpg.draw_circle((cx + r, cy), 4, color=(255, 0, 0, 255), fill=(255, 0, 0, 200), parent="drawlist_principal")
        # Centre
        dpg.draw_circle((cx, cy), 4, color=(255, 255, 255, 255), fill=(255, 255, 255, 200), parent="drawlist_principal")

        label = format_diametre(r)
        dpg.draw_text((cx - 55, cy - r - 14), label, color=(0, 255, 0, 255), size=13, parent="drawlist_principal")

    #Segments dessinés
    for i, (x1, y1, x2, y2) in enumerate(segments):
        is_etalon = (i == segment_etalon_idx)
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        couleur = (255, 165, 0, 255) if is_etalon else (0, 255, 0, 255)
        dpg.draw_line((x1,y1), (x2, y2), color=(255, 0, 0, 255), thickness=2, parent="drawlist_principal")
        dpg.draw_circle((cx, cy), 4, color=(255, 255, 255, 255), fill=(255, 255, 255, 200), parent="drawlist_principal")
        r = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) / 2
        label = format_diametre(r)
        if is_etalon:
            label += "  ETALON"
        dpg.draw_text((cx - 55, cy - 14), label, color=couleur, size=13,
                      parent="drawlist_principal")

    #Point de départ du tracé en cours
    if point1_temp:
        x1, y1 = point1_temp
        dpg.draw_circle((x1, y1), 6, color=(0, 200, 255, 255),
                        fill=(0, 200, 255, 180), parent="drawlist_principal")
        # dpg.draw_text((x1 + 8, y1 - 8), "Point 1", color=(0, 200, 255, 255),
        #               size=12, parent="drawlist_principal")

    #Détails calibration
    if ratio_px_mm:
        dpg.draw_rectangle((0, H - 18), (W, H), fill=(20, 50, 20, 220),
                           parent="drawlist_principal")
        dpg.draw_text((6, H - 15),
                      f"Calibre — Kp = {ratio_px_mm:.4f} px/mm  |  Etalon {DIAMETRE_ETALON_MM:.0f} mm",
                      color=(100, 255, 100), size=12, parent="drawlist_principal")
    else:
        dpg.draw_rectangle((0, H - 18), (W, H), fill=(55, 35, 10, 220),
                           parent="drawlist_principal")
        dpg.draw_text((6, H - 15),
                      "Non calibre — dessinez le trou central 60 mm puis cliquez 'Calibration'",
                      color=(255, 165, 0), size=12, parent="drawlist_principal")

    update_resultats()

def update_resultats():
    if not dpg.does_item_exist("table_resultats"):
        return
    dpg.delete_item("table_resultats", children_only=True)
    dpg.add_table_column(label="#",        parent="table_resultats", width_fixed=True, init_width_or_weight=20)
    dpg.add_table_column(label="Diam.",    parent="table_resultats", width_fixed=True, init_width_or_weight=90)
    dpg.add_table_column(label="Type",     parent="table_resultats", width_fixed=True, init_width_or_weight=60)

    #cercles
    for i, (cx, cy, r) in enumerate(cercles):
        with dpg.table_row(parent="table_resultats"):
            dpg.add_text(str(i + 1))
            dpg.add_text(format_diametre(r))
            dpg.add_text("Mesure", color=(100, 255, 100))

    #segments
    for i, (x1, y1, x2, y2) in enumerate(segments):
        with dpg.table_row(parent="table_resultats"):
            dpg.add_text(str(i + 1))
            r = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) / 2
            dpg.add_text(format_diametre(r))
            if i == segment_etalon_idx:
                dpg.add_text("Etalon", color=(255, 165, 0))
            else:
                dpg.add_text("Mesure", color=(100, 255, 100))

# ─────────────────────────────────────────
# region CHARGER IMAGE
# ─────────────────────────────────────────
def charger_image():
    dpg.show_item("dialogue_fichier")

def calibrate():
    global K, D, h, w
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
            objpoints.append(objp.reshape(-1,1,3))
            imgpoints.append(corners.reshape(-1,1,2))

            # Affichage (pour vérifier)
            # cv2.drawChessboardCorners(img, pattern_size, corners, ret)
            # cv2.imshow(f"Corners_{fname}", img)
            # cv2.waitKey(200)
    
        #     print(fname, "-> OK ✅")
        # else:
        #     print(fname, "-> ECHEC ❌")
    
    # ✅ Vérification
    if len(objpoints) < 5:
        print("Calibration : Pas assez d'images valides ❌")
        exit()
    
    # 📏 Récupération taille image
    img = cv2.imread(images[0])
    h, w = img.shape[:2]
    # print (f"damier : h={h} et w={w}")
    
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

def correction():
    global chemin_image_actuelle
    img = cv2.imread(chemin_image_actuelle)
    hi, wi = img.shape[:2]

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
    
    # Sauvegarde
    filename = os.path.basename(chemin_image_actuelle)
    name, ext = os.path.splitext(filename)
    new_name = name + "_corrigee" + ext
    folder = os.path.dirname(chemin_image_actuelle)
    full_path = os.path.join(folder, new_name)
    cv2.imwrite(full_path, undistorted)
    chemin_image_actuelle = full_path

def callback_fichier(sender, app_data):
    global chemin_image_actuelle, texture_tag
    calibrate()
    if app_data and app_data.get("file_path_name"):
        chemin_image_actuelle = app_data["file_path_name"]
        correction()
        img = cv2.imread(chemin_image_actuelle)
        if img is None:
            dpg.set_value("statut", "Erreur : impossible de charger l'image")
            return

        img = cv2.resize(img, (W, H))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
        img_data = img.flatten().astype(np.float32) / 255.0

        if texture_tag and dpg.does_item_exist(texture_tag):
            dpg.delete_item(texture_tag)
        with dpg.texture_registry():
            texture_tag = dpg.add_static_texture(W, H, img_data)

        update_display()
        dpg.set_value("statut", f"Image chargee : {os.path.basename(chemin_image_actuelle)}")

# ─────────────────────────────────────────
# region MODE DESSIN
# ─────────────────────────────────────────
def toggle_draw_mode_cercle():
    global mode_dessin_cercle, point1_temp, mode_dessin_segment
    if calibration:
        return
    mode_dessin_cercle = not mode_dessin_cercle
    if mode_dessin_cercle:
        mode_dessin_segment = False
        point1_temp = None
        dpg.configure_item("btn_draw", label="ACTIF — cliquez pour desactiver")
        dpg.configure_item("btn_draw_sgt", label="Dessiner un segment")
        dpg.set_value("statut", "Mode dessin cercle ACTIF")
    else:
        point1_temp = None
        dpg.configure_item("btn_draw", label="Dessiner un cercle")
        dpg.set_value("statut", "Mode dessin cercle desactive")
        update_display()

def toggle_draw_mode_segment():
    global mode_dessin_segment, point1_temp, mode_dessin_cercle
    mode_dessin_segment = not mode_dessin_segment
    if mode_dessin_segment:
        mode_dessin_cercle = False
        point1_temp = None
        dpg.configure_item("btn_draw_sgt", label="ACTIF — cliquez pour desactiver")
        dpg.configure_item("btn_draw", label="Dessiner un cercle")
        dpg.set_value("statut", "Mode dessin segment ACTIF")
    else:
        point1_temp = None
        dpg.configure_item("btn_draw_sgt", label="Dessiner un segment")
        dpg.set_value("statut", "Mode dessin desactive")
        update_display()

# ─────────────────────────────────────────
# region CALIBRATION
# ─────────────────────────────────────────
def definir_etalon():
    global ratio_px_mm, segment_etalon_idx, calibration, idx_segments, mode_dessin_segment, mode_dessin_cercle
    calibration = not calibration
    if calibration:
        #print(f"calib : cercle : {mode_dessin_cercle} et sgt : {mode_dessin_segment}")
        mode_dessin_segment = True
        mode_dessin_cercle = False
        dpg.configure_item("btn_draw", label="Dessiner un cercle")
        dpg.configure_item("btn_draw_sgt", label="ACTIF — cliquez pour desactiver")
        dpg.configure_item("btn_calib", label=" Valider calibration ")
        dpg.set_value("statut", "Calibration en cours... sélectionner le cercle de 60mm de diamètre ")
    else:
        mode_dessin_segment = False
        dpg.configure_item("btn_calib", label=" Calibration ")
        idx_segments = len(segments) - 1
        x1, y1, x2, y2= segments[idx_segments]
        r = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) / 2
        d_px = r * 2

        ratio_px_mm = d_px / DIAMETRE_ETALON_MM
        segment_etalon_idx = idx_segments

        dpg.set_value("label_kp", f"Kp = {ratio_px_mm:.4f} px/mm")
        dpg.set_value("statut",f"Calibration OK — etalon = {int(d_px)} px  Kp = {ratio_px_mm:.4f} px/mm")
        update_display()

def reset_calibration():
    global ratio_px_mm, segment_etalon_idx
    ratio_px_mm = None
    segment_etalon_idx = None
    dpg.set_value("label_kp", "Kp = non calibre")
    dpg.set_value("statut", "Calibration reinitialisee")
    update_display()

# ─────────────────────────────────────────
# region GESTION SOURIS
# ─────────────────────────────────────────
def on_mouse_click():
    global point1_temp
    if not mode_dessin_cercle and not mode_dessin_segment:
        return
    if not dpg.is_item_hovered("drawlist_principal"):
        return

    x, y = dpg.get_drawing_mouse_pos()
    if x < 0 or x > W or y < 0 or y > H:
        return
    # print(f"mode dessin : {mode_dessin_cercle}, seg : {mode_dessin_segment}")
    if mode_dessin_segment : 
        if point1_temp is None:
            point1_temp = (x, y)
            update_display()
            dpg.set_value("statut",
                f"Point 1 pose ({int(x)}, {int(y)}) — Clic 2 : point oppose du segment")
        else:
            x1, y1 = point1_temp
            if calibration :
                x2, y2 = x, y1
                cy = y1
            else :
                x2, y2 = x, y
                cy = (y1 + y2) / 2
            cx = (x1 + x2) / 2
            segments.append((x1, y1, x2, y2))
            r = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) / 2
            if ratio_px_mm:
                diam_mm = (r * 2) / ratio_px_mm
                dpg.set_value("statut",
                    f"Segment ajoute — Centre ({int(cx)},{int(cy)}) | O = {diam_mm:.2f} mm")
            else:
                dpg.set_value("statut",
                    f"Segment ajoute — {int(r*2)} px ")
            point1_temp = None
            update_display()
    elif mode_dessin_cercle :
        if point1_temp is None:
            # ── Premier clic : bord 1
            point1_temp = (x, y)
            update_display()
            dpg.set_value("statut",
                f"Point 1 posé ({int(x)}, {int(y)}) — Clic 2 : bord opposé du cercle")
        else:
            # ── Deuxième clic : bord 2 → calcul centre + rayon
            x1, y1 = point1_temp
            x2, y2 = x, y

            # Centre = milieu du segment
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            # Rayon = moitié de la distance entre les 2 points
            radius = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) / 2

            cercles.append((cx, cy, radius))
            if ratio_px_mm:
                diam_mm = (radius * 2) / ratio_px_mm
                dpg.set_value("statut",
                    f" Cercle ajouté — Centre ({int(cx)},{int(cy)}) |  = {diam_mm:.2f} mm")
            else:
                dpg.set_value("statut",
                    f"Cercle ajouté — Centre ({int(cx)},{int(cy)}) | = {int(radius*2)} px  "
                    f"— Cliquez ' Définir étalon' si c'est le trou central")
            point1_temp = None
            update_display()

def on_mouse_move():
    if (not mode_dessin_cercle and not mode_dessin_segment) or point1_temp is None:
        return
    if not dpg.is_item_hovered("drawlist_principal"):
        return

    x, y = dpg.get_drawing_mouse_pos()
    if not (0 <= x <= W and 0 <= y <= H):
        return

    x1, y1 = point1_temp
    cx = (x1 + x) / 2
    cy = (y1 + y) / 2
    radius = math.sqrt((x - x1) ** 2 + (y - y1) ** 2) / 2

    update_display()

    # Prévisualisation : segment / cercle calculé
    if mode_dessin_segment : 
        if calibration :
            y = y1
        # print(f"x = {x} et x1 = {x1} et y = {y} et y1 = {y1}")
        dpg.draw_line((x1, y1), (x, y), color=(0, 200, 255, 180),thickness=1, parent="drawlist_principal")
    elif mode_dessin_cercle:
        dpg.draw_line((x1, y1), (x, y), color=(0, 200, 255, 180), thickness=1, parent="drawlist_principal")
        dpg.draw_circle((cx, cy), radius, color=(0, 200, 255, 200), thickness=2, parent="drawlist_principal")
        dpg.draw_circle((cx, cy), 4, color=(255, 255, 255, 255), fill=(255, 255, 255, 200), parent="drawlist_principal")
        dpg.draw_circle((x, y), 6, color=(0, 200, 255, 255), fill=(0, 200, 255, 180), parent="drawlist_principal")
    
    if ratio_px_mm and radius > 0:
        diam_mm = (radius * 2) / ratio_px_mm
        dpg.set_value("statut", f"O = {diam_mm:.2f} mm  |  Centre : ({int(cx)}, {int(cy)})")
    else:
        dpg.set_value("statut",
            f"O = {int(radius*2)} px  |  Centre : ({int(cx)}, {int(cy)})")

def clear_cercles():
    global cercles, point1_temp
    cercles = []
    point1_temp = None
    update_display()
    dpg.set_value("statut", "Cercles effaces")

def clear_segments():
    global segments, point1_temp, ratio_px_mm, segment_etalon_idx
    segments = []
    point1_temp = None
    ratio_px_mm = None
    segment_etalon_idx = None
    dpg.set_value("label_kp", "Kp = non calibré")
    update_display()
    dpg.set_value("statut", "Segments effacés — calibration réinitialisée")

def supprimer_dernier_cercle():
    global cercles
    if cercles:
        cercles.pop()
        dpg.set_value("statut", "Dernier cercle supprime")
        update_display()

def supprimer_dernier_segment():
    global segments, segment_etalon_idx, ratio_px_mm
    if segments:
        segments.pop()
        if segment_etalon_idx == idx_segments:
            segment_etalon_idx = None
            ratio_px_mm = None
            dpg.set_value("label_kp", "Kp = non calibre")
            dpg.set_value("statut", "Segment etalon supprime : recalibrez")
        else:
            dpg.set_value("statut", "Dernier segment supprime")
        update_display()

def lancer_mesure():
    if chemin_image_actuelle is None:
        dpg.set_value("statut", "Chargez une image d'abord !")
        return
    dpg.set_value("statut", "Mesure automatique en cours...")

def exporter_rapport():
    dpg.set_value("statut", "Export en cours...")

# ─────────────────────────────────────────
# region INTERFACE
# ─────────────────────────────────────────
dpg.create_context()

with dpg.texture_registry():
    pass

with dpg.file_dialog(tag="dialogue_fichier", callback=callback_fichier,
                     show=False, width=600, height=400):
    dpg.add_file_extension(".jpg")
    dpg.add_file_extension(".png")
    dpg.add_file_extension(".bmp")
    dpg.add_file_extension(".jpeg")

with dpg.handler_registry():
    dpg.add_mouse_click_handler(callback=lambda: on_mouse_click())
    dpg.add_mouse_move_handler(callback=lambda: on_mouse_move())

with dpg.theme() as theme_principal:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_WindowBg,      (45, 45, 45))
        dpg.add_theme_color(dpg.mvThemeCol_ChildBg,       (55, 55, 55))
        dpg.add_theme_color(dpg.mvThemeCol_Text,          (240, 240, 240))
        dpg.add_theme_color(dpg.mvThemeCol_Button,        (75, 75, 75))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (100, 100, 100))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,  (130, 130, 130))
        dpg.add_theme_color(dpg.mvThemeCol_TableRowBg,    (55, 55, 55))
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6)
        dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)

with dpg.window(tag="fenetre_principale", width=1920, height=1080):
    dpg.add_text("CAMVIS — Analyse des 'usures'", color=(255, 255, 255))
    dpg.add_text("WHE — Equipe Instrumentation & Vision  |  CdCF-CAMVIS-001 Rev.A",
                 color=(180, 180, 180))
    dpg.add_separator()
    dpg.add_spacer(height=4)

    with dpg.group(horizontal=True):

        # ── PANNEAU GAUCHE ──────────────────────
        with dpg.child_window(width=260, height=1000):

            dpg.add_text("Image", color=(200, 200, 200))
            dpg.add_button(label="Charger une image",
                           callback=charger_image, width=235)
            dpg.add_spacer(height=8)

            dpg.add_separator()
            dpg.add_text("Dessin (2 points)", color=(200, 200, 200))
            # dpg.add_text("Clic 1 : bord gauche du trou", color=(160, 160, 160))
            # dpg.add_text("Clic 2 : bord droit du trou",  color=(160, 160, 160))
            # dpg.add_text("centre + diametre calcules auto", color=(0, 200, 255))
            # dpg.add_spacer(height=4)
            dpg.add_button(label="Dessiner un cercle",
                           tag="btn_draw", callback=toggle_draw_mode_cercle, width=235)
            dpg.add_button(label="Supprimer le dernier cercle",
                           callback=supprimer_dernier_cercle, width=235)
            dpg.add_button(label="Effacer tout les cercles",
                           callback=clear_cercles, width=235)
            dpg.add_spacer(height=8)
            dpg.add_button(label="Dessiner un segment",
                           tag="btn_draw_sgt", callback=toggle_draw_mode_segment, width=235)
            dpg.add_button(label="Supprimer le dernier segment",
                           callback=supprimer_dernier_segment, width=235)
            dpg.add_button(label="Effacer tout les segments",
                           callback=clear_segments, width=235)
            dpg.add_spacer(height=8)

            dpg.add_separator()
            dpg.add_text("Calibration", color=(255, 165, 0))
            # dpg.add_text("1. Dessinez le trou central",  color=(200, 200, 200))
            # dpg.add_text("2. Cliquez 'Definir etalon'",  color=(200, 200, 200))
            dpg.add_text(f"   Kp = D_px / {DIAMETRE_ETALON_MM:.0f} mm", color=(160, 160, 160))
            dpg.add_spacer(height=4)
            dpg.add_button(label="Calibration", tag="btn_calib",
                           callback=definir_etalon, width=235)
            dpg.add_button(label="Reinitialiser calibration",
                           callback=reset_calibration, width=235)
            dpg.add_spacer(height=4)
            dpg.add_text("Kp = non calibre", tag="label_kp", color=(255, 165, 0))

            dpg.add_separator()
            dpg.add_spacer(height=8)
            dpg.add_text("Actions", color=(200, 200, 200))
            dpg.add_button(label="Lancer mesure auto",
                           callback=lancer_mesure, width=235)
            dpg.add_button(label="Exporter PDF / CSV",
                           callback=exporter_rapport, width=235)

            dpg.add_separator()
            dpg.add_spacer(height=8)
            dpg.add_text("Statut :", color=(255, 255, 255))
            dpg.add_text("Pret", tag="statut", color=(100, 255, 100), wrap=235)

            dpg.add_separator()
            dpg.add_spacer(height=8)
            dpg.add_text("Resultats :", color=(255, 255, 255))
            dpg.add_spacer(height=4)
            with dpg.table(tag="table_resultats", header_row=True,
                           borders_innerH=True, borders_outerH=True,
                           borders_innerV=True, borders_outerV=True,
                           row_background=True, width=235):
                dpg.add_table_column(label="#",     width_fixed=True, init_width_or_weight=20)
                dpg.add_table_column(label="Diam.", width_fixed=True, init_width_or_weight=90)
                dpg.add_table_column(label="Type",  width_fixed=True, init_width_or_weight=60)

        # ── ZONE IMAGE ──────────────────────────
        with dpg.child_window(width=1640, height=1000):
            with dpg.drawlist(width=W, height=H, tag="drawlist_principal"):
                dpg.draw_rectangle((0, 0), (W, H), fill=(40, 40, 40))
                dpg.draw_text((W//2 - 180, H//2),
                              "Chargez une image pour commencer",
                              color=(130, 130, 130), size=18)

dpg.bind_theme(theme_principal)
dpg.create_viewport(title="CAMVIS — WHE Instrumentation", width=1920, height=1080)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("fenetre_principale", True)
dpg.start_dearpygui()
dpg.destroy_context()
