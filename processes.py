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

class ProcessManager:
    """Clase principal que agrupa todas las funcionalidades de gestión de procesos."""
    def __init__(self):
        self.handle_cache = ProcessHandleCache()
        self.settings_applicator = BatchedSettingsApplicator(self.handle_cache)
        self.suspension_manager = ProcessSuspensionManager()
        self.job_manager = JobObjectManager()

    def apply_eco_qos_to_all_background(self, foreground_pid):
        for p in psutil.process_iter(['pid']):
            if p.pid != foreground_pid:
                self.settings_applicator.apply_batched_settings(p.pid, {'eco_qos': True})