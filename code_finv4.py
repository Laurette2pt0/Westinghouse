import dearpygui.dearpygui as dpg
import cv2
import numpy as np
import math
import os
import json
import csv
from datetime import datetime
import sqlite3
import glob

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# ─────────────────────────────────────────
# region VARIABLES GLOBALES
# ─────────────────────────────────────────
chemin_image_actuelle = None
texture_tag = None
cercles = []
segments = []
mode_dessin_cercle = False
mode_dessin_segment = False
point1_temp = None
nom_element = ""

DIAMETRE_ETALON_MM = 60.0
ratio_px_mm = None
cercle_etalon_idx = None
segment_etalon_idx = None  
calibration_mode = False  
ID_CAMERA_PAR_DEFAUT = "CAM-001"

W = 1630
H = 970

#pour la pop up 
diametre = 0
temp_cx = 0
temp_cy = 0
temp_x1 = 0
temp_y1 = 0
temp_x2 = 0
temp_y2 = 0
obj = ""

# Initialisation matrices
K = np.zeros((3, 3))
D = np.zeros((4, 1))  # modèle fisheye = 4 coeff

#Dimension damier
h, w = 0, 0

# ─────────────────────────────────────────
# region ZOOM & PAN
# ─────────────────────────────────────────
zoom_level = 1.0
ZOOM_MIN   = 1.0
ZOOM_MAX   = 10.0
ZOOM_STEP  = 0.15

view_x = 0.0
view_y = 0.0

tex_src_x = 0
tex_src_y = 0

pan_actif  = False
pan_last_x = 0.0
pan_last_y = 0.0

MINI_W = 260
MINI_H = 0
MINI_X = W - MINI_W - 10
MINI_Y = 10

img_originale = None

# ─────────────────────────────────────────
# region HELPERS ZOOM
# ─────────────────────────────────────────
def screen_to_image(sx, sy):
    return tex_src_x + sx / zoom_level, tex_src_y + sy / zoom_level

def image_to_screen(ix, iy):
    return (ix - tex_src_x) * zoom_level, (iy - tex_src_y) * zoom_level

def clamp_view():
    global view_x, view_y
    if img_originale is None:
        return
    orig_h, orig_w = img_originale.shape[:2]
    visible_w = W / zoom_level
    visible_h = H / zoom_level

    if orig_w * zoom_level <= W:
        # Image plus petite que canvas → centrer
        view_x = -(W / zoom_level - orig_w) / 2
    else:
        view_x = max(0.0, min(view_x, orig_w - visible_w))

    if orig_h * zoom_level <= H:
        # Image plus petite que canvas → centrer
        view_y = -(H / zoom_level - orig_h) / 2
    else:
        view_y = max(0.0, min(view_y, orig_h - visible_h))

def rebuild_texture_zoom():
    global texture_tag, tex_src_x, tex_src_y
    if img_originale is None:
        return
    orig_h, orig_w = img_originale.shape[:2]

    # Taille visible en pixels image
    src_w = int(W / zoom_level) + 2
    src_h = int(H / zoom_level) + 2

    # Offset dans l'image (peut être négatif si image plus petite que canvas)
    src_x = int(max(0, view_x))
    src_y = int(max(0, view_y))
    src_w = max(1, min(src_w, orig_w - src_x))
    src_h = max(1, min(src_h, orig_h - src_y))

    # tex_src = view réel (négatif possible) pour que image_to_screen soit correct
    tex_src_x = view_x
    tex_src_y = view_y

    crop = img_originale[src_y:src_y + src_h, src_x:src_x + src_w]

    # Canvas de sortie noir, on colle le crop à la bonne position
    canvas = np.zeros((H, W, 4), dtype=np.uint8)

    # Position du coin haut-gauche de l'image sur le canvas
    canvas_x = int(-view_x * zoom_level) if view_x < 0 else 0
    canvas_y = int(-view_y * zoom_level) if view_y < 0 else 0

    # Taille du crop affiché sur le canvas
    display_w = min(int(src_w * zoom_level), W - canvas_x)
    display_h = min(int(src_h * zoom_level), H - canvas_y)

    if display_w > 0 and display_h > 0:
        resized = cv2.resize(crop, (display_w, display_h), interpolation=cv2.INTER_LINEAR)
        canvas[canvas_y:canvas_y + display_h, canvas_x:canvas_x + display_w] = resized

    img_data = canvas.flatten().astype(np.float32) / 255.0
    if texture_tag and dpg.does_item_exist(texture_tag):
        dpg.delete_item(texture_tag)
    with dpg.texture_registry():
        texture_tag = dpg.add_static_texture(W, H, img_data)

