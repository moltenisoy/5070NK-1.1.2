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
from PIL import Image, ImageTk, ImageDraw, ImageFont
import pystray
import threading
import psutil
import os
from config_manager import ConfigManager

# Intentar importar plyer para notificaciones
try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    print("Advertencia: plyer no está instalado. Las notificaciones no estarán disponibles.")

# --- Constantes y Configuración de la GUI ---
APP_NAME = "Motor de Optimización Avanzada"
ICON_PATH = "1.ico"  # Asegúrate de que el archivo 1.ico esté en el mismo directorio

# =============================================================================
# --- SISTEMA DE NOTIFICACIONES TOAST ---
# =============================================================================

class NotificationManager:
    """Gestor de notificaciones del sistema"""
    
    @staticmethod
    def notify_thermal_warning(temperature):
        """Notifica cuando hay una alerta térmica"""
        if not PLYER_AVAILABLE:
            return
        
        try:
            notification.notify(
                title="⚠️ Alerta Térmica",
                message=f"Temperatura: {temperature}°C\nThrottling activado",
                app_icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
                timeout=10
            )
        except Exception as e:
            print(f"Error al enviar notificación térmica: {e}")
    
    @staticmethod
    def notify_optimization_applied(process_name):
        """Notifica cuando se aplica una optimización"""
        if not PLYER_AVAILABLE:
            return
        
        try:
            notification.notify(
                title="✓ Optimización Aplicada",
                message=f"Proceso optimizado: {process_name}",
                app_icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
                timeout=5
            )
        except Exception as e:
            print(f"Error al enviar notificación de optimización: {e}")
    
    @staticmethod
    def notify_mode_changed(mode):
        """Notifica cuando cambia el modo de operación"""
        if not PLYER_AVAILABLE:
            return
        
        try:
            notification.notify(
                title="🔄 Modo Cambiado",
                message=f"Nuevo modo: {mode}",
                app_icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
                timeout=5
            )
        except Exception as e:
            print(f"Error al enviar notificación de cambio de modo: {e}")
    
    @staticmethod
    def notify_driver_status(loaded):
        """Notifica el estado del driver en kernel"""
        if not PLYER_AVAILABLE:
            return
        
        try:
            status = "activado" if loaded else "desactivado"
            notification.notify(
                title=f"⚙️ Driver en Kernel {status.capitalize()}",
                message=f"El driver en modo kernel ha sido {status}",
                app_icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
                timeout=5
            )
        except Exception as e:
            print(f"Error al enviar notificación de driver: {e}")
    
    @staticmethod
    def notify_critical_error(error_message):
        """Notifica errores críticos"""
        if not PLYER_AVAILABLE:
            return
        
        try:
            notification.notify(
                title="❌ Error Crítico",
                message=error_message,
                app_icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
                timeout=10
            )
        except Exception as e:
            print(f"Error al enviar notificación de error crítico: {e}")

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
            bootstyle="primary-round-toggle",
            command=self.toggle_autostart
        )
        autostart_check.pack(anchor=W, pady=10)

        # --- Control del Gestor ---
        manager_frame = ttk.LabelFrame(self, text="Control del Sistema", padding=10)
        manager_frame.pack(fill=X, pady=10)
        
        module_manager_switch = ttk.Checkbutton(
            manager_frame,
            text="Gestor de Módulos (Optimización en tiempo real)",
            variable=self.module_manager_var,
            bootstyle="success-round-toggle",
            command=self.toggle_module_manager
        )
        module_manager_switch.pack(anchor=W, pady=10)

        # --- Modos de Operación ---
        modes_frame = ttk.LabelFrame(self, text="Modos de Operación", padding=10)
        modes_frame.pack(fill=X, pady=10)

        # Fila 1: Modo Juego y Modo Ahorro
        row1_frame = ttk.Frame(modes_frame)
        row1_frame.pack(fill=X, pady=5)
        
        game_button = ttk.Button(
            row1_frame, 
            text="🎮 Activar Modo Juego", 
            bootstyle="primary",
            command=self.toggle_game_mode
        )
        game_button.pack(side=LEFT, padx=5, fill=X, expand=True)

        ahorro_button = ttk.Button(
            row1_frame, 
            text="💚 Activar Modo Ahorro", 
            bootstyle="success-outline",
            command=self.toggle_ahorro_mode
        )
        ahorro_button.pack(side=LEFT, padx=5, fill=X, expand=True)

        # Fila 2: Modo Ultra Baja Latencia y Modo Extremo
        row2_frame = ttk.Frame(modes_frame)
        row2_frame.pack(fill=X, pady=5)

        ultra_low_latency_button = ttk.Button(
            row2_frame, 
            text="⚡ Activar Modo Ultra Baja Latencia", 
            bootstyle="info",
            command=self.toggle_ultra_low_latency
        )
        ultra_low_latency_button.pack(side=LEFT, padx=5, fill=X, expand=True)

        extremo_button = ttk.Button(
            row2_frame, 
            text="🚀 Activar Modo Extremo", 
            bootstyle="warning-outline",
            command=self.toggle_extremo_mode
        )
        extremo_button.pack(side=LEFT, padx=5, fill=X, expand=True)

        # --- Estado Actual ---
        status_frame = ttk.LabelFrame(self, text="Estado Actual", padding=10)
        status_frame.pack(fill=X, pady=10)
        
        self.status_label = ttk.Label(
            status_frame, 
            text="Estado: Gestor Activo - Modo Normal",
            bootstyle="info"
        )
        self.status_label.pack(anchor=W, pady=5)
    
    def toggle_autostart(self):
        """Activa/desactiva el inicio automático."""
        if self.autostart_var.get():
            messagebox.showinfo("Inicio Automático", "Inicio automático activado.", parent=self)
            # Implementar lógica de registro en Windows
        else:
            messagebox.showinfo("Inicio Automático", "Inicio automático desactivado.", parent=self)
    
    def toggle_module_manager(self):
        """Activa/desactiva el gestor de módulos."""
        if self.module_manager_var.get():
            self.status_label.config(text="Estado: Gestor Activo - Optimización en tiempo real")
            if self.module_manager:
                # self.module_manager.start()
                pass
        else:
            self.status_label.config(text="Estado: Gestor Detenido - Sin optimización")
            if self.module_manager:
                # self.module_manager.stop()
                pass
    
    def toggle_game_mode(self):
        """Activa el modo juego."""
        messagebox.showinfo("Modo Juego", "Modo Juego activado manualmente.", parent=self)
        self.status_label.config(text="Estado: Modo Juego Activo 🎮")
        if self.module_manager:
            # self.module_manager.set_game_mode(True)
            pass
    
    def toggle_ahorro_mode(self):
        """Activa el modo ahorro."""
        messagebox.showinfo("Modo Ahorro", "Modo Ahorro activado.", parent=self)
        self.status_label.config(text="Estado: Modo Ahorro Activo 💚")
        if self.module_manager:
            # self.module_manager.set_ahorro_mode(True)
            pass
    
    def toggle_ultra_low_latency(self):
        """Activa el modo ultra baja latencia."""
        response = messagebox.askyesno(
            "Modo Ultra Baja Latencia",
            "Este modo aplica optimizaciones agresivas.\n¿Desea continuar?",
            parent=self
        )
        if response:
            self.status_label.config(text="Estado: Modo Ultra Baja Latencia Activo ⚡")
            if self.module_manager:
                # self.module_manager.set_ultra_low_latency(True)
                pass
    
    def toggle_extremo_mode(self):
        """Activa el modo extremo."""
        response = messagebox.askyesno(
            "Modo Extremo",
            "⚠️ ADVERTENCIA: Este modo aplica las optimizaciones más agresivas\n"
            "y puede causar inestabilidad en el sistema.\n\n"
            "¿Desea continuar?",
            parent=self
        )
        if response:
            self.status_label.config(text="Estado: Modo Extremo Activo 🚀")
            if self.module_manager:
                # self.module_manager.set_extremo_mode(True)
                pass

