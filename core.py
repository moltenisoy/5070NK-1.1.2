"""
Módulo Núcleo (Core) - VERSIÓN EXTENDIDA
-----------------------------------------

Este módulo define todas las constantes de bajo nivel, estructuras de ctypes,
carga las funciones de la API de Windows, y proporciona herramientas de utilidad
reutilizables que el Gestor y otros módulos utilizarán.

NUEVAS CARACTERÍSTICAS:
- ✅ Soporte completo para DeviceIoControl (comunicación con drivers)
- ✅ Estructuras extendidas para control de threads
- ✅ Funciones para manipulación de prioridades en kernel
- ✅ Soporte para Job Objects avanzado
- ✅ Herramientas de caché y optimización mejoradas
- ✅ Decoradores de memoización con TTL
- ✅ Pool de estructuras ctypes para reducir GC

Dependencias de Windows API:
- ctypes.WinDLL: Acceso directo a DLLs de Windows
  - kernel32.dll: Gestión de procesos, threads, memoria y dispositivos
  - ntdll.dll: Funciones nativas de bajo nivel del NT kernel
  - advapi32.dll: Funciones de seguridad y privilegios
  - user32.dll: Funciones de ventanas y eventos de interfaz
  - winmm.dll: Funciones multimedia y de tiempo
  - powrprof.dll: Funciones de gestión de energía
  
Nota de compatibilidad:
- Este módulo requiere Windows 10 20H2+ o Windows 11
- Requiere privilegios de administrador para muchas funciones
- WinDLL y WINFUNCTYPE son proporcionados por ctypes estándar de Python
"""

import ctypes
from ctypes import wintypes
import threading
import time
import winreg
from collections import defaultdict, OrderedDict
from functools import wraps
import logging

# Configurar logging
logger = logging.getLogger("Core")

# =============================================================================
# --- 1. DEFINICIÓN DE CONSTANTES Y ESTRUCTURAS (ctypes) ---
# =============================================================================

# --- Constantes Generales ---
PROCESS_ALL_ACCESS = 0x1F0FFF
THREAD_ALL_ACCESS = 0x1F03FF
THREAD_SET_INFORMATION = 0x0020
THREAD_QUERY_INFORMATION = 0x0040
SE_PRIVILEGE_ENABLED = 0x00000002
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04
INVALID_HANDLE_VALUE = -1

# --- Constantes para CreateToolhelp32Snapshot ---
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPTHREAD = 0x00000004
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPALL = TH32CS_SNAPPROCESS | TH32CS_SNAPTHREAD | TH32CS_SNAPMODULE

# --- Constantes para SetWinEventHook ---
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002
EVENT_SYSTEM_FOREGROUND = 0x0003

# --- Constantes para Prioridades ---
THREAD_PRIORITY_TIME_CRITICAL = 15
THREAD_PRIORITY_HIGHEST = 2
THREAD_PRIORITY_ABOVE_NORMAL = 1
THREAD_PRIORITY_NORMAL = 0
THREAD_PRIORITY_BELOW_NORMAL = -1
THREAD_PRIORITY_LOWEST = -2
THREAD_PRIORITY_IDLE = -15

REALTIME_PRIORITY_CLASS = 0x00000100
HIGH_PRIORITY_CLASS = 0x00000080
ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
NORMAL_PRIORITY_CLASS = 0x00000020
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
IDLE_PRIORITY_CLASS = 0x00000040

# --- Constantes para Gestión de Memoria y Procesos ---
PROCESS_PAGE_PRIORITY = 39
PROCESS_POWER_THROTTLING = 77
PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION = 0x4
MEMORY_PRIORITY_NORMAL = 5
MEMORY_PRIORITY_MEDIUM = 3
MEMORY_PRIORITY_LOW = 2
MEMORY_PRIORITY_VERY_LOW = 1
MEMORY_PRIORITY_LOWEST = 0
MEM_LARGE_PAGES = 0x20000000

# --- Constantes para Job Objects ---
JOB_OBJECT_LIMIT_WORKINGSET = 0x00000001
JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
JOB_OBJECT_LIMIT_JOB_TIME = 0x00000004
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_AFFINITY = 0x00000010
JOB_OBJECT_LIMIT_PRIORITY_CLASS = 0x00000020
JOB_OBJECT_LIMIT_PRESERVE_JOB_TIME = 0x00000040
JOB_OBJECT_LIMIT_SCHEDULING_CLASS = 0x00000080
JOB_OBJECT_CPU_RATE_CONTROL_ENABLE = 0x00000001
JOB_OBJECT_CPU_RATE_CONTROL_WEIGHT_BASED = 0x00000002
JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP = 0x00000004
JOB_OBJECT_CPU_RATE_CONTROL_NOTIFY = 0x00000008