# ─────────────────────────────────────────
# region EXPORT IMAGE
# ─────────────────────────────────────────
def exporter_image():
    if img_originale is None:
        dpg.set_value("statut", "ERREUR: Aucune image chargee")
        return
    if not cercles and not segments:
        dpg.set_value("statut", "ERREUR: Aucun cercle ou segment a exporter")
        return
    
    try:
        os.makedirs("exports", exist_ok=True)
        nom = f"exports/image_mesures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        img_export = cv2.cvtColor(img_originale.copy(), cv2.COLOR_RGBA2BGR)
        
        # Dessiner les cercles
        for i, (cx_img, cy_img, r_img, n_elmt) in enumerate(cercles):
            if i == cercle_etalon_idx:
                couleur = (0, 165, 255)
            else:
                couleur = (0, 255, 0)
            
            centre = (int(cx_img), int(cy_img))
            rayon = int(r_img)
            
            cv2.circle(img_export, centre, rayon, couleur, 3)
            cv2.line(img_export, (int(cx_img - r_img), int(cy_img)), (int(cx_img + r_img), int(cy_img)), couleur, 2)
            cv2.circle(img_export, (int(cx_img - r_img), int(cy_img)), 6, (0, 0, 255), -1)
            cv2.circle(img_export, (int(cx_img + r_img), int(cy_img)), 6, (0, 0, 255), -1)
            cv2.circle(img_export, centre, 5, (255, 255, 255), -1)
            
            if ratio_px_mm:
                texte = f"{(r_img * 2) / ratio_px_mm:.2f} mm"
            else:
                texte = f"{int(r_img * 2)} px"
            
            cv2.putText(img_export, texte, (int(cx_img - 60), int(cy_img - rayon - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2)
        
        # Dessiner les segments
        for i, (x1, y1, x2, y2, n_elmt) in enumerate(segments):
            if n_elmt == segment_etalon_idx:
                couleur = (0, 165, 255)
            else:
                couleur = (0, 255, 0)
            
            cv2.line(img_export, (int(x1), int(y1)), (int(x2), int(y2)), couleur, 3)
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            r = math.sqrt((x2 - x1)**2 + (y2 - y1)**2) / 2
            cv2.circle(img_export, (int(cx), int(cy)), 5, (255, 255, 255), -1)
            
            if ratio_px_mm:
                texte = f"{(r * 2) / ratio_px_mm:.2f} mm"
            else:
                texte = f"{int(r * 2)} px"
            if n_elmt == segment_etalon_idx:
                texte += " ETALON"
            
            cv2.putText(img_export, texte, (int(cx - 60), int(cy - 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2)
        
        info_y = img_export.shape[0] - 20
        if ratio_px_mm:
            info = f"CAMVIS - Kp = {ratio_px_mm:.4f} px/mm"
        else:
            info = "CAMVIS - Non calibre"
        cv2.putText(img_export, info, (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        
        cv2.imwrite(nom, img_export)
        dpg.set_value("statut", f"IMAGE exportee: {nom}")
        
    except Exception as e:
        dpg.set_value("statut", f"ERREUR image: {str(e)}")

def ouvrir_dossier():
    import subprocess
    dossier = os.path.abspath("exports")
    os.makedirs(dossier, exist_ok=True)
    subprocess.Popen(f'explorer "{dossier}"')
    dpg.set_value("statut", f"Dossier ouvert: {dossier}")

# ─────────────────────────────────────────
# region EXPORTS CSV, JSON, PDF
# ─────────────────────────────────────────
def exporter_csv():
    if not cercles and not segments:
        dpg.set_value("statut", "Aucune mesure a exporter")
        return
    try:
        os.makedirs("exports", exist_ok=True)
        nom = f"exports/mesures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(nom, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["CAMVIS - Export des mesures"])
            w.writerow([f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"])
            w.writerow([f"Camera ID: {dpg.get_value('id_camera') if dpg.does_item_exist('id_camera') else ID_CAMERA_PAR_DEFAUT}"])
            w.writerow([f"Image: {os.path.basename(chemin_image_actuelle) if chemin_image_actuelle else 'N/A'}"])
            w.writerow([f"Calibration: {'Activee' if ratio_px_mm else 'Non activee'}"])
            if ratio_px_mm: w.writerow([f"Kp: {ratio_px_mm:.4f} px/mm"])
            w.writerow([])
            w.writerow(["=== CERCLES ==="])
            w.writerow(["Numero","Centre X","Centre Y","Diametre (px)","Diametre (mm)","Type"])
            for i, (cx, cy, r, n_elmt) in enumerate(cercles):
                d_px = r*2
                d_mm = d_px/ratio_px_mm if ratio_px_mm else ""
                w.writerow([i+1, f"{cx:.1f}", f"{cy:.1f}", f"{d_px:.1f}",
                            f"{d_mm:.2f}" if d_mm else "--",
                            "Etalon" if i==cercle_etalon_idx else "Mesure"])
            w.writerow([])
            w.writerow(["=== SEGMENTS ==="])
            w.writerow(["Numero","X1","Y1","X2","Y2","Longueur (px)","Longueur (mm)","Type"])
            for i, (x1, y1, x2, y2, n_elmt) in enumerate(segments):
                longueur = math.sqrt((x2-x1)**2 + (y2-y1)**2)
                l_mm = longueur/ratio_px_mm if ratio_px_mm else ""
                w.writerow([i+1, f"{x1:.1f}", f"{y1:.1f}", f"{x2:.1f}", f"{y2:.1f}",
                            f"{longueur:.1f}", f"{l_mm:.2f}" if l_mm else "--",
                            "Etalon" if n_elmt == segment_etalon_idx else "Mesure"])
        dpg.set_value("statut", f"CSV exporte: {nom}")
    except Exception as e:
        dpg.set_value("statut", f"Erreur CSV: {str(e)}")

def exporter_json():
    if not cercles and not segments:
        dpg.set_value("statut", "Aucune mesure a exporter")
        return
    try:
        os.makedirs("exports", exist_ok=True)
        nom = f"exports/mesures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data = {"date": datetime.now().isoformat(),
                "camera_id": dpg.get_value("id_camera") if dpg.does_item_exist("id_camera") else ID_CAMERA_PAR_DEFAUT,
                "image": chemin_image_actuelle,
                "calibration": {"active": ratio_px_mm is not None, "kp": ratio_px_mm,
                                "diametre_etalon_mm": DIAMETRE_ETALON_MM},
                "cercles": [],
                "segments": []}
        for i, (cx, cy, r, n_elmt) in enumerate(cercles):
            data["cercles"].append({"numero": i+1, "centre_x": cx, "centre_y": cy,
                                    "diametre_px": r*2,
                                    "diametre_mm": (r*2)/ratio_px_mm if ratio_px_mm else None,
                                    "type": "Etalon" if i==cercle_etalon_idx else "Mesure"})
        for i, (x1, y1, x2, y2,n_elmt) in enumerate(segments):
            longueur = math.sqrt((x2-x1)**2 + (y2-y1)**2)
            data["segments"].append({"numero": i+1, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                                     "longueur_px": longueur,
                                     "longueur_mm": longueur/ratio_px_mm if ratio_px_mm else None,
                                     "type": "Etalon" if n_elmt==segment_etalon_idx else "Mesure"})
        with open(nom, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        dpg.set_value("statut", f"JSON exporte: {nom}")
    except Exception as e:
        dpg.set_value("statut", f"Erreur JSON: {str(e)}")

def exporter_pdf():
    if not cercles and not segments:
        dpg.set_value("statut", "Aucune mesure a exporter")
        return
    if not REPORTLAB_AVAILABLE:
        dpg.set_value("statut", "PDF: Reportlab non installe")
        return
    try:
        os.makedirs("exports", exist_ok=True)
        nom = f"exports/rapport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        doc = SimpleDocTemplate(nom, pagesize=A4)
        styles = getSampleStyleSheet()
        story = [Paragraph("CAMVIS - Rapport d'Analyse Dimensionnelle", styles['Title']),
                 Spacer(1, 12),
                 Paragraph(f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles['Normal']),
                 Paragraph(f"Camera ID: {dpg.get_value('id_camera') if dpg.does_item_exist('id_camera') else ID_CAMERA_PAR_DEFAUT}", styles['Normal']),
                 Spacer(1, 12)]
        
        if cercles:
            story.append(Paragraph("Cercles mesures:", styles['Heading2']))
            data = [["N°","Diametre (px)","Diametre (mm)","Type"]]
            for i, (cx, cy, r, n_elmt) in enumerate(cercles):
                d_px = r*2
                d_mm = d_px/ratio_px_mm if ratio_px_mm else 0
                data.append([str(i+1), f"{d_px:.1f}", f"{d_mm:.2f}" if ratio_px_mm else "--",
                             "Etalon" if i==cercle_etalon_idx else "Mesure"])
            t = Table(data)
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.grey),
                                   ('ALIGN',(0,0),(-1,-1),'CENTER'),
                                   ('GRID',(0,0),(-1,-1),1,colors.black)]))
            story.append(t)
            story.append(Spacer(1, 12))
        
        if segments:
            story.append(Paragraph("Segments mesures:", styles['Heading2']))
            data = [["N°","Longueur (px)","Longueur (mm)","Type"]]
            for i, (x1, y1, x2, y2, n_elmt) in enumerate(segments):
                longueur = math.sqrt((x2-x1)**2 + (y2-y1)**2)
                l_mm = longueur/ratio_px_mm if ratio_px_mm else 0
                data.append([str(i+1), f"{longueur:.1f}", f"{l_mm:.2f}" if ratio_px_mm else "--",
                             "Etalon" if n_elmt == segment_etalon_idx else "Mesure"])
            t = Table(data)
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.grey),
                                   ('ALIGN',(0,0),(-1,-1),'CENTER'),
                                   ('GRID',(0,0),(-1,-1),1,colors.black)]))
            story.append(t)
        
        doc.build(story)
        dpg.set_value("statut", f"PDF exporte: {nom}")
    except Exception as e:
        dpg.set_value("statut", f"Erreur PDF: {str(e)}")

