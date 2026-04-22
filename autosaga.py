import constantes as const
import pyautogui
import funciones
import historial
import tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime
import json
import threading
import time
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi


# ─── Paleta de colores ───────────────────────────────────────────────────────
BG        = "#1e1e2e"
BG_PANEL  = "#2a2a3e"
ACCENT    = "#7c6af7"
FG        = "#e0e0f0"
FG_DIM    = "#8888aa"
RED       = "#f28b82"
GREEN     = "#81c995"
YELLOW    = "#f9c74f"
ENTRY_BG  = "#13131f"
BTN_BG    = "#3a3a5c"
BTN_HOV   = "#4e4e7a"

FONT_LABEL = ("Segoe UI", 9)
FONT_ENTRY = ("Consolas", 10)
FONT_BTN   = ("Segoe UI Semibold", 9)
FONT_SMALL = ("Segoe UI", 8)
FONT_MONO  = ("Consolas", 8)


# ─── Helpers de transformación ───────────────────────────────────────────────

def transformar_orden(orden: str) -> str:
    """
    Aplica prefijo/infijo según el primer dígito de la orden:
      2... →  0 adelante       ej: 214103 → 0214103
      3... →  0 después del 3  ej: 312456 → 3012456
      4... →  0 después del 4  ej: 498765 → 4098765
      5... →  1 antes del 5    ej: 567890 → 1567890
      6... →  2 antes del 6    ej: 623001 → 2623001
    """
    if not orden:
        return orden
    primer = orden[0]
    resto  = orden[1:]
    if primer == "2":
        return "0" + orden
    elif primer == "3":
        return "3" + "0" + resto
    elif primer == "4":
        return "4" + "0" + resto
    elif primer == "5":
        return "1" + orden
    elif primer == "6":
        return "2" + orden
    return orden


# ─── Widgets reutilizables ────────────────────────────────────────────────────

class StyledEntry(tk.Entry):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            justify="center",
            bg=ENTRY_BG,
            fg=FG,
            insertbackground=ACCENT,
            relief="flat",
            font=FONT_ENTRY,
            highlightthickness=1,
            highlightbackground=BG_PANEL,
            highlightcolor=ACCENT,
            **kwargs,
        )

    def set(self, value: str):
        self.delete(0, "end")
        self.insert(0, value)


class StyledButton(tk.Button):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            bg=BTN_BG,
            fg=FG,
            activebackground=BTN_HOV,
            activeforeground=FG,
            relief="flat",
            cursor="hand2",
            font=FONT_BTN,
            padx=10,
            pady=5,
            **kwargs,
        )
        self.bind("<Enter>", lambda _: self.config(bg=BTN_HOV))
        self.bind("<Leave>", lambda _: self.config(bg=BTN_BG))