# --- Constantes para DeviceIoControl ---
FILE_DEVICE_UNKNOWN = 0x00000022
METHOD_BUFFERED = 0
METHOD_IN_DIRECT = 1
METHOD_OUT_DIRECT = 2
METHOD_NEITHER = 3
FILE_ANY_ACCESS = 0
FILE_READ_ACCESS = 1
FILE_WRITE_ACCESS = 2

# --- Constantes para CreateFile ---
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

# --- Nombres de Privilegios ---
SE_DEBUG_NAME = "SeDebugPrivilege"
SE_LOCK_MEMORY_NAME = "SeLockMemoryPrivilege"
SE_INCREASE_BASE_PRIORITY_NAME = "SeIncreaseBasePriorityPrivilege"
SE_INCREASE_QUOTA_NAME = "SeIncreaseQuotaPrivilege"

# =============================================================================
# --- 2. ESTRUCTURAS CTYPES ---
# =============================================================================

class LUID(ctypes.Structure):
    _fields_ = [
        ("LowPart", wintypes.DWORD),
        ("HighPart", wintypes.LONG),
    ]

class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Luid", LUID),
        ("Attributes", wintypes.DWORD),
    ]

class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", wintypes.DWORD),
        ("Privileges", LUID_AND_ATTRIBUTES * 1),
    ]

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.CHAR * 260),
    ]

class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('cntUsage', wintypes.DWORD),
        ('th32ThreadID', wintypes.DWORD),
        ('th32OwnerProcessID', wintypes.DWORD),
        ('tpBasePri', wintypes.LONG),
        ('tpDeltaPri', wintypes.LONG),
        ('dwFlags', wintypes.DWORD),
    ]

class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
    _fields_ = [
        ("Version", wintypes.ULONG),
        ("ControlMask", wintypes.ULONG),
        ("StateMask", wintypes.ULONG),
    ]

class MEMORY_PRIORITY_INFORMATION(ctypes.Structure):
    _fields_ = [("MemoryPriority", wintypes.ULONG)]

class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]

class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.POINTER(wintypes.ULONG)),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]

class JOBOBJECT_CPU_RATE_CONTROL_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("ControlFlags", wintypes.DWORD),
        ("Value", wintypes.DWORD),  # Puede ser CpuRate o Weight según flags
    ]

class SYSTEM_INFO(ctypes.Structure):
    _fields_ = [
        ("wProcessorArchitecture", wintypes.WORD),
        ("wReserved", wintypes.WORD),
        ("dwPageSize", wintypes.DWORD),
        ("lpMinimumApplicationAddress", wintypes.LPVOID),
        ("lpMaximumApplicationAddress", wintypes.LPVOID),
        ("dwActiveProcessorMask", ctypes.POINTER(wintypes.DWORD)),
        ("dwNumberOfProcessors", wintypes.DWORD),
        ("dwProcessorType", wintypes.DWORD),
        ("dwAllocationGranularity", wintypes.DWORD),
        ("wProcessorLevel", wintypes.WORD),
        ("wProcessorRevision", wintypes.WORD),
    ]

# =============================================================================
# --- 3. CARGA DE FUNCIONES DE LA API DE WINDOWS ---
# =============================================================================

# --- Carga de DLLs ---
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
ntdll = ctypes.WinDLL('ntdll', use_last_error=True)
advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
user32 = ctypes.WinDLL('user32', use_last_error=True)
winmm = ctypes.WinDLL('winmm', use_last_error=True)
powrprof = ctypes.WinDLL('powrprof', use_last_error=True)

# --- Definición de Prototipos de Funciones ---

# Advapi32
advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
advapi32.OpenProcessToken.restype = wintypes.BOOL
advapi32.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(LUID)]
advapi32.LookupPrivilegeValueW.restype = wintypes.BOOL
advapi32.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(TOKEN_PRIVILEGES), wintypes.DWORD, ctypes.POINTER(TOKEN_PRIVILEGES), ctypes.POINTER(wintypes.DWORD)]
advapi32.AdjustTokenPrivileges.restype = wintypes.BOOL

# Kernel32 - Básico
kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.GetCurrentProcessId.argtypes = []
kernel32.GetCurrentProcessId.restype = wintypes.DWORD
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenThread.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

# Kernel32 - Snapshots
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Process32First.restype = wintypes.BOOL
kernel32.Process32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Process32Next.restype = wintypes.BOOL
kernel32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
kernel32.Thread32First.restype = wintypes.BOOL
kernel32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
kernel32.Thread32Next.restype = wintypes.BOOL

