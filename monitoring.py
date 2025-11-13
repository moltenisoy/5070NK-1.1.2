"""
Módulo Monitorización (Detección de Hardware y Sistema)
-------------------------------------------------------

Este módulo es de solo lectura. Su única función es recopilar datos
sobre el hardware del sistema y el estado del software, proporcionando
esta información al Gestor para que tome decisiones.
"""
import subprocess
import json
import os
import time
import ctypes
import psutil
from core import kernel32, PROCESSENTRY32, TH32CS_SNAPPROCESS, INVALID_HANDLE_VALUE

class HardwareDetector:
    """Detecta el tipo de CPU, GPU y almacenamiento usando WMIC."""
    def __init__(self):
        self.cpu_info = self._detect_cpu()
        self.gpu_info = self._detect_gpu()
        self.storage_info = self._detect_storage()
        
        self.is_intel = 'intel' in self.cpu_info.get('manufacturer', '').lower()
        self.is_amd = 'amd' in self.cpu_info.get('manufacturer', '').lower()
        self.is_ssd = any(st['MediaType'] == 'SSD' for st in self.storage_info)
        self.is_nvme = any('nvme' in st['InterfaceType'].lower() for st in self.storage_info)

    def _execute_wmic(self, command):
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Error al ejecutar WMIC '{command[0]}...': {e}")
            return ""

    def _detect_cpu(self):
        output = self._execute_wmic("wmic cpu get manufacturer,name /format:list")
        info = {k.strip().lower(): v.strip() for k, v in (line.split('=', 1) for line in output.splitlines() if '=' in line)}
        return info

    def _detect_gpu(self):
        output = self._execute_wmic("wmic path win32_VideoController get name /format:list")
        info = {'gpus': [v.strip() for k, v in (line.split('=', 1) for line in output.splitlines() if '=' in line)]}
        return info

    def _detect_storage(self):
        # Esta consulta es más compleja y puede devolver múltiples bloques por disco
        output = self._execute_wmic("wmic diskdrive get MediaType,Model,InterfaceType /format:list")
        devices = []
        current_device = {}
        for line in output.splitlines():
            if not line.strip():
                if current_device:
                    devices.append(current_device)
                    current_device = {}
            elif '=' in line:
                key, value = line.split('=', 1)
                current_device[key.strip()] = value.strip()
        if current_device:
            devices.append(current_device)
        return devices

class CPPTopology:
    """
    Consulta y mapea la topología exacta de la CPU (P-cores, E-cores, Cachés, NUMA).
    Utiliza un archivo de caché para acelerar inicios futuros.
    """
    CACHE_FILE = ".cpu_topology_cache.json"

    def __init__(self):
        self.topology = {}
        if os.path.exists(self.CACHE_FILE):
            print("Cargando topología de CPU desde caché...")
            with open(self.CACHE_FILE, 'r') as f:
                self.topology = json.load(f)
        else:
            print("Consultando topología de CPU desde el sistema (puede tardar)...")
            self._query_cpu_topology()
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.topology, f, indent=4)
        
        self.p_cores = self.topology.get("p_cores", [])
        self.e_cores = self.topology.get("e_cores", [])
        self.l3_cache_groups = self.topology.get("l3_cache_groups", [])
        self.numa_nodes = self.topology.get("numa_nodes", [])

    def _query_cpu_topology(self):
        # Esta es una implementación simplificada. Una real sería mucho más compleja,
        # iterando sobre GetLogicalProcessorInformationEx y parseando las estructuras.
        # Por ahora, usamos psutil como una aproximación de alto nivel.
        physical_cores = psutil.cpu_count(logical=False)
        logical_cores = psutil.cpu_count(logical=True)
        
        self.topology['total_physical_cores'] = physical_cores
        self.topology['total_logical_cores'] = logical_cores

        # Heurística simple para P/E cores (no siempre precisa)
        # Una implementación real usaría `GetLogicalProcessorInformationEx`
        # y buscaría `RelationProcessorCore` para obtener `EfficiencyClass`.
        if logical_cores > physical_cores and physical_cores > 4: # Sugiere SMT y posiblemente P/E
             self.topology['p_cores'] = list(range(0, physical_cores * 2, 2))
             self.topology['e_cores'] = list(range(physical_cores * 2, logical_cores))
             # Esto es una suposición y requeriría una lógica mucho más robusta
             if not self.topology['e_cores']: # Fallback para SMT simple
                 self.topology['p_cores'] = list(range(logical_cores))
                 self.topology['smt_pairs'] = [(i, i+1) for i in range(0, logical_cores, 2)]
        else:
            self.topology['p_cores'] = list(range(logical_cores))
            self.topology['e_cores'] = []

        # ... Lógica para L3 y NUMA usando GetLogicalProcessorInformation(Ex) iría aquí ...
        self.topology['l3_cache_groups'] = [self.topology['p_cores']]
        self.topology['numa_nodes'] = [self.topology['p_cores']]

