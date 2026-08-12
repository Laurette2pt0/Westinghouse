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
import re
import io

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# ─────────────────────────────────────────
# region VARIABLES GLOBALES
# ─────────────────────────────────────────
version = "1.0.0.0" #version du logiciel

chemin_image_actuelle = None  # Chemin de l'image actuellement chargée
texture_tag = None  # Tag de la texture affichée dans la vue principale
texture_minimap = None  # Tag de la texture pour la mini-carte
cercles = []  # Liste des cercles dessinés : (cx, cy, rayon, nom)
segments = []  # Liste des segments dessinés : (x1, y1, x2, y2, nom)
mode_dessin_cercle = False  # Indique si le mode dessin cercle est actif
mode_dessin_segment = False  # Indique si le mode dessin segment est actif
point1_temp = None  # Point temporaire pour le dessin (premier clic)
nom_element = ""  # Nom temporaire de l'élément en cours de creation
ptit_cercle = 0  # Numéro des petits cercles créés rapidement (Z0, Z1, ...)
ptit_sgmt = 0  # Numéro des segments créés rapidement (S0, S1, ...)
premier_segment = None  # Stocke le premier segment pour la perpendiculaire
image_canaux = "lib/canaux.png"  # Chemin de l'image de référence des canaux
survol_canaux = False  # Indique si la souris survole l'image des canaux
xc, yc, xcf, ycf = 0, 0, 0, 0  # Coordonnées de l'image des canaux
texture_canaux_petit = None  # Tag de l'image des canaux en bas à droite
texture_canaux_grand = None  # Tag de l'image des canaux agrandie
cx, cy, w_g, h_g = 0, 0, 0, 0  # Coordonnées de l'image des canaux agrandie

sx_perp1, sy_perp1, sx_perp2, sy_perp2 = 0, 0, 0, 0

DIAMETRE_ETALON_MM = 60.0  # diametre de l'étalon en mm
ratio_px_mm = None  # ratio entre l'étalon identifier par l'utilisateur et le DIAMETRE_ETALON_MM
cercle_etalon_idx = None  # indice du cercle étalon
segment_etalon_idx = None  # indice du segment étalon
calibration_mode = False  # Indique si la calibration a été effectuée

# POUR LES REFERENCES 
reference_idx = None  # Index de l'élément de référence (cercle ou segment)
reference_type = None  # "cercle" ou "segment"
reference_value = None  # Valeur de référence (diamètre pour cercle, longueur pour segment)
reference_nom = None    # Nom de l'élément de référence

# region Informations du rapport 
fichier_donnee = "donnees.json"
info_affaire = ""  # Nom de l'affaire
info_palier = ""  # Nom du palier
info_central = ""  # Nom de la centrale
info_tranche = ""  # Numéro de tranche
info_visite = ""  # Numéro de visite

# Variables pour les canaux les plus abîmés (saisie manuelle par l'utilisateur)
canal_plus_use_BD_nom = ""      # Nom du canal B/D le plus usé
canal_plus_use_BD_cas = ""      # Cas du canal B/D le plus usé
canal_plus_use_BD_rapport = ""  # Rapport du canal B/D le plus usé
canal_plus_use_CF_nom = ""      # Nom du canal C/F le plus usé
canal_plus_use_CF_cas = ""      # Cas du canal C/F le plus usé
canal_plus_use_CF_rapport = ""  # Rapport du canal C/F le plus usé

# Vérifie si le fichier existe
if not os.path.exists(fichier_donnee):
    donnees_pv = {
        "info_affaire": info_affaire,
        "info_palier": info_palier,
        "info_central": info_central,
        "info_tranche": info_tranche,
        "info_visite": info_visite
    }
    with open(fichier_donnee, "w", encoding="utf-8") as f:
        json.dump(donnees_pv, f, indent=4)

# Chargement
try:
    with open(fichier_donnee, "r", encoding="utf-8") as fichier:
        donnees = json.load(fichier)
    info_affaire = donnees["info_affaire"]
    info_palier = donnees["info_palier"]
    info_central = donnees["info_central"]
    info_tranche = donnees["info_tranche"]
    info_visite = donnees["info_visite"]
except FileNotFoundError:
    info_affaire = ""
    info_palier = ""
    info_central = ""
    info_tranche = ""
    info_visite = ""

# Informations spécifiques pour l'export PDF
pdf_chrono = ""  # Numéro de chrono
pdf_revision = ""  # Révision du document
pdf_ref_gdg = ""  # Référence GDG
pdf_carte = ""  # Numéro de carte

W = 1630  # Largeur de la zone de dessin
H = 970  # Hauteur de la zone de dessin

# pour la pop up 
diametre = 0  # Diamètre temporaire pour la popup
temp_cx = 0  # Centre X temporaire
temp_cy = 0  # Centre Y temporaire
temp_x1 = 0  # Point 1 X temporaire
temp_y1 = 0  # Point 1 Y temporaire
temp_x2 = 0  # Point 2 X temporaire
temp_y2 = 0  # Point 2 Y temporaire
obj = ""  # Type d'objet en cours ("cercle" ou "segment")

# Initialisation matrices
distorsion = False  # Indique si les matrices de distorsion ont bien été initialisé
ID_CAMERA = ""  # Identifiant de la caméra
K = np.zeros((3, 3))  # Matrice intrinsèque de la caméra
D = np.zeros((4, 1))  # Coefficients de distorsion fisheye
h, w = 0, 0  # Dimensions du pattern de calibration

bureau = os.path.expanduser(r"~/Desktop") #~\OneDrive - Westinghouse Electric Company LLC\Bureau" -si sur pc westinghouse -- ~/Desktop -si pc classique
dossier_export = os.path.join(bureau, "CAMVIS_Export")
os.makedirs(dossier_export, exist_ok=True)
nom_dossier = ""  # Nom du sous-dossier pour l'export
nom_fichier = ""  # Nom du fichier PDF

# ─────────────────────────────────────────
# region ZOOM & PAN
# ─────────────────────────────────────────
zoom_level = 1.0
ZOOM_MIN = 0.81
ZOOM_MAX = 10.0
ZOOM_STEP = 0.15

view_x = 0.0
view_y = 0.0
tex_src_x = 0
tex_src_y = 0

pan_actif = False
pan_last_x = 0.0
pan_last_y = 0.0

MINI_W = 260
MINI_H = 0
MINI_X = W - MINI_W - 10
MINI_Y = 10

img_originale = None
img_originale_corrigee = None
name_img = ""
name_img_corrigee = ""
COEFF_REDUCTION = 9.675 / 10.67  # = 0.9067

# ─────────────────────────────────────────
# region HELPERS ZOOM
# ─────────────────────────────────────────
"""Convertir les coordonnes ecran en coordonnees image"""
def screen_to_image(sx, sy):
    return tex_src_x + sx / zoom_level, tex_src_y + sy / zoom_level

"""Convertir les coordonnees image en coordonnees ecran"""
def image_to_screen(ix, iy):
    return (ix - tex_src_x) * zoom_level, (iy - tex_src_y) * zoom_level

"""Limiter la position de la vue pour ne pas dépasser les bords de l'image corrigée"""
def clamp_view():
    global view_x, view_y
    if img_originale_corrigee is None:
        return
    orig_h, orig_w = img_originale_corrigee.shape[:2]
    visible_w = W / zoom_level
    visible_h = H / zoom_level
    if orig_w * zoom_level <= W:
        view_x = -(W / zoom_level - orig_w) / 2
    else:
        view_x = max(0.0, min(view_x, orig_w - visible_w))
    if orig_h * zoom_level <= H:
        view_y = -(H / zoom_level - orig_h) / 2
    else:
        view_y = max(0.0, min(view_y, orig_h - visible_h))

"""Reconstruire la texture affichée en fonction du zoom et de la position de la vue"""
def rebuild_texture_zoom():
    global texture_tag, tex_src_x, tex_src_y
    if img_originale_corrigee is None:
        return
    orig_h, orig_w = img_originale_corrigee.shape[:2]
    src_w = int(W / zoom_level) + 2
    src_h = int(H / zoom_level) + 2
    src_x = int(max(0, view_x))
    src_y = int(max(0, view_y))
    src_w = max(1, min(src_w, orig_w - src_x))
    src_h = max(1, min(src_h, orig_h - src_y))
    tex_src_x = view_x
    tex_src_y = view_y
    crop = img_originale_corrigee[src_y:src_y + src_h, src_x:src_x + src_w]
    canvas = np.zeros((H, W, 4), dtype=np.uint8)
    canvas_x = int(-view_x * zoom_level) if view_x < 0 else 0
    canvas_y = int(-view_y * zoom_level) if view_y < 0 else 0
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
# region EXPORT IMAGE, CSV, PDF
# ─────────────────────────────────────────
"""Génère l'image analysée (avec cercles et segments dessinés) et la retourne en BGR"""
def creer_image_analysee():
    if img_originale_corrigee is None:
        return None
    img_export = cv2.cvtColor(img_originale_corrigee.copy(), cv2.COLOR_RGBA2BGR)
    couleur = []
    for i, (cx_img, cy_img, r_img, n_elmt) in enumerate(cercles):
        clr, couleur_fill, label = color(r_img, n_elmt, i, "cercle")
        for j in range(0, 3):
            couleur.append(clr[2 - j])
        centre = (int(cx_img), int(cy_img))
        rayon = int(r_img)
        cv2.circle(img_export, centre, rayon, couleur, 1)  # Trait fin
        cv2.line(img_export, (int(cx_img - r_img), int(cy_img)), (int(cx_img + r_img), int(cy_img)), couleur, 1)
        # cv2.circle(img_export, centre, 4, (255, 255, 255), -1)
        couleur = []

    for i, (x1, y1, x2, y2, n_elmt) in enumerate(segments):
        r = math.sqrt((x2 - x1)**2 + (y2 - y1)**2) / 2
        # clr, couleur_fill, label = color(r, n_elmt, i, "segment")
        # for j in range(0, 3):
        #     couleur.append(clr[2 - j])
        cv2.line(img_export, (int(x1), int(y1)), (int(x2), int(y2)), [0,0,250], 1)  # Trait fin
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        # cv2.circle(img_export, (int(cx), int(cy)), 4, couleur, -1)
        # couleur = []

    info_y = img_export.shape[0] - 20
    if reference_value is not None:
        info = f"CAMVIS - Reference Canal {reference_nom}"
    else:
        info = "CAMVIS"
    return img_export