# Kernel32 - Afinidad y Prioridad
kernel32.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]
kernel32.SetProcessAffinityMask.restype = wintypes.BOOL
kernel32.SetThreadAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.SetThreadAffinityMask.restype = wintypes.DWORD
kernel32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.SetPriorityClass.restype = wintypes.BOOL
kernel32.SetThreadPriority.argtypes = [wintypes.HANDLE, ctypes.c_int]
kernel32.SetThreadPriority.restype = wintypes.BOOL
kernel32.GetThreadPriority.argtypes = [wintypes.HANDLE]
kernel32.GetThreadPriority.restype = ctypes.c_int
kernel32.SetProcessPriorityBoost.argtypes = [wintypes.HANDLE, wintypes.BOOL]
kernel32.SetProcessPriorityBoost.restype = wintypes.BOOL
kernel32.SetThreadPriorityBoost.argtypes = [wintypes.HANDLE, wintypes.BOOL]
kernel32.SetThreadPriorityBoost.restype = wintypes.BOOL

# Kernel32 - Memoria
kernel32.SetProcessWorkingSetSizeEx.argtypes = [wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
kernel32.SetProcessWorkingSetSizeEx.restype = wintypes.BOOL
kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
kernel32.VirtualAllocEx.restype = wintypes.LPVOID
kernel32.VirtualFreeEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]
kernel32.VirtualFreeEx.restype = wintypes.BOOL

# Kernel32 - Sistema
kernel32.GetSystemInfo.argtypes = [ctypes.POINTER(SYSTEM_INFO)]
kernel32.GetSystemInfo.restype = None

# Kernel32 - Job Objects
kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
kernel32.SetInformationJobObject.restype = wintypes.BOOL
kernel32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryInformationJobObject.restype = wintypes.BOOL

# Kernel32 - DeviceIoControl (✅ NUEVO - Para comunicación con drivers)
kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,  # lpFileName
    wintypes.DWORD,    # dwDesiredAccess
    wintypes.DWORD,    # dwShareMode
    wintypes.LPVOID,   # lpSecurityAttributes
    wintypes.DWORD,    # dwCreationDisposition
    wintypes.DWORD,    # dwFlagsAndAttributes
    wintypes.HANDLE    # hTemplateFile
]
kernel32.CreateFileW.restype = wintypes.HANDLE

kernel32.DeviceIoControl.argtypes = [
    wintypes.HANDLE,                    # hDevice
    wintypes.DWORD,                     # dwIoControlCode
    wintypes.LPVOID,                    # lpInBuffer
    wintypes.DWORD,                     # nInBufferSize
    wintypes.LPVOID,                    # lpOutBuffer
    wintypes.DWORD,                     # nOutBufferSize
    ctypes.POINTER(wintypes.DWORD),     # lpBytesReturned
    wintypes.LPVOID                     # lpOverlapped
]
kernel32.DeviceIoControl.restype = wintypes.BOOL

# Ntdll
ntdll.NtSetInformationProcess.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID, wintypes.ULONG]
ntdll.NtSetInformationProcess.restype = wintypes.LONG
ntdll.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG)]
ntdll.NtQueryInformationProcess.restype = wintypes.LONG
ntdll.NtSuspendProcess.argtypes = [wintypes.HANDLE]
ntdll.NtSuspendProcess.restype = wintypes.LONG
ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
ntdll.NtResumeProcess.restype = wintypes.LONG
ntdll.NtSetInformationThread.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID, wintypes.ULONG]
ntdll.NtSetInformationThread.restype = wintypes.LONG

# User32
WinEventProcType = ctypes.WINFUNCTYPE(
    None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND, wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD
)
user32.SetWinEventHook.argtypes = [wintypes.UINT, wintypes.UINT, wintypes.HMODULE, WinEventProcType, wintypes.DWORD, wintypes.DWORD, wintypes.UINT]
user32.SetWinEventHook.restype = wintypes.HANDLE
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = wintypes.LPARAM
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND

# =============================================================================
# --- 4. FUNCIONES DE PRIVILEGIOS ---
# =============================================================================