def exporter_rapport_complet():
    exporter_csv()
    exporter_json()
    exporter_pdf()
    exporter_image()
    dpg.set_value("statut", "Export complet termine (CSV, JSON, PDF, Image)")

# ─────────────────────────────────────────
# region AFFICHAGE
# ─────────────────────────────────────────
def format_diametre(r):
    if ratio_px_mm:
        return f"{(r * 2) / ratio_px_mm:.2f} mm"
    return f"{int(r * 2)} px"

def format_longueur(longueur):
    if ratio_px_mm:
        return f"{longueur / ratio_px_mm:.2f} mm"
    return f"{int(longueur)} px"

def draw_minimap():
    if img_originale is None:
        return
    global MINI_H
    ratio = img_originale.shape[0] / img_originale.shape[1]
    MINI_H = int(MINI_W * ratio)
    mx = MINI_X
    my = MINI_Y

    dpg.draw_rectangle((mx - 2, my - 2), (mx + MINI_W + 2, my + MINI_H + 2),
                       fill=(0, 0, 0, 180), color=(100, 100, 100, 200),
                       thickness=1, parent="drawlist_principal")
    if dpg.does_item_exist("texture_minimap"):
        dpg.draw_image("texture_minimap", (mx, my), (mx + MINI_W, my + MINI_H),
                       parent="drawlist_principal")

    vis_x0 = tex_src_x
    vis_y0 = tex_src_y
    vis_x1 = tex_src_x + W / zoom_level
    vis_y1 = tex_src_y + H / zoom_level

    scale_x = MINI_W / img_originale.shape[1]
    scale_y = MINI_H / img_originale.shape[0]

    rx0 = max(mx, min(mx + vis_x0 * scale_x, mx + MINI_W))
    ry0 = max(my, min(my + vis_y0 * scale_y, my + MINI_H))
    rx1 = max(mx, min(mx + vis_x1 * scale_x, mx + MINI_W))
    ry1 = max(my, min(my + vis_y1 * scale_y, my + MINI_H))

    dpg.draw_rectangle((rx0, ry0), (rx1, ry1),
                       color=(255, 60, 60, 255), thickness=2,
                       parent="drawlist_principal")
    dpg.draw_text((mx, my + MINI_H + 4),
                  f"Zoom x{zoom_level:.2f}  |  molette=zoom  clic_droit=pan  clic_minimap=nav",
                  color=(180, 180, 180), size=11, parent="drawlist_principal")