"""Export de l'image corrigée, ainsi que l'image originale et corrigée sans les mesures"""
def exporter_image():
    if img_originale_corrigee is None:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "ERREUR: Aucune image chargee")
        return
    if not cercles and not segments:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "ERREUR: Aucun cercle ou segment a exporter")
        return

    try:
        nom = f"{nom_dossier}/{name_img}_analysee.png"
        img_export = creer_image_analysee()
        cv2.imwrite(nom, img_export)

        full_path = f"{nom_dossier}/{name_img_corrigee}.png"
        cv2.imwrite(full_path, img_originale_corrigee)

        full_path = f"{nom_dossier}/{name_img}.png"
        cv2.imwrite(full_path, img_originale)

    except Exception as e:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", f"ERREUR image: {str(e)}")

"""Ouvrir le dossier d'export dans l'explorateur de fichiers"""
def ouvrir_dossier():
    import subprocess
    subprocess.Popen(f'explorer "{dossier_export}"')
    dpg.configure_item("statut", color=(0, 255, 0))
    dpg.set_value("statut", f"Dossier ouvert: {dossier_export}")

"""Exporter les mesures au format CSV avec les informations de référence et de classification"""
def exporter_csv():
    if not cercles and not segments:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Aucune mesure a exporter")
        return
    try:
        nom = f"{nom_dossier}/mesures_CAMVIS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(nom, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(["CAMVIS - Export des mesures"])
            w.writerow([f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"])
            if reference_value is not None:
                w.writerow([f"Reference : {reference_nom}"])
            w.writerow([])
            w.writerow(["=== CERCLES ==="])
            w.writerow(["Nom", "Cas", "Type"])
            for i, (cx, cy, r, n_elmt) in enumerate(cercles):
                d_px = r*2
                rapport_str, type_str = choose_cas(n_elmt, d_px, "cercle", i)
                w.writerow([n_elmt, rapport_str, type_str])
            w.writerow([])
            w.writerow(["=== SEGMENTS ==="])
            w.writerow(["Nom", "Cas", "Type"])
            for i, (x1, y1, x2, y2, n_elmt) in enumerate(segments):
                longueur = math.sqrt((x2-x1)**2 + (y2-y1)**2)
                rapport_str, type_str = choose_cas(n_elmt, longueur, "segment", i)
                w.writerow([n_elmt, rapport_str, type_str])
    except Exception as e:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", f"Erreur CSV: {str(e)}")

"""création de l'ntete et pied de page du pdf"""
def ajouter_entete_pdp(canvas, doc):
    canvas.saveState()
    chemin_logo = "lib/logo_entreprise.png"
    page_num = canvas.getPageNumber()
    canvas.setFont("Helvetica", 10)
    #entête
    if os.path.exists(chemin_logo):
        canvas.drawImage(
            chemin_logo,
            40,      # x
            760,     # y
            width=120,
            height=80,
            mask='auto'
        )
    if page_num != 1 :
        canvas.drawString(355, 795, "Rapport d'examen canaux complémentaires")    
    # Pied de page
    canvas.drawString(50, 35, "22821-PVG-015-A")
    canvas.drawString(50, 25, "FORAQ-4036-A")

    # Numéro de page
    canvas.drawRightString(550, 30,f"Page {page_num}")
    canvas.restoreState()

"""Exporter les mesures et les informations dans un rapport PDF formaté avec classification et référence"""
def exporter_pdf():
    if not cercles and not segments:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Aucune mesure a exporter")
        return False
    if not REPORTLAB_AVAILABLE:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "PDF: Reportlab non installe")
        return False
    try:
        from reportlab.platypus import Image, PageBreak
        from reportlab.lib.utils import ImageReader

        nom = f"{nom_dossier}/{nom_fichier}.pdf"
        doc = SimpleDocTemplate(nom, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("Mesures d'usures des guides de grappes", styles['Title']))
        story.append(Paragraph("C@MVIS - Rapport d'examen canaux complémentaires", styles['Title']))
        story.append(Spacer(1, 12))
        
        # Informations generales
        story.append(Paragraph("Informations generales:", styles['Heading2']))
        story.append(Spacer(1, 6))

        tableau_donnees = []
        tableau_donnees.append(["Camera ID:", ID_CAMERA])
        tableau_donnees.append(["Image:", os.path.basename(chemin_image_actuelle) if chemin_image_actuelle else 'N/A'])
        tableau_donnees.append(["Affaire:", info_affaire if info_affaire else "-"])
        tableau_donnees.append(["Centrale:", info_central if info_central else "-"])
        tableau_donnees.append(["Chrono:", pdf_chrono if pdf_chrono else "-"])
        tableau_donnees.append(["Revision:", pdf_revision if pdf_revision else "-"])
        tableau_donnees.append(["Reference GDG:", pdf_ref_gdg if pdf_ref_gdg else "-"])
        tableau_donnees.append(["Carte:", pdf_carte if pdf_carte else "-"])
        if reference_nom is not None:
            tableau_donnees.append(["Canal A (Reference):", reference_nom])
        else:
            tableau_donnees.append(["Canal A (Reference):", "Non defini"])

        t = Table(tableau_donnees, colWidths=[120, 350])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

        # ==========================================================
        # TABLEAUX CANAUX USÉS B/D et C/F - avec saisie manuelle
        # ==========================================================

        # Tableau pour les canaux B/D
        story.append(Paragraph("Canaux B/D - Canal le plus usé:", styles['Heading2']))
        story.append(Spacer(1, 6))

        if canal_plus_use_BD_nom and canal_plus_use_BD_cas:
            data = [
                ["Nom du canal", "Classification"],
                [canal_plus_use_BD_nom, canal_plus_use_BD_cas]
            ]
            t = Table(data, colWidths=[120, 120])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6)
            ]))
            story.append(t)
        else:
            story.append(Paragraph("Aucun canal B/D usé renseigné", styles['Normal']))

        story.append(Spacer(1, 12))
        

        # Tableau pour les canaux C/F
        story.append(Paragraph("Canaux C/F - Canal le plus usé:", styles['Heading2']))
        story.append(Spacer(1, 6))

        if canal_plus_use_CF_nom and canal_plus_use_CF_cas:
            data = [
                ["Nom du canal", "Classification"],
                [canal_plus_use_CF_nom, canal_plus_use_CF_cas]
            ]
            t = Table(data, colWidths=[120, 120])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6)
            ]))
            story.append(t)
        else:
            story.append(Paragraph("Aucun canal C/F usé renseigné", styles['Normal']))

        story.append(Spacer(1, 12))

        # ==========================================================
        # RAPPEL DES CAS POUR CANAUX B/D (4 cas)
        # ==========================================================
        story.append(Paragraph("Rappel des cas - Canaux B/D :", styles['Heading2']))
        story.append(Spacer(1, 6))

        rappel_BD_data = [
            ["Cas", "Critere"],
            ["Cas 0", "L <= 1.5D"],
            ["Cas 1", "1.5D < L <= 2D"],
            ["Cas 2", "2D < L <= 2.5D"],
            ["Cas 3", "L > 2.5D"],
        ]

        rappel_BD_table = Table(rappel_BD_data, colWidths=[80, 180])
        rappel_BD_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
           
        ]))
        story.append(rappel_BD_table)
        story.append(Spacer(1, 14))
        story.append(PageBreak())

        # ==========================================================
        # RAPPEL DES CAS POUR CANAUX C/F (2 cas)
        # ==========================================================
        story.append(Paragraph("Rappel des cas - Canaux C/F :", styles['Heading2']))
        story.append(Spacer(1, 6))

        rappel_CF_data = [
            ["Cas", "Critere"],
            ["Cas 0", "L <= 1.5D"],
            ["Cas 1", "L > 1.5D"],
        ]

        rappel_CF_table = Table(rappel_CF_data, colWidths=[80, 180])
        rappel_CF_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            
        ]))
        story.append(rappel_CF_table)
        story.append(Spacer(1, 14))

        # ==========================================================
        # IMAGE CORRIGEE
        # ==========================================================
        story.append(Paragraph("Image corrigee:", styles['Heading2']))
        story.append(Spacer(1, 6))
        if img_originale_corrigee is not None:
            try:
                img_bgr = cv2.cvtColor(img_originale_corrigee.copy(), cv2.COLOR_RGBA2BGR)
                h_i, w_img = img_bgr.shape[:2]
                max_width_px = 1400
                if w_img > max_width_px:
                    new_h = int(h_i * max_width_px / w_img)
                    img_bgr = cv2.resize(img_bgr, (max_width_px, new_h), interpolation=cv2.INTER_AREA)
                success, buffer = cv2.imencode('.png', img_bgr, [cv2.IMWRITE_PNG_COMPRESSION, 3])
                if success:
                    img_buffer = io.BytesIO(buffer.tobytes())
                    display_width_pt = 450
                    display_height_pt = display_width_pt * img_bgr.shape[0] / img_bgr.shape[1]
                    img_pdf = Image(img_buffer, width=display_width_pt, height=display_height_pt)
                    story.append(img_pdf)
                    story.append(Spacer(1, 12))
            except Exception as e:
                print(f"ERREUR image corrigee PDF: {e}")
        else :
            story.append(Paragraph("Aucune image corrigée renseignée", styles['Normal']))

        # ==========================================================
        # IMAGE ANALYSEE
        # ==========================================================
        story.append(Paragraph("Image analysee:", styles['Heading2']))
        story.append(Spacer(1, 6))
        img_analysee = creer_image_analysee()
        if img_analysee is not None:
            try:
                h_a, w_a = img_analysee.shape[:2]
                max_width_px = 1400
                if w_a > max_width_px:
                    new_h = int(h_a * max_width_px / w_a)
                    img_analysee = cv2.resize(img_analysee, (max_width_px, new_h), interpolation=cv2.INTER_AREA)
                success, buffer = cv2.imencode('.png', img_analysee, [cv2.IMWRITE_PNG_COMPRESSION, 3])
                if success:
                    img_buffer2 = io.BytesIO(buffer.tobytes())
                    display_width_pt = 450
                    display_height_pt = display_width_pt * img_analysee.shape[0] / img_analysee.shape[1]
                    img_pdf2 = Image(img_buffer2, width=display_width_pt, height=display_height_pt)
                    
                    story.append(img_pdf2)
                    story.append(Spacer(1, 12))
            except Exception as e:
                print(f"ERREUR image analysee PDF: {e}")
        else:
            story.append(Paragraph("Aucune image analysée renseignée", styles['Normal']))

        # ==========================================================
        # TABLEAU SIGNATURES
        # ==========================================================
        story.append(Paragraph("Validation du rapport:", styles['Heading2']))
        story.append(Spacer(1, 6))
        signature_data = [
            ["", "Signature"],
            ["Analyste :", ""],
            ["Controle technique :", ""],
        ]
        signature_table = Table(signature_data, colWidths=[150, 300], rowHeights=[20, 40, 40])
        signature_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(signature_table)
        story.append(Spacer(1, 12))
        story.append(PageBreak())

        doc.build(story, onFirstPage=ajouter_entete_pdp, onLaterPages=ajouter_entete_pdp)
        return True
    except Exception as e:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", f"Erreur PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
