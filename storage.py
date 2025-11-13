"""
Módulo Almacenamiento
---------------------

Gestiona todas las optimizaciones estáticas y dinámicas relacionadas
con discos (HDD/SSD/NVMe), la caché del sistema de archivos y las
operaciones de E/S.
"""
from kernel import RegistryManager
import subprocess
import winreg

class NCQOptimizer(RegistryManager):
    """Ajusta la profundidad de cola para controladores SATA/AHCI."""
    KEY_PATH = r"SYSTEM\CurrentControlSet\Services\storahci\Parameters\Device"
    
    def set_queue_depth_for_gaming(self, is_gaming):
        depth = 32 if is_gaming else 256
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "QueueDepth", depth)
        
class AdaptiveNVMeScheduler(RegistryManager):
    """Ajusta la profundidad de cola para controladores NVMe."""
    KEY_PATH = r"SYSTEM\CurrentControlSet\Services\stornvme\Parameters\Device"

    def adjust_nvme_queue_depth(self, system_load):
        # system_load es un float de 0.0 a 1.0
        if system_load < 0.3: depth = 32
        elif system_load < 0.6: depth = 128
        elif system_load < 0.8: depth = 512
        else: depth = 1024
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "QueueDepth", depth)

class FileSystemCacheManager(RegistryManager):
    """Gestiona la caché del sistema de archivos y la paginación del kernel."""
    KEY_PATH = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"

    def optimize_cache_for_gaming(self):
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "DisablePagingExecutive", 1)
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "LargeSystemCache", 0)

    def optimize_write_cache_for_gaming(self):
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "LargeSystemCache", 1)
        # 512 MB
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "IoPageLockLimit", 536870912)

class CustomIOScheduler(RegistryManager):
    """Ajusta el timeout del servicio de disco."""
    KEY_PATH = r"SYSTEM\CurrentControlSet\Services\Disk"

    def prioritize_reads_for_gaming(self):
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "TimeOutValue", 10)

class IntelligentTRIMScheduler:
    """Ejecuta TRIM en SSDs durante periodos de inactividad."""
    def execute_trim(self, is_gaming, cpu_load):
        # La lógica de tiempo e inactividad está en el Gestor
        if not is_gaming and cpu_load < 10.0:
            try:
                subprocess.run(['defrag', '/L', 'C:'], creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception as e:
                print(f"Error al ejecutar TRIM: {e}")

class MetadataOptimizer(RegistryManager):
    """Optimiza las operaciones de metadatos de NTFS."""
    KEY_PATH = r"SYSTEM\CurrentControlSet\Control\FileSystem"
    
    def optimize_metadata_operations(self):
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "NtfsDisableLastAccessUpdate", 1)
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "NtfsDisable8dot3NameCreation", 1)


class StoragePowerManager:
    """Gestiona políticas de ahorro de energía en unidades de almacenamiento"""
    
    def __init__(self):
        self.is_laptop = self._detect_laptop()
        print(f"[StoragePower] Sistema detectado como: {'Portátil' if self.is_laptop else 'Escritorio'}")
    
    def _detect_laptop(self):
        """Detecta si el sistema es un portátil"""
        try:
            import psutil
            battery = psutil.sensors_battery()
            return battery is not None
        except Exception:
            return False
    
    def _get_battery_level(self):
        """Obtiene el nivel de batería"""
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                return battery.percent
            return 100  # Si no hay batería, asumir 100%
        except Exception:
            return 100
    
    def disable_storage_power_saving(self):
        """Desactiva todas las políticas de ahorro de energía en almacenamiento"""
        # Verificar batería si es portátil
        if self.is_laptop:
            battery_level = self._get_battery_level()
            if battery_level < 20:
                print(f"[StoragePower] Batería baja ({battery_level}%), manteniendo ahorro de energía")
                return
        
        print("[StoragePower] Desactivando ahorro de energía en almacenamiento...")
        
        try:
            # Deshabilitar apagado de discos duros
            subprocess.run(
                ['powercfg', '/setacvalueindex', 'SCHEME_CURRENT', 
                 'SUB_DISK', 'DISKIDLE', '0'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            subprocess.run(
                ['powercfg', '/setdcvalueindex', 'SCHEME_CURRENT', 
                 'SUB_DISK', 'DISKIDLE', '0'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Aplicar cambios
            subprocess.run(
                ['powercfg', '/setactive', 'SCHEME_CURRENT'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            print("[StoragePower] Políticas de ahorro de energía desactivadas")
        
        except Exception as e:
            print(f"[StoragePower] Error al desactivar ahorro de energía: {e}")
    
    def enable_storage_power_saving(self):
        """Reactiva las políticas de ahorro de energía"""
        print("[StoragePower] Reactivando ahorro de energía en almacenamiento...")
        
        try:
            # Establecer timeout de 20 minutos
            subprocess.run(
                ['powercfg', '/setacvalueindex', 'SCHEME_CURRENT', 
                 'SUB_DISK', 'DISKIDLE', '1200'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            subprocess.run(
                ['powercfg', '/setdcvalueindex', 'SCHEME_CURRENT', 
                 'SUB_DISK', 'DISKIDLE', '600'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Aplicar cambios
            subprocess.run(
                ['powercfg', '/setactive', 'SCHEME_CURRENT'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            print("[StoragePower] Políticas de ahorro de energía reactivadas")
        
        except Exception as e:
            print(f"[StoragePower] Error al reactivar ahorro de energía: {e}")