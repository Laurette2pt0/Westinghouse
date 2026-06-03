import dearpygui.dearpygui as dpg
import cv2
import numpy as np

# Variable globale
chemin_image_actuelle = None

# ─────────────────────────────────────────
# CALLBACKS
# ─────────────────────────────────────────

def afficher_image(chemin):
    img = cv2.imread(chemin)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
    img = cv2.resize(img, (810, 440))
    img_flat = img.flatten().astype(np.float32) / 255.0

    if dpg.does_item_exist("texture_image"):
        dpg.delete_item("texture_image")
    if dpg.does_item_exist("affichage_image"):
        dpg.delete_item("affichage_image")

    with dpg.texture_registry():
        dpg.add_dynamic_texture(810, 440, img_flat, tag="texture_image")

    dpg.add_image("texture_image", tag="affichage_image", parent="zone_image")
    dpg.set_value("statut", "Statut : Image chargee")

def callback_fichier(sender, app_data):
    global chemin_image_actuelle
    chemin_image_actuelle = app_data["file_path_name"]
    afficher_image(chemin_image_actuelle)

def charger_image():
    dpg.show_item("dialogue_fichier")

def lancer_calibration():
    dpg.set_value("statut", "Statut : Calibration en cours...")

def lancer_mesure():
    global chemin_image_actuelle

    if chemin_image_actuelle is None:
        dpg.set_value("statut", "Statut : Chargez une image d'abord !")
        return

    dpg.set_value("statut", "Statut : Detection des trous en cours...")

    # Charger l'image
    image = cv2.imread(chemin_image_actuelle)
    image_affichage = image.copy()

    # Convertir en niveaux de gris
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Flouter pour réduire le bruit
    gris_flou = cv2.GaussianBlur(gris, (9, 9), 2)

    # Détecter les cercles avec HoughCircles
    cercles = cv2.HoughCircles(
        gris_flou,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=30,
        param1=80,
        param2=35,
        minRadius=10,
        maxRadius=200
    )

    nb_trous = 0

    if cercles is not None:
        cercles = np.round(cercles[0, :]).astype("int")
        nb_trous = len(cercles)

        for (x, y, r) in cercles:
            # Dessiner le cercle en vert
            cv2.circle(image_affichage, (x, y), r, (0, 255, 0), 2)
            # Dessiner le centre en rouge
            cv2.circle(image_affichage, (x, y), 4, (0, 0, 255), -1)
            # Écrire le diamètre en pixels
            cv2.putText(
                image_affichage,
                f"D={r*2}px",
                (x - 30, y - r - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

    # Afficher l'image annotée dans l'interface
    image_rgba = cv2.cvtColor(image_affichage, cv2.COLOR_BGR2RGBA)
    image_rgba = cv2.resize(image_rgba, (810, 440))
    img_flat = image_rgba.flatten().astype(np.float32) / 255.0

    if dpg.does_item_exist("texture_image"):
        dpg.delete_item("texture_image")
    if dpg.does_item_exist("affichage_image"):
        dpg.delete_item("affichage_image")

    with dpg.texture_registry():
        dpg.add_dynamic_texture(810, 440, img_flat, tag="texture_image")

    dpg.add_image("texture_image", tag="affichage_image", parent="zone_image")

    # Afficher les résultats
    if cercles is not None:
        diametre_moyen = int(np.mean([r * 2 for (x, y, r) in cercles]))
        diametre_max   = int(np.max([r * 2 for (x, y, r) in cercles]))
        diametre_min   = int(np.min([r * 2 for (x, y, r) in cercles]))
        dpg.set_value("resultat_distance",    f"Trous detectes : {nb_trous}")
        dpg.set_value("resultat_diametre",    f"Diametre moyen : {diametre_moyen} px")
        dpg.set_value("resultat_incertitude", f"Min : {diametre_min}px  Max : {diametre_max}px")
        dpg.set_value("statut", f"Statut : {nb_trous} trou(s) detecte(s)")
    else:
        dpg.set_value("resultat_distance",    "Trous detectes : 0")
        dpg.set_value("resultat_diametre",    "Diametre moyen : -- px")
        dpg.set_value("resultat_incertitude", "Aucun cercle trouve")
        dpg.set_value("statut", "Statut : Aucun trou detecte")

def exporter_rapport():
    dpg.set_value("statut", "Statut : Rapport exporte")

# ─────────────────────────────────────────
# CREATION
# ─────────────────────────────────────────

dpg.create_context()

with dpg.file_dialog(tag="dialogue_fichier", callback=callback_fichier, show=False, width=600, height=400):
    dpg.add_file_extension(".jpg")
    dpg.add_file_extension(".png")
    dpg.add_file_extension(".bmp")

with dpg.theme() as theme_principal:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_WindowBg,       (50, 50, 50))
        dpg.add_theme_color(dpg.mvThemeCol_ChildBg,        (60, 60, 60))
        dpg.add_theme_color(dpg.mvThemeCol_PopupBg,        (55, 55, 55))
        dpg.add_theme_color(dpg.mvThemeCol_Text,           (255, 255, 255))
        dpg.add_theme_color(dpg.mvThemeCol_Button,         (80, 80, 80))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered,  (100, 100, 100))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,   (120, 120, 120))
        dpg.add_theme_color(dpg.mvThemeCol_Separator,      (120, 120, 120))
        dpg.add_theme_color(dpg.mvThemeCol_Border,         (100, 100, 100))
        dpg.add_theme_color(dpg.mvThemeCol_FrameBg,        (70, 70, 70))
        dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (90, 90, 90))
        dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive,  (110, 110, 110))
        dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg,    (50, 50, 50))
        dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab,  (100, 100, 100))
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding,  6)
        dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)
        dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing,    8, 6)

