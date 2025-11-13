"""
Módulo Gestión de Procesos
---------------------------

Este módulo contiene los motores para aplicar activamente cambios
a procesos y hilos específicos en tiempo real, según las instrucciones
del Gestor.
"""
import ctypes
from core import kernel32, ntdll, advapi32, ProcessHandleCache, PROCESS_POWER_THROTTLING_STATE, TH32CS_SNAPTHREAD, THREADENTRY32
import psutil

class BatchedSettingsApplicator:
    """Motor para aplicar un lote de ajustes a un PID de forma eficiente."""
    def __init__(self, handle_cache):
        self.handle_cache = handle_cache

    def apply_batched_settings(self, pid, settings_dict):
        if not settings_dict:
            return
        
        handle = self.handle_cache.get_handle(pid)
        if not handle:
            return

        for setting, value in settings_dict.items():
            try:
                if setting == 'priority': self._apply_priority(handle, value)
                elif setting == 'priority_boost': self._apply_priority_boost(handle, value)
                elif setting == 'page_priority': self._apply_page_priority(handle, value)
                elif setting == 'working_set_trim': self._apply_working_set_trim(handle)
                elif setting == 'affinity': self._apply_affinity(handle, value)
                elif setting == 'io_priority': psutil.Process(pid).ionice(value)
                elif setting == 'eco_qos': self._apply_eco_qos(handle, value)
                elif setting == 'thread_io_priority': self._apply_thread_io_priority(pid, value)
            except Exception as e:
                print(f"Error aplicando '{setting}' a PID {pid}: {e}")

    def _apply_priority(self, handle, priority_class):
        priority_map = {
            'REALTIME': 256, 'HIGH': 128, 'ABOVE_NORMAL': 32768,
            'NORMAL': 32, 'BELOW_NORMAL': 16384, 'IDLE': 64
        }
        if isinstance(priority_class, str) and priority_class in priority_map:
            priority_class = priority_map[priority_class]
        kernel32.SetPriorityClass(handle, priority_class)

    def _apply_priority_boost(self, handle, disable_boost):
        kernel32.SetProcessPriorityBoost(handle, ctypes.wintypes.BOOL(disable_boost))

    def _apply_page_priority(self, handle, priority_level):
        info = ctypes.c_ulong(priority_level)
        ntdll.NtSetInformationProcess(handle, 39, ctypes.byref(info), ctypes.sizeof(info))

    def _apply_working_set_trim(self, handle):
        # El valor -1 es una señal a Windows para que libere la mayor cantidad de memoria posible
        kernel32.SetProcessWorkingSetSizeEx(handle, -1, -1, 0)
    
    def _apply_affinity(self, handle, cores_list):
        mask = sum(1 << core for core in cores_list)
        kernel32.SetProcessAffinityMask(handle, ctypes.pointer(ctypes.c_ulong(mask)))

    def _apply_eco_qos(self, handle, enable):
        state = PROCESS_POWER_THROTTLING_STATE()
        state.Version = 1
        state.ControlMask = 1 # PROCESS_POWER_THROTTLING_EXECUTION_SPEED
        state.StateMask = 1 if enable else 0
        ntdll.NtSetInformationProcess(handle, 77, ctypes.byref(state), ctypes.sizeof(state))
    
    def _apply_thread_io_priority(self, pid, priority):
        h_snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
        te32 = THREADENTRY32()
        te32.dwSize = ctypes.sizeof(THREADENTRY32)
        if kernel32.Thread32First(h_snapshot, ctypes.byref(te32)):
            while True:
                if te32.th32OwnerProcessID == pid:
                    THREAD_SET_INFORMATION = 0x0020
                    h_thread = kernel32.OpenThread(THREAD_SET_INFORMATION, False, te32.th32ThreadID)
                    if h_thread:
                        # ntdll.NtSetInformationThread con ThreadIoPriority (43)
                        pass # Implementación compleja, omitida por brevedad
                    kernel32.CloseHandle(h_thread)
                if not kernel32.Thread32Next(h_snapshot, ctypes.byref(te32)):
                    break
        kernel32.CloseHandle(h_snapshot)