"""Export complet : PDF + CSV + Images"""
def exporter_rapport_complet():
    pdf_ok = exporter_pdf()
    exporter_csv()
    exporter_image()
    if pdf_ok:
        dpg.configure_item("statut", color=(0, 255, 0))
        dpg.set_value("statut", "Export complet termine (CSV, PDF, Images)")
    else:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "PDF ECHEC - CSV et Images exportes")

# ─────────────────────────────────────────
# region AFFICHAGE
# ─────────────────────────────────────────
"""Récupération du diamètre des cercles"""
def format_diametre(r):
    if reference_value is not None and reference_type == "cercle":
        rapport = (r * 2) / reference_value
        return f"x{rapport:.2f}"
    elif ratio_px_mm:
        return f"{(r * 2) / ratio_px_mm:.2f} mm"
    return f"{int(r * 2)} px"

"""Récupération de la longueur des segments"""
def format_longueur(longueur):
    if reference_value is not None and reference_type == "segment":
        rapport = longueur / reference_value
        return f"x{rapport:.2f}"
    elif ratio_px_mm:
        return f"{longueur / ratio_px_mm:.2f} mm"
    return f"{int(longueur)} px"

"""Charge les images des canaux (petite et grande) en mémoire"""
def charger_canaux():
    global texture_canaux_petit, texture_canaux_grand, xc, yc, xcf, ycf, cx, cy, w_g, h_g
    
    img = cv2.imread(image_canaux)
    if img is None:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Erreur : impossible de charger l'image des canaux")
        return
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)

    # Petite image
    cote = MINI_W + 4
    img_ptite = cv2.resize(img, (cote, cote), interpolation=cv2.INTER_AREA)
    hauteur, largeur = img_ptite.shape[:2]
    image = img_ptite.flatten().astype(np.float32) / 255.0
    x, y = W - largeur, H - hauteur
    xc, yc, xcf, ycf = x, y, x + largeur, y + hauteur
    with dpg.texture_registry():
        texture_canaux_petit = dpg.add_static_texture(img_ptite.shape[1], img_ptite.shape[0], image)

    # Grande image
    grande_taille = 970
    img_grande = cv2.resize(img, (grande_taille, grande_taille), interpolation=cv2.INTER_LINEAR)
    h_g, w_g = img_grande.shape[:2]
    img_data = img_grande.flatten().astype(np.float32) / 255.0
    cx = W // 2 - w_g // 2
    cy = H // 2 - h_g // 2
    with dpg.texture_registry():
        texture_canaux_grand = dpg.add_static_texture(w_g, h_g, img_data)

"""Affichage de l'image de référence des canaux dans le coin en bas à droite"""
def afficher_canaux():
    global xc, yc, xcf, ycf, cx, cy, w_g, h_g
    
    if texture_canaux_petit is not None:
        dpg.draw_image(texture_canaux_petit, (xc, yc), (xcf, ycf), parent="drawlist_principal")
    
    if survol_canaux and texture_canaux_grand is not None:
        dpg.draw_image(texture_canaux_grand, (cx, cy), (cx + w_g, cy + h_g), parent="drawlist_principal")

"""Affichage de la mini-carte dans le coin en bas à droite, avec un rectangle indiquant la zone visible de l'image corrigée en fonction du zoom et du pan, et des instructions pour l'utilisateur"""
def draw_minimap():
    global texture_minimap
    if img_originale_corrigee is None:
        return
    global MINI_H
    ratio = img_originale_corrigee.shape[0] / img_originale_corrigee.shape[1]
    MINI_H = int(MINI_W * ratio)
    mx = MINI_X
    my = MINI_Y

    dpg.draw_rectangle((mx - 2, my - 2), (mx + MINI_W + 2, my + MINI_H + 2),
                       fill=(0, 0, 0, 180), color=(100, 100, 100, 200),
                       thickness=1, parent="drawlist_principal")
    if texture_minimap and dpg.does_item_exist(texture_minimap):
        dpg.draw_image(texture_minimap, (mx, my), (mx + MINI_W, my + MINI_H),
                       parent="drawlist_principal")

    vis_x0 = tex_src_x
    vis_y0 = tex_src_y
    vis_x1 = tex_src_x + W / zoom_level
    vis_y1 = tex_src_y + H / zoom_level

    scale_x = MINI_W / img_originale_corrigee.shape[1]
    scale_y = MINI_H / img_originale_corrigee.shape[0]

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

"""retourne le cas de chaque mesure et son type par rapport à la référence et son nom"""
def choose_cas(n_elmt, d, type, i):
    BD = n_elmt.startswith('B') or n_elmt.startswith('D')
    CF = n_elmt.startswith('C') or n_elmt.startswith('F')
    
    if i == reference_idx and reference_type == type:
        rapport_str = "REF"
        type_str = "REFERENCE"
    
    elif reference_value is not None and BD:
        rapport = d / reference_value
        if rapport <= 1.5:
            rapport_str = "cas 0"
            type_str = "Mesure"
        elif rapport <= 2.0:
            rapport_str = "cas 1"
            type_str = "Mesure"
        elif rapport <= 2.5:
            rapport_str = "cas 2"
            type_str = "Mesure"
        else:
            rapport_str = "cas 3"
            type_str = "Mesure"
    
    elif reference_value is not None and CF:
        rapport = d / reference_value
        if rapport <= 1.5:
            rapport_str = "cas 0"
            type_str = "Mesure"
        else:
            rapport_str = "cas 1"
            type_str = "Mesure"
    
    else:
        rapport_str = "/"
        type_str = type
    
    return rapport_str, type_str

"""Définit la couleur de l'élément de mesure en fonction de son nom, sa dimension (et de son cas)"""
def color(d, n_elmt, i, obj):
    if obj == "cercle":
        d = d*2
    if n_elmt == reference_nom and i == reference_idx and obj == reference_type:
        couleur_bord = (0, 0, 255)
        couleur_fill = (0, 0, 255, 35)
        label = f"REF: {n_elmt}"
    elif reference_idx is not None:
        label = n_elmt
        BD = n_elmt.startswith('B') or n_elmt.startswith('D')
        CF = n_elmt.startswith('C') or n_elmt.startswith('F')
        if (BD or CF) and ((d / reference_value) <= 1.5):
            couleur_bord = (0, 255, 0)
            couleur_fill = (0, 255, 0, 35)
        elif BD and (1.5 < (d / reference_value) <= 2):
            couleur_bord = (255, 255, 0)
            couleur_fill = (255, 255, 0, 35)
        elif BD and (2 < (d / reference_value) <= 2.5):
            couleur_bord = (255, 165, 0)
            couleur_fill = (255, 165, 0, 35)
        elif BD or CF:
            couleur_bord = (255, 0, 0)
            couleur_fill = (255, 0, 0, 35)
        else:
            couleur_bord = (250, 250, 250)
            couleur_fill = (250, 250, 250, 35)
    else:
        couleur_bord = (250, 250, 250)
        couleur_fill = (250, 250, 250, 35)
        label = n_elmt
    return couleur_bord, couleur_fill, label