class ProcessSnapshotEngine:
    """
    Utiliza CreateToolhelp32Snapshot para listar procesos de forma rápida y eficiente.
    """
    def __init__(self):
        self._process_cache = []
        self._last_scan_time = 0
        self.cache_ttl = 1.0 # segundos

    def get_all_processes(self):
        if time.monotonic() - self._last_scan_time < self.cache_ttl:
            return self._process_cache

        processes = []
        h_snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if h_snapshot == INVALID_HANDLE_VALUE:
            return []

        pe32 = PROCESSENTRY32()
        pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)

        if kernel32.Process32First(h_snapshot, ctypes.byref(pe32)):
            while True:
                processes.append({
                    "pid": pe32.th32ProcessID,
                    "name": pe32.szExeFile.decode('utf-8', 'ignore'),
                    "parent_pid": pe32.th32ParentProcessID
                })
                if not kernel32.Process32Next(h_snapshot, ctypes.byref(pe32)):
                    break
        
        kernel32.CloseHandle(h_snapshot)
        self._process_cache = processes
        self._last_scan_time = time.monotonic()
        return self._process_cache

class SystemMonitor:
    """Clase principal de monitorización que agrupa todas las funcionalidades."""
    def __init__(self):
        self.hardware = HardwareDetector()
        self.cpu_topology = CPPTopology()
        self.snapshot_engine = ProcessSnapshotEngine()
        self.process_tree_cache = {}

    def get_process_tree(self, root_pid):
        """Construye y devuelve un árbol de procesos a partir de un PID raíz."""
        all_procs = self.snapshot_engine.get_all_processes()
        # Construir un mapa de padre a hijos para una búsqueda eficiente
        parent_map = {}
        for p in all_procs:
            parent_id = p['parent_pid']
            if parent_id not in parent_map:
                parent_map[parent_id] = []
            parent_map[parent_id].append(p['pid'])
            
        tree = {root_pid}
        queue = [root_pid]
        while queue:
            current_pid = queue.pop(0)
            if current_pid in parent_map:
                children = parent_map[current_pid]
                for child_pid in children:
                    if child_pid not in tree:
                        tree.add(child_pid)
                        queue.append(child_pid)
        return list(tree)

    def measure_network_latency(self, target='8.8.8.8'):
        try:
            result = subprocess.run(
                ['ping', '-n', '1', '-w', '1000', target],
                capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.splitlines():
                if 'Average' in line or 'Media' in line:
                    return int(line.split(' = ')[-1].replace('ms', ''))
            return 100 # Fallback
        except Exception:
            return 100 # Fallback

    def is_overheating(self, thresholds):
        """Compara las temperaturas actuales con los umbrales del usuario."""
        temps = psutil.sensors_temperatures()
        if not temps:
            return False
            
        # Buscar la temperatura del paquete de la CPU
        cpu_temps = temps.get('coretemp', []) or temps.get('k10temp', [])
        if not cpu_temps:
            return False

        # Asumimos que la temperatura más alta es la relevante
        current_max_temp = max(t.current for t in cpu_temps)
        return current_max_temp >= thresholds['soft']