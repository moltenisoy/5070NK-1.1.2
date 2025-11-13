"""
Módulo Memoria
--------------

Gestiona todas las optimizaciones relacionadas con la memoria RAM,
tanto a nivel de proceso (Working Set, Prioridad de Página) como a
nivel de sistema (Standby List, Compresión).
"""
import subprocess
import psutil
from core import kernel32, MEMORY_PRIORITY_NORMAL, MEMORY_PRIORITY_LOW, MEMORY_PRIORITY_VERY_LOW

class WorkingSetOptimizer:
    """Recorta el working set de procesos en segundo plano."""
    def __init__(self, process_manager):
        self.process_manager = process_manager

    def trim_private_pages(self, pid):
        """Instruye al gestor de procesos para recortar el WS."""
        # La lógica de cuándo llamar a esto está en el Gestor principal
        self.process_manager.settings_applicator.apply_batched_settings(pid, {'working_set_trim': True})

class MemoryBandwidthManager:
    """Gestiona la prioridad de acceso a la memoria."""
    def __init__(self, process_manager):
        self.process_manager = process_manager
    
    def set_memory_priority(self, pid, level):
        priority_map = {
            "NORMAL": MEMORY_PRIORITY_NORMAL,
            "LOW": MEMORY_PRIORITY_LOW,
            "VERY_LOW": MEMORY_PRIORITY_VERY_LOW
        }
        if level in priority_map:
            self.process_manager.settings_applicator.apply_batched_settings(pid, {'page_priority': priority_map[level]})

class LargePageManager:
    """Gestiona la habilitación de Páginas Grandes."""
    def enable_large_pages_for_process(self, pid, handle, rss_mb):
        if rss_mb > 512: # Umbral para considerar páginas grandes
            # Esta es una técnica, no una garantía. Fuerza un WS mínimo y máximo.
            min_ws = 512 * 1024 * 1024
            max_ws = -1 # Sin límite superior estricto
            # QUOTA_LIMITS_HARDWS_MIN_ENABLE = 4, QUOTA_LIMITS_HARDWS_MAX_ENABLE = 8
            flags = 4 | 8
            kernel32.SetProcessWorkingSetSizeEx(handle, min_ws, max_ws, flags)
            
class StandbyListCleaner:
    """Limpia la caché de memoria 'Standby List'."""
    def clear_ram_cache(self):
        # Asume que 'emptystandbylist.exe' está en el PATH o en el mismo directorio.
        try:
            subprocess.Popen(['emptystandbylist.exe', 'standbylist'], creationflags=subprocess.CREATE_NO_WINDOW)
            print("Limpiando Standby List...")
        except FileNotFoundError:
            print("Advertencia: 'emptystandbylist.exe' no encontrado. No se puede limpiar la caché de RAM.")

class MemoryCompressionManager:
    """Habilita la compresión de memoria del sistema."""
    def enable_memory_compression(self):
        try:
            subprocess.run(
                ['powershell', '-Command', 'Enable-MMAgent -MemoryCompression'],
                capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            print(f"No se pudo habilitar la compresión de memoria: {e}")

class MemoryScrubbingOptimizer:
    """Programa la ejecución del limpiador de memoria de Windows."""
    def schedule_scrubbing_low_load(self):
        # La lógica de cuándo llamar (carga <20%) está en el Gestor
        try:
            subprocess.run(['mdsched.exe'], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            print(f"No se pudo iniciar mdsched.exe: {e}")


class MemoryBalloon:
    """Libera memoria proactivamente cuando es necesario (Memory Ballooning)"""
    
    def __init__(self, low_threshold_mb=2048, high_threshold_mb=4096):
        self.low_threshold = low_threshold_mb * 1024 * 1024  # Convertir a bytes
        self.high_threshold = high_threshold_mb * 1024 * 1024
        print(f"[MemoryBalloon] Inicializado: umbral bajo={low_threshold_mb}MB, alto={high_threshold_mb}MB")
    
    def check_and_balloon(self):
        """Verifica memoria disponible y libera si es necesario"""
        memory = psutil.virtual_memory()
        available = memory.available
        
        if available < self.low_threshold:
            print(f"[MemoryBalloon] Memoria crítica: {available / 1024 / 1024:.0f}MB disponible")
            self.aggressive_trim()
        elif available < self.high_threshold:
            print(f"[MemoryBalloon] Memoria baja: {available / 1024 / 1024:.0f}MB disponible")
            self.moderate_trim()
    
    def aggressive_trim(self):
        """Recorte agresivo de memoria"""
        print("[MemoryBalloon] Iniciando recorte agresivo de memoria")
        
        trimmed_count = 0
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                if self.is_trimmable(proc):
                    handle = kernel32.OpenProcess(0x1F0FFF, False, proc.info['pid'])
                    if handle:
                        # Recortar working set
                        kernel32.SetProcessWorkingSetSizeEx(handle, -1, -1, 0)
                        kernel32.CloseHandle(handle)
                        trimmed_count += 1
            except Exception:
                pass
        
        print(f"[MemoryBalloon] Recortados {trimmed_count} procesos")
    
    def moderate_trim(self):
        """Recorte moderado de memoria"""
        print("[MemoryBalloon] Iniciando recorte moderado de memoria")
        
        trimmed_count = 0
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                # Solo recortar procesos con más de 100MB de memoria
                if self.is_trimmable(proc) and proc.info['memory_info'].rss > 100 * 1024 * 1024:
                    handle = kernel32.OpenProcess(0x1F0FFF, False, proc.info['pid'])
                    if handle:
                        kernel32.SetProcessWorkingSetSizeEx(handle, -1, -1, 0)
                        kernel32.CloseHandle(handle)
                        trimmed_count += 1
            except Exception:
                pass
        
        print(f"[MemoryBalloon] Recortados {trimmed_count} procesos")
    
    def is_trimmable(self, proc):
        """Determina si un proceso puede ser recortado"""
        # Lista de procesos críticos que no deben ser recortados
        critical_processes = [
            'system', 'system idle process', 'registry',
            'smss.exe', 'csrss.exe', 'wininit.exe', 'services.exe',
            'lsass.exe', 'svchost.exe', 'dwm.exe', 'explorer.exe',
            'winlogon.exe', 'fontdrvhost.exe'
        ]
        
        try:
            name = proc.info['name'].lower()
            return name not in critical_processes
        except Exception:
            return False