def enable_privilege(privilege_name):
    """
    Habilita un privilegio específico para el proceso actual.
    
    :param privilege_name: Nombre del privilegio (ej: SE_DEBUG_NAME)
    :return: True si se habilitó exitosamente, False en caso contrario
    """
    try:
        h_process = kernel32.GetCurrentProcess()
        h_token = wintypes.HANDLE()
        
        if not advapi32.OpenProcessToken(h_process, TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(h_token)):
            logger.error(f"Error al abrir token del proceso: {ctypes.get_last_error()}")
            return False
        
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, privilege_name, ctypes.byref(luid)):
            logger.error(f"Error al buscar privilegio {privilege_name}: {ctypes.get_last_error()}")
            kernel32.CloseHandle(h_token)
            return False
        
        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
        
        if not advapi32.AdjustTokenPrivileges(h_token, False, ctypes.byref(tp), 0, None, None):
            logger.error(f"Error al ajustar privilegios: {ctypes.get_last_error()}")
            kernel32.CloseHandle(h_token)
            return False
        
        error = ctypes.get_last_error()
        kernel32.CloseHandle(h_token)
        
        if error == 1300:  # ERROR_NOT_ALL_ASSIGNED
            logger.warning(f"⚠️  No se pudo obtener el privilegio {privilege_name}. ¿Ejecutando como Admin?")
            return False
        
        logger.info(f"✓ Privilegio habilitado: {privilege_name}")
        return True
        
    except Exception as e:
        logger.error(f"Excepción al habilitar privilegio {privilege_name}: {e}")
        return False

def enable_debug_privilege():
    """Habilita SeDebugPrivilege para el script actual."""
    return enable_privilege(SE_DEBUG_NAME)

def enable_lock_memory_privilege():
    """Habilita SeLockMemoryPrivilege (necesario para páginas grandes)."""
    return enable_privilege(SE_LOCK_MEMORY_NAME)

def enable_increase_priority_privilege():
    """Habilita SeIncreaseBasePriorityPrivilege (para prioridad realtime)."""
    return enable_privilege(SE_INCREASE_BASE_PRIORITY_NAME)

def enable_all_privileges():
    """Habilita todos los privilegios necesarios."""
    privileges = [
        SE_DEBUG_NAME,
        SE_LOCK_MEMORY_NAME,
        SE_INCREASE_BASE_PRIORITY_NAME,
        SE_INCREASE_QUOTA_NAME
    ]
    
    results = {}
    for priv in privileges:
        results[priv] = enable_privilege(priv)
    
    return results

# =============================================================================
# --- 5. CLASES DE UTILIDAD Y CACHÉ ---
# =============================================================================

class ProcessHandleCache:
    """
    Administrador para abrir, retener y cerrar handles de procesos,
    evitando E/S constante y mejorando el rendimiento.
    """
    def __init__(self, access_flags=PROCESS_ALL_ACCESS, max_size=500):
        self._cache = OrderedDict()
        self._lock = threading.Lock()
        self.default_access_flags = access_flags
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get_handle(self, pid):
        """Obtiene un handle de proceso, usando caché si está disponible."""
        with self._lock:
            if pid in self._cache:
                self.hits += 1
                # Mover al final (LRU)
                self._cache.move_to_end(pid)
                return self._cache[pid]
            
            self.misses += 1
            handle = kernel32.OpenProcess(self.default_access_flags, False, pid)
            if not handle or handle == INVALID_HANDLE_VALUE:
                return None
            
            # Agregar a caché
            self._cache[pid] = handle
            
            # Eviction LRU si excede tamaño máximo
            if len(self._cache) > self.max_size:
                oldest_pid, oldest_handle = self._cache.popitem(last=False)
                kernel32.CloseHandle(oldest_handle)
            
            return handle

    def release_handle(self, pid):
        """Libera un handle específico de la caché."""
        with self._lock:
            if pid in self._cache:
                kernel32.CloseHandle(self._cache.pop(pid))

    def clear(self):
        """Limpia toda la caché y cierra todos los handles."""
        with self._lock:
            for handle in self._cache.values():
                try:
                    kernel32.CloseHandle(handle)
                except Exception as e:
                    # Ignorar errores al cerrar handles (pueden estar ya cerrados)
                    logger.debug(f"Error cerrando handle: {e}")
            self._cache.clear()
            logger.info(f"[ProcessHandleCache] Caché limpiada. Stats: {self.hits} hits, {self.misses} misses")

    def stats(self):
        """Retorna estadísticas de la caché."""
        return {
            'size': len(self._cache),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0
        }