class ProcessSuspensionManager:
    """Gestiona la suspensión y reanudación de procesos."""
    def suspend_process(self, pid):
        PROCESS_SUSPEND_RESUME = 0x0800
        handle = kernel32.OpenProcess(PROCESS_SUSPEND_RESUME, False, pid)
        if handle:
            ntdll.NtSuspendProcess(handle)
            kernel32.CloseHandle(handle)

    def resume_process(self, pid):
        PROCESS_SUSPEND_RESUME = 0x0800
        handle = kernel32.OpenProcess(PROCESS_SUSPEND_RESUME, False, pid)
        if handle:
            ntdll.NtResumeProcess(handle)
            kernel32.CloseHandle(handle)

class JobObjectManager:
    """Gestiona los Job Objects de Windows para agrupar y limitar procesos."""
    def __init__(self):
        self.jobs = {}

    def ensure_job_for_group(self, group_name):
        if group_name in self.jobs:
            return self.jobs[group_name]
        
        job_handle = kernel32.CreateJobObjectW(None, group_name)
        self.jobs[group_name] = job_handle
        return job_handle

    def set_job_cpu_limit(self, job_handle, limit_percent):
        # Implementación simplificada usando ctypes
        # En producción se usarían las estructuras JOBOBJECT_*_INFORMATION completas
        pass
    
    def assign_pid_to_job(self, job_handle, pid):
        PROCESS_SET_QUOTA = 0x0100
        PROCESS_TERMINATE = 0x0001
        proc_handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
        if proc_handle:
            kernel32.AssignProcessToJobObject(job_handle, proc_handle)
            # No cerramos el handle del proceso aquí; el Job Object lo gestiona

class AdvancedJobManager:
    """Gestión avanzada de Job Objects con control exhaustivo"""
    
    def __init__(self):
        self.jobs = {}
        print("[AdvancedJobManager] Inicializado")
    
    def create_gaming_job(self, pids):
        """Crea Job Object optimizado para juegos"""
        try:
            job_name = "GamingJob_" + str(hash(tuple(pids)))
            job = kernel32.CreateJobObjectW(None, job_name)
            
            if not job:
                print("[AdvancedJobManager] Error creando Job Object")
                return None
            
            # Asignar procesos al job
            for pid in pids:
                PROCESS_SET_QUOTA = 0x0100
                PROCESS_TERMINATE = 0x0001
                handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
                if handle:
                    kernel32.AssignProcessToJobObject(job, handle)
                    kernel32.CloseHandle(handle)
            
            self.jobs[job_name] = job
            print(f"[AdvancedJobManager] Job Object creado para {len(pids)} procesos")
            return job
        
        except Exception as e:
            print(f"[AdvancedJobManager] Error creando gaming job: {e}")
            return None


