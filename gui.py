"""
Módulo GUI (Interfaz Gráfica de Usuario)
-----------------------------------------

Responsable de toda la interacción con el usuario. Se comunica exclusivamente
con el 'Gestor de Módulos' para enviar comandos y recibir actualizaciones de estado.
No contiene lógica de optimización.

Funcionalidades:
- Icono en la bandeja del sistema con menú contextual.
- Ventana de configuración moderna y con pestañas.
- Pestaña de gestión de procesos (listas blanca y de juegos).
- Pestaña de opciones generales (modos, inicio automático).
- Pestaña de ajustes finos (paginación, cachés, gestión térmica).
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
import pystray
import threading
import psutil
import os

# --- Constantes y Configuración de la GUI ---
APP_NAME = "Motor de Optimización Avanzada"
ICON_PATH = "1.ico"  # Asegúrate de que el archivo 1.ico esté en el mismo directorio

class ProcessManagementTab(ttk.Frame):
    """Pestaña para la gestión de procesos."""
    def __init__(self, master, module_manager_facade):
        super().__init__(master, padding=15)
        self.module_manager = module_manager_facade
        self.processes_data = []

        self._create_widgets()
        self.load_process_list()

    def _create_widgets(self):
        # --- Sección de Procesos en Ejecución ---
        process_frame = ttk.LabelFrame(self, text="Procesos en Ejecución", padding=10)
        process_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        process_tree_frame = ttk.Frame(process_frame)
        process_tree_frame.pack(fill=BOTH, expand=True)

        self.process_tree = ttk.Treeview(
            process_tree_frame,
            columns=("pid", "name", "cpu", "memory"),
            show="headings",
            bootstyle="primary"
        )
        self.process_tree.heading("pid", text="PID")
        self.process_tree.heading("name", text="Nombre del Proceso")
        self.process_tree.heading("cpu", text="% CPU")
        self.process_tree.heading("memory", text="Memoria (MB)")

        self.process_tree.column("pid", width=80, anchor=CENTER)
        self.process_tree.column("name", width=250)
        self.process_tree.column("cpu", width=80, anchor=CENTER)
        self.process_tree.column("memory", width=120, anchor=E)

        vsb_process = ttk.Scrollbar(process_tree_frame, orient="vertical", command=self.process_tree.yview)
        self.process_tree.configure(yscrollcommand=vsb_process.set)
        
        self.process_tree.pack(side=LEFT, fill=BOTH, expand=True)
        vsb_process.pack(side=RIGHT, fill=Y)

        button_process_frame = ttk.Frame(process_frame)
        button_process_frame.pack(fill=X, pady=(10, 0))

        refresh_button = ttk.Button(
            button_process_frame,
            text="Actualizar Lista",
            command=self.load_process_list,
            bootstyle="secondary-outline"
        )
        refresh_button.pack(side=LEFT, padx=(0, 10))

        add_from_explorer_button = ttk.Button(
            button_process_frame,
            text="Agregar desde Explorador...",
            command=self.add_from_explorer,
            bootstyle="info-outline"
        )
        add_from_explorer_button.pack(side=LEFT)

        # --- Sección de Listas de Gestión ---
        lists_frame = ttk.Frame(self)
        lists_frame.pack(fill=BOTH, expand=True)

        whitelist_frame = ttk.LabelFrame(lists_frame, text="Lista Blanca (Procesos Ignorados)", padding=10)
        whitelist_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))

        self.whitelist_listbox = tk.Listbox(whitelist_frame, height=10)
        self.whitelist_listbox.pack(fill=BOTH, expand=True)

        game_list_frame = ttk.LabelFrame(lists_frame, text="Lista de Juegos (Alta Prioridad)", padding=10)
        game_list_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(5, 0))

        self.gamelist_listbox = tk.Listbox(game_list_frame, height=10)
        self.gamelist_listbox.pack(fill=BOTH, expand=True)
        
        # --- Botones de acción para las listas ---
        action_buttons_frame = ttk.Frame(self)
        action_buttons_frame.pack(fill=X, pady=(10,0))

        add_to_whitelist_button = ttk.Button(
            action_buttons_frame,
            text="-> Añadir a Lista Blanca",
            command=lambda: self.add_to_list(self.whitelist_listbox, "whitelist")
        )
        add_to_whitelist_button.pack(side=LEFT, padx=(0, 10))

        add_to_gamelist_button = ttk.Button(
            action_buttons_frame,
            text="-> Añadir a Lista de Juegos",
            command=lambda: self.add_to_list(self.gamelist_listbox, "gamelist")
        )
        add_to_gamelist_button.pack(side=LEFT, padx=(85, 10))

        remove_from_whitelist_button = ttk.Button(
            action_buttons_frame,
            text="Quitar Seleccionado",
            bootstyle="danger-outline",
            command=lambda: self.remove_from_list(self.whitelist_listbox, "whitelist")
        )
        remove_from_whitelist_button.pack(side=LEFT, padx=(10, 40))

        remove_from_gamelist_button = ttk.Button(
            action_buttons_frame,
            text="Quitar Seleccionado",
            bootstyle="danger-outline",
            command=lambda: self.remove_from_list(self.gamelist_listbox, "gamelist")
        )
        remove_from_gamelist_button.pack(side=LEFT, padx=(10, 0))

    def load_process_list(self):
        """Carga y muestra la lista de procesos en ejecución."""
        for i in self.process_tree.get_children():
            self.process_tree.delete(i)
        
        self.processes_data = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
            try:
                mem_mb = p.info['memory_info'].rss / (1024 * 1024)
                self.processes_data.append(
                    (p.info['pid'], p.info['name'], f"{p.info['cpu_percent']:.2f}", f"{mem_mb:.2f}")
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Ordenar por nombre de proceso por defecto
        self.processes_data.sort(key=lambda x: x[1].lower())

        for proc_data in self.processes_data:
            self.process_tree.insert("", END, values=proc_data)

    def add_to_list(self, listbox, list_name):
        """Añade un proceso seleccionado a la lista especificada."""
        selected_items = self.process_tree.selection()
        if not selected_items:
            messagebox.showwarning("Sin Selección", "Por favor, seleccione un proceso de la lista.", parent=self)
            return

        for item in selected_items:
            process_name = self.process_tree.item(item, 'values')[1]
            if process_name not in listbox.get(0, END):
                listbox.insert(END, process_name)
                # Comunicar al gestor de módulos
                # self.module_manager.add_process_to_list(process_name, list_name)

    def remove_from_list(self, listbox, list_name):
        """Elimina un proceso de la lista especificada."""
        selected_indices = listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Sin Selección", "Por favor, seleccione un proceso de la lista a eliminar.", parent=self)
            return
            
        for i in reversed(selected_indices):
            process_name = listbox.get(i)
            listbox.delete(i)
            # Comunicar al gestor de módulos
            # self.module_manager.remove_process_from_list(process_name, list_name)

    def add_from_explorer(self):
        """Abre un diálogo para seleccionar un .exe y lo presenta para ser añadido a una lista."""
        filepath = filedialog.askopenfilename(
            title="Seleccionar Ejecutable",
            filetypes=[("Archivos Ejecutables", "*.exe")],
            parent=self
        )
        if filepath:
            process_name = os.path.basename(filepath)
            # Preguntar al usuario a qué lista añadirlo
            response = messagebox.askyesnocancel(
                "Añadir Proceso",
                f"¿A qué lista desea añadir '{process_name}'?\n\n"
                "Sí = Lista de Juegos\n"
                "No = Lista Blanca\n"
                "Cancelar = No añadir",
                parent=self
            )
            if response is True: # Sí
                if process_name not in self.gamelist_listbox.get(0, END):
                    self.gamelist_listbox.insert(END, process_name)
                    # self.module_manager.add_process_to_list(process_name, "gamelist")
            elif response is False: # No
                if process_name not in self.whitelist_listbox.get(0, END):
                    self.whitelist_listbox.insert(END, process_name)
                    # self.module_manager.add_process_to_list(process_name, "whitelist")

class GeneralOptionsTab(ttk.Frame):
    """Pestaña para las opciones generales del optimizador."""
    def __init__(self, master, module_manager_facade):
        super().__init__(master, padding=15)
        self.module_manager = module_manager_facade

        self.autostart_var = tk.BooleanVar()
        self.module_manager_var = tk.BooleanVar(value=True)

        self._create_widgets()
    
    def _create_widgets(self):
        frame = ttk.Frame(self)
        frame.pack(fill=X, pady=5)
        
        autostart_check = ttk.Checkbutton(
            frame,
            text="Iniciar automáticamente con Windows",
            variable=self.autostart_var,
            bootstyle="primary-round-toggle"
        )
        autostart_check.pack(anchor=W, pady=10)

        modes_frame = ttk.LabelFrame(self, text="Modos de Operación", padding=10)
        modes_frame.pack(fill=X, pady=10)

        # Aquí usamos style 'info.TButton' para que se vean diferentes
        ahorro_button = ttk.Button(modes_frame, text="Activar Modo Ahorro", bootstyle="success-outline")
        ahorro_button.pack(side=LEFT, padx=5, pady=5, fill=X, expand=True)

        extremo_button = ttk.Button(modes_frame, text="Activar Modo Extremo", bootstyle="warning-outline")
        extremo_button.pack(side=LEFT, padx=5, pady=5, fill=X, expand=True)

        manager_frame = ttk.LabelFrame(self, text="Control General", padding=10)
        manager_frame.pack(fill=X, pady=10)
        
        module_manager_switch = ttk.Checkbutton(
            manager_frame,
            text="Gestor de Módulos (Optimización en tiempo real)",
            variable=self.module_manager_var,
            bootstyle="success-round-toggle"
        )
        module_manager_switch.pack(anchor=W, pady=10)

class FineTuningTab(ttk.Frame):
    """Pestaña para los ajustes finos y de gestión térmica."""
    def __init__(self, master, module_manager_facade):
        super().__init__(master, padding=15)
        self.module_manager = module_manager_facade
        self._create_widgets()

    def _create_widget(self, parent, label_text, default_value, unit):
        frame = ttk.Frame(parent)
        frame.pack(fill=X, pady=5)
        
        label = ttk.Label(frame, text=label_text, width=45)
        label.pack(side=LEFT, padx=(0, 10))

        entry = ttk.Entry(frame, width=10)
        entry.insert(0, str(default_value))
        entry.pack(side=LEFT, padx=(0, 5))
        
        unit_label = ttk.Label(frame, text=unit)
        unit_label.pack(side=LEFT)
        return entry

    def _create_widgets(self):
        # --- Ajustes de Memoria ---
        memory_frame = ttk.LabelFrame(self, text="Ajustes de Memoria", padding=10)
        memory_frame.pack(fill=X, pady=10, anchor=N)

        self.pagefile_entry = self._create_widget(memory_frame, "Tamaño del Archivo de Paginación:", 8192, "MB")
        self.cache_entry = self._create_widget(memory_frame, "Tamaños de Cachés del Sistema:", 512, "MB")
        
        # --- Gestión Térmica ---
        thermal_frame = ttk.LabelFrame(self, text="Gestión Térmica", padding=10)
        thermal_frame.pack(fill=X, pady=10, anchor=N)
        
        self.soft_throttle_entry = self._create_widget(thermal_frame, "Temperatura de Comienzo para Thermal Throttling Suave:", 80, "°C")
        self.hard_throttle_entry = self._create_widget(thermal_frame, "Temperatura de Comienzo para Thermal Throttling Fuerte:", 90, "°C")
        self.shutdown_temp_entry = self._create_widget(thermal_frame, "Temperatura para Apagado Forzado por Seguridad:", 100, "°C")
        
        # --- Botón para aplicar los cambios ---
        apply_button = ttk.Button(self, text="Aplicar Ajustes Finos", bootstyle="primary")
        apply_button.pack(pady=20)


class SettingsWindow(tk.Toplevel):
    """Ventana principal de configuración de la aplicación."""
    def __init__(self, master, module_manager_facade):
        super().__init__(master)
        self.module_manager = module_manager_facade
        
        self.title(APP_NAME + " - Configuración")
        try:
            self.iconbitmap(ICON_PATH)
        except tk.TclError:
            print(f"Advertencia: No se pudo cargar el icono '{ICON_PATH}'.")
            
        self.geometry("800x600")
        self.minsize(700, 500)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self._create_notebook()

    def _create_notebook(self):
        notebook = ttk.Notebook(self, bootstyle="primary")
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # Crear y añadir las pestañas
        process_tab = ProcessManagementTab(notebook, self.module_manager)
        options_tab = GeneralOptionsTab(notebook, self.module_manager)
        tuning_tab = FineTuningTab(notebook, self.module_manager)

        notebook.add(process_tab, text=" Gestión de Procesos ")
        notebook.add(options_tab, text=" Opciones Generales ")
        notebook.add(tuning_tab, text=" Ajustes Finos ")


class MainApplication:
    """Clase principal que gestiona la bandeja del sistema y la ventana de configuración."""
    def __init__(self, root):
        self.root = root
        self.root.withdraw()  # Ocultar la ventana raíz de Tkinter
        self.module_manager = None # Placeholder para el gestor real
        self.settings_window = None

        self._setup_tray_icon()

    def _setup_tray_icon(self):
        try:
            image = Image.open(ICON_PATH)
        except FileNotFoundError:
            print(f"Error: El archivo de icono '{ICON_PATH}' no fue encontrado.")
            self.root.destroy()
            return
            
        menu = (
            pystray.MenuItem('Pasar a Modo Juego', self.toggle_game_mode, checked=lambda item: getattr(self, "game_mode_active", False)),
            pystray.MenuItem('Abrir Configuración', self.show_settings_window),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Cerrar Script', self.quit_application)
        )
        self.tray_icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
        
        # Iniciar el icono en un hilo separado para no bloquear el bucle de Tkinter
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_settings_window(self):
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(self.root, self.module_manager)
        self.settings_window.deiconify()
        self.settings_window.lift()
        self.settings_window.focus_force()

    def toggle_game_mode(self):
        self.game_mode_active = not getattr(self, "game_mode_active", False)
        print(f"Modo Juego: {'Activado' if self.game_mode_active else 'Desactivado'}")
        # Lógica para comunicar al gestor de módulos
        # if self.module_manager:
        #     self.module_manager.set_game_mode(self.game_mode_active)

    def quit_application(self):
        self.tray_icon.stop()
        self.root.quit()
        self.root.destroy()

if __name__ == '__main__':
    # Usando el tema 'darkly' de ttkbootstrap
    root = tb.Window(themename="darkly")
    app = MainApplication(root)
    root.mainloop()