class AutocompleteEntry(StyledEntry):
    """Entry con dropdown de sugerencias."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._opciones: list[str] = []
        self._toplevel: tk.Toplevel | None = None
        self._listbox: tk.Listbox | None = None
        self.bind("<KeyRelease>", self._on_keyrelease)
        self.bind("<FocusOut>", self._cerrar_dropdown)
        self.bind("<Escape>", self._cerrar_dropdown)

    def set_opciones(self, opciones: list[str]):
        self._opciones = sorted(opciones)

    def _on_keyrelease(self, event):
        if event.keysym in ("Down", "Up", "Return", "Escape", "Tab"):
            if event.keysym == "Down" and self._listbox:
                self._listbox.focus_set()
                self._listbox.selection_set(0)
            return

        texto = self.get().strip().lower()
        if not texto:
            self._cerrar_dropdown()
            return

        coincidencias = [o for o in self._opciones if o.lower().startswith(texto)]
        if coincidencias:
            self._mostrar_dropdown(coincidencias)
        else:
            self._cerrar_dropdown()

    def _mostrar_dropdown(self, opciones: list[str]):
        self._cerrar_dropdown(None)
        self._toplevel = tk.Toplevel(self)
        self._toplevel.wm_overrideredirect(True)
        self._toplevel.configure(bg=BG_PANEL)

        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        w = self.winfo_width()
        alto = min(len(opciones), 6) * 20
        self._toplevel.geometry(f"{w}x{alto}+{x}+{y}")

        self._listbox = tk.Listbox(
            self._toplevel, bg=BG_PANEL, fg=FG,
            selectbackground=ACCENT, selectforeground="#fff",
            relief="flat", font=FONT_MONO, borderwidth=0, highlightthickness=0,
        )
        self._listbox.pack(fill="both", expand=True)
        for op in opciones:
            self._listbox.insert("end", op)

        self._listbox.bind("<Return>", self._seleccionar)
        self._listbox.bind("<Double-Button-1>", self._seleccionar)
        self._listbox.bind("<Escape>", self._cerrar_dropdown)

    def _seleccionar(self, event=None):
        if self._listbox:
            idx = self._listbox.curselection()
            if idx:
                self.set(self._listbox.get(idx))
        self._cerrar_dropdown()
        self.focus_set()

    def _cerrar_dropdown(self, event=None):
        if self._toplevel:
            self._toplevel.destroy()
            self._toplevel = None
            self._listbox = None


# ─── Aplicación principal ─────────────────────────────────────────────────────

class MyApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AutoSAGA")
        self.root.geometry("360x590")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.templates: dict = {}
        self._procesando = False
        self._datos_multi: list[dict] = []

        historial.inicializar()
        self._build_ui()
        self._connect_mongo_async()
        self._update_timer()

    # ─── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        tk.Label(self.root, text="AutoSAGA", bg=BG, fg=ACCENT,
                 font=("Segoe UI Black", 16)).pack(pady=(14, 0))
        tk.Label(self.root, text="Sistema de carga automatizada", bg=BG,
                 fg=FG_DIM, font=FONT_SMALL).pack()
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=20, pady=8)

        style = ttk.Style()
        style.theme_use("clam")
        for w in ("TNotebook", "TFrame"):
            style.configure(w, background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG_PANEL, foreground=FG_DIM,
                        padding=[12, 5], font=FONT_LABEL)
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#ffffff")])

        self.panel = ttk.Notebook(self.root)
        self.panel.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        tab1 = tk.Frame(self.panel, bg=BG)
        self.panel.add(tab1, text="  Unitaria  ")

        tab2 = tk.Frame(self.panel, bg=BG)
        self.panel.add(tab2, text="  Múltiple  ")

        tab3 = tk.Frame(self.panel, bg=BG)
        self.panel.add(tab3, text="  Historial  ")

        self._build_unitaria(tab1)
        self._build_multiple(tab2)
        self._build_historial(tab3)

    def _field(self, parent, texto: str, entry_class=None) -> StyledEntry:
        if entry_class is None:
            entry_class = StyledEntry
        tk.Label(parent, text=texto, bg=BG, fg=FG_DIM,
                 font=FONT_LABEL, anchor="w").pack(fill="x", padx=18, pady=(6, 1))
        entry = entry_class(parent)
        entry.pack(fill="x", padx=18, ipady=4)
        return entry

    def _build_unitaria(self, parent):
        self.e_orden       = self._field(parent, "Orden")
        self.e_chasis      = self._field(parent, "Chasis")
        self.e_recepcion   = self._field(parent, "Fecha recepción")
        self.e_kilometraje = self._field(parent, "Kilometraje")
        self.e_reparacion  = self._field(parent, "Fecha reparación")

        tk.Label(parent, text="Código", bg=BG, fg=FG_DIM,
                 font=FONT_LABEL, anchor="w").pack(fill="x", padx=18, pady=(6, 1))
        self.e_codigo = AutocompleteEntry(parent)
        self.e_codigo.pack(fill="x", padx=18, ipady=4)
        self.e_codigo.bind("<KeyRelease>", self._actualizar_preview)

        self.preview_label = tk.Label(parent, text="", bg=BG, fg=GREEN,
                                      font=FONT_SMALL, anchor="w")
        self.preview_label.pack(fill="x", padx=18)

        self.status_label = tk.Label(parent, text="", bg=BG, fg=RED,
                                     font=FONT_SMALL, wraplength=300)
        self.status_label.pack(pady=(4, 0))

        bf1 = tk.Frame(parent, bg=BG)
        bf1.pack(pady=6, fill="x", padx=18)
        self.btn_reclamar = StyledButton(bf1, text="▶  Reclamar",
                                         command=self._reclamar, state="disabled")
        self.btn_reclamar.pack(side="left", expand=True, fill="x", padx=(0, 4))
        StyledButton(bf1, text="✕  Borrar", command=self._borrar).pack(
            side="left", expand=True, fill="x", padx=(4, 0))

        bf2 = tk.Frame(parent, bg=BG)
        bf2.pack(fill="x", padx=18, pady=(0, 4))
        StyledButton(bf2, text="📂  Cargar JSON", command=self._cargar_json).pack(fill="x")

        footer = tk.Frame(parent, bg=BG)
        footer.pack(fill="x", padx=18, pady=(6, 2))
        self.conn_label = tk.Label(footer, text="⏳  Conectando...", bg=BG,
                                   fg=FG_DIM, font=FONT_SMALL, anchor="w")
        self.conn_label.pack(side="left")
        self.timer_label = tk.Label(footer, text="", bg=BG, fg=FG_DIM,
                                    font=FONT_SMALL, anchor="e")
        self.timer_label.pack(side="right")
        tk.Label(parent, text="© JPsoft", bg=BG, fg=FG_DIM, font=FONT_SMALL).pack(pady=(0, 6))

    def _build_multiple(self, parent):
        tk.Label(parent, text="Carga múltiple desde JSON",
                 bg=BG, fg=FG_DIM, font=FONT_LABEL).pack(pady=(16, 4))
        tk.Label(parent,
                 text="El archivo debe contener un array de objetos\ncon los mismos campos que la carga unitaria.",
                 bg=BG, fg=FG_DIM, font=FONT_SMALL, justify="center").pack(pady=(0, 8))

        frame_lista = tk.Frame(parent, bg=BG_PANEL, highlightthickness=1,
                               highlightbackground=BTN_BG)
        frame_lista.pack(fill="both", expand=True, padx=18, pady=(0, 8))

        self.lista_multi = tk.Listbox(
            frame_lista, bg=BG_PANEL, fg=FG, selectbackground=ACCENT,
            relief="flat", font=FONT_MONO, borderwidth=0, highlightthickness=0,
        )
        scroll = ttk.Scrollbar(frame_lista, orient="vertical",
                               command=self.lista_multi.yview)
        self.lista_multi.config(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.lista_multi.pack(fill="both", expand=True, padx=4, pady=4)

        self.status_multi = tk.Label(parent, text="", bg=BG, fg=FG_DIM,
                                     font=FONT_SMALL, wraplength=300)
        self.status_multi.pack()

        bf = tk.Frame(parent, bg=BG)
        bf.pack(fill="x", padx=18, pady=(4, 10))
        StyledButton(bf, text="📂  Seleccionar JSON",
                     command=self._cargar_json_multiple).pack(
            side="left", expand=True, fill="x", padx=(0, 4))
        self.btn_reclamar_multi = StyledButton(
            bf, text="▶  Procesar todo",
            command=self._reclamar_multiples, state="disabled")
        self.btn_reclamar_multi.pack(side="left", expand=True, fill="x", padx=(4, 0))

    def _build_historial(self, parent):
        tk.Label(parent, text="Historial de reclamos", bg=BG, fg=FG_DIM,
                 font=FONT_LABEL).pack(pady=(12, 6))

        frame_tree = tk.Frame(parent, bg=BG)
        frame_tree.pack(fill="both", expand=True, padx=12)

        style = ttk.Style()
        style.configure("Hist.Treeview", background=BG_PANEL, foreground=FG,
                        fieldbackground=BG_PANEL, rowheight=22, font=FONT_MONO,
                        borderwidth=0)
        style.configure("Hist.Treeview.Heading", background=BTN_BG, foreground=FG,
                        font=FONT_LABEL, relief="flat")
        style.map("Hist.Treeview", background=[("selected", ACCENT)])

        cols = ("fecha", "orden", "codigo", "resultado")
        self.tree = ttk.Treeview(frame_tree, columns=cols, show="headings",
                                 style="Hist.Treeview", selectmode="browse")
        for col, ancho, txt in zip(cols, (120, 70, 60, 55),
                                   ("Fecha", "Orden", "Código", "Estado")):
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=ancho, anchor="center")

        scroll_tree = ttk.Scrollbar(frame_tree, orient="vertical",
                                    command=self.tree.yview)
        self.tree.config(yscrollcommand=scroll_tree.set)
        scroll_tree.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        bf = tk.Frame(parent, bg=BG)
        bf.pack(fill="x", padx=12, pady=6)
        StyledButton(bf, text="🔄  Actualizar",
                     command=self._cargar_historial).pack(
            side="left", expand=True, fill="x", padx=(0, 4))
        StyledButton(bf, text="🗑  Limpiar todo",
                     command=self._limpiar_historial).pack(
            side="left", expand=True, fill="x", padx=(4, 0))

        self._cargar_historial()

    # ─── MongoDB ──────────────────────────────────────────────────────────────

    def _connect_mongo_async(self):
        threading.Thread(target=self._connect_mongo, daemon=True).start()

    def _connect_mongo(self):
        try:
            uri = (
                f"mongodb+srv://{const.USER_MONGO}:{const.PASS_MONGO}"
                "@cluster0.g0ktnap.mongodb.net/?retryWrites=true&w=majority"
            )
            with MongoClient(uri, server_api=ServerApi("1"),
                             serverSelectionTimeoutMS=8000) as client:
                coleccion = list(client["work"].get_collection("templates").find({}))

            self.templates = {doc["codigo"]: doc["data"] for doc in coleccion}
            codigos = sorted(self.templates.keys())

            def _on_ok():
                self.conn_label.config(
                    text=f"✔  {len(self.templates)} templates", fg=GREEN)
                self.e_codigo.set_opciones(codigos)
                self.btn_reclamar.config(state="normal")

            self.root.after(0, _on_ok)
        except Exception:
            self.root.after(0, lambda: self.conn_label.config(
                text="✘  Sin conexión", fg=RED))

    # ─── Timer ────────────────────────────────────────────────────────────────

    TARGET_DATE = getattr(const, "TARGET_DATE", datetime(2026, 12, 31, 23, 59, 59))

    def _update_timer(self):
        remaining = self.TARGET_DATE - datetime.now()
        if remaining.total_seconds() <= 0:
            self.timer_label.config(text="Licencia expirada", fg=RED)
            self.root.after(2000, self.root.destroy)
            return
        d = remaining.days
        h, rem = divmod(remaining.seconds, 3600)
        m, s = divmod(rem, 60)
        self.timer_label.config(text=f"{d}d {h:02d}:{m:02d}:{s:02d}")
        self.root.after(1000, self._update_timer)

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, color: str = RED):
        self.status_label.config(text=msg, fg=color)

    def _actualizar_preview(self, event=None):
        codigo = self.e_codigo.get().strip()
        if codigo in self.templates:
            try:
                cab = self.templates[codigo][0]["cabecera"]
                tipo = cab.get("tipo", "—")
                at   = cab.get("at", "—")
                self.preview_label.config(
                    text=f"✔  Tipo: {tipo}  |  AT: {at}", fg=GREEN)
            except (IndexError, KeyError):
                self.preview_label.config(text="✔  Template encontrado", fg=GREEN)
        else:
            self.preview_label.config(text="")

    def _borrar(self):
        for e in (self.e_orden, self.e_chasis, self.e_recepcion,
                  self.e_kilometraje, self.e_reparacion, self.e_codigo):
            e.delete(0, "end")
        self._set_status("")
        self.preview_label.config(text="")

    def _valores_ui(self) -> dict | None:
        v = {
            "orden":       self.e_orden.get().strip(),
            "chasis":      self.e_chasis.get().strip(),
            "recepcion":   self.e_recepcion.get().strip(),
            "kilometraje": self.e_kilometraje.get().strip(),
            "reparacion":  self.e_reparacion.get().strip(),
            "codigo":      self.e_codigo.get().strip(),
        }
        if not all(v.values()):
            self._set_status("⚠  Faltan ingresar datos")
            return None
        if v["codigo"] not in self.templates:
            self._set_status(f"⚠  Código '{v['codigo']}' no encontrado")
            return None
        return v

    # ─── Carga unitaria ───────────────────────────────────────────────────────

    def _reclamar(self):
        if self._procesando:
            return
        v = self._valores_ui()
        if not v:
            return
        self._set_status("⏳  Procesando...", YELLOW)
        self.btn_reclamar.config(state="disabled")
        threading.Thread(target=self._ejecutar_reclamo, args=(v,), daemon=True).start()

    def _ejecutar_reclamo(self, v: dict):
        self._procesando = True
        data = self.templates[v["codigo"]]
        try:
            funciones.cargarCabecera(v["orden"], v["chasis"], v["recepcion"],
                                     v["kilometraje"], v["reparacion"], v["codigo"], data)
            funciones.cargarLocal(data)
            funciones.cargarTercero(data)
            pos = pyautogui.locateCenterOnScreen("img/completar.png", confidence=0.8)
              
            if pos:
                pyautogui.moveTo(pos)
                pyautogui.click()

            historial.guardar_reclamo(**v, resultado="ok")
            self.root.after(0, lambda: self._set_status("✔  Reclamo cargado correctamente", GREEN))
        except Exception as exc:
            msg = str(exc)
            historial.guardar_reclamo(**v, resultado="error", detalle=msg)
            self.root.after(0, lambda: self._set_status(f"✘  Error: {msg}"))
        finally:
            self._procesando = False
            self.root.after(0, lambda: self.btn_reclamar.config(state="normal"))
            self.root.after(0, self._cargar_historial)

    # ─── Carga múltiple ───────────────────────────────────────────────────────

    def _cargar_json_multiple(self):
        path = filedialog.askopenfilename(
            title="Seleccionar JSON con múltiples órdenes",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, dict):
                datos = [datos]

            self._datos_multi = datos
            self.lista_multi.delete(0, "end")
            for i, d in enumerate(datos, 1):
                self.lista_multi.insert(
                    "end",
                    f"  {i:02d}.  Orden {d.get('orden','?')}  |  "
                    f"{d.get('codigo','?')}  |  {d.get('chasis','?')}"
                )

            faltantes = {d.get("codigo", "") for d in datos
                         if d.get("codigo", "") not in self.templates}
            if faltantes:
                self.status_multi.config(
                    text=f"⚠  Códigos no encontrados: {', '.join(faltantes)}", fg=RED)
            else:
                self.status_multi.config(
                    text=f"✔  {len(datos)} orden(es) lista(s) para procesar", fg=GREEN)
            self.btn_reclamar_multi.config(state="normal")
        except (json.JSONDecodeError, OSError) as exc:
            self.status_multi.config(text=f"✘  Error: {exc}", fg=RED)

    def _reclamar_multiples(self):
        if self._procesando or not self._datos_multi:
            return
        self.btn_reclamar_multi.config(state="disabled")
        threading.Thread(target=self._ejecutar_multiples, daemon=True).start()

    def _ejecutar_multiples(self):
        self._procesando = True
        total = len(self._datos_multi)
        ok = 0
        errores = []

        for i, d in enumerate(self._datos_multi):
            orden       = str(d.get("orden", ""))
            chasis      = str(d.get("chasis", ""))
            recepcion   = str(d.get("apertura", ""))
            kilometraje = str(d.get("kilometraje", ""))
            reparacion  = str(d.get("cierre", ""))
            codigo      = str(d.get("codigo", ""))

            self.root.after(0, lambda j=i: self.lista_multi.itemconfig(j, fg=YELLOW))
            self.root.after(0, lambda n=i+1: self.status_multi.config(
                text=f"⏳  Procesando {n}/{total}...", fg=YELLOW))

            if codigo not in self.templates:
                errores.append(f"Orden {orden}: código '{codigo}' no existe")
                self.root.after(0, lambda j=i: self.lista_multi.itemconfig(j, fg=RED))
                continue

            data = self.templates[codigo]
            try:
                funciones.cargarCabecera(orden, chasis, recepcion, kilometraje,
                                         reparacion, codigo, data)
                funciones.cargarLocal(data)
                funciones.cargarTercero(data)
                pos = pyautogui.locateCenterOnScreen("img/completar.png", confidence=0.8)
                if pos:
                    pyautogui.moveTo(pos)
                    pyautogui.click()
                    time.sleep(3)

                historial.guardar_reclamo(
                    orden=orden, chasis=chasis, codigo=codigo,
                    kilometraje=kilometraje, recepcion=recepcion,
                    reparacion=reparacion, resultado="ok",
                )
                ok += 1
                self.root.after(0, lambda j=i: self.lista_multi.itemconfig(j, fg=GREEN))
            except Exception as exc:
                msg = str(exc)
                historial.guardar_reclamo(
                    orden=orden, chasis=chasis, codigo=codigo,
                    kilometraje=kilometraje, recepcion=recepcion,
                    reparacion=reparacion, resultado="error", detalle=msg,
                )
                errores.append(f"Orden {orden}: {msg}")
                self.root.after(0, lambda j=i: self.lista_multi.itemconfig(j, fg=RED))

        resumen = f"✔  {ok}/{total} procesadas"
        if errores:
            resumen += f"  |  ✘ {len(errores)} error(es)"
        color = GREEN if not errores else YELLOW
        self.root.after(0, lambda: self.status_multi.config(text=resumen, fg=color))
        self._procesando = False
        self.root.after(0, lambda: self.btn_reclamar_multi.config(state="normal"))
        self.root.after(0, self._cargar_historial)

    # ─── JSON unitario ────────────────────────────────────────────────────────

    def _cargar_json(self):
        path = filedialog.askopenfilename(
            title="Seleccionar archivo JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, list):
                datos = datos[0]
            self._borrar()
            self.e_orden.set(transformar_orden(str(datos.get("orden", ""))))
            self.e_chasis.set(str(datos.get("chasis", "")))
            self.e_recepcion.set(str(datos.get("apertura", "")))
            self.e_kilometraje.set(str(datos.get("kilometraje", "")))
            self.e_reparacion.set(str(datos.get("cierre", "")))
            self.e_codigo.set(str(datos.get("codigo", "")))
            self._actualizar_preview()
            self._set_status("✔  JSON cargado", GREEN)
        except (json.JSONDecodeError, OSError) as exc:
            self._set_status(f"✘  Error al leer JSON: {exc}")

    # ─── Historial ────────────────────────────────────────────────────────────

    def _cargar_historial(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for reg in historial.obtener_historial():
            self.tree.insert("", "end",
                             values=(reg["fecha"], reg["orden"],
                                     reg["codigo"], reg["resultado"]),
                             tags=(reg["resultado"],))
        self.tree.tag_configure("ok",    foreground=GREEN)
        self.tree.tag_configure("error", foreground=RED)

    def _limpiar_historial(self):
        historial.limpiar_historial()
        self._cargar_historial()


if __name__ == "__main__":
    root = tk.Tk()
    app = MyApp(root)
    root.mainloop()