class FineTuningTab(ttk.Frame):
    """Pestaña para los ajustes finos y de gestión térmica."""
    def __init__(self, master, module_manager_facade):
        super().__init__(master, padding=15)
        self.module_manager = module_manager_facade
        self.config_manager = ConfigManager()
        self._create_widgets()
        self._load_saved_settings()

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

    def _create_slider(self, parent, label_text, from_value, to_value, default_value, unit):
        frame = ttk.Frame(parent)
        frame.pack(fill=X, pady=5)
        
        label = ttk.Label(frame, text=label_text, width=50)
        label.pack(side=LEFT, padx=(0, 10))
        
        value_var = tk.IntVar(value=default_value)
        value_label = ttk.Label(frame, text=f"{default_value} {unit}", width=10)
        value_label.pack(side=RIGHT, padx=(5, 0))
        
        slider = ttk.Scale(
            frame, 
            from_=from_value, 
            to=to_value, 
            variable=value_var,
            orient=tk.HORIZONTAL,
            bootstyle="info",
            command=lambda val: value_label.config(text=f"{int(float(val))} {unit}")
        )
        slider.pack(side=RIGHT, fill=X, expand=True, padx=(0, 5))
        
        return value_var

    def _create_widgets(self):
        # --- Ajustes de Memoria ---
        memory_frame = ttk.LabelFrame(self, text="Ajustes de Memoria", padding=10)
        memory_frame.pack(fill=X, pady=10, anchor=N)

        self.pagefile_entry = self._create_widget(memory_frame, "Tamaño del Archivo de Paginación:", 8192, "MB")
        self.cache_entry = self._create_widget(memory_frame, "Tamaños de Cachés del Sistema:", 512, "MB")
        
        # --- Gestión Térmica con Sliders ---
        thermal_frame = ttk.LabelFrame(self, text="Gestión Térmica", padding=10)
        thermal_frame.pack(fill=X, pady=10, anchor=N)
        
        self.soft_throttle_var = self._create_slider(
            thermal_frame, 
            "Temperatura para Thermal Throttling Suave:", 
            60, 95, 80, "°C"
        )
        
        self.hard_throttle_var = self._create_slider(
            thermal_frame, 
            "Temperatura para Thermal Throttling Fuerte:", 
            70, 100, 90, "°C"
        )
        
        self.shutdown_temp_var = self._create_slider(
            thermal_frame, 
            "Temperatura Límite para Apagado Forzado:", 
            80, 110, 100, "°C"
        )
        
        # --- Botón para aplicar los cambios ---
        apply_button = ttk.Button(
            self, 
            text="Aplicar Ajustes Finos", 
            bootstyle="primary",
            command=self.apply_settings
        )
        apply_button.pack(pady=20)
    
    def apply_settings(self):
        """Aplica los ajustes al gestor de módulos."""
        thermal_thresholds = {
            'soft': self.soft_throttle_var.get(),
            'hard': self.hard_throttle_var.get(),
            'shutdown': self.shutdown_temp_var.get()
        }
        
        # Guardar configuración
        self.config_manager.set_thermal_thresholds(thermal_thresholds)
        
        # Aplicar al gestor de módulos si está disponible
        if self.module_manager and hasattr(self.module_manager, 'set_thermal_thresholds'):
            self.module_manager.set_thermal_thresholds(thermal_thresholds)
        
        messagebox.showinfo("Ajustes Aplicados", "Los ajustes térmicos han sido guardados y aplicados correctamente.", parent=self)
    
    def _load_saved_settings(self):
        """Carga los ajustes guardados desde la configuración."""
        try:
            thermal_thresholds = self.config_manager.get_thermal_thresholds()
            self.soft_throttle_var.set(thermal_thresholds.get('soft', 80))
            self.hard_throttle_var.set(thermal_thresholds.get('hard', 90))
            self.shutdown_temp_var.set(thermal_thresholds.get('shutdown', 100))
        except Exception as e:
            print(f"Error al cargar ajustes guardados: {e}")