class ThreadHandleCache:
    """Caché similar para handles de threads."""
    def __init__(self, access_flags=THREAD_ALL_ACCESS, max_size=1000):
        self._cache = OrderedDict()
        self._lock = threading.Lock()
        self.default_access_flags = access_flags
        self.max_size = max_size

    def get_handle(self, thread_id):
        """Obtiene un handle de thread."""
        with self._lock:
            if thread_id in self._cache:
                self._cache.move_to_end(thread_id)
                return self._cache[thread_id]
            
            handle = kernel32.OpenThread(self.default_access_flags, False, thread_id)
            if not handle or handle == INVALID_HANDLE_VALUE:
                return None
            
            self._cache[thread_id] = handle
            
            if len(self._cache) > self.max_size:
                oldest_tid, oldest_handle = self._cache.popitem(last=False)
                kernel32.CloseHandle(oldest_handle)
            
            return handle

    def release_handle(self, thread_id):
        """Libera un handle de thread."""
        with self._lock:
            if thread_id in self._cache:
                kernel32.CloseHandle(self._cache.pop(thread_id))

    def clear(self):
        """Limpia la caché de threads."""
        with self._lock:
            for handle in self._cache.values():
                try:
                    kernel32.CloseHandle(handle)
                except Exception as e:
                    # Ignorar errores al cerrar handles (pueden estar ya cerrados)
                    logger.debug(f"Error cerrando handle de thread: {e}")
            self._cache.clear()


class ForegroundDebouncer:
    """
    Gestiona eventos de cambio de ventana y evita "thrashing" si el usuario
    alterna rápidamente entre ventanas.
    """
    def __init__(self, debounce_time_ms, callback):
        self.debounce_time = debounce_time_ms / 1000.0
        self.callback = callback
        self.last_event_time = 0
        self.timer = None
        self.last_pid = None
        self.lock = threading.Lock()

    def handle_event(self, pid):
        """Maneja un evento de cambio de ventana con debouncing."""
        with self.lock:
            if pid == self.last_pid:
                return  # No hay cambio real
                
            current_time = time.monotonic()
            
            if self.timer:
                self.timer.cancel()
                
            time_since_last = current_time - self.last_event_time
            
            if time_since_last < self.debounce_time:
                # Demasiado rápido, programar el callback
                self.timer = threading.Timer(self.debounce_time, self._execute_callback, [pid])
                self.timer.start()
            else:
                # Tiempo suficiente ha pasado, ejecutar inmediatamente
                self._execute_callback(pid)
    
    def _execute_callback(self, pid):
        """Ejecuta el callback después del debounce."""
        with self.lock:
            self.last_pid = pid
            self.last_event_time = time.monotonic()
            
        if self.callback:
            try:
                self.callback(pid)
            except Exception as e:
                logger.error(f"[ForegroundDebouncer] Error en callback: {e}")


class CTypesStructurePool:
    """
    Pool de objetos reutilizables para estructuras ctypes.
    Reduce la sobrecarga del GC al reutilizar objetos en lugar de crearlos/destruirlos.
    """
    def __init__(self, structure_class, initial_size=10, max_size=100):
        self.structure_class = structure_class
        self.max_size = max_size
        self._pool = []
        self._lock = threading.Lock()
        self._in_use = set()
        
        # Pre-poblar el pool
        for _ in range(initial_size):
            self._pool.append(structure_class())
    
    def acquire(self):
        """Obtiene una estructura del pool."""
        with self._lock:
            if self._pool:
                obj = self._pool.pop()
            else:
                obj = self.structure_class()
            
            self._in_use.add(id(obj))
            return obj
    
    def release(self, obj):
        """Devuelve una estructura al pool."""
        with self._lock:
            obj_id = id(obj)
            if obj_id not in self._in_use:
                logger.warning("[CTypesStructurePool] Intento de liberar objeto que no estaba en uso")
                return
            
            self._in_use.remove(obj_id)
            
            if len(self._pool) < self.max_size:
                # Limpiar el objeto (establecer todos los campos a 0)
                ctypes.memset(ctypes.addressof(obj), 0, ctypes.sizeof(obj))
                self._pool.append(obj)
    
    def stats(self):
        """Estadísticas del pool."""
        return {
            'available': len(self._pool),
            'in_use': len(self._in_use),
            'total': len(self._pool) + len(self._in_use)
        }


