import pyautogui
import re
import time


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _click_imagen(nombre_img: str, confidence: float = 0.8, timeout: float = 5.0):
    """
    Busca y hace click en una imagen en pantalla.
    Reintenta durante `timeout` segundos antes de lanzar una excepción.
    """
    inicio = time.time()
    while True:
        pos = pyautogui.locateCenterOnScreen(nombre_img, confidence=confidence)
        if pos is not None:
            pyautogui.click(pos)
            return pos
        if time.time() - inicio > timeout:
            raise RuntimeError(f"No se encontró '{nombre_img}' en pantalla.")
        time.sleep(0.3)


# ─── Funciones principales ───────────────────────────────────────────────────

def cargarCabecera(orden, chasis, recepcion, kilometraje, reparacion, codigo, data):
    if not data:
        raise ValueError("data no puede ser None o vacío.")

    cabecera_obj = data[0].get("cabecera", {})

    _click_imagen("img/taller.png")
    pyautogui.press("down")
    pyautogui.press("enter")
    pyautogui.press("tab")


    _click_imagen("img/n-reclamacion.png")
    pyautogui.write(orden, interval=0.05)
    pyautogui.press("tab")
    pyautogui.write(cabecera_obj.get("tipo", ""), interval=0.05)

    _click_imagen("img/bastidor.png")
    pyautogui.write(chasis, interval=0.05)

    _click_imagen("img/recepcion.png")
    pyautogui.write(recepcion, interval=0.05)

    pyautogui.press("tab", presses=2, interval=0.05)
    pyautogui.write(kilometraje, interval=0.05)

    _click_imagen("img/at.png")
    pyautogui.write(cabecera_obj.get("at", ""), interval=0.05)

    pyautogui.press("tab")
    pyautogui.write(cabecera_obj.get("defecto", ""), interval=0.05)

    ubicacion = cabecera_obj.get("ubicacion", "")
    if ubicacion:
        pyautogui.write(ubicacion, interval=0.05)
    else:
        pyautogui.press("tab")

    pyautogui.write(reparacion, interval=0.05)

    criterio = cabecera_obj.get("criterio", "")
    if criterio:
        criterios = re.split(r"\s", criterio)
        pos_criterio = _click_imagen("img/criterio.png")
        for cr in criterios:
            pyautogui.click(pos_criterio)
            pyautogui.write(cr, interval=0.05)
            time.sleep(1)
            pyautogui.press("enter")

    _click_imagen("img/proveedor.png")
    pyautogui.write(cabecera_obj.get("proveedor", ""), interval=0.05)

    _click_imagen("img/comentarios.png")
    pyautogui.write(cabecera_obj.get("comentarios", ""), interval=0.03)


def cargarLocal(data):
    if not data:
        return

    objeto = data[1]
    if "local" not in objeto:
        return

    _click_imagen("img/local.png")

    # Mano de obra local
    for op in objeto["local"].get("mo", []):
        _click_imagen("img/entrada1.png")
        if op.get("causal") == 1:
            _click_imagen("img/causal-local.png")
        pyautogui.write(op["operacion"], interval=0.05)
        pyautogui.press("tab", presses=3, interval=0.05)
        pyautogui.write(op["ut"], interval=0.05)
        pyautogui.press("enter")

    # Material local
    for pieza in objeto["local"].get("material", []):
        _click_imagen("img/entrada2.png", confidence=0.9)
        if pieza.get("causal") == 1:
            _click_imagen("img/causal-local.png")
        pyautogui.write(pieza["codigo"], interval=0.05)
        pyautogui.press("tab")
        pyautogui.write(pieza["cantidad"], interval=0.05)
        pyautogui.press("enter")


def cargarTercero(data):
    if not data:
        return

    # Soporta data con 2 o 3 elementos
    objeto = data[2] if len(data) == 3 else data[1]

    if "tercero" not in objeto:
        return

    _click_imagen("img/tercero.png")

    # MO externa
    for op in objeto["tercero"].get("emo", []):
        _click_imagen("img/entrada3.png", confidence=0.7)
        if op.get("causal") == 1:
            _click_imagen("img/causal-local.png")
        pyautogui.write(op["operacion"], interval=0.05)
        pyautogui.press("enter", interval=0.05)
        pyautogui.write(op["importe"], interval=0.05)
        pyautogui.press("enter")

    # Material externo
    for pieza in objeto["tercero"].get("ematerial", []):
        _click_imagen("img/entrada4.png", confidence=0.9)
        if pieza.get("causal") == 1:
            _click_imagen("img/causal-local.png")
        pyautogui.write(pieza["codigo"], interval=0.05)
        pyautogui.press("tab")
        pyautogui.write(pieza.get("comentario", ""), interval=0.05)
        pyautogui.press("tab")
        pyautogui.write(pieza["cantidad"], interval=0.05)
        pyautogui.press("enter")
        pyautogui.press("enter")
        pyautogui.press("down", presses=3)
        pyautogui.press("enter")
        pyautogui.press("enter")
        pyautogui.write(pieza["importe"], interval=0.05)
        pyautogui.press("enter")