"""permet de mettre à jour l'interface à chaque modification"""
def update_display():
    if not dpg.does_item_exist("drawlist_principal"):
        return
    dpg.delete_item("drawlist_principal", children_only=True)

    if texture_tag and dpg.does_item_exist(texture_tag):
        dpg.draw_image(texture_tag, (0, 0), (W, H), parent="drawlist_principal")
    else:
        dpg.draw_rectangle((0, 0), (W, H), fill=(40, 40, 40), parent="drawlist_principal")
        dpg.draw_text((W//2 - 180, H//2), "Chargez une image pour commencer",
                      color=(130, 130, 130), size=10, parent="drawlist_principal")

    # Cercles
    for i, (cx_img, cy_img, r_img, n_elmt) in enumerate(cercles):
        sx, sy = image_to_screen(cx_img, cy_img)
        r_screen = r_img * zoom_level
        arr = np.array([sx + r_screen < 0, sx - r_screen > W, sy + r_screen < 0, sy - r_screen > H])
        if arr.any():
            continue

        couleur_bord, couleur_fill, label = color(r_img, n_elmt, i, "cercle")
        dpg.draw_circle((sx, sy), r_screen, color=couleur_bord, fill=couleur_fill, thickness=2, segments=64, parent="drawlist_principal")
        dpg.draw_line((sx - r_screen, sy), (sx + r_screen, sy), color=(255, 50, 50, 220), thickness=2, parent="drawlist_principal")
        dpg.draw_circle((sx, sy), 4, color=(255, 255, 255, 255), fill=(255, 255, 255, 200), parent="drawlist_principal")
        dpg.draw_text((sx - 55, sy - r_screen - 14), label, color=couleur_bord, size=13, parent="drawlist_principal")

    # Segments
    for i, (x1_img, y1_img, x2_img, y2_img, n_elmt) in enumerate(segments):
        sx1, sy1 = image_to_screen(x1_img, y1_img)
        sx2, sy2 = image_to_screen(x2_img, y2_img)
        longueur = math.sqrt((x2_img - x1_img)**2 + (y2_img - y1_img)**2)
        couleur_bord, couleur_fill, label = color(longueur, n_elmt, i, "segment")
        dpg.draw_line((sx1, sy1), (sx2, sy2), color=couleur_bord, thickness=3, parent="drawlist_principal")
        cx = (sx1 + sx2) / 2
        cy = (sy1 + sy2) / 2
        dpg.draw_circle((cx, cy), 4, color=(255, 255, 255, 255), fill=(255, 255, 255, 200), parent="drawlist_principal")
        dpg.draw_text((cx - 55, cy - 20), label, color=couleur_bord, size=13, parent="drawlist_principal")

    if point1_temp:
        x1_img, y1_img = point1_temp
        sx1, sy1 = image_to_screen(x1_img, y1_img)
        dpg.draw_circle((sx1, sy1), 6, color=(0, 200, 255, 255),
                        fill=(0, 200, 255, 180), parent="drawlist_principal")
        dpg.draw_text((sx1 + 8, sy1 - 8), "Point 1",
                      color=(0, 200, 255, 255), size=13, parent="drawlist_principal")

    if ratio_px_mm:
        dpg.draw_rectangle((0, H - 18), (W, H), fill=(20, 50, 20, 220), parent="drawlist_principal")
        dpg.draw_text((6, H - 15),
                      f"Calibre — Kp = {ratio_px_mm:.4f} px/mm ; Etalon {DIAMETRE_ETALON_MM:.0f} mm",
                      color=(100, 255, 100), size=12, parent="drawlist_principal")

    afficher_canaux()
    draw_minimap()

"""Détermine le type de canal à partir du nom (B/D ou C/F)"""
def get_canal_type(nom):
    if not nom:
        return "autre"
    lettre = nom[0].upper()
    if lettre in ['B', 'D']:
        return "BD"
    elif lettre in ['C', 'F']:
        return "CF"
    return "autre"

# ─────────────────────────────────────────
# region CHARGER IMAGE
# ─────────────────────────────────────────
"""Affiche une pop up qui permet à l'utilisateur de charger l'image de son choix"""
def charger_image():
    global distorsion
    if distorsion == False:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Erreur : Choisir une camera")
        return
    dpg.show_item("dialogue_fichier")

"""permet d'obtenir les matrice de distorsion de la camera choisie"""
def calibrate():
    global K, D, h, w, distorsion, ID_CAMERA
    valeur = dpg.get_value("camera")
    pattern_size = (8, 5)
    objp = np.zeros((pattern_size[0]*pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
    objpoints = []
    imgpoints = []

    if valeur == "CAM_GDG_v1_air":
        images = glob.glob("lib/CAM_001_air/*.jpg")
    elif valeur == "CAM_GDG_v1_eau":
        images = glob.glob("lib/CAM_001_eau/*.jpg")
    else:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Erreur : Pas de donné pour réaliser la matrice de distorsion")
        return

    ID_CAMERA = valeur
    for fname in images:
        img = cv2.imread(fname)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCornersSB(gray, pattern_size)
        if ret:
            objpoints.append(objp.reshape(-1, 1, 3))
            imgpoints.append(corners.reshape(-1, 1, 2))

    if len(objpoints) < 5:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Erreur : Pas assez d'images valides; choisir une autre camera")
        return

    img = cv2.imread(images[0])
    h, w = img.shape[:2]
    flags = cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC + cv2.fisheye.CALIB_CHECK_COND + cv2.fisheye.CALIB_FIX_SKEW
    rms, K, D, rvecs, tvecs = cv2.fisheye.calibrate(
        objpoints, imgpoints, (w, h), K, D, None, None,
        flags, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6)
    )
    dpg.configure_item("statut", color=(0, 255, 0))
    dpg.set_value("statut", "Matrice de distorsion effectuée, charger une image")
    distorsion = True

"""permet de corriger l'image charger pas l'utilisateur"""
def correction():
    global chemin_image_actuelle, img_originale_corrigee, name_img, name_img_corrigee
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
    img_originale_corrigee = undistorted
    filename = os.path.basename(chemin_image_actuelle)
    name_img, ext = os.path.splitext(filename)
    name_img_corrigee = name_img + "_corrigee" + ext
    folder = os.path.dirname(chemin_image_actuelle)
    full_path = os.path.join(folder, name_img_corrigee)
    cv2.imwrite(full_path, undistorted)
    chemin_image_actuelle = full_path

"""récupérer l'image choisie par l'utilisateur et afficher l'image corrigee"""   
def callback_fichier(sender, app_data):
    global chemin_image_actuelle, img_originale_corrigee, texture_minimap, img_originale
    global zoom_level, view_x, view_y, tex_src_x, tex_src_y, cercles, segments, ratio_px_mm, cercle_etalon_idx, segment_etalon_idx
    if app_data and app_data.get("file_path_name"):
        chemin_image_actuelle = app_data["file_path_name"]

        img = cv2.imread(chemin_image_actuelle)
        if img is None:
            dpg.configure_item("statut", color=(255, 0, 0))
            dpg.set_value("statut", "Erreur : impossible de charger l'image")
            return
        img_originale = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)

        correction()
        img = cv2.imread(chemin_image_actuelle)
        if img is None:
            dpg.configure_item("statut", color=(255, 0, 0))
            dpg.set_value("statut", "Erreur : impossible de charger l'image")
            return
        img_originale_corrigee = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
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

        clamp_view()
        tex_src_x = view_x
        tex_src_y = view_y

        mini_h = int(MINI_W * img_originale_corrigee.shape[0] / img_originale_corrigee.shape[1])
        mini_img = cv2.resize(img_originale_corrigee, (MINI_W, mini_h), interpolation=cv2.INTER_AREA)
        mini_data = mini_img.flatten().astype(np.float32) / 255.0

        if texture_minimap and dpg.does_item_exist(texture_minimap):
            dpg.delete_item(texture_minimap)
        with dpg.texture_registry():
            texture_minimap = dpg.add_static_texture(MINI_W, mini_h, mini_data)
        rebuild_texture_zoom()
        update_display()
        dpg.configure_item("statut", color=(0, 255, 0))
        dpg.set_value("statut", f"Image chargee : {os.path.basename(chemin_image_actuelle)}")

# ─────────────────────────────────────────
# region REFERENCE
# ─────────────────────────────────────────
"""Définit l'élément (cercle ou segment) choisi comme référence"""
def definir_reference():
    if not cercles and not segments:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Aucun element a definir comme reference")
        return

    with dpg.window(tag="reference_window", label="Choisir canal de reference", width=300, height=200,
                    pos=(dpg.get_viewport_width()//2 - 150, dpg.get_viewport_height()//2 - 100)):
        dpg.add_text("Choisissez le canal de référence :")
        dpg.add_spacer(height=10)

        items = []
        for i, (cx, cy, r, nom) in enumerate(cercles):
            if nom.startswith('A'):
                items.append(f"{nom} - cercle")
        for i, (x1, y1, x2, y2, nom) in enumerate(segments):
            if nom.startswith('A'):
                items.append(f"{nom} - segment")

        combo = dpg.add_combo(items=items, width=250, tag="cercle_a_supprimer")
        dpg.add_spacer(height=15)

        with dpg.group(horizontal=True):
            dpg.add_button(label="Valider", callback=lambda: valider_ref(dpg.get_value(combo)), width=100)
            dpg.add_button(label="Annuler", callback=lambda: dpg.delete_item("reference_window"), width=100)

"""initialiser les valeur du canal de ref"""
def valider_ref(nom_selectionne):
    global reference_idx, reference_type, reference_value, reference_nom
    if not nom_selectionne:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Aucun canal sélectionné")
        return

    nom_ref = nom_selectionne.split(" - ")[0]
    reference_type = nom_selectionne.split(" - ")[1]
    if reference_type == "segment":
        for i, (x1, y1, x2, y2, nom) in enumerate(segments):
            if nom == nom_ref:
                longueur = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                reference_value = longueur * COEFF_REDUCTION
                reference_idx = i
                reference_nom = nom
                dpg.configure_item("statut", color=(0, 255, 0))
                dpg.set_value("statut", f"Reference definie - Segment '{nom_ref}'")
                break
    else:
        for i, (cx, cy, r, nom) in enumerate(cercles):
            if nom == nom_ref:
                reference_value = r * 2 * COEFF_REDUCTION
                reference_idx = i
                reference_nom = nom
                dpg.configure_item("statut", color=(0, 255, 0))
                dpg.set_value("statut", f"Reference definie - Cercle '{nom}'")
                break

    dpg.delete_item("reference_window")
    update_display()

"""Réinitialise la référence"""
def reset_reference():
    global reference_idx, reference_type, reference_value, reference_nom
    reference_idx = None
    reference_type = None
    reference_value = None
    reference_nom = None
    dpg.configure_item("statut", color=(0, 255, 0))
    dpg.set_value("statut", "Reference reinitialisee")
    update_display()

# ─────────────────────────────────────────
# region MODE DESSIN
# ─────────────────────────────────────────
"""Active le mode dessin de cercle : quand l'utilisateur appuiera sur l'image il dessinera un cercle"""
def toggle_draw_mode_cercle():
    global mode_dessin_cercle, mode_dessin_segment, point1_temp, calibration_mode
    if calibration_mode:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Desactivez la calibration d'abord")
        return
    mode_dessin_cercle = not mode_dessin_cercle
    if mode_dessin_cercle:
        mode_dessin_segment = False
        point1_temp = None
        dpg.configure_item("btn_draw", label="ACTIF cliquez pour desactiver")
        dpg.configure_item("btn_draw_sgt", label="Dessiner un segment")
        dpg.configure_item("statut", color=(0, 255, 0))
        dpg.set_value("statut", "Mode dessin CERCLE ACTIF")
    else:
        point1_temp = None
        dpg.configure_item("btn_draw", label="Dessiner un cercle")
        dpg.configure_item("statut", color=(0, 255, 0))
        dpg.set_value("statut", "Mode dessin cercle desactive")
        update_display()

"""Active le mode dessin de segment : quand l'utilisateur appuiera sur l'image il dessinera un segment"""
def toggle_draw_mode_segment():
    global mode_dessin_segment, mode_dessin_cercle, point1_temp, calibration_mode
    mode_dessin_segment = not mode_dessin_segment
    if mode_dessin_segment:
        mode_dessin_cercle = False
        point1_temp = None
        dpg.configure_item("btn_draw_sgt", label="ACTIF cliquez pour desactiver")
        dpg.configure_item("btn_draw", label="Dessiner un cercle")
        dpg.configure_item("statut", color=(0, 255, 0))
        dpg.set_value("statut", "Mode dessin SEGMENT ACTIF")
    else:
        point1_temp = None
        dpg.configure_item("btn_draw_sgt", label="Dessiner un segment")
        dpg.configure_item("statut", color=(0, 255, 0))
        dpg.set_value("statut", "Mode dessin segment desactive")
        update_display()

# ─────────────────────────────────────────
# region POP-UP pour nommer les élements
# ─────────────────────────────────────────
"""Création de la pop-up permettant de choisir le nom de l'élément qu'on vient de créer"""
def ouvrir_popup(Dist):
    global diametre
    diametre = Dist
    with dpg.window(label="Saisie utilisateur", modal=True, tag="fenetre_saisie",
                    pos=(dpg.get_viewport_width()//2 - 150, dpg.get_viewport_height()//2 - 100),
                    on_close=annuler_saisie):
        dpg.add_text("Écris le nom de l'élément :", tag="text_popup")
        dpg.add_input_text(tag="input_texte")
        dpg.add_button(label="Valider", callback=valider)

"""Eviter les beugs lorsque l'utilisateur appuie sur la croix"""
def annuler_saisie():
    global point1_temp
    point1_temp = None
    if dpg.does_item_exist("fenetre_saisie"):
        dpg.delete_item("fenetre_saisie")
    update_display()

"""vérifie que le nom tapé par l'utilisateur est bien valide (ex : B2)"""
def format_valide(nom):
    return bool(re.match(r'^[A-Z]\d+$', nom))

"""Vérifie que le nom attribué à l'élément n'a pas déjà été choisie"""
def nom_exist(n_temp):
    for i, (cx, cy, r, n_elmt) in enumerate(cercles):
        if n_elmt == n_temp:
            return True
    for i, (x1_img, y1_img, x2_img, y2_img, n_elmt) in enumerate(segments):
        if n_elmt == n_temp:
            return True
    return False

"""récupérer le texte saisie par l'utilisateur"""
def valider(sender, app_data):
    global nom_element
    nom_element = dpg.get_value("input_texte")
    
    # Vérification du format
    if not format_valide(nom_element):
        dpg.set_value("text_popup", "Format invalide ! Exemple valide : B1, A3, D2")
        return
    
    # Vérification des doublons
    if nom_exist(nom_element):
        dpg.set_value("text_popup", "Nom déjà existant !")
        return
    
    dpg.set_value("input_texte", "")
    dpg.hide_item("fenetre_saisie")
    
    if reference_value is not None:
        pourc = (diametre*2 / reference_value) * 100
        dpg.configure_item("statut", color=(0, 255, 0))
        dpg.set_value("statut", f"{nom_element} ajoute")
    elif ratio_px_mm:
        dpg.configure_item("statut", color=(0, 255, 0))
        dpg.set_value("statut", f"{nom_element} ajoute")
    else:
        dpg.configure_item("statut", color=(0, 255, 0))
        dpg.set_value("statut", f"{nom_element} ajoute")
    
    if obj == "cercle":
        cercles.append((temp_cx, temp_cy, diametre, nom_element))
    elif obj == "segment":
        segments.append((temp_x1, temp_y1, temp_x2, temp_y2, nom_element))
    
    dpg.delete_item("fenetre_saisie")
    update_display()

# ─────────────────────────────────────────
# region GESTION SOURIS
# ─────────────────────────────────────────
"""Gère la molette de souris pour le zoom"""
def on_mouse_wheel(sender, app_data):
    global zoom_level, view_x, view_y, tex_src_x, tex_src_y
    if not dpg.is_item_hovered("drawlist_principal"):
        return
    if img_originale_corrigee is None:
        return

    mx, my = dpg.get_drawing_mouse_pos()
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

"""Vérifie si un nouveau cercle chevauche un cercle existant"""
def cercle_chevauche(cx_temp, cy_temp):
    for i, (cx, cy, r, n_elmt) in enumerate(cercles):
        distance = math.sqrt((cx_temp - cx)**2 + (cy_temp - cy)**2)
        if distance < (reference_value/2 + r):
            return True
    return False

"""Gère le click souris selon ce qu'est en train de faire l'utilisateur  : création d'un élément ; validation de l'élément"""
def on_mouse_click(sender, app_data):
    global point1_temp, cercles, segments, view_x, view_y, temp_cx, temp_cy, temp_x1, temp_y1, temp_x2, temp_y2, obj, reference_value, ptit_cercle, ptit_sgmt, premier_segment, sx_perp1, sy_perp1,sx_perp2, sy_perp2
    if not dpg.is_item_hovered("drawlist_principal"):
        return
    if img_originale_corrigee is None:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Erreur : Charger une image")
        return

    mx, my = dpg.get_drawing_mouse_pos()

    if app_data == 0:
        # Navigation sur la mini-carte
        if img_originale_corrigee is not None:
            mini_h = int(MINI_W * img_originale_corrigee.shape[0] / img_originale_corrigee.shape[1])
            if MINI_X <= mx <= MINI_X + MINI_W and MINI_Y <= my <= MINI_Y + mini_h:
                rel_x = (mx - MINI_X) / MINI_W
                rel_y = (my - MINI_Y) / mini_h
                img_cx = rel_x * img_originale_corrigee.shape[1]
                img_cy = rel_y * img_originale_corrigee.shape[0]
                view_x = img_cx - (W / zoom_level) / 2
                view_y = img_cy - (H / zoom_level) / 2
                clamp_view()
                rebuild_texture_zoom()
                update_display()
                return

        ix, iy = screen_to_image(mx, my)

        # ==========================================================
        # DESSIN D'UN SEGMENT
        # ==========================================================
        if mode_dessin_segment and 0 <= mx <= W and 0 <= my <= H:
            if point1_temp is None and premier_segment is None:
                point1_temp = (ix, iy)
                update_display()
                dpg.configure_item("statut", color=(0, 255, 0))
                if premier_segment is None:
                    dpg.set_value("statut", "Point 1 du premier segment - Cliquez pour le point 2")
                else:
                    dpg.set_value("statut", "Cliquez pour définir la direction du segment perpendiculaire (il passera par le milieu)")
            elif point1_temp is None and premier_segment is not None: #DEUXI7ME SEGMENT
                nom_element = f"S{ptit_sgmt}"
                while nom_exist(nom_element):
                    ptit_sgmt += 1
                    nom_element = f"S{ptit_sgmt}"
        #         dpg.draw_line((sx_perp1, sy_perp1), (sx_perp2, sy_perp2), color=(255, 165, 0, 200), thickness=2, parent="drawlist_principal")
                # print(f"coordonées cliquer {sx_perp1, sy_perp1,sx_perp2, sy_perp2}")
                sx_perp2, sy_perp2 = screen_to_image(sx_perp2, sy_perp2)
                sx_perp1, sy_perp1 = screen_to_image(sx_perp1, sy_perp1)
                segments.append((sx_perp1, sy_perp1,sx_perp2, sy_perp2, nom_element))
                ptit_sgmt += 1
                
                point1_temp = None
                premier_segment = None  # Réinitialiser pour le prochain
                dpg.configure_item("statut", color=(0, 255, 0))
                dpg.set_value("statut", f"Segment perpendiculaire {nom_element} ajouté (passe par le milieu)")
                update_display()
            else: # ===== PREMIER SEGMENT =====
                x1, y1 = point1_temp
                x2, y2 = ix, iy
                # if premier_segment is None:
                temp_x1, temp_y1, temp_x2, temp_y2 = x1, y1, x2, y2
                nom_element = f"S{ptit_sgmt}"
                while nom_exist(nom_element):
                    ptit_sgmt += 1
                    nom_element = f"S{ptit_sgmt}"
                segments.append((temp_x1, temp_y1, temp_x2, temp_y2, nom_element))
                ptit_sgmt += 1
                
                # Stocker ce segment comme référence
                premier_segment = (x1, y1, x2, y2)
                point1_temp = None
                dpg.configure_item("statut", color=(0, 255, 0))
                dpg.set_value("statut", f"Premier segment {nom_element} tracé - Tracez maintenant le segment perpendiculaire (il passera par le milieu)")
                update_display()
            return

        # ==========================================================
        # DESSIN D'UN CERCLE
        # ==========================================================
        if mode_dessin_cercle and 0 <= mx <= W and 0 <= my <= H:
            if reference_value is None:
                # Mode normal : 2 clics + popup
                if point1_temp is None:
                    point1_temp = (ix, iy)
                    update_display()
                    dpg.configure_item("statut", color=(0, 255, 0))
                else:
                    x1, y1 = point1_temp
                    cx = (x1 + ix) / 2
                    cy = (y1 + iy) / 2
                    temp_cx, temp_cy = cx, cy
                    radius = math.sqrt((ix - x1)**2 + (iy - y1)**2) / 2
                    obj = "cercle"
                    ouvrir_popup(radius)
                    point1_temp = None
            else:
                # Mode rapide avec référence : cercle Z (avec vérification de chevauchement)
                if cercle_chevauche(ix, iy):
                    dpg.configure_item("statut", color=(255, 0, 0))
                    dpg.set_value("statut", "Erreur : Cercle trop proche d'un autre cercle !")
                    return
                
                # Trouver un nom unique pour Z
                nom_element = f"Z{ptit_cercle}"
                while nom_exist(nom_element):
                    ptit_cercle += 1
                    nom_element = f"Z{ptit_cercle}"
                
                diametre = reference_value
                cercles.append((ix, iy, diametre / 2, nom_element))
                ptit_cercle += 1
                dpg.configure_item("statut", color=(0, 255, 0))
                dpg.set_value("statut", f"Cercle {nom_element} ajouté")
                update_display()
            return

"""Gère le clique relaché de la souris pour dire que l'utilisateur est en train de créer un élément"""
def on_mouse_down(sender, app_data):
    global pan_actif, pan_last_x, pan_last_y
    if app_data == 1 and dpg.is_item_hovered("drawlist_principal"):
        pan_actif = True
        mx, my = dpg.get_mouse_pos()
        pan_last_x = mx
        pan_last_y = my

"""Gère le clique relaché de la souris pour dire que l'utilisateur à fini de créer un élément"""
def on_mouse_release(sender, app_data):
    global pan_actif
    if app_data == 1:
        pan_actif = False

"""True Si la souris est sur l'image des canaux de réference, false sinon (pour savoir quand afficher l'image en grand)"""
def souris_sur_canaux(mx, my):
    return xc <= mx <= xcf and yc <= my <= ycf

"""lorsque l'utilisateur est en train de créer un élement pour avoir un apperçu temporaire de l'élément"""
def on_mouse_move(sender, app_data):
    global pan_last_x, pan_last_y, view_x, view_y, survol_canaux, point1_temp, premier_segment, sx_perp1, sy_perp1, sx_perp2, sy_perp2

    if dpg.is_item_hovered("drawlist_principal"):
        mx, my = dpg.get_drawing_mouse_pos()
        nouveau_survol = survol_canaux
        if souris_sur_canaux(mx, my):
            survol_canaux = True
        else:
            survol_canaux = False
        if nouveau_survol != survol_canaux:
            update_display()

    if pan_actif and img_originale_corrigee is not None:
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

    if (not mode_dessin_cercle and not mode_dessin_segment) or (point1_temp is None and reference_value is None and mode_dessin_cercle ) or (point1_temp is None and premier_segment is None and mode_dessin_segment):
        return
    if not dpg.is_item_hovered("drawlist_principal"):
        return

    mx, my = dpg.get_drawing_mouse_pos()
    if not (0 <= mx <= W and 0 <= my <= H):
        return

    ix, iy = screen_to_image(mx, my)

    if point1_temp is not None:
        x1, y1 = point1_temp

    # APERÇU DU SEGMENT
    if mode_dessin_segment :
        update_display()
        sx2, sy2 = image_to_screen(ix, iy)
        if premier_segment is not None:
            # ON EST EN TRAIN DE TRACER LE SEGMENT PERPENDICULAIRE
            # Afficher le premier segment en vert
            ref_x1, ref_y1, ref_x2, ref_y2 = premier_segment
            srx1, sry1 = image_to_screen(ref_x1, ref_y1)
            srx2, sry2 = image_to_screen(ref_x2, ref_y2)
            dpg.draw_line((srx1, sry1), (srx2, sry2), color=(0, 255, 0, 200), thickness=3, parent="drawlist_principal")
            dpg.draw_text(((srx1+srx2)/2 - 40, (sry1+sry2)/2 - 20), "REFERENCE", color=(0, 255, 0, 200), size=11, parent="drawlist_principal")

            #projection du pt de la souris sur le premier segment
            abx = ref_x2 - ref_x1
            aby = ref_y2 - ref_y1
            apx = ix - ref_x1
            apy = iy - ref_y1

            ab_len2 = abx * abx + aby * aby
            if ab_len2 > 0:
                t = (apx * abx + apy * aby) / ab_len2
                # Limiter au segment
                t = max(0.0, min(1.0, t))
                point_x = ref_x1 + t * abx
                point_y = ref_y1 + t * aby

            ancrage_x = point_x
            ancrage_y = point_y
            smilieu_x, smilieu_y = image_to_screen(ancrage_x, ancrage_y)

            # Afficher le point d'accroche(petit cercle)
            dpg.draw_circle((smilieu_x, smilieu_y), 5, color=(255, 255, 0, 255), fill=(255, 255, 0, 100), parent="drawlist_principal")
            dpg.draw_text((smilieu_x + 10, smilieu_y - 8), "Milieu", color=(255, 255, 0, 255), size=10, parent="drawlist_principal")

            # Calculer le segment perpendiculaire
            ref_dx = ref_x2 - ref_x1
            ref_dy = ref_y2 - ref_y1
            
            # Perpendiculaire
            dx_perp = -ref_dy
            dy_perp = ref_dx
            norm_perp = math.sqrt(dx_perp**2 + dy_perp**2)
            
            if norm_perp > 0 and (ref_dx**2 + ref_dy**2) > 0:
                dx_perp_norm = dx_perp / norm_perp
                dy_perp_norm = dy_perp / norm_perp
                
                # Longueur du segment perpendiculaire (indiquée par l'utilisateur)
                dx_user = sx2 - smilieu_x
                dy_user = sy2 - smilieu_y
                longueur_user = math.sqrt(dx_user**2 + dy_user**2)
                
                if longueur_user > 0:
                    # Apercu symetrique : le segment est centre sur le milieu (passe par le milieu)
                    # demi_longueur = longueur_user / 2
                    x_perp1 = ancrage_x - dx_perp_norm * longueur_user
                    y_perp1 = ancrage_y - dy_perp_norm * longueur_user

                    x_perp2 = ancrage_x + dx_perp_norm * longueur_user
                    y_perp2 = ancrage_y + dy_perp_norm * longueur_user
                    
                    sx_perp1, sy_perp1 = image_to_screen(x_perp1, y_perp1)
                    sx_perp2, sy_perp2 = image_to_screen(x_perp2, y_perp2)
                    
                    # Afficher le segment perpendiculaire complet (centre sur le milieu) en orange
                    dpg.draw_line((sx_perp1, sy_perp1), (sx_perp2, sy_perp2), color=(255, 165, 0, 200), thickness=2, parent="drawlist_principal")
                    # print(f"coordonée temp : {sx_perp1, sy_perp1, sx_perp2, sy_perp2}")
                    dpg.draw_circle((sx_perp1, sy_perp1), 6, color=(255, 165, 0, 255), fill=(255, 165, 0, 100), parent="drawlist_principal")
                    dpg.draw_circle((sx_perp2, sy_perp2), 6, color=(255, 165, 0, 255), fill=(255, 165, 0, 100), parent="drawlist_principal")
                    dpg.draw_text((sx_perp2 + 10, sy_perp2 - 8), "Perpendiculaire", color=(255, 165, 0, 255), size=11, parent="drawlist_principal")
                    
                    # Afficher l'angle droit au milieu
                    angle_size = 15
                    dpg.draw_line((smilieu_x + angle_size, smilieu_y), (smilieu_x + angle_size, smilieu_y - angle_size), color=(255, 255, 255, 150), thickness=1, parent="drawlist_principal")
                    dpg.draw_line((smilieu_x, smilieu_y - angle_size), (smilieu_x + angle_size, smilieu_y - angle_size), color=(255, 255, 255, 150), thickness=1, parent="drawlist_principal")
                    
                    # Afficher la direction du point1
                    dpg.draw_line((smilieu_x, smilieu_y), (sx2, sy2), color=(0, 200, 255, 150), thickness=1, parent="drawlist_principal")
                    dpg.draw_text((sx2 + 10, sy2 - 8), "Direction", color=(0, 200, 255, 150), size=10, parent="drawlist_principal")

            
        elif point1_temp is not None:
            sx1, sy1 = image_to_screen(x1, y1)
            # ON EST EN TRAIN DE TRACER LE PREMIER SEGMENT
            dpg.draw_line((sx1, sy1), (sx2, sy2), color=(0, 200, 255, 180), thickness=2, parent="drawlist_principal")
            dpg.draw_text((sx2 + 10, sy2 - 8), "Premier segment", color=(0, 200, 255, 180), size=10, parent="drawlist_principal")
        return

    # APERÇU DU CERCLE
    if mode_dessin_cercle:
        if reference_value is None and point1_temp is not None:
            update_display()
            sx1, sy1 = image_to_screen(x1, y1)
            sx2, sy2 = image_to_screen(ix, iy)
            cx = (sx1 + sx2) / 2
            cy = (sy1 + sy2) / 2
            radius = math.sqrt((sx2 - sx1)**2 + (sy2 - sy1)**2) / 2
            dpg.draw_line((sx1, sy1), (sx2, sy2), color=(0, 200, 255, 180), thickness=1, parent="drawlist_principal")
            dpg.draw_circle((cx, cy), radius, color=(0, 200, 255, 200), fill=(0, 200, 255, 30), thickness=2, parent="drawlist_principal")
            dpg.draw_circle((cx, cy), 4, color=(255, 255, 255, 255), fill=(255, 255, 255, 200), parent="drawlist_principal")
        else:
            update_display()
            centre = (mx, my)
            radius = (reference_value / 2) * zoom_level
            # Vérifier si le chevauchement est OK
            if cercle_chevauche(ix, iy):
                couleur = (255, 0, 0, 200)  # Rouge si chevauchement
                fill = (255, 0, 0, 30)
            else:
                couleur = (0, 200, 255, 200)  # Bleu si OK
                fill = (0, 200, 255, 30)
            dpg.draw_line((mx - radius, my), (mx + radius, my), color=couleur, thickness=1, parent="drawlist_principal")
            dpg.draw_circle(centre, radius, color=couleur, fill=fill, thickness=2, parent="drawlist_principal")
        return
# ─────────────────────────────────────────
# region ACTIONS SUPPLEMENTAIRES
# ─────────────────────────────────────────
"""Réinitialise le zoom et la position de la vue."""
def reset_zoom():
    global zoom_level, view_x, view_y, tex_src_x, tex_src_y
    zoom_level = 1.0
    view_x = 0.0
    view_y = 0.0
    tex_src_x = 0
    tex_src_y = 0
    if img_originale_corrigee is not None:
        rebuild_texture_zoom()
    update_display()
    dpg.configure_item("statut", color=(0, 255, 0))
    dpg.set_value("statut", "Zoom reinitialise")

"""effacer tous les cercles"""
def clear_cercles():
    global cercles, point1_temp, reference_idx, reference_type, reference_value, reference_nom, ptit_cercle
    cercles = []
    point1_temp = None
    ptit_cercle = 0
    if reference_type == "cercle":
        reference_idx = None
        reference_type = None
        reference_value = None
        reference_nom = None
    update_display()
    dpg.configure_item("statut", color=(0, 255, 0))
    dpg.set_value("statut", "Cercles effaces")

"""effacer tous les segments"""
def clear_segments():
    global segments, point1_temp, ratio_px_mm, segment_etalon_idx, reference_idx, reference_type, reference_value, reference_nom, ptit_sgmt, premier_segment
    segments = []
    point1_temp = None
    ptit_sgmt = 0
    premier_segment = None  # ← AJOUTER
    if reference_type == "segment":
        reference_idx = None
        reference_type = None
        reference_value = None
        reference_nom = None
    if not calibration_mode:
        ratio_px_mm = None
        segment_etalon_idx = None
    update_display()
    dpg.configure_item("statut", color=(0, 255, 0))
    dpg.set_value("statut", "Segments effaces")

"""Fenetre pour choisir quel cercle supprimer"""
def supprimer_cercle_par_nom():
    if not cercles:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Aucun cercle à supprimer")
        return

    with dpg.window(tag="supprimer_cercle_window", label="Supprimer un cercle", width=300, height=200,
                    pos=(dpg.get_viewport_width()//2 - 150, dpg.get_viewport_height()//2 - 100)):
        dpg.add_text("Choisissez le cercle à supprimer:")
        dpg.add_spacer(height=10)
        items = [nom for _, _, _, nom in cercles]
        combo = dpg.add_combo(items=items, width=250, tag="cercle_a_supprimer")
        dpg.add_spacer(height=15)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Supprimer", callback=lambda: valider_suppression_cercle(dpg.get_value(combo)), width=100)
            dpg.add_button(label="Annuler", callback=lambda: dpg.delete_item("supprimer_cercle_window"), width=100)

"""supprimer un cercle choisi par l'utilisateur"""
def valider_suppression_cercle(nom_selectionne):
    global cercles, cercle_etalon_idx, ratio_px_mm, reference_idx, reference_value
    if not nom_selectionne:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Aucun cercle sélectionné")
        return

    for i, (cx, cy, r, nom) in enumerate(cercles):
        if nom == nom_selectionne:
            cercles.pop(i)
            if cercle_etalon_idx == i:
                cercle_etalon_idx = None
                ratio_px_mm = None
            if reference_idx == i and reference_type == "cercle":
                reference_idx = None
                reference_value = None
            elif reference_idx is not None and i < reference_idx and reference_type == "cercle":
                reference_idx -= 1
            dpg.configure_item("statut", color=(0, 255, 0))
            dpg.set_value("statut", f"Cercle '{nom_selectionne}' supprimé")
            break

    dpg.delete_item("supprimer_cercle_window")
    update_display()

"""Fenetre pour choisir quel segment supprimer"""
def supprimer_segment_par_nom():
    if not segments:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Aucun segment à supprimer")
        return

    with dpg.window(tag="supprimer_segment_window", label="Supprimer un segment", width=300, height=200,
                    pos=(dpg.get_viewport_width()//2 - 150, dpg.get_viewport_height()//2 - 100)):
        dpg.add_text("Choisissez le segment à supprimer:")
        dpg.add_spacer(height=10)
        items = [nom for _, _, _, _, nom in segments]
        combo = dpg.add_combo(items=items, width=250, tag="segment_a_supprimer")
        dpg.add_spacer(height=15)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Supprimer", callback=lambda: valider_suppression_segment(dpg.get_value(combo)), width=100)
            dpg.add_button(label="Annuler", callback=lambda: dpg.delete_item("supprimer_segment_window"), width=100)

"""supprimer un segment choisi par l'utilisateur"""
def valider_suppression_segment(nom_selectionne):
    global segments, segment_etalon_idx, ratio_px_mm
    if not nom_selectionne:
        dpg.configure_item("statut", color=(255, 0, 0))
        dpg.set_value("statut", "Aucun segment sélectionné")
        return

    for i, (x1, y1, x2, y2, nom) in enumerate(segments):
        if nom == nom_selectionne:
            segments.pop(i)
            if segment_etalon_idx == nom:
                segment_etalon_idx = None
                ratio_px_mm = None
            dpg.configure_item("statut", color=(0, 255, 0))
            dpg.set_value("statut", f"Segment '{nom_selectionne}' supprimé")
            break

    dpg.delete_item("supprimer_segment_window")
    update_display()

# ─────────────────────────────────────────
# region SAUVEGARDE INFOS
# ─────────────────────────────────────────
"""Sauvegarder les info dans le json"""
def sauvegarder():
    global info_affaire, info_palier, info_central, info_tranche, info_visite
    donnees_pv = {
        "info_affaire": info_affaire,
        "info_palier": info_palier,
        "info_central": info_central,
        "info_tranche": info_tranche,
        "info_visite": info_visite
    }
    with open(fichier_donnee, "w", encoding="utf-8") as f:
        json.dump(donnees_pv, f, indent=4)

"""Sauvegarde les informations et ferme la popup"""
def sauvegarder_infos(sender, app_data):
    global info_affaire, info_palier, info_central, info_tranche, info_visite
    info_affaire = dpg.get_value("popup_affaire")
    info_palier = dpg.get_value("popup_palier")
    info_central = dpg.get_value("popup_central")
    info_tranche = dpg.get_value("popup_tranche")
    info_visite = dpg.get_value("popup_visite")
    dpg.delete_item("popup_infos")
    dpg.configure_item("statut", color=(0, 255, 0))
    sauvegarder()
    dpg.set_value("statut", "Informations enregistrees")

"""Ouvre la popup pour modifier les informations"""
def ouvrir_popup_infos():
    global info_affaire, info_palier, info_central, info_tranche, info_visite
    if dpg.does_item_exist("popup_infos"):
        dpg.delete_item("popup_infos")

    with dpg.window(tag="popup_infos", label="Informations du rapport", width=420, height=380,
                    pos=(dpg.get_viewport_width()//2 - 210, dpg.get_viewport_height()//2 - 190),
                    modal=True, show=True, no_resize=True):
        dpg.add_text(" IDENTIFICATION ", color=(255, 165, 0))
        dpg.add_spacer(height=5)
        dpg.add_text("Affaire:", color=(240, 240, 240))
        dpg.add_input_text(tag="popup_affaire", width=340, default_value=info_affaire)
        dpg.add_spacer(height=5)
        dpg.add_text("Palier:", color=(240, 240, 240))
        dpg.add_input_text(tag="popup_palier", width=340, default_value=info_palier)
        dpg.add_spacer(height=5)
        dpg.add_text("Centrale:", color=(240, 240, 240))
        dpg.add_input_text(tag="popup_central", width=340, default_value=info_central)
        dpg.add_spacer(height=5)
        dpg.add_text("Tranche:", color=(240, 240, 240))
        dpg.add_input_text(tag="popup_tranche", width=340, default_value=info_tranche)
        dpg.add_spacer(height=5)
        dpg.add_text("Visite:", color=(240, 240, 240))
        dpg.add_input_text(tag="popup_visite", width=340, default_value=info_visite)
        dpg.add_spacer(height=20)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Enregistrer", callback=sauvegarder_infos, width=150)

# ─────────────────────────────────────────
# region POPUP EXPORT
# ─────────────────────────────────────────
"""Ferme la popup sans exporter"""
def fermer_popup_export(sender, app_data):
    dpg.delete_item("popup_export_complet")

"""Ouvre une seule popup avec toutes les informations pour l'export"""
def ouvrir_popup_export_complet():
    global pdf_chrono, pdf_revision, pdf_ref_gdg, pdf_carte
    global canal_plus_use_BD_nom, canal_plus_use_BD_cas, canal_plus_use_BD_rapport
    global canal_plus_use_CF_nom, canal_plus_use_CF_cas, canal_plus_use_CF_rapport
    
    if dpg.does_item_exist("popup_export_complet"):
        dpg.delete_item("popup_export_complet")
    
    with dpg.window(tag="popup_export_complet", label="Export du rapport", width=480, height=580,
                    pos=(dpg.get_viewport_width()//2 - 240, dpg.get_viewport_height()//2 - 290),
                    modal=True, show=True, no_resize=True):
        
        # Section 1: Référence document
        dpg.add_text(" REFERENCE DOCUMENT ", color=(255, 165, 0))
        dpg.add_spacer(height=5)
        
        dpg.add_text("Chrono:")
        dpg.add_input_text(tag="pdf_chrono", width=400, default_value=pdf_chrono)
        dpg.add_spacer(height=5)
        
        dpg.add_text("Revision:")
        dpg.add_input_text(tag="pdf_revision", width=400, default_value=pdf_revision)
        dpg.add_spacer(height=5)
        
        dpg.add_text("Reference GDG:")
        dpg.add_input_text(tag="pdf_ref_gdg", width=400, default_value=pdf_ref_gdg)
        dpg.add_spacer(height=5)
        
        dpg.add_text("Carte:")
        dpg.add_input_text(tag="pdf_carte", width=400, default_value=pdf_carte)
        dpg.add_spacer(height=10)
        
        dpg.add_separator()
        dpg.add_spacer(height=5)
        
        # ==========================================================
        # SECTION CANAUX B/D - Canal le plus usé
        # ==========================================================
        dpg.add_text(" CANAUX B/D - Canal le plus usé ", color=(255, 165, 0))
        dpg.add_spacer(height=5)
        
        dpg.add_text("Nom du canal B/D:")
        dpg.add_input_text(tag="input_BD_nom", width=400, default_value=canal_plus_use_BD_nom)
        dpg.add_spacer(height=5)
        
        # ICI : Remplacer "Cas" par "Rapport"
        dpg.add_text("Rapport (par rapport à la référence):")
        dpg.add_input_text(tag="input_BD_rapport", width=400, default_value=canal_plus_use_BD_rapport,
                           callback=lambda s, a: update_cas_automatique())
        dpg.add_spacer(height=5)
        
        # Afficher le cas calculé automatiquement
        dpg.add_text("Cas associé (calculé automatiquement):", color=(200, 200, 200))
        dpg.add_text("", tag="label_BD_cas", color=(255, 165, 0))
        dpg.add_spacer(height=10)
        
        # ==========================================================
        # SECTION CANAUX C/F - Canal le plus usé
        # ==========================================================
        dpg.add_text(" CANAUX C/F - Canal le plus usé ", color=(255, 165, 0))
        dpg.add_spacer(height=5)
        
        dpg.add_text("Nom du canal C/F:")
        dpg.add_input_text(tag="input_CF_nom", width=400, default_value=canal_plus_use_CF_nom)
        dpg.add_spacer(height=5)
        
        # ICI : Remplacer "Cas" par "Rapport"
        dpg.add_text("Rapport (par rapport à la référence):")
        dpg.add_input_text(tag="input_CF_rapport", width=400, default_value=canal_plus_use_CF_rapport,
                           callback=lambda s, a: update_cas_automatique())
        dpg.add_spacer(height=5)
        
        # Afficher le cas calculé automatiquement
        dpg.add_text("Cas associé (calculé automatiquement):", color=(200, 200, 200))
        dpg.add_text("", tag="label_CF_cas", color=(255, 165, 0))
        dpg.add_spacer(height=15)
        
        # Boutons
        with dpg.group(horizontal=True):
            dpg.add_button(label="Exporter", callback=sauvegarder_export_complet, width=180)
            dpg.add_button(label="Annuler", callback=fermer_popup_export, width=120)
    
    # Mettre à jour les cas automatiquement
    update_cas_automatique()

"""Met à jour automatiquement les cas en fonction des rapports saisis"""
def update_cas_automatique():
    # Récupérer les rapports saisis par l'utilisateur
    try:
        val_BD = dpg.get_value("input_BD_rapport").replace(",", ".")
        rapport_BD = float(val_BD) if val_BD else 0
    except ValueError:
        rapport_BD = 0
    
    try:
        val_CF = dpg.get_value("input_CF_rapport").replace(",", ".")
        rapport_CF = float(val_CF) if val_CF else 0
    except ValueError:
        rapport_CF = 0
    
    # ==========================================================
    # DÉTERMINATION DU CAS POUR B/D
    # ==========================================================
    if rapport_BD > 0:
        if rapport_BD <= 1.5:
            cas_BD = "Cas 0"
        elif rapport_BD <= 2.0:
            cas_BD = "Cas 1"
        elif rapport_BD <= 2.5:
            cas_BD = "Cas 2"
        else:
            cas_BD = "Cas 3"
    else:
        cas_BD = "Aucun rapport saisi"
    
    # ==========================================================
    # DÉTERMINATION DU CAS POUR C/F
    # ==========================================================
   # ==========================================================
    # DÉTERMINATION DU CAS POUR C/F (2 familles seulement : seuil unique à 1.5 D)
    # ==========================================================
    if rapport_CF > 0:
        if rapport_CF <= 1.5:
            cas_CF = "Cas 0"
        else:
            cas_CF = "Cas 1"
    else:
        cas_CF = "Aucun rapport saisi"
    
    # Mettre à jour les labels dans la popup
    if dpg.does_item_exist("label_BD_cas"):
        dpg.set_value("label_BD_cas", cas_BD)
    if dpg.does_item_exist("label_CF_cas"):
        dpg.set_value("label_CF_cas", cas_CF)
    
"""Sauvegarde toutes les infos et exporte le rapport"""
def sauvegarder_export_complet(sender, app_data):
    global pdf_chrono, pdf_revision, pdf_ref_gdg, pdf_carte
    global canal_plus_use_BD_nom, canal_plus_use_BD_cas, canal_plus_use_BD_rapport
    global canal_plus_use_CF_nom, canal_plus_use_CF_cas, canal_plus_use_CF_rapport
    global nom_dossier, nom_fichier
    
    # Récupérer les valeurs de la popup
    pdf_chrono = dpg.get_value("pdf_chrono")
    pdf_revision = dpg.get_value("pdf_revision")
    pdf_ref_gdg = dpg.get_value("pdf_ref_gdg")
    pdf_carte = dpg.get_value("pdf_carte")
    canal_plus_use_BD_nom = dpg.get_value("input_BD_nom")
    canal_plus_use_BD_rapport = dpg.get_value("input_BD_rapport")
    canal_plus_use_CF_nom = dpg.get_value("input_CF_nom")
    canal_plus_use_CF_rapport = dpg.get_value("input_CF_rapport")
    
    # ==========================================================
    # CALCULER LES CAS AUTOMATIQUEMENT
    # ==========================================================
    try:
        val_BD = canal_plus_use_BD_rapport.replace(",", ".")
        rapport_BD = float(val_BD) if val_BD else 0
    except ValueError:
        rapport_BD = 0
    
    try:
        val_CF = canal_plus_use_CF_rapport.replace(",", ".")
        rapport_CF = float(val_CF) if val_CF else 0
    except ValueError:
        rapport_CF = 0
    
    # Cas B/D
    if rapport_BD > 0:
        if rapport_BD <= 1.5:
            canal_plus_use_BD_cas = "Cas 0"
        elif rapport_BD <= 2.0:
            canal_plus_use_BD_cas = "Cas 1"
        elif rapport_BD <= 2.5:
            canal_plus_use_BD_cas = "Cas 2"
        else:
            canal_plus_use_BD_cas = "Cas 3"
    else:
        canal_plus_use_BD_cas = ""
    
    # Cas C/F (2 familles seulement : seuil unique à 1.5 D)
    if rapport_CF > 0:
        if rapport_CF <= 1.5:
            canal_plus_use_CF_cas = "Cas 0"
        else:
            canal_plus_use_CF_cas = "Cas 1"
    else:
        canal_plus_use_CF_cas = ""
    
    dpg.delete_item("popup_export_complet")
    
    # Construction du nom du fichier
    nom_fichier = ""
    if info_affaire:
        nom_fichier = info_affaire
    if nom_fichier:
        nom_fichier = f"{nom_fichier}_PVG"
    else:
        nom_fichier = "PVG"
    if pdf_chrono:
        nom_fichier = f"{nom_fichier}_{pdf_chrono}"
    if pdf_revision:
        nom_fichier = f"{nom_fichier}_{pdf_revision}"
    if not nom_fichier or nom_fichier == "PVG": 
        #region heeere 
        nom_fichier = f"PVG_CAMVIS_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    caracteres_interdits = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for c in caracteres_interdits:
        nom_fichier = nom_fichier.replace(c, '_')
    
    nom_dossier = os.path.join(dossier_export, nom_fichier)
    os.makedirs(nom_dossier, exist_ok=True)
    
    dpg.configure_item("statut", color=(0, 255, 0))
    dpg.set_value("statut", "Export en cours...")
    
    exporter_rapport_complet()

# ─────────────────────────────────────────
# region INTERFACE
# ─────────────────────────────────────────
dpg.create_context()

with dpg.texture_registry():
    pass

with dpg.file_dialog(tag="dialogue_fichier", callback=callback_fichier, show=False, width=600, height=400):
    dpg.add_file_extension(".bmp")
    dpg.add_file_extension(".jpg")
    dpg.add_file_extension(".png")
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
    dpg.add_button(label="Informations rapport", callback=ouvrir_popup_infos, width=235)

    with dpg.group(horizontal=True):
        with dpg.child_window(width=260, height=1000):
            dpg.add_text("Image", color=(200, 200, 200))
            dpg.add_combo(items=["CAM_GDG_v1_eau", "CAM_GDG_v1_air"], default_value="CAM_GDG_v1_eau",
                         label="Camera", callback=calibrate, tag="camera")
            dpg.add_button(label="Charger une image", callback=charger_image, width=235)
            dpg.add_spacer(height=4)

            dpg.add_separator()
            dpg.add_text("Dessin", color=(200, 200, 200))
            dpg.add_button(label="Dessiner un cercle",
                           tag="btn_draw", callback=toggle_draw_mode_cercle, width=235)
            dpg.add_button(label="Supprimer un cercle",
                           callback=supprimer_cercle_par_nom, width=235)
            dpg.add_button(label="Effacer tous les cercles",
                           callback=clear_cercles, width=235)
            dpg.add_spacer(height=8)
            dpg.add_button(label="Dessiner un segment",
                           tag="btn_draw_sgt", callback=toggle_draw_mode_segment, width=235)
            dpg.add_button(label="Supprimer un segment",
                           callback=supprimer_segment_par_nom, width=235)
            dpg.add_button(label="Effacer tous les segments",
                           callback=clear_segments, width=235)
            dpg.add_spacer(height=8)
            dpg.add_button(label="Definir comme reference (Canal A)",
                           callback=definir_reference, width=235)
            dpg.add_button(label="Reinitialiser reference",
                           callback=reset_reference, width=235)

            dpg.add_spacer(height=8)

            dpg.add_separator()
            dpg.add_spacer(height=8)
            dpg.add_text("Statut :", color=(255, 255, 255))
            dpg.add_text("Pret", tag="statut", color=(100, 255, 100), wrap=235)

            #dpg.add_separator()
            #dpg.add_spacer(height=8)
            #dpg.add_text("Resultats :", color=(255, 255, 255))
            #dpg.add_spacer(height=4)
           # with dpg.table(tag="table_resultats", header_row=True,
                           #borders_innerH=True, borders_outerH=True,
                           #borders_innerV=True, borders_outerV=True,
                           #row_background=True, width=300):
                #dpg.add_table_column(label="Nom", width_fixed=True, init_width_or_weight=50)
                #dpg.add_table_column(label="Rapport", width_fixed=True, init_width_or_weight=50)
                #dpg.add_table_column(label="Cas", width_fixed=True, init_width_or_weight=50)
                #dpg.add_table_column(label="Type", width_fixed=True, init_width_or_weight=70)

            dpg.add_separator()
            dpg.add_text("Export", color=(200, 200, 200))
            dpg.add_button(label="Ouvrir dossier", callback=ouvrir_dossier, width=235)
            dpg.add_button(label="Exporter rapport", callback=ouvrir_popup_export_complet, width=235)

        with dpg.child_window(width=1640, height=1000):
            with dpg.drawlist(width=W, height=H, tag="drawlist_principal"):
                dpg.draw_rectangle((0, 0), (W, H), fill=(40, 40, 40))
                dpg.draw_text((W//2 - 180, H//2),
                              "Chargez une image pour commencer",
                              color=(130, 130, 130), size=18)

charger_canaux()
calibrate()
dpg.bind_theme(theme_principal)
dpg.create_viewport(title=f"CAMVIS WHE Instrumentation {version}", width=1920, height=1080)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("fenetre_principale", True)
ouvrir_popup_infos()
dpg.start_dearpygui()
dpg.destroy_context()
