"""
Módulo Red
----------

Gestiona todas las optimizaciones de la pila de red, tanto
estáticas (Registro) como dinámicas (PowerShell, Ping).
"""
from kernel import RegistryManager
import subprocess
import psutil
import winreg

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
    
    def apply_system_process_qos_limits(self):
        """Aplica límites mínimos de QoS a procesos de sistema que no interfieren con gaming"""
        print("[QoS] Aplicando límites QoS a procesos de sistema...")
        
        # Procesos de sistema a limitar durante gaming
        system_processes = [
            'svchost.exe', 'SearchIndexer.exe', 'MsMpEng.exe',
            'WindowsUpdate.exe', 'TrustedInstaller.exe', 'WmiPrvSE.exe',
            'RuntimeBroker.exe', 'dllhost.exe', 'taskhost.exe'
        ]
        
        limited_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] in system_processes:
                    # Asignar DSCP bajo (8 = Class Selector 1, baja prioridad)
                    policy_name = f"QoSLimit_{proc.info['name']}_{proc.info['pid']}"
                    
                    # Eliminar política antigua si existe
                    subprocess.run(
                        ['powershell', '-Command', f'Remove-NetQosPolicy -Name "{policy_name}" -Confirm:$false'],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        stderr=subprocess.DEVNULL
                    )
                    
                    # Crear nueva política con prioridad baja
                    cmd = f'New-NetQosPolicy -Name "{policy_name}" -AppPath "{proc.exe()}" -DSCPAction 8'
                    subprocess.run(
                        ['powershell', '-Command', cmd],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        stderr=subprocess.DEVNULL
                    )
                    limited_count += 1
            except Exception:
                pass
        
        print(f"[QoS] Limitados {limited_count} procesos de sistema")


class NetworkLatencyOptimizer:
    """Optimiza latencia de red dinámicamente con monitoreo de ping"""
    
    def __init__(self):
        from collections import deque
        self.latency_history = deque(maxlen=100)
        self.target_servers = ['8.8.8.8', '1.1.1.1']  # Google DNS y Cloudflare
        print("[NetLatency] Optimizador de latencia inicializado")
    
    def measure_latency(self):
        """Mide latencia actual haciendo ping a servidores"""
        latencies = []
        
        for server in self.target_servers:
            try:
                # Usar ping de Windows
                result = subprocess.run(
                    ['ping', '-n', '1', '-w', '1000', server],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                # Parsear resultado
                if 'tiempo=' in result.stdout or 'time=' in result.stdout:
                    # Extraer tiempo en ms
                    import re
                    match = re.search(r'(?:tiempo|time)[=<](\d+)', result.stdout)
                    if match:
                        latencies.append(int(match.group(1)))
            except Exception:
                pass
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            return avg_latency
        return None
    
    def adaptive_optimization(self):
        """Optimiza basándose en latencia medida"""
        current_latency = self.measure_latency()
        
        if current_latency is None:
            return
        
        self.latency_history.append(current_latency)
        
        if len(self.latency_history) >= 5:
            avg_latency = sum(self.latency_history) / len(self.latency_history)
            
            if avg_latency > 50:  # ms - Latencia alta
                print(f"[NetLatency] Latencia alta ({avg_latency:.1f}ms), optimizando agresivamente...")
                self.disable_nagle()
                self.set_tcp_ack_frequency(1)
                self.enable_tcp_timestamps()
            
            elif avg_latency < 20:  # ms - Latencia baja
                print(f"[NetLatency] Latencia baja ({avg_latency:.1f}ms), configuración balanceada")
                self.set_tcp_ack_frequency(2)
    
    def disable_nagle(self):
        """Deshabilita el algoritmo de Nagle para reducir latencia"""
        try:
            from kernel import RegistryManager
            reg_manager = RegistryManager()
            
            # Deshabilitar Nagle en todas las interfaces
            key_path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
            
            # TcpAckFrequency = 1 (enviar ACK inmediatamente)
            # TCPNoDelay = 1 (deshabilitar Nagle)
            reg_manager.write_dword(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                "TcpAckFrequency",
                1
            )
            
            print("[NetLatency] Algoritmo de Nagle deshabilitado")
        except Exception as e:
            print(f"[NetLatency] Error deshabilitando Nagle: {e}")
    
    def set_tcp_ack_frequency(self, frequency):
        """Establece frecuencia de ACK de TCP"""
        try:
            from kernel import RegistryManager
            reg_manager = RegistryManager()
            reg_manager.write_dword(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                "TcpAckFrequency",
                frequency
            )
            print(f"[NetLatency] TCP ACK frequency establecida en {frequency}")
        except Exception as e:
            print(f"[NetLatency] Error estableciendo ACK frequency: {e}")
    
    def enable_tcp_timestamps(self):
        """Habilita TCP timestamps para mejor medición de RTT"""
        try:
            from kernel import RegistryManager
            reg_manager = RegistryManager()
            reg_manager.write_dword(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                "Tcp1323Opts",
                3  # Habilita timestamps y window scaling
            )
            print("[NetLatency] TCP timestamps habilitados")
        except Exception as e:
            print(f"[NetLatency] Error habilitando timestamps: {e}")


class BandwidthShaper:
    """Controla ancho de banda por proceso usando QoS de Windows"""
    
    def __init__(self):
        self.limits = {}
        print("[BandwidthShaper] Gestor de ancho de banda inicializado")
    
    def set_bandwidth_limit(self, pid, limit_mbps):
        """Establece límite de ancho de banda para un proceso"""
        try:
            proc = psutil.Process(pid)
            process_name = proc.name()
            policy_name = f"BW_Limit_{pid}"
            
            # Eliminar política antigua si existe
            subprocess.run(
                ['powershell', '-Command', f'Remove-NetQosPolicy -Name "{policy_name}" -Confirm:$false'],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stderr=subprocess.DEVNULL
            )
            
            # Crear política QoS con límite de ancho de banda
            # ThrottleRateActionBitsPerSecond en bits por segundo
            bps = limit_mbps * 1000000
            cmd = f'New-NetQosPolicy -Name "{policy_name}" -AppPathNameMatchCondition "{proc.exe()}" -ThrottleRateActionBitsPerSecond {bps}'
            
            subprocess.run(
                ['powershell', '-Command', cmd],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stderr=subprocess.DEVNULL
            )
            
            self.limits[pid] = limit_mbps
            print(f"[BandwidthShaper] Límite de {limit_mbps}Mbps establecido para PID {pid} ({process_name})")
        
        except Exception as e:
            print(f"[BandwidthShaper] Error estableciendo límite de ancho de banda: {e}")
    
    def monitor_bandwidth_usage(self):
        """Monitorea uso de ancho de banda por proceso"""
        usage_stats = []
        
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                io = proc.io_counters()
                # Calcular uso aproximado (bytes totales)
                total_bytes = io.read_bytes + io.write_bytes
                usage_stats.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'total_bytes': total_bytes
                })
            except Exception:
                pass
        
        return usage_stats
    
    def get_process_name(self, pid):
        """Obtiene el nombre de un proceso por PID"""
        try:
            return psutil.Process(pid).name()
        except Exception:
            return "Unknown"