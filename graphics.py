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