class ControlPanelTab(ttk.Frame):
    """Pestaña de control que muestra el estado de todos los ajustes."""
    def __init__(self, master, module_manager_facade):
        super().__init__(master, padding=15)
        self.module_manager = module_manager_facade
        self.status_labels = {}
        self._create_widgets()
        
        # Iniciar actualización periódica
        self.update_status()
    
    def _create_widgets(self):
        # Título
        title_label = ttk.Label(
            self, 
            text="Panel de Control - Estado de Optimizaciones",
            font=("Segoe UI", 12, "bold"),
            bootstyle="primary"
        )
        title_label.pack(pady=(0, 10))
        
        # Frame con scroll
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Lista de ajustes organizados por categoría
        categories = {
            "Sistema": [
                "Gestor de Módulos",
                "Modo Actual",
                "Privilegios de Depuración",
                "Driver en Kernel-Mode"
            ],
            "CPU": [
                "Turbo Boost",
                "Core Parking",
                "Afinidad de Procesos",
                "Clasificación de Threads",
                "Optimización SMT",
                "Localidad de Caché L3"
            ],
            "Memoria": [
                "Prioridad de Memoria",
                "Páginas Grandes",
                "Compresión de Memoria",
                "Working Set Optimization"
            ],
            "Almacenamiento": [
                "Caché de Escritura",
                "Profundidad de Cola NCQ/NVMe",
                "TRIM Automático",
                "Paginación del Kernel"
            ],
            "Red": [
                "Algoritmo BBR",
                "TCP Fast Open",
                "QoS para Primer Plano",
                "Moderación de Interrupciones",
                "DNS Cache Optimizado"
            ],
            "Gráficos": [
                "Hardware GPU Scheduling",
                "Ancho de Banda PCIe",
                "DirectX Optimizado"
            ],
            "Térmica": [
                "Monitoreo de Temperatura",
                "Thermal Throttling"
            ]
        }
        
        for category, items in categories.items():
            # Frame de categoría
            category_frame = ttk.LabelFrame(scrollable_frame, text=category, padding=10)
            category_frame.pack(fill=X, pady=5, padx=5)
            
            for item in items:
                item_frame = ttk.Frame(category_frame)
                item_frame.pack(fill=X, pady=2)
                
                # Label del ajuste
                label = ttk.Label(item_frame, text=f"• {item}:", width=35)
                label.pack(side=LEFT)
                
                # Label de estado
                status_label = ttk.Label(
                    item_frame, 
                    text="⚫ Desconocido",
                    width=20,
                    foreground="gray"
                )
                status_label.pack(side=LEFT, padx=(10, 0))
                
                # Guardar referencia
                self.status_labels[item] = status_label
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # Botón de actualización manual
        refresh_button = ttk.Button(
            self,
            text="🔄 Actualizar Estado",
            bootstyle="info-outline",
            command=self.update_status
        )
        refresh_button.pack(pady=10)
    
    def update_status(self):
        """Actualiza el estado de todos los ajustes."""
        try:
            if self.module_manager:
                # Obtener estado real del gestor de módulos
                is_running = getattr(self.module_manager, '_running', False)
                
                # Sistema
                self._update_label("Gestor de Módulos", is_running, "Activo" if is_running else "Detenido")
                
                # Determinar modo actual
                mode = "Normal"
                if hasattr(self.module_manager, 'game_mode') and self.module_manager.game_mode:
                    mode = "Juego"
                elif hasattr(self.module_manager, 'ahorro_mode') and self.module_manager.ahorro_mode:
                    mode = "Ahorro"
                elif hasattr(self.module_manager, 'extremo_mode') and self.module_manager.extremo_mode:
                    mode = "Extremo"
                self._update_label("Modo Actual", is_running, mode)
                
                # Verificar privilegios de depuración
                import core
                debug_priv = hasattr(core, 'enable_debug_privilege') and core.enable_debug_privilege()
                self._update_label("Privilegios de Depuración", debug_priv, "Habilitado" if debug_priv else "No disponible")
                
                # Driver en Kernel-Mode
                driver_loaded = False
                if hasattr(self.module_manager, 'driver_km'):
                    driver_loaded = getattr(self.module_manager.driver_km, 'driver_loaded', False)
                self._update_label("Driver en Kernel-Mode", driver_loaded, "Cargado" if driver_loaded else "No cargado")
                
                # Para otros ajustes, mostrar estado basado en si el gestor está activo
                # y si los módulos están cargados
                modules_active = is_running
                
                # CPU
                self._update_label("Turbo Boost", modules_active, "Habilitado" if modules_active else "Inactivo")
                self._update_label("Core Parking", modules_active, "Optimizado" if modules_active else "Por defecto")
                self._update_label("Afinidad de Procesos", modules_active, "Configurada" if modules_active else "Sin configurar")
                self._update_label("Clasificación de Threads", modules_active, "Activa" if modules_active else "Inactiva")
                self._update_label("Optimización SMT", modules_active, "Activa" if modules_active else "Inactiva")
                self._update_label("Localidad de Caché L3", modules_active, "Optimizada" if modules_active else "Por defecto")
                
                # Memoria
                self._update_label("Prioridad de Memoria", modules_active, "Configurada" if modules_active else "Por defecto")
                self._update_label("Páginas Grandes", modules_active, "Habilitadas" if modules_active else "Por defecto")
                self._update_label("Compresión de Memoria", modules_active, "Activa" if modules_active else "Por defecto")
                self._update_label("Working Set Optimization", modules_active, "Activa" if modules_active else "Inactiva")
                
                # Almacenamiento
                self._update_label("Caché de Escritura", modules_active, "Optimizada" if modules_active else "Por defecto")
                self._update_label("Profundidad de Cola NCQ/NVMe", modules_active, "Ajustada" if modules_active else "Por defecto")
                self._update_label("TRIM Automático", modules_active, "Configurado" if modules_active else "Por defecto")
                self._update_label("Paginación del Kernel", modules_active, "Optimizada" if modules_active else "Por defecto")
                
                # Red
                self._update_label("Algoritmo BBR", modules_active, "Habilitado" if modules_active else "Por defecto")
                self._update_label("TCP Fast Open", modules_active, "Habilitado" if modules_active else "Por defecto")
                self._update_label("QoS para Primer Plano", modules_active, "Activo" if modules_active else "Inactivo")
                self._update_label("Moderación de Interrupciones", modules_active, "Optimizada" if modules_active else "Por defecto")
                self._update_label("DNS Cache Optimizado", modules_active, "Configurado" if modules_active else "Por defecto")
                
                # Gráficos
                self._update_label("Hardware GPU Scheduling", modules_active, "Habilitado" if modules_active else "Por defecto")
                self._update_label("Ancho de Banda PCIe", modules_active, "Optimizado" if modules_active else "Por defecto")
                self._update_label("DirectX Optimizado", modules_active, "Configurado" if modules_active else "Por defecto")
                
                # Térmica
                self._update_label("Monitoreo de Temperatura", modules_active, "Activo" if modules_active else "Inactivo")
                thermal_active = is_running and hasattr(self.module_manager, 'thermal_thresholds')
                self._update_label("Thermal Throttling", thermal_active, "Configurado" if thermal_active else "Inactivo")
            else:
                # Sin gestor, todo desactivado
                for label in self.status_labels.values():
                    label.config(text="⚫ Gestor No Iniciado", foreground="gray")
        
        except Exception as e:
            print(f"Error actualizando estado: {e}")
            import traceback
            traceback.print_exc()
        
        # Programar siguiente actualización
        self.after(5000, self.update_status)  # Actualizar cada 5 segundos
    
    def _update_label(self, item, is_working, status_text):
        """Actualiza el color y texto de un label de estado."""
        if item in self.status_labels:
            label = self.status_labels[item]
            if is_working:
                label.config(text=f"✓ {status_text}", foreground="green")
            else:
                label.config(text=f"✗ {status_text}", foreground="red")


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
            
        self.geometry("900x700")
        self.minsize(800, 600)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self._create_notebook()

    def _create_notebook(self):
        notebook = ttk.Notebook(self, bootstyle="primary")
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # Crear y añadir las pestañas
        control_tab = ControlPanelTab(notebook, self.module_manager)
        process_tab = ProcessManagementTab(notebook, self.module_manager)
        options_tab = GeneralOptionsTab(notebook, self.module_manager)
        tuning_tab = FineTuningTab(notebook, self.module_manager)

        notebook.add(control_tab, text=" 📊 Panel de Control ")
        notebook.add(process_tab, text=" 🔧 Gestión de Procesos ")
        notebook.add(options_tab, text=" ⚙️ Opciones Generales ")
        notebook.add(tuning_tab, text=" 🎯 Ajustes Finos ")


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