class RegistryWriteBuffer:
    """
    Optimiza escrituras en el registro por lotes.
    Acumula cambios y los aplica periódicamente para reducir I/O.
    """
    def __init__(self, flush_interval=5.0, max_buffer_size=50):
        self.flush_interval = flush_interval
        self.max_buffer_size = max_buffer_size
        self._buffer = []
        self._lock = threading.Lock()
        self._flush_timer = None
        self._start_flush_timer()
    
    def write(self, hkey, subkey, value_name, value, value_type):
        """Agrega una escritura al buffer."""
        with self._lock:
            self._buffer.append((hkey, subkey, value_name, value, value_type))
            
            if len(self._buffer) >= self.max_buffer_size:
                self._flush_now()
    
    def _start_flush_timer(self):
        """Inicia el timer de flush periódico."""
        self._flush_timer = threading.Timer(self.flush_interval, self._flush_periodic)
        self._flush_timer.daemon = True
        self._flush_timer.start()
    
    def _flush_periodic(self):
        """Flush periódico automático."""
        self._flush_now()
        self._start_flush_timer()
    
    def _flush_now(self):
        """Aplica todas las escrituras pendientes."""
        with self._lock:
            if not self._buffer:
                return
            
            for hkey, subkey, value_name, value, value_type in self._buffer:
                try:
                    key = winreg.OpenKey(hkey, subkey, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY)
                    winreg.SetValueEx(key, value_name, 0, value_type, value)
                    winreg.CloseKey(key)
                except Exception as e:
                    logger.debug(f"[RegistryWriteBuffer] Error al escribir {subkey}\\{value_name}: {e}")
            
            logger.debug(f"[RegistryWriteBuffer] Flushed {len(self._buffer)} escrituras al registro")
            self._buffer.clear()
    
    def flush(self):
        """Fuerza un flush inmediato."""
        self._flush_now()
    
    def __del__(self):
        """Asegura que se haga flush al destruir."""
        if self._flush_timer:
            self._flush_timer.cancel()
        self._flush_now()


def memoize_with_ttl(ttl_seconds):
    """
    Decorador de caché con tiempo de vida (Time-To-Live).
    
    Uso:
        @memoize_with_ttl(30)  # Cachear por 30 segundos
        def funcion_costosa(arg1, arg2):
            # Cómputo pesado...
            return resultado
    """
    def decorator(func):
        cache = {}
        cache_times = {}
        lock = threading.Lock()
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Crear clave de caché
            key = (args, tuple(sorted(kwargs.items())))
            current_time = time.time()
            
            with lock:
                # Verificar si está en caché y no ha expirado
                if key in cache:
                    if current_time - cache_times[key] < ttl_seconds:
                        return cache[key]
                    else:
                        # Expiró, eliminar
                        del cache[key]
                        del cache_times[key]
                
                # Ejecutar función y cachear resultado
                result = func(*args, **kwargs)
                cache[key] = result
                cache_times[key] = current_time
                
                # Limpieza de entradas expiradas (cada 100 llamadas)
                if len(cache) > 100:
                    expired_keys = [k for k, t in cache_times.items() if current_time - t >= ttl_seconds]
                    for k in expired_keys:
                        del cache[k]
                        del cache_times[k]
                
                return result
        
        wrapper.cache_clear = lambda: cache.clear() or cache_times.clear()
        wrapper.cache_info = lambda: {'size': len(cache), 'ttl': ttl_seconds}
        
        return wrapper
    return decorator


# =============================================================================
# --- 6. DETECCIÓN DE VENTANA DE PRIMER PLANO ---
# =============================================================================

_foreground_callback = None
_win_event_hook_handle = None

