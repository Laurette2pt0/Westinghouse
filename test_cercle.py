#création de cercle avec la souris
#1clique gauche pour sélectionner le milieu du cercle
#2glisser la souris pour redimansionner le cercle
#3clique droit pour valider

import dearpygui.dearpygui as dpg
import math

dpg.create_context()

circles_data = {}
drawing_state = {
    "active": False,
    "center": None,
    "preview_tag": None,
    "count": 0
}

def get_mouse_pos_on_canvas():
    mouse_pos = dpg.get_mouse_pos(local=False)
    canvas_pos = dpg.get_item_rect_min("canvas")
    x = mouse_pos[0] - canvas_pos[0]
    y = mouse_pos[1] - canvas_pos[1]
    return x, y

def on_mouse_down(sender, app_data):
    print(f"on_mouse_down : {app_data}")
    #print(f"return appdata = {app_data} and {type(app_data[0])}")
    if not dpg.is_item_hovered("canvas"):
        return
    if app_data[0] != 0:  # Bouton gauche uniquement
        print(f"return appdata = {app_data} and {type(app_data[0])} so {app_data[0]==0}")
        return

    x, y = get_mouse_pos_on_canvas()
    drawing_state["active"] = True
    drawing_state["center"] = (x, y)

    # Créer un cercle de prévisualisation
    preview_tag = f"preview_circle"
    if dpg.does_item_exist(preview_tag):
        dpg.delete_item(preview_tag)

    dpg.draw_circle(
        center=(x, y), radius=1,
        color=(255, 200, 0, 180), thickness=2,
        tag=preview_tag, parent="canvas"
    )
    drawing_state["preview_tag"] = preview_tag

def on_mouse_move(sender, app_data):
    if not drawing_state["active"]:
        return

    x, y = get_mouse_pos_on_canvas()
    cx, cy = drawing_state["center"]
    radius = max(1, math.sqrt((x - cx)**2 + (y - cy)**2))

    preview_tag = drawing_state["preview_tag"]
    if dpg.does_item_exist(preview_tag):
        dpg.configure_item(preview_tag, center=(cx, cy), radius=radius)

    dpg.set_value("info_text",
        f"Prévisualisation — Centre: ({int(cx)}, {int(cy)}) | Rayon: {int(radius)} | Diamètre: {int(radius*2)}")

def on_mouse_release(sender, app_data):
    print(f"appdata mouse realse= {app_data}")
    if not drawing_state["active"]:
        return
    if app_data == 0:
        return

    drawing_state["active"] = False
    x, y = get_mouse_pos_on_canvas()
    cx, cy = drawing_state["center"]
    radius = max(1, math.sqrt((x - cx)**2 + (y - cy)**2))

    # Supprimer la prévisualisation
    if dpg.does_item_exist("preview_circle"):
        dpg.delete_item("preview_circle")

    # Créer le cercle définitif
    count = drawing_state["count"]
    tag = f"circle_{count}"
    drawing_state["count"] += 1

    dpg.draw_circle(
        center=(cx, cy), radius=radius,
        color=(0, 200, 100, 255), thickness=2,
        tag=tag, parent="canvas"
    )
    circles_data[tag] = {"center": (cx, cy), "radius": radius}

    dpg.set_value("info_text",
        f"✅ [{tag}] Centre: ({int(cx)}, {int(cy)}) | Rayon: {int(radius)} | Diamètre: {int(radius*2)}")

def clear_canvas():
    for tag in list(circles_data.keys()):
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)
    circles_data.clear()
    drawing_state["count"] = 0
    dpg.set_value("info_text", "Canvas effacé.")

with dpg.handler_registry():
    dpg.add_mouse_down_handler(callback=on_mouse_down)
    dpg.add_mouse_move_handler(callback=on_mouse_move)
    dpg.add_mouse_release_handler(callback=on_mouse_release)

with dpg.window(label="Dessin de cercles", width=720, height=540, tag="main_window"):
    dpg.add_text("🖱 Clic gauche + glisser pour dessiner un cercle")
    dpg.add_button(label="🗑 Effacer tout", callback=clear_canvas)
    dpg.add_text("", tag="info_text")

    with dpg.drawlist(width=700, height=450, tag="canvas"):
        pass

dpg.create_viewport(title="Cercles à la souris", width=740, height=580)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()