class OptimizedServicesManager:
    """
    Gestor de servicios optimizados con 3 modos:
    - APAGADO: Servicios funcionan normalmente
    - ENCENDIDO: Desactiva servicios innecesarios y ajusta otros
    - AGRESIVO: Desactiva también telemetría y diagnósticos
    """
    
    # Servicios a desactivar en modo ENCENDIDO
    SERVICES_TO_DISABLE = [
        "BITS",  # Background Intelligent Transfer Service
        "defragsvc",  # Desfragmentación
        "DoSvc",  # Delivery Optimization
        "MapsBroker",  # Mapas descargados
        "SysMain",  # Superfetch
        "AssignedAccessManagerSvc",
        "autotimesvc",
        "AxInstSV",
        "BcmBtRSupport",
        "BTAGService",
        "BthAvctpSvc",
        "CertPropSvc",
        "CscService",
        "DiagTrack",  # Telemetría
        "diagnosticshub.standardcollector.service",
        "dmwappushservice",
        "DusmSvc",
        "Fax",
        "fhsvc",
        "lfsvc",
        "Netlogon",
        "NetTcpPortSharing",
        "RemoteAccess",
        "RemoteRegistry",
        "RetailDemo",
        "ScDeviceEnum",
        "SCPolicySvc",
        "SEMgrSvc",
        "SensorDataService",
        "SensorMonitoringService",
        "SensorService",
        "shpamsvc",
        "SmsRouter",
        "Spooler",  # Solo si no usa impresora
        "TabletInputService",
        "TapiSrv",
        "TermService",
        "UevAgentService",
        "WalletService",
        "WbioSrvc",
        "WerSvc",  # Windows Error Reporting
        "WFDSConMgrSvc",
        "WiaRpc",
        "WlanSvc"  # Solo si usa Ethernet
    ]
    
    # Servicios a pasar a inicio MANUAL
    SERVICES_TO_MANUAL = [
        "WMPNetworkSvc",  # Windows Media Player Network Sharing
        "WSearch",  # Windows Search
        "wuauserv",  # Windows Update
        "UsoSvc",  # Update Orchestrator Service
        "WaaSMedicSvc",  # Windows Update Medic Service
        "uhssvc",  # Microsoft Update Health Service
        "upfc",  # Update Facilitator Service
    ]
    
    # Servicios adicionales de telemetría y diagnóstico (modo AGRESIVO)
    TELEMETRY_SERVICES = [
        "DiagTrack",
        "dmwappushservice",
        "diagnosticshub.standardcollector.service",
        "WerSvc",
        "wercplsupport",
        "PcaSvc",
        "DPS",
        "WdiServiceHost",
        "WdiSystemHost",
        "TrkWks",
        "SysMain",
        "CDPSvc",
        "CDPUserSvc",
        "OneSyncSvc",
        "UnistoreSvc"
    ]
    
    # Procesos que pueden detenerse durante gaming local
    LOCAL_GAMING_STOPPABLE = [
        "OneDrive.exe",
        "SkypeApp.exe",
        "Spotify.exe",
        "Discord.exe",  # Si no se usa para comunicación
        "Steam.exe",  # Excepto el juego que se está ejecutando
        "EpicGamesLauncher.exe",
        "Origin.exe",
        "upc.exe",  # Ubisoft Connect
        "Dropbox.exe",
        "GoogleDriveFS.exe",
        "Teams.exe",
        "Slack.exe",
        "Chrome.exe",  # Navegadores
        "Firefox.exe",
        "MicrosoftEdge.exe",
        "Outlook.exe",
        "EXCEL.EXE",
        "WINWORD.EXE",
        "POWERPNT.EXE"
    ]
    
    # Procesos para gaming online (mantener conectividad)
    ONLINE_GAMING_STOPPABLE = [
        "OneDrive.exe",
        "Dropbox.exe",
        "GoogleDriveFS.exe",
        "Teams.exe",
        "Slack.exe",
        "Outlook.exe",
        "EXCEL.EXE",
        "WINWORD.EXE",
        "POWERPNT.EXE",
        "Spotify.exe"  # Excepto si se usa música de fondo
    ]
    
    def __init__(self):
        self.current_mode = "OFF"  # OFF, ON, AGGRESSIVE
        self.original_states = {}  # Para restaurar
        self.stopped_processes = []
        print("[OptimizedServices] Gestor de servicios inicializado en modo OFF")
    
    def set_mode(self, mode):
        """Establece el modo: OFF, ON, o AGGRESSIVE"""
        mode = mode.upper()
        if mode not in ["OFF", "ON", "AGGRESSIVE"]:
            print(f"[OptimizedServices] Modo inválido: {mode}")
            return False
        
        print(f"[OptimizedServices] Cambiando modo de {self.current_mode} a {mode}")
        
        if mode == "OFF":
            self._restore_original_state()
        elif mode == "ON":
            self._apply_standard_optimizations()
        elif mode == "AGGRESSIVE":
            self._apply_aggressive_optimizations()
        
        self.current_mode = mode
        return True
    
    def _get_service_startup_type(self, service_name):
        """Obtiene el tipo de inicio actual de un servicio"""
        try:
            import subprocess
            result = subprocess.run(
                ['sc', 'qc', service_name],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if 'START_TYPE' in result.stdout:
                if 'AUTO_START' in result.stdout:
                    return 'auto'
                elif 'DEMAND_START' in result.stdout:
                    return 'demand'
                elif 'DISABLED' in result.stdout:
                    return 'disabled'
            
            return None
        except Exception:
            return None
    
    def _apply_standard_optimizations(self):
        """Aplica optimizaciones estándar (modo ON)"""
        print("[OptimizedServices] Aplicando optimizaciones estándar...")
        
        # Guardar estado original antes de cambiar
        for service in self.SERVICES_TO_DISABLE + self.SERVICES_TO_MANUAL:
            if service not in self.original_states:
                startup_type = self._get_service_startup_type(service)
                if startup_type:
                    self.original_states[service] = startup_type
        
        # Desactivar servicios
        disabled_count = 0
        for service in self.SERVICES_TO_DISABLE:
            if self._disable_service(service):
                disabled_count += 1
        
        print(f"[OptimizedServices] Desactivados {disabled_count} servicios")
        
        # Pasar a manual
        manual_count = 0
        for service in self.SERVICES_TO_MANUAL:
            if self._set_service_manual(service):
                manual_count += 1
        
        print(f"[OptimizedServices] {manual_count} servicios configurados en inicio manual")
    
    def _apply_aggressive_optimizations(self):
        """Aplica optimizaciones agresivas (modo AGGRESSIVE)"""
        print("[OptimizedServices] Aplicando optimizaciones AGRESIVAS...")
        
        # Primero aplicar optimizaciones estándar
        self._apply_standard_optimizations()
        
        # Luego desactivar telemetría y diagnósticos
        telemetry_count = 0
        for service in self.TELEMETRY_SERVICES:
            if service not in self.original_states:
                startup_type = self._get_service_startup_type(service)
                if startup_type:
                    self.original_states[service] = startup_type
            
            if self._disable_service(service):
                telemetry_count += 1
        
        print(f"[OptimizedServices] Desactivados {telemetry_count} servicios de telemetría/diagnóstico")
    
    def _restore_original_state(self):
        """Restaura el estado original de todos los servicios"""
        print("[OptimizedServices] Restaurando estado original de servicios...")
        
        restored_count = 0
        for service, startup_type in self.original_states.items():
            if self._set_service_startup_type(service, startup_type):
                restored_count += 1
        
        print(f"[OptimizedServices] Restaurados {restored_count} servicios")
        self.original_states.clear()
    
    def _disable_service(self, service_name):
        """Desactiva un servicio"""
        try:
            import subprocess
            # Detener servicio
            subprocess.run(
                ['sc', 'stop', service_name],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5
            )
            
            # Deshabilitar servicio
            result = subprocess.run(
                ['sc', 'config', service_name, 'start=', 'disabled'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5
            )
            
            return result.returncode == 0
        except Exception as e:
            # Servicio puede no existir o no tener permisos
            return False
    
    def _set_service_manual(self, service_name):
        """Establece un servicio en inicio manual"""
        try:
            import subprocess
            result = subprocess.run(
                ['sc', 'config', service_name, 'start=', 'demand'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _set_service_startup_type(self, service_name, startup_type):
        """Establece el tipo de inicio de un servicio"""
        try:
            import subprocess
            type_map = {
                'auto': 'auto',
                'demand': 'demand',
                'disabled': 'disabled'
            }
            
            sc_type = type_map.get(startup_type, 'demand')
            result = subprocess.run(
                ['sc', 'config', service_name, 'start=', sc_type],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def stop_processes_for_gaming(self, mode='local'):
        """Detiene procesos según el modo de gaming (local u online)"""
        process_list = self.LOCAL_GAMING_STOPPABLE if mode == 'local' else self.ONLINE_GAMING_STOPPABLE
        
        print(f"[OptimizedServices] Deteniendo procesos para gaming {mode}...")
        
        stopped_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] in process_list:
                    proc.terminate()
                    self.stopped_processes.append(proc.info['pid'])
                    stopped_count += 1
            except Exception:
                pass
        
        print(f"[OptimizedServices] Detenidos {stopped_count} procesos")


class ProcessManager:
    """Clase principal que agrupa todas las funcionalidades de gestión de procesos."""
    def __init__(self):
        self.handle_cache = ProcessHandleCache()
        self.settings_applicator = BatchedSettingsApplicator(self.handle_cache)
        self.suspension_manager = ProcessSuspensionManager()
        self.job_manager = JobObjectManager()
        
        # Nuevos gestores
        self.advanced_job_manager = AdvancedJobManager()
        self.services_manager = OptimizedServicesManager()

    def apply_eco_qos_to_all_background(self, foreground_pid):
        for p in psutil.process_iter(['pid']):
            if p.pid != foreground_pid:
                self.settings_applicator.apply_batched_settings(p.pid, {'eco_qos': True})