def update_display():
    if not dpg.does_item_exist("drawlist_principal"):
        return
    dpg.delete_item("drawlist_principal", children_only=True)

    if texture_tag and dpg.does_item_exist(texture_tag):
        dpg.draw_image(texture_tag, (0, 0), (W, H), parent="drawlist_principal")
    else:
        dpg.draw_rectangle((0, 0), (W, H), fill=(40, 40, 40), parent="drawlist_principal")
        dpg.draw_text((W//2 - 180, H//2), "Chargez une image pour commencer",
                      color=(130, 130, 130), size=18, parent="drawlist_principal")

    # Cercles
    for i, (cx_img, cy_img, r_img, n_elmt) in enumerate(cercles):
        sx, sy = image_to_screen(cx_img, cy_img)
        r_screen = r_img * zoom_level
        arr = np.array([sx + r_screen < 0 , sx - r_screen > W,sy + r_screen < 0 ,sy - r_screen > H])
        # print(f" cest quoi ca encore  : {arr}")
        if arr.any():
            print("bonsoir?")
            continue
        print(f"sx = {sx}; sy = {sy};r = {r_screen}") 
        couleur_bord = (0, 255, 0, 255)
        couleur_fill = (0, 255, 0, 35)
        print("draw my girl")
        dpg.draw_circle((sx, sy), r_screen, color=couleur_bord, fill=couleur_fill, thickness=2, parent="drawlist_principal")
        dpg.draw_line((sx - r_screen, sy), (sx + r_screen, sy), color=(255, 50, 50, 220), thickness=2, parent="drawlist_principal")
        dpg.draw_circle((sx, sy), 4, color=(255, 255, 255, 255), fill=(255, 255, 255, 200), parent="drawlist_principal")

        label = format_diametre(r_img)
        label += " " + n_elmt
        dpg.draw_text((sx - 55, sy - r_screen - 14), label, color=couleur_bord, size=13, parent="drawlist_principal")

    # Segments
    for i, (x1_img, y1_img, x2_img, y2_img, n_elmt) in enumerate(segments):
        sx1, sy1 = image_to_screen(x1_img, y1_img)
        sx2, sy2 = image_to_screen(x2_img, y2_img)
        
        is_etalon = (n_elmt == segment_etalon_idx)
        if is_etalon:
            couleur_bord = (255, 165, 0, 255)
        else:
            couleur_bord = (0, 255, 0, 255)
        print("fait un segment non ?")
        dpg.draw_line((sx1, sy1), (sx2, sy2), color=couleur_bord, thickness=3, parent="drawlist_principal")
        
        # Centre du segment
        cx = (sx1 + sx2) / 2
        cy = (sy1 + sy2) / 2
        longueur = math.sqrt((x2_img - x1_img)**2 + (y2_img - y1_img)**2)
        
        dpg.draw_circle((cx, cy), 4,
                        color=(255, 255, 255, 255), fill=(255, 255, 255, 200),
                        parent="drawlist_principal")
        
        label = format_longueur(longueur)
        if is_etalon:
            label += "  ETALON"
        label += " " + n_elmt
        dpg.draw_text((cx - 55, cy - 20), label, color=couleur_bord, size=13, parent="drawlist_principal")

    # Point temporaire
    if point1_temp:
        x1_img, y1_img = point1_temp
        sx1, sy1 = image_to_screen(x1_img, y1_img)
        dpg.draw_circle((sx1, sy1), 6, color=(0, 200, 255, 255),
                        fill=(0, 200, 255, 180), parent="drawlist_principal")
        dpg.draw_text((sx1 + 8, sy1 - 8), "Point 1",
                      color=(0, 200, 255, 255), size=12, parent="drawlist_principal")

    if ratio_px_mm:
        dpg.draw_rectangle((0, H - 18), (W, H), fill=(20, 50, 20, 220), parent="drawlist_principal")
        dpg.draw_text((6, H - 15),
                      f"Calibre — Kp = {ratio_px_mm:.4f} px/mm ; Etalon {DIAMETRE_ETALON_MM:.0f} mm",
                      color=(100, 255, 100), size=12, parent="drawlist_principal")
    else:
        dpg.draw_rectangle((0, H - 18), (W, H), fill=(55, 35, 10, 220), parent="drawlist_principal")
        dpg.draw_text((6, H - 15),
                      "Non calibre ; cliquez 'Calibration' puis dessinez un segment horizontal sur l'etalon 60 mm",
                      color=(255, 165, 0), size=12, parent="drawlist_principal")
    print("next")
    draw_minimap()
    update_resultats()

def update_resultats():
    if not dpg.does_item_exist("table_resultats"):
        return
    dpg.delete_item("table_resultats", children_only=True)
    dpg.add_table_column(label="#", parent="table_resultats", width_fixed=True, init_width_or_weight=20)
    dpg.add_table_column(label="Diam/Long", parent="table_resultats", width_fixed=True, init_width_or_weight=90)
    dpg.add_table_column(label="Type", parent="table_resultats", width_fixed=True, init_width_or_weight=60)
    
    for i, (cx, cy, r, n_elmt) in enumerate(cercles):
        with dpg.table_row(parent="table_resultats"):
            dpg.add_text(n_elmt)
            print(f"r = {r}")
            dpg.add_text(format_diametre(r))
            if i == cercle_etalon_idx:
                dpg.add_text("Etalon", color=(255, 165, 0))
            else:
                dpg.add_text("Cercle", color=(100, 255, 100))
    
    for i, (x1, y1, x2, y2, n_elmt) in enumerate(segments):
        longueur = math.sqrt((x2-x1)**2 + (y2-y1)**2)
        with dpg.table_row(parent="table_resultats"):
            dpg.add_text(n_elmt)
            dpg.add_text(format_longueur(longueur))
            if n_elmt == segment_etalon_idx:
                dpg.add_text("Etalon", color=(255, 165, 0))
            else:
                dpg.add_text("Segment", color=(100, 255, 100))

# ─────────────────────────────────────────
# region CHARGER IMAGE
# ─────────────────────────────────────────
def charger_image():
    dpg.show_item("dialogue_fichier")

def calibrate():
    global K, D, h, w
    valeur = dpg.get_value("camera")
    # Taille du damier (coins INTERNES)
    pattern_size = (8, 5)
    
    # Préparation des points 3D (grille réelle)
    objp = np.zeros((pattern_size[0]*pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
    
    objpoints = []  # points réels
    imgpoints = []  # points image

    if valeur==ID_CAMERA_PAR_DEFAUT:
        images = glob.glob("*.jpg")
    else : 
        print("Pas de donné pour réaliser la matrice de distorsion")
        return
    #  Détection des coins (version robuste)
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
    
        #     print(fname, "-> OK ")
        # else:
        #     print(fname, "-> ECHEC ")
    
    #  Vérification
    if len(objpoints) < 5:
        print("Calibration : Pas assez d'images valides")
        exit()
    
    # Récupération taille image
    img = cv2.imread(images[0])
    h, w = img.shape[:2]
    # print (f"damier : h={h} et w={w}")
    
    # flags fisheye
    flags = cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC + \
            cv2.fisheye.CALIB_CHECK_COND + \
            cv2.fisheye.CALIB_FIX_SKEW
    
    #  Calibration FISHEYE
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
    global chemin_image_actuelle, img_originale
    # calibrate()
    
    img = cv2.imread(chemin_image_actuelle)
    h_img, w_img = img.shape[:2]

    scale_x = w_img / w
    scale_y = h_img / h

    K_scaled = K.copy()
    K_scaled[0, 0] *= scale_x
    K_scaled[1, 1] *= scale_y
    K_scaled[0, 2] *= scale_x
    K_scaled[1, 2] *= scale_y

    map1, map2 = cv2.fisheye.initUndistortRectifyMap(
    K_scaled, D, np.eye(3), K_scaled, (w_img, h_img), cv2.CV_32FC1)
    
    undistorted = cv2.remap(img, map1, map2, cv2.INTER_LINEAR)
    img_originale = undistorted
    filename = os.path.basename(chemin_image_actuelle)
    name, ext = os.path.splitext(filename)
    new_name = name + "_corrigee" + ext
    folder = os.path.dirname(chemin_image_actuelle)
    full_path = os.path.join(folder, new_name)
    cv2.imwrite(full_path, undistorted)
    chemin_image_actuelle = full_path
    
def callback_fichier(sender, app_data):
    global chemin_image_actuelle, img_originale
    global zoom_level, view_x, view_y, tex_src_x, tex_src_y, cercles, segments, ratio_px_mm, cercle_etalon_idx, segment_etalon_idx
    if app_data and app_data.get("file_path_name"):
        chemin_image_actuelle = app_data["file_path_name"]
        valeur = dpg.get_value("camera")
        if valeur==ID_CAMERA_PAR_DEFAUT:
            images = glob.glob("*.jpg")
        else : 
            dpg.set_value("statut", "Erreur : Sélectionner une camera")
            return
        correction() #corriger l'image
        img = cv2.imread(chemin_image_actuelle)
        if img is None:
            dpg.set_value("statut", "Erreur : impossible de charger l'image")
            return

        img_originale = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
        cercles = []
        segments = []
        ratio_px_mm = None
        cercle_etalon_idx = None
        segment_etalon_idx = None
        point1_temp = None
        zoom_level = 1.0
        view_x = 0.0
        view_y = 0.0
        tex_src_x = 0
        tex_src_y = 0
        # Dans callback_fichier, après zoom_level=1.0, view_x=0.0 etc...
        zoom_level = 1.0
        view_x = 0.0
        view_y = 0.0
        tex_src_x = 0
        tex_src_y = 0

        clamp_view()
        tex_src_x = view_x
        tex_src_y = view_y
        
        dpg.set_value("label_kp", "Kp = non calibre")

        mini_h = int(MINI_W * img_originale.shape[0] / img_originale.shape[1])
        mini_img = cv2.resize(img_originale, (MINI_W, mini_h), interpolation=cv2.INTER_AREA)
        mini_data = mini_img.flatten().astype(np.float32) / 255.0
        
        if dpg.does_item_exist("texture_minimap"):
            dpg.set_value("texture_minimap", mini_data)
        else : 
            with dpg.texture_registry():
                dpg.add_static_texture(MINI_W, mini_h, mini_data, tag="texture_minimap")

        rebuild_texture_zoom()
        update_display()
        dpg.set_value("statut", f"Image chargee : {os.path.basename(chemin_image_actuelle)}")

# ─────────────────────────────────────────
# region MODE DESSIN
# ─────────────────────────────────────────
def toggle_draw_mode_cercle():
    global mode_dessin_cercle, mode_dessin_segment, point1_temp, calibration_mode
    if calibration_mode:
        dpg.set_value("statut", "Desactivez la calibration d'abord")
        return
    mode_dessin_cercle = not mode_dessin_cercle
    if mode_dessin_cercle:
        mode_dessin_segment = False
        point1_temp = None
        dpg.configure_item("btn_draw", label="ACTIF — cliquez pour desactiver")
        dpg.configure_item("btn_draw_sgt", label="Dessiner un segment")
        dpg.set_value("statut", "Mode dessin CERCLE ACTIF")
    else:
        point1_temp = None
        dpg.configure_item("btn_draw", label="Dessiner un cercle")
        dpg.set_value("statut", "Mode dessin cercle desactive")
        update_display()

def toggle_draw_mode_segment():
    global mode_dessin_segment, mode_dessin_cercle, point1_temp, calibration_mode
    mode_dessin_segment = not mode_dessin_segment
    if mode_dessin_segment:
        mode_dessin_cercle = False
        point1_temp = None
        dpg.configure_item("btn_draw_sgt", label="ACTIF — cliquez pour desactiver")
        dpg.configure_item("btn_draw", label="Dessiner un cercle")
        dpg.set_value("statut", "Mode dessin SEGMENT ACTIF")
    else:
        point1_temp = None
        dpg.configure_item("btn_draw_sgt", label="Dessiner un segment")
        dpg.set_value("statut", "Mode dessin segment desactive")
        update_display()

# ─────────────────────────────────────────
# region CALIBRATION
# ─────────────────────────────────────────
def definir_etalon():
    global ratio_px_mm, segment_etalon_idx, calibration_mode, mode_dessin_segment, mode_dessin_cercle
    calibration_mode = not calibration_mode
    
    if calibration_mode:
        mode_dessin_segment = True
        mode_dessin_cercle = False
        point1_temp = None
        dpg.configure_item("btn_draw", label="Dessiner un cercle")
        dpg.configure_item("btn_draw_sgt", label="ACTIF — cliquez pour desactiver")
        dpg.configure_item("btn_calib", label=" VALIDER CALIBRATION ")
        dpg.set_value("statut", "Calibration en cours... dessinez un segment horizontal sur l'etalon de 60mm")
    else:
        if not segments:
            dpg.set_value("statut", "Aucun segment a calibrer")
            calibration_mode = False
            dpg.configure_item("btn_calib", label=" Calibration ")
            return
        
        # Prendre le dernier segment comme etalon
        idx = len(segments) - 1
        x1, y1, x2, y2, nom_element = segments[idx]
        longueur_px = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        ratio_px_mm = longueur_px / DIAMETRE_ETALON_MM
        segment_etalon_idx = nom_element
        
        mode_dessin_segment = False
        dpg.configure_item("btn_calib", label=" Calibration ")
        dpg.configure_item("btn_draw_sgt", label="Dessiner un segment")
        dpg.set_value("label_kp", f"Kp = {ratio_px_mm:.4f} px/mm")
        dpg.set_value("statut", f"Calibration OK — etalon = {int(longueur_px)} px  Kp = {ratio_px_mm:.4f} px/mm")
        update_display()

def reset_calibration():
    global ratio_px_mm, segment_etalon_idx, calibration_mode
    ratio_px_mm = None
    segment_etalon_idx = None
    calibration_mode = False
    dpg.set_value("label_kp", "Kp = non calibre")
    dpg.set_value("statut", "Calibration reinitialisee")
    update_display()

# ─────────────────────────────────────────
# region POP-UP
# ─────────────────────────────────────────
# Callback bouton principal
def ouvrir_popup(Dist):
    global diametre
    diametre = Dist
    dpg.show_item("fenetre_saisie")

# Callback validation
def valider(sender, app_data):
    global nom_element
    nom_element = dpg.get_value("input_texte")
    print("Utilisateur a écrit :", nom_element)
    dpg.set_value("input_texte", "")
    dpg.hide_item("fenetre_saisie")  # fermer la popup
    if ratio_px_mm:
        dpg.set_value("statut", f"{nom_element} ajoute ; D = {(diametre*2)/ratio_px_mm:.2f} mm")
    else:
        dpg.set_value("statut", f"{nom_element} ajoute ; D = {diametre*2:.1f} px")
    if obj=="cercle" :
        print(f"D = {diametre}")
        cercles.append((temp_cx, temp_cy, diametre, nom_element))
    elif obj=="segment" :
        segments.append((temp_x1, temp_y1, temp_x2, temp_y2, nom_element))
    update_display()

# ─────────────────────────────────────────
# region GESTION SOURIS
# ─────────────────────────────────────────
def on_mouse_wheel(sender, app_data):
    global zoom_level, view_x, view_y, tex_src_x, tex_src_y
    if not dpg.is_item_hovered("drawlist_principal"):
        return
    if img_originale is None:
        return

    mx, my = dpg.get_drawing_mouse_pos()
    # print(f"AVANT  zoom={zoom_level:.3f} view=({view_x:.1f},{view_y:.1f}) tex_src=({tex_src_x:.1f},{tex_src_y:.1f}) mouse=({mx:.0f},{my:.0f})")

    img_x_under = tex_src_x + mx / zoom_level
    img_y_under = tex_src_y + my / zoom_level

    if app_data > 0:
        zoom_level = min(zoom_level * (1 + ZOOM_STEP), ZOOM_MAX)
    else:
        zoom_level = max(zoom_level / (1 + ZOOM_STEP), ZOOM_MIN)

    view_x = img_x_under - mx / zoom_level
    view_y = img_y_under - my / zoom_level

    clamp_view()
    tex_src_x = view_x
    tex_src_y = view_y

    rebuild_texture_zoom()
    update_display()

    # print(f"APRES  zoom={zoom_level:.3f} view=({view_x:.1f},{view_y:.1f}) tex_src=({tex_src_x:.1f},{tex_src_y:.1f})")

def on_mouse_click(sender, app_data):
    global point1_temp, cercles, segments, view_x, view_y, temp_cx, temp_cy, temp_x1, temp_y1, temp_x2, temp_y2, obj

    if not dpg.is_item_hovered("drawlist_principal"):
        return

    mx, my = dpg.get_drawing_mouse_pos()

    if app_data == 0:
        # Clic sur minimap
        if img_originale is not None:
            mini_h = int(MINI_W * img_originale.shape[0] / img_originale.shape[1])
            if MINI_X <= mx <= MINI_X + MINI_W and MINI_Y <= my <= MINI_Y + mini_h:
                rel_x = (mx - MINI_X) / MINI_W
                rel_y = (my - MINI_Y) / mini_h
                img_cx = rel_x * img_originale.shape[1]
                img_cy = rel_y * img_originale.shape[0]
                view_x = img_cx - (W / zoom_level) / 2
                view_y = img_cy - (H / zoom_level) / 2
                clamp_view()
                rebuild_texture_zoom()
                update_display()
                return

        # Conversion coordonnées écran → image
        ix, iy = screen_to_image(mx, my)
        
        # Mode dessin segment
        if mode_dessin_segment and 0 <= mx <= W and 0 <= my <= H:
            if point1_temp is None:
                point1_temp = (ix, iy)
                update_display()
                dpg.set_value("statut", f"Point 1 ({ix:.1f}, {iy:.1f}) — Clic 2 : point oppose")
            else:
                x1, y1 = point1_temp
                x2, y2 = ix, iy
                temp_x1 = x1
                temp_x2 = ix
                temp_y1 = y1
                temp_y2 = y2
                
                longueur = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                
                obj = "segment"
                ouvrir_popup(longueur)
                point1_temp = None
        
        # Mode dessin cercle
        elif mode_dessin_cercle and 0 <= mx <= W and 0 <= my <= H:
            if point1_temp is None:
                point1_temp = (ix, iy)
                update_display()
                dpg.set_value("statut", f"Point 1 ({ix:.1f}, {iy:.1f}) — Clic 2 : bord oppose")
            else:
                x1, y1 = point1_temp
                cx = (x1 + ix) / 2
                cy = (y1 + iy) / 2
                temp_cx = cx
                temp_cy = cy
                radius = math.sqrt((ix - x1)**2 + (iy - y1)**2) / 2
                # if ratio_px_mm:
                #     dpg.set_value("statut", f"Cercle {nom_element} ajoute — Diam = {(radius*2)/ratio_px_mm:.2f} mm")
                # else:
                #     dpg.set_value("statut", f"Cercle {nom_element} ajoute — Diam = {radius*2:.1f} px")
                obj = "cercle"
                ouvrir_popup(radius)
                point1_temp = None

def on_mouse_down(sender, app_data):
    global pan_actif, pan_last_x, pan_last_y
    if app_data == 1 and dpg.is_item_hovered("drawlist_principal"):
        pan_actif = True
        mx, my = dpg.get_mouse_pos()
        pan_last_x = mx
        pan_last_y = my

def on_mouse_release(sender, app_data):
    global pan_actif
    if app_data == 1:
        pan_actif = False

def on_mouse_move(sender, app_data):
    global pan_last_x, pan_last_y, view_x, view_y

    if pan_actif and img_originale is not None:
        mx, my = dpg.get_mouse_pos()
        dx = mx - pan_last_x
        dy = my - pan_last_y
        view_x -= dx / zoom_level
        view_y -= dy / zoom_level
        pan_last_x = mx
        pan_last_y = my
        clamp_view()
        rebuild_texture_zoom()
        update_display()
        return

    # Aperçu pendant le dessin
    if (not mode_dessin_cercle and not mode_dessin_segment) or point1_temp is None:
        return
    if not dpg.is_item_hovered("drawlist_principal"):
        return

    mx, my = dpg.get_drawing_mouse_pos()
    if not (0 <= mx <= W and 0 <= my <= H):
        return

    ix, iy = screen_to_image(mx, my)
    x1, y1 = point1_temp
    
    if mode_dessin_segment:
        update_display()
        sx1, sy1 = image_to_screen(x1, y1)
        sx2, sy2 = image_to_screen(ix, iy)
        dpg.draw_line((sx1, sy1), (sx2, sy2), color=(0, 200, 255, 180), thickness=2, parent="drawlist_principal")
        
        longueur = math.sqrt((ix - x1)**2 + ((iy if not calibration_mode else y1) - y1)**2)
        if ratio_px_mm:
            dpg.set_value("statut", f"Longueur temporaire = {longueur/ratio_px_mm:.2f} mm")
        else:
            dpg.set_value("statut", f"Longueur temporaire = {longueur:.1f} px")
    
    elif mode_dessin_cercle:
        update_display()
        sx1, sy1 = image_to_screen(x1, y1)
        sx2, sy2 = image_to_screen(ix, iy)
        cx = (sx1 + sx2) / 2
        cy = (sy1 + sy2) / 2
        radius = math.sqrt((sx2 - sx1)**2 + (sy2 - sy1)**2) / 2
        
        dpg.draw_line((sx1, sy1), (sx2, sy2), color=(0, 200, 255, 180), thickness=1, parent="drawlist_principal")
        dpg.draw_circle((cx, cy), radius, color=(0, 200, 255, 200), fill=(0, 200, 255, 30), thickness=2, parent="drawlist_principal")
        dpg.draw_circle((cx, cy), 4, color=(255, 255, 255, 255), fill=(255, 255, 255, 200), parent="drawlist_principal")
        dpg.draw_circle((sx2, sy2), 6, color=(0, 200, 255, 255), fill=(0, 200, 255, 180), parent="drawlist_principal")
        
        r = math.sqrt((ix - x1)**2 + (iy - y1)**2) / 2
        if ratio_px_mm:
            dpg.set_value("statut", f"Diametre temporaire = {(r*2)/ratio_px_mm:.2f} mm")
        else:
            dpg.set_value("statut", f"Diametre temporaire = {r*2:.1f} px")

def reset_zoom():
    global zoom_level, view_x, view_y, tex_src_x, tex_src_y
    zoom_level = 1.0
    view_x = 0.0
    view_y = 0.0
    tex_src_x = 0
    tex_src_y = 0
    if img_originale is not None:
        rebuild_texture_zoom()
    update_display()
    dpg.set_value("statut", "Zoom reinitialise")

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
    if not calibration_mode:
        ratio_px_mm = None
        segment_etalon_idx = None
        dpg.set_value("label_kp", "Kp = non calibre")
    update_display()
    dpg.set_value("statut", "Segments effaces")

def supprimer_dernier_cercle():
    global cercles, cercle_etalon_idx, ratio_px_mm
    if cercles:
        idx = len(cercles) - 1
        cercles.pop()
        if cercle_etalon_idx == idx:
            cercle_etalon_idx = None
            ratio_px_mm = None
            dpg.set_value("label_kp", "Kp = non calibre")
            dpg.set_value("statut", "Cercle etalon supprime : recalibrez")
        else:
            dpg.set_value("statut", "Dernier cercle supprime")
        update_display()

def supprimer_dernier_segment():
    global segments, segment_etalon_idx, ratio_px_mm
    if segments:
        idx = len(segments) - 1
        (x1, y1, x2, y2, n_elmt) = segments[idx]
        segments.pop()
        if segment_etalon_idx == n_elmt:
            segment_etalon_idx = None
            if not calibration_mode:
                ratio_px_mm = None
                dpg.set_value("label_kp", "Kp = non calibre")
            dpg.set_value("statut", "Segment etalon supprime : recalibrez")
        else:
            dpg.set_value("statut", "Dernier segment supprime")
        update_display()

# ─────────────────────────────────────────
# region INTERFACE
# ─────────────────────────────────────────
dpg.create_context()
# init_database()

with dpg.texture_registry():
    pass

with dpg.file_dialog(tag="dialogue_fichier", callback=callback_fichier,
                     show=False, width=600, height=400):
    dpg.add_file_extension(".jpg")
    dpg.add_file_extension(".png")
    dpg.add_file_extension(".bmp")
    dpg.add_file_extension(".jpeg")

with dpg.handler_registry():
    dpg.add_mouse_wheel_handler(callback=on_mouse_wheel)
    dpg.add_mouse_click_handler(callback=on_mouse_click)
    dpg.add_mouse_down_handler(callback=on_mouse_down)
    dpg.add_mouse_release_handler(callback=on_mouse_release)
    dpg.add_mouse_move_handler(callback=on_mouse_move)

with dpg.theme() as theme_principal:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (45, 45, 45))
        dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (55, 55, 55))
        dpg.add_theme_color(dpg.mvThemeCol_Text, (240, 240, 240))
        dpg.add_theme_color(dpg.mvThemeCol_Button, (75, 75, 75))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (100, 100, 100))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (130, 130, 130))
        dpg.add_theme_color(dpg.mvThemeCol_TableRowBg, (55, 55, 55))
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6)
        dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)