def _win_event_proc(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
    """Función de callback que Windows llama cuando cambia la ventana de primer plano."""
    global _foreground_callback
    if event == EVENT_SYSTEM_FOREGROUND and _foreground_callback:
        try:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value:
                _foreground_callback(pid.value)
        except Exception as e:
            logger.error(f"[ForegroundHook] Error en callback: {e}")

def _hook_thread_proc():
    """Función que se ejecuta en un hilo separado para mantener el bucle de mensajes."""
    global _foreground_callback, _win_event_hook_handle
    
    # Es necesario definir el callback aquí para que ctypes lo mantenga vivo
    c_win_event_proc = WinEventProcType(_win_event_proc)

    _win_event_hook_handle = user32.SetWinEventHook(
        EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
        0, c_win_event_proc, 0, 0, WINEVENT_OUTOFCONTEXT
    )
    
    if not _win_event_hook_handle:
        logger.error(f"[ForegroundHook] Error al establecer WinEventHook: {ctypes.get_last_error()}")
        return

    logger.info("[ForegroundHook] Hook de ventana de primer plano establecido")

    # Bucle de mensajes de Windows
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

def start_foreground_hook(callback_func):
    """
    Inicia el gancho de eventos de ventana de primer plano en un hilo separado.
    
    :param callback_func: La función a llamar cuando cambie la ventana. 
                          Debe aceptar un argumento: el PID del nuevo proceso.
    :return: El thread creado
    """
    global _foreground_callback
    if not callable(callback_func):
        raise TypeError("El callback debe ser una función.")
        
    _foreground_callback = callback_func
    
    hook_thread = threading.Thread(target=_hook_thread_proc, name="WinEventHookThread", daemon=True)
    hook_thread.start()
    return hook_thread


# =============================================================================
# --- 7. FUNCIONES AUXILIARES AVANZADAS ---
# =============================================================================

def get_system_info():
    """Obtiene información del sistema."""
    sys_info = SYSTEM_INFO()
    kernel32.GetSystemInfo(ctypes.byref(sys_info))
    return {
        'processor_architecture': sys_info.wProcessorArchitecture,
        'page_size': sys_info.dwPageSize,
        'num_processors': sys_info.dwNumberOfProcessors,
        'processor_type': sys_info.dwProcessorType,
        'allocation_granularity': sys_info.dwAllocationGranularity
    }


def enumerate_threads(pid):
    """
    Enumera todos los threads de un proceso.
    
    :param pid: Process ID
    :return: Lista de thread IDs
    """
    threads = []
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    
    if snapshot == INVALID_HANDLE_VALUE:
        return threads
    
    try:
        te32 = THREADENTRY32()
        te32.dwSize = ctypes.sizeof(THREADENTRY32)
        
        if kernel32.Thread32First(snapshot, ctypes.byref(te32)):
            while True:
                if te32.th32OwnerProcessID == pid:
                    threads.append(te32.th32ThreadID)
                
                if not kernel32.Thread32Next(snapshot, ctypes.byref(te32)):
                    break
    finally:
        kernel32.CloseHandle(snapshot)
    
    return threads


def ioctl_code(device_type, function, method, access):
    """
    Construye un código IOCTL para DeviceIoControl.
    
    CTL_CODE macro de Windows:
    ((DeviceType) << 16) | ((Access) << 14) | ((Function) << 2) | (Method)
    """
    return (device_type << 16) | (access << 14) | (function << 2) | method


# =============================================================================
# --- INICIALIZACIÓN AUTOMÁTICA ---
# =============================================================================

# Crear instancias globales de cachés para uso compartido
_global_process_cache = ProcessHandleCache()
_global_thread_cache = ThreadHandleCache()

def get_process_cache():
    """Retorna la caché global de handles de procesos."""
    return _global_process_cache

def get_thread_cache():
    """Retorna la caché global de handles de threads."""
    return _global_thread_cache


# =============================================================================
# --- GESTOR DE PRIVILEGIOS MEJORADO ---
# =============================================================================

# Constantes de privilegios adicionales
SE_DEBUG_NAME = "SeDebugPrivilege"
SE_LOCK_MEMORY_NAME = "SeLockMemoryPrivilege"
SE_INCREASE_BASE_PRIORITY_NAME = "SeIncreaseBasePriorityPrivilege"
SE_INCREASE_QUOTA_NAME = "SeIncreaseQuotaPrivilege"
SE_PROF_SINGLE_PROCESS_NAME = "SeProfileSingleProcessPrivilege"
SE_SYSTEM_PROFILE_NAME = "SeSystemProfilePrivilege"

class PrivilegeManager:
    """Gestión avanzada de privilegios del sistema"""
    
    def __init__(self):
        self.required_privileges = [
            SE_DEBUG_NAME,
            SE_LOCK_MEMORY_NAME,
            SE_INCREASE_BASE_PRIORITY_NAME,
            SE_INCREASE_QUOTA_NAME,
            SE_PROF_SINGLE_PROCESS_NAME,
            SE_SYSTEM_PROFILE_NAME
        ]
        
        self.privilege_status = {}
        logger.info("[PrivilegeManager] Inicializando gestor de privilegios")
    
    def check_all_privileges(self):
        """Verifica estado de todos los privilegios"""
        for priv in self.required_privileges:
            self.privilege_status[priv] = self.is_privilege_enabled(priv)
        
        enabled_count = sum(1 for v in self.privilege_status.values() if v)
        logger.info(f"[PrivilegeManager] {enabled_count}/{len(self.required_privileges)} privilegios habilitados")
        return self.privilege_status
    
    def is_privilege_enabled(self, privilege_name):
        """Verifica si un privilegio está habilitado"""
        try:
            # Usar la función existente enable_privilege
            return enable_privilege(privilege_name)
        except Exception as e:
            logger.warning(f"[PrivilegeManager] No se pudo verificar privilegio {privilege_name}: {e}")
            return False
    
    def elevate_if_needed(self):
        """Solicita elevación si es necesario"""
        if not ctypes.windll.shell32.IsUserAnAdmin():
            logger.warning("[PrivilegeManager] Requiere privilegios de administrador")
            return self.request_elevation()
        return True
    
    def request_elevation(self):
        """Solicita UAC elevation"""
        import sys
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, 
                "runas", 
                sys.executable, 
                " ".join(sys.argv), 
                None, 
                1
            )
            logger.info("[PrivilegeManager] Solicitada elevación UAC")
            return True
        except Exception as e:
            logger.error(f"[PrivilegeManager] Error al solicitar elevación: {e}")
            return False


