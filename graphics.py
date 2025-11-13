"""
Módulo Gráficos
---------------

Gestiona los ajustes estáticos del registro relacionados con la GPU,
el bus PCIe y las API de renderizado.
"""
from kernel import RegistryManager
import winreg

class GPUSchedulingOptimizer(RegistryManager):
    """Habilita HAGS (Hardware-accelerated GPU Scheduling)."""
    KEY_PATH = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
    
    def enable_hardware_gpu_scheduling(self):
        # 2 = Habilitado
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "HwSchMode", 2)

class PCIeBandwidthOptimizer(RegistryManager):
    """Maximiza el ancho de banda de PCIe (complementario a powercfg)."""
    KEY_PATH = r"SYSTEM\CurrentControlSet\Services\pci\Parameters"
    
    def maximize_pcie_bandwidth(self):
        # Deshabilita ASPM a nivel de registro
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "ASPMOptOut", 1)

class DirectXVulkanOptimizer(RegistryManager):
    """Optimiza el rendimiento de las API de renderizado."""
    KEY_PATH = r"SOFTWARE\Microsoft\DirectX"
    
    def optimize_rendering_performance(self):
        # Deshabilita la capa de depuración de DirectX para reducir la sobrecarga
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "DisableDebugLayer", 1)


class GPUMultimediaPriorityOptimizer(RegistryManager):
    """Asigna valores máximos de prioridad a parámetros GPU en registro multimedia"""
    
    MULTIMEDIA_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
    TASKS_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks"
    
    def optimize_gpu_multimedia_priorities(self):
        """Establece prioridades máximas para GPU en el sistema multimedia"""
        print("[GPU Multimedia] Optimizando prioridades multimedia de GPU...")
        
        try:
            # Configurar prioridades base del sistema multimedia
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.MULTIMEDIA_KEY, "SystemResponsiveness", 0)
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.MULTIMEDIA_KEY, "NetworkThrottlingIndex", 0xFFFFFFFF)
            
            # GPU Priority (10 = Máxima prioridad)
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.MULTIMEDIA_KEY, "GPUPriority", 8)
            
            # Prioridad de scheduling
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.MULTIMEDIA_KEY, "SchedulingCategory", 1)  # High
            
            # Prioridad de MMCSS (Multimedia Class Scheduler Service)
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.MULTIMEDIA_KEY, "Priority", 1)  # High
            
            print("[GPU Multimedia] Prioridades base establecidas")
            
            # Configurar tareas específicas
            self._configure_gaming_task()
            self._configure_display_postprocessing()
            
            print("[GPU Multimedia] Optimización multimedia completada")
        
        except Exception as e:
            print(f"[GPU Multimedia] Error optimizando multimedia: {e}")
    
    def _configure_gaming_task(self):
        """Configura la tarea de Gaming con máxima prioridad"""
        gaming_key = self.TASKS_KEY + r"\Games"
        
        # GPU Priority: 8 (máxima para aplicaciones)
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, gaming_key, "GPU Priority", 8)
        
        # Priority: 6 (High)
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, gaming_key, "Priority", 6)
        
        # Scheduling Category: High (1)
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, gaming_key, "Scheduling Category", 1)
        
        # SFIO Priority: High
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, gaming_key, "SFIO Priority", "High")
        
        print("[GPU Multimedia] Tarea Gaming configurada")
    
    def _configure_display_postprocessing(self):
        """Configura post-procesamiento de display"""
        display_key = self.TASKS_KEY + r"\DisplayPostProcessing"
        
        # GPU Priority máxima
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, display_key, "GPU Priority", 8)
        
        # Priority alta
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, display_key, "Priority", 8)
        
        # Scheduling Category: High
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, display_key, "Scheduling Category", 1)
        
        print("[GPU Multimedia] Display PostProcessing configurado")


class GPUSystemCommunicationOptimizer(RegistryManager):
    """Optimiza comunicación del sistema con la GPU para prioridad máxima"""
    
    def optimize_gpu_communication_priority(self):
        """Hace que la comunicación con GPU sea prioritaria sobre todo lo demás"""
        print("[GPU System] Optimizando prioridad de comunicación con GPU...")
        
        try:
            # Deshabilitar TDR (Timeout Detection and Recovery) para evitar interrupciones
            tdr_key = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, tdr_key, "TdrLevel", 0)
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, tdr_key, "TdrDelay", 60)
            print("[GPU System] TDR optimizado para evitar timeouts")
            
            # Maximizar prioridad de DWM (Desktop Window Manager)
            dwm_key = r"SOFTWARE\Microsoft\Windows\Dwm"
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, dwm_key, "OverlayTestMode", 5)
            print("[GPU System] DWM optimizado")
            
            # Optimizar driver de video
            video_key = r"SYSTEM\CurrentControlSet\Control\Video"
            # Deshabilitar características que pueden causar latencia
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, tdr_key, "TdrDdiDelay", 60)
            
            # Prioridad de interrupción de GPU
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, tdr_key, "InterruptPriority", 0x80000000)
            
            print("[GPU System] Comunicación GPU optimizada")
        
        except Exception as e:
            print(f"[GPU System] Error optimizando comunicación GPU: {e}")
    
    def optimize_gpu_performance_settings(self):
        """Optimiza ajustes de sistema para mejor rendimiento GPU"""
        print("[GPU System] Aplicando ajustes de rendimiento del sistema...")
        
        try:
            # Deshabilitar MPO (Multiplane Overlay) si causa problemas
            graphics_key = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
            # DisableOverlays puede mejorar rendimiento en algunos casos
            # 0 = Habilitado, 1 = Deshabilitado (comentado por defecto para no interferir)
            # self.write_dword(winreg.HKEY_LOCAL_MACHINE, graphics_key, "DisableOverlays", 0)
            
            # Habilitar aceleración de hardware máxima
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, graphics_key, "HwSchMode", 2)
            
            # Prioridad de proceso gráfico
            multimedia_key = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games"
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, multimedia_key, "Affinity", 0)
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, multimedia_key, "Background Only", "False")
            self.write_dword(winreg.HKEY_LOCAL_MACHINE, multimedia_key, "Clock Rate", 10000)
            
            print("[GPU System] Ajustes de rendimiento aplicados")
        
        except Exception as e:
            print(f"[GPU System] Error aplicando ajustes de rendimiento: {e}")