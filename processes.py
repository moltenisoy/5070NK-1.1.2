"""
Módulo Gestión de Procesos
---------------------------

Este módulo contiene los motores para aplicar activamente cambios
a procesos y hilos específicos en tiempo real, según las instrucciones
del Gestor.
"""
import ctypes
from core import kernel32, ntdll, advapi32, ProcessHandleCache, PROCESS_POWER_THROTTLING_STATE, TH32CS_SNAPTHREAD, THREADENTRY32
import win32process
import win32job
import win32api
import win32con
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
        win32process.SetPriorityClass(handle, priority_class)

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
        kernel32.SetProcessAffinityMask(handle, ctypes.c_ulong(mask))

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
                    h_thread = kernel32.OpenThread(win32con.THREAD_SET_INFORMATION, False, te32.th32ThreadID)
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
        handle = win32api.OpenProcess(win32con.PROCESS_SUSPEND_RESUME, False, pid)
        if handle:
            ntdll.NtSuspendProcess(handle)
            win32api.CloseHandle(handle)

    def resume_process(self, pid):
        handle = win32api.OpenProcess(win32con.PROCESS_SUSPEND_RESUME, False, pid)
        if handle:
            ntdll.NtResumeProcess(handle)
            win32api.CloseHandle(handle)

class JobObjectManager:
    """Gestiona los Job Objects de Windows para agrupar y limitar procesos."""
    def __init__(self):
        self.jobs = {}

    def ensure_job_for_group(self, group_name):
        if group_name in self.jobs:
            return self.jobs[group_name]
        
        job_handle = win32job.CreateJobObject(None, group_name)
        self.jobs[group_name] = job_handle
        return job_handle

    def set_job_cpu_limit(self, job_handle, limit_percent):
        info = win32job.QueryInformationJobObject(job_handle, win32job.JobObjectExtendedLimitInformation)
        info['BasicLimitInformation']['LimitFlags'] = win32job.JOB_OBJECT_LIMIT_CPU_RATE_CONTROL
        win32job.SetInformationJobObject(job_handle, win32job.JobObjectExtendedLimitInformation, info)

        rate_info = {'CpuRate': limit_percent * 100, 'ControlFlags': win32job.JOB_OBJECT_CPU_RATE_CONTROL_ENABLE}
        win32job.SetInformationJobObject(job_handle, win32job.JobObjectCpuRateControlInformation, rate_info)
    
    def assign_pid_to_job(self, job_handle, pid):
        proc_handle = win32api.OpenProcess(win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, pid)
        if proc_handle:
            win32job.AssignProcessToJobObject(job_handle, proc_handle)
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