with dpg.window(tag="fenetre_principale", label="", width=1100, height=700, no_title_bar=True):

    dpg.add_text("CAMVIS - Logiciel d'Analyse Dimensionnelle par Vision", color=(255, 255, 255))
    dpg.add_text("WHE - Equipe Instrumentation & Vision", color=(200, 200, 200))
    dpg.add_separator()
    dpg.add_spacer(height=5)

    with dpg.group(horizontal=True):

        with dpg.child_window(tag="panneau_gauche", width=250, height=570):

            dpg.add_text("Camera", color=(255, 255, 255))
            dpg.add_separator()
            dpg.add_input_text(tag="id_camera", label="ID Camera", default_value="CAM-001", width=150)
            dpg.add_spacer(height=8)

            dpg.add_text("Image", color=(255, 255, 255))
            dpg.add_separator()
            dpg.add_button(tag="btn_charger", label="  Charger une image  ", callback=charger_image, width=220)
            dpg.add_spacer(height=8)

            dpg.add_text("Calibration", color=(255, 255, 255))
            dpg.add_separator()
            dpg.add_text("Etalon : disque 60 mm", color=(220, 220, 220))
            dpg.add_button(tag="btn_calibration", label="  Lancer la calibration  ", callback=lancer_calibration, width=220)
            dpg.add_spacer(height=8)

            dpg.add_text("Mesure", color=(255, 255, 255))
            dpg.add_separator()
            dpg.add_radio_button(tag="type_mesure", items=("Distance", "Diametre"), horizontal=False)
            dpg.add_spacer(height=5)
            dpg.add_button(tag="btn_mesure", label="  Lancer la mesure  ", callback=lancer_mesure, width=220)
            dpg.add_spacer(height=10)

            dpg.add_text("Export", color=(255, 255, 255))
            dpg.add_separator()
            dpg.add_button(tag="btn_export", label="  Exporter PDF / CSV  ", callback=exporter_rapport, width=220)

        dpg.add_spacer(width=10)

        with dpg.group(tag="zone_droite"):

            with dpg.child_window(tag="zone_image", width=820, height=460):
                dpg.add_text("[ Chargez une image pour commencer ]", tag="texte_placeholder", color=(150, 150, 150))

            dpg.add_spacer(height=8)

            with dpg.child_window(tag="zone_resultats", width=820, height=95):
                dpg.add_text("Resultats de mesure", color=(255, 255, 255))
                dpg.add_separator()
                with dpg.group(horizontal=True):
                    dpg.add_text("Trous detectes : --", tag="resultat_distance",    color=(255, 255, 255))
                    dpg.add_spacer(width=40)
                    dpg.add_text("Diametre moyen : --", tag="resultat_diametre",    color=(255, 255, 255))
                    dpg.add_spacer(width=40)
                    dpg.add_text("Min / Max : --",      tag="resultat_incertitude", color=(255, 255, 255))

    dpg.add_spacer(height=5)
    dpg.add_separator()
    dpg.add_text("Statut : Pret", tag="statut", color=(255, 255, 255))

# ─────────────────────────────────────────
# LANCEMENT
# ─────────────────────────────────────────

dpg.bind_theme(theme_principal)
dpg.create_viewport(title="CAMVIS", width=1100, height=700)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("fenetre_principale", True)
dpg.start_dearpygui()
dpg.destroy_context()