# =============================================================================
# --- POOL DE THREADS OPTIMIZADO ---
# =============================================================================

import queue as queue_module

class SystemThreadPool:
    """Pool de threads optimizado para operaciones del sistema"""
    
    def __init__(self, num_threads=4):
        self.num_threads = num_threads
        self.task_queue = queue_module.PriorityQueue()
        self.threads = []
        self.running = True
        
        logger.info(f"[SystemThreadPool] Inicializando pool con {num_threads} threads")
        
        for i in range(num_threads):
            thread = threading.Thread(
                target=self._worker,
                name=f"SystemWorker-{i}",
                daemon=True
            )
            thread.start()
            self.threads.append(thread)
        
        logger.info(f"[SystemThreadPool] Pool iniciado con {len(self.threads)} workers")
    
    def submit(self, priority, func, *args, **kwargs):
        """Envía tarea con prioridad (menor número = mayor prioridad)"""
        self.task_queue.put((priority, func, args, kwargs))
    
    def _worker(self):
        """Worker thread que procesa tareas"""
        while self.running:
            try:
                priority, func, args, kwargs = self.task_queue.get(timeout=1)
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"[SystemThreadPool] Error en tarea: {e}")
                finally:
                    self.task_queue.task_done()
            except queue_module.Empty:
                continue
            except Exception as e:
                logger.error(f"[SystemThreadPool] Error en worker: {e}")
    
    def shutdown(self):
        """Detiene el pool de threads"""
        logger.info("[SystemThreadPool] Deteniendo pool...")
        self.running = False
        for thread in self.threads:
            thread.join(timeout=2)
        logger.info("[SystemThreadPool] Pool detenido")


# =============================================================================
# --- CONTEXT MANAGERS PARA RECURSOS ---
# =============================================================================

from contextlib import contextmanager

@contextmanager
def process_handle(pid, access=PROCESS_ALL_ACCESS):
    """Context manager para handles de proceso"""
    handle = kernel32.OpenProcess(access, False, pid)
    try:
        yield handle
    finally:
        if handle:
            kernel32.CloseHandle(handle)


@contextmanager
def thread_handle(thread_id, access=THREAD_ALL_ACCESS):
    """Context manager para handles de thread"""
    handle = kernel32.OpenThread(access, False, thread_id)
    try:
        yield handle
    finally:
        if handle:
            kernel32.CloseHandle(handle)


# =============================================================================
# --- MAIN (Pruebas) ---
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("MÓDULO CORE - VERSIÓN EXTENDIDA")
    print("=" * 60)

    print("\n1. Habilitando privilegios...")
    privileges = enable_all_privileges()
    for priv, success in privileges.items():
        status = "✓" if success else "✗"
        print(f"   {status} {priv}")

    print("\n2. Información del sistema:")
    sys_info = get_system_info()
    print(f"   - Procesadores: {sys_info['num_processors']}")
    print(f"   - Tamaño de página: {sys_info['page_size']} bytes")
    print(f"   - Granularidad de asignación: {sys_info['allocation_granularity']} bytes")

    print("\n3. Probando ProcessHandleCache...")
    cache = get_process_cache()
    current_pid = kernel32.GetCurrentProcessId()
    handle = cache.get_handle(current_pid)
    print(f"   - Handle para PID {current_pid}: {handle}")
    print(f"   - Stats: {cache.stats()}")

    print("\n4. Enumerando threads del proceso actual...")
    threads = enumerate_threads(current_pid)
    print(f"   - Threads encontrados: {len(threads)}")
    print(f"   - IDs: {threads[:5]}{'...' if len(threads) > 5 else ''}")

    print("\n5. Iniciando detector de ventana de primer plano (5 segundos)...")
    def test_callback(pid):
        print(f"   → [EVENTO] Nueva ventana: PID {pid}")

    hook_thread = start_foreground_hook(test_callback)
    try:
        time.sleep(5)
        print("   - Prueba finalizada")
    except KeyboardInterrupt:
        pass

    print("\n6. Limpiando cachés...")
    cache.clear()
    print("   - Cachés limpiadas")

    print("\n" + "=" * 60)
    print("✓ TODAS LAS PRUEBAS COMPLETADAS")
    print("=" * 60)