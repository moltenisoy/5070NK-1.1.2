"""
Módulo Red
----------

Gestiona todas las optimizaciones de la pila de red, tanto
estáticas (Registro) como dinámicas (PowerShell, Ping).
"""
from kernel import RegistryManager
import subprocess
import psutil

class NetworkStackOptimizer(RegistryManager):
    """Ajusta parámetros clave de la pila TCP/IP."""
    KEY_PATH = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"

    def adjust_tcp_window_scaling(self, latency_ms):
        if latency_ms < 20: size = 32768
        elif latency_ms < 50: size = 65536
        else: size = 131072
        
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "TcpWindowSize", size)
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "Tcp1323Opts", 3)

    def configure_rss(self, cpu_count):
        # Usar hasta 4 núcleos para RSS en sistemas con muchos núcleos
        num_queues = min(4, cpu_count)
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "RssBaseCpu", 0)
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "MaxRssProcessors", num_queues)

    def disable_network_throttling(self):
        THROTTLE_KEY_PATH = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, THROTTLE_KEY_PATH, "NetworkThrottlingIndex", 0xFFFFFFFF)

    def enable_tcp_fast_open(self):
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "EnableTcpFastOpen", 1)
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "TcpMaxDataRetransmissions", 3)
    
    def enable_bbr_algorithm(self):
        # 2 = BBR. Requiere una versión de Windows que lo soporte.
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "TcpCongestionControl", 2)
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "TcpAckFrequency", 2)

    def enable_polling_mode(self, is_gaming):
        value = 1 if is_gaming else 0
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "DisableTaskOffload", value)

class InterruptCoalescer:
    """Ajusta la moderación de interrupciones de la NIC."""
    def optimize_interrupt_coalescing(self, throughput_mbps):
        if throughput_mbps > 100: level = "Extreme" # Alto throughput, agrupar más
        elif throughput_mbps > 10: level = "Adaptive"
        else: level = "Minimal" # Bajo throughput, menos latencia

        cmd = f'Get-NetAdapter | Set-NetAdapterAdvancedProperty -DisplayName "Interrupt Moderation" -DisplayValue "{level}"'
        try:
            subprocess.run(['powershell', '-Command', cmd], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            print(f"No se pudo ajustar la moderación de interrupciones: {e}")

class DNSCacheOptimizer(RegistryManager):
    """Configura la caché de DNS para ser más agresiva."""
    KEY_PATH = r"SYSTEM\CurrentControlSet\Services\Dnscache\Parameters"
    
    def configure_dns_caching(self):
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "MaxCacheTtl", 86400) # 24 horas
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "MaxNegativeCacheTtl", 3600) # 1 hora

class QoSManager:
    """Crea políticas de QoS para priorizar tráfico de red."""
    def prioritize_foreground_traffic(self, pid, process_name):
        # DSCP 46 (Expedited Forwarding) es común para VoIP/juegos
        # DSCP 34 (Assured Forwarding 41) para tráfico interactivo
        dscp_value = 46 if "game" in process_name.lower() else 34
        policy_name = f"QoSPolicy_PID_{pid}"
        
        # Eliminar política antigua si existe
        subprocess.run(['powershell', '-Command', f'Remove-NetQosPolicy -Name "{policy_name}" -Confirm:$false'], creationflags=subprocess.CREATE_NO_WINDOW, stderr=subprocess.DEVNULL)
        
        # Crear nueva política
        cmd = f'New-NetQosPolicy -Name "{policy_name}" -AppPath "{psutil.Process(pid).exe()}" -DSCPAction {dscp_value}'
        try:
            subprocess.run(['powershell', '-Command', cmd], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            print(f"No se pudo crear la política de QoS para PID {pid}: {e}")