with dpg.window(tag="fenetre_principale", width=1920, height=1080):
    dpg.add_text("CAMVIS — Analyse Dimensionnelle par Vision", color=(255, 255, 255))
    dpg.add_text("WHE — Equipe Instrumentation & Vision  |  CdCF-CAMVIS-001 Rev.A",
                 color=(180, 180, 180))
    dpg.add_separator()
    dpg.add_spacer(height=4)

    with dpg.group(horizontal=True):

        with dpg.child_window(width=260, height=1000):
            dpg.add_text("Image", color=(200, 200, 200))
            dpg.add_button(label="Charger une image", callback=charger_image, width=235)
            dpg.add_spacer(height=4)

            dpg.add_separator()
            dpg.add_text("Navigation", color=(200, 200, 200))
            dpg.add_button(label="Reinitialiser zoom (1:1)", callback=reset_zoom, width=235)
            dpg.add_spacer(height=4)

            dpg.add_separator()
            dpg.add_text("Dessin", color=(200, 200, 200))
            dpg.add_button(label="Dessiner un cercle",
                           tag="btn_draw", callback=toggle_draw_mode_cercle, width=235)
            dpg.add_button(label="Supprimer dernier cercle",
                           callback=supprimer_dernier_cercle, width=235)
            dpg.add_button(label="Effacer tous les cercles",
                           callback=clear_cercles, width=235)
            dpg.add_spacer(height=8)
            dpg.add_button(label="Dessiner un segment",
                           tag="btn_draw_sgt", callback=toggle_draw_mode_segment, width=235)
            dpg.add_button(label="Supprimer dernier segment",
                           callback=supprimer_dernier_segment, width=235)
            dpg.add_button(label="Effacer tous les segments",
                           callback=clear_segments, width=235)
            dpg.add_spacer(height=8)

            dpg.add_separator()
            dpg.add_text("Calibration", color=(255, 165, 0))
            dpg.add_text(f"Etalon de {DIAMETRE_ETALON_MM:.0f} mm", color=(200, 200, 200))
            dpg.add_spacer(height=4)
            dpg.add_button(label="Calibration", tag="btn_calib",
                           callback=definir_etalon, width=235)
            dpg.add_button(label="Reinitialiser calibration",
                           callback=reset_calibration, width=235)
            dpg.add_spacer(height=4)
            dpg.add_text("Kp = non calibre", tag="label_kp", color=(255, 165, 0))
            # dpg.add_input_text(tag="id_camera", label="ID Camera",
            #                    default_value=ID_CAMERA_PAR_DEFAUT, width=230)
            
            dpg.add_combo(items=[ID_CAMERA_PAR_DEFAUT, "Option 2",],label="Choisir une camera",callback=calibrate,tag="camera")

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
                dpg.add_table_column(label="#", width_fixed=True, init_width_or_weight=30)
                dpg.add_table_column(label="Diam/Long", width_fixed=True, init_width_or_weight=90)
                dpg.add_table_column(label="Type", width_fixed=True, init_width_or_weight=60)

            dpg.add_separator()
            dpg.add_text("Export", color=(200, 200, 200))
            dpg.add_button(label="Exporter CSV", callback=exporter_csv, width=235)
            dpg.add_button(label="Exporter JSON", callback=exporter_json, width=235)
            dpg.add_button(label="Exporter PDF", callback=exporter_pdf, width=235)
            dpg.add_button(label="Exporter IMAGE", callback=exporter_image, width=235)
            dpg.add_button(label="Ouvrir dossier", callback=ouvrir_dossier, width=235)
            dpg.add_button(label="Exporter complet", callback=exporter_rapport_complet, width=235)

        with dpg.child_window(width=1640, height=1000):
            with dpg.drawlist(width=W, height=H, tag="drawlist_principal"):
                dpg.draw_rectangle((0, 0), (W, H), fill=(40, 40, 40))
                dpg.draw_text((W//2 - 180, H//2),
                              "Chargez une image pour commencer",
                              color=(130, 130, 130), size=18)


# popup cachée au départ pour écrire le nom des éléments créés
with dpg.window(label="Saisie utilisateur", modal=True, show=False, tag="fenetre_saisie"):
    dpg.add_text("Écris le nom de l'élément :")
    dpg.add_input_text(tag="input_texte")
    dpg.add_button(label="Valider", callback=valider)

dpg.bind_theme(theme_principal)
dpg.create_viewport(title="CAMVIS — WHE Instrumentation", width=1920, height=1080)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("fenetre_principale", True)
dpg.start_dearpygui()
dpg.destroy_context()
