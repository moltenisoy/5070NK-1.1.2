"""
Módulo CPU
----------

Implementa las estrategias avanzadas de planificación y afinidad, basándose
en la topología detectada por ModuloMonitorizacion.
"""
import psutil
import core

class HeterogeneousScheduler:
    """Gestiona la planificación en arquitecturas híbridas (P-cores/E-cores)."""
    def __init__(self, topology):
        self.p_cores = topology.get('p_cores', [])
        self.e_cores = topology.get('e_cores', [])

    def classify_and_schedule_threads(self, pid, is_latency_sensitive):
        """Devuelve una máscara de afinidad para hilos basada en sensibilidad a la latencia."""
        if not self.e_cores:
            return {} # No es una arquitectura híbrida

        target_cores = self.p_cores if is_latency_sensitive else self.e_cores
        return {'thread_affinity': target_cores}

class EnhancedSMTOptimizer:
    """Optimiza la afinidad para SMT (Hyper-Threading)."""
    def __init__(self, topology):
        self.physical_cores_count = topology.get('total_physical_cores')
        self.logical_cores_count = topology.get('total_logical_cores')
        self.all_cores = list(range(self.logical_cores_count))

    def optimize_for_latency(self, pid):
        """Devuelve máscara de afinidad solo para núcleos físicos."""
        if self.logical_cores_count == self.physical_cores_count:
            return {} # No SMT
        
        # Asume que los núcleos físicos son los pares (0, 2, 4...)
        physical_only = [i for i in self.all_cores if i % 2 == 0]
        return {'affinity': physical_only}

    def optimize_for_throughput(self, pid):
        """Devuelve máscara de afinidad para todos los núcleos (físicos y lógicos)."""
        return {'affinity': self.all_cores}
        
class AVXInstructionOptimizer:
    """Detecta y optimiza procesos que usan intensivamente AVX."""
    AVX_KEYWORDS = ['render', 'encode', 'ffmpeg', 'numpy', 'premiere', 'blender', 'v-ray']

    def detect_and_optimize(self, process_name, all_cores):
        if any(keyword in process_name.lower() for keyword in self.AVX_KEYWORDS):
            # Limitar a la mitad de los núcleos para evitar thermal throttling
            target_cores = all_cores[:len(all_cores) // 2]
            return {
                'affinity': target_cores,
                'priority': 32768  # ABOVE_NORMAL_PRIORITY_CLASS
            }
        return {}

class L3CacheOptimizer:
    """Optimiza la afinidad para mejorar la localidad de caché L3."""
    def __init__(self, topology):
        self.l3_groups = topology.get('l3_cache_groups', [])
        # ... Lógica para rastrear la contención en cada grupo ...

    def optimize_process_cache_locality(self, pid):
        if not self.l3_groups: return {}
        # Lógica para encontrar el grupo L3 con menor contención
        target_group = self.l3_groups[0] # Simplificado
        return {'affinity': target_group}

class CPUIDDetector:
    """Detección de CPU usando CPUID para capacidades específicas"""
    
    def __init__(self):
        self.vendor = self.get_vendor()
        self.features = self.detect_features()
    
    def cpuid(self, eax, ecx=0):
        """Ejecuta instrucción CPUID usando ctypes"""
        # Crear array para almacenar resultados
        regs = (ctypes.c_uint32 * 4)()
        
        try:
            # Intentar usar cpuid de psutil si está disponible
            # Nota: implementación simplificada, requiere ensamblador real en producción
            return (0, 0, 0, 0)  # Placeholder
        except Exception:
            return (0, 0, 0, 0)
    
    def get_vendor(self):
        """Obtiene el vendedor de la CPU"""
        try:
            # Usar psutil para obtener info básica
            import platform
            return platform.processor()
        except Exception:
            return "Unknown"
    
    def detect_features(self):
        """Detecta features de CPU disponibles"""
        features = {
            'sse': False,
            'sse2': False,
            'sse3': False,
            'ssse3': False,
            'sse4_1': False,
            'sse4_2': False,
            'avx': False,
            'avx2': False,
            'avx512': False,
            'fma': False,
            'aes': False,
            'sha': False,
            'hybrid_architecture': False,
            'turbo_boost': False
        }
        
        # Detectar arquitectura híbrida (P-cores/E-cores)
        if 'Intel' in self.vendor and hasattr(psutil, 'cpu_freq'):
            # CPUs híbridas tienen frecuencias variables
            features['hybrid_architecture'] = len(set([c.current for c in psutil.cpu_freq(percpu=True)])) > 2
        
        return features
    
    def get_cache_info(self):
        """Obtiene información de cachés L1, L2, L3"""
        caches = {
            'l1_data': 0,
            'l1_instruction': 0,
            'l2': 0,
            'l3': 0
        }
        
        # Usar WMI o registro de Windows para obtener info de caché
        # Implementación simplificada
        return caches


class IntelligentThreadScheduler:
    """Clasifica y programa threads automáticamente según su comportamiento"""
    
    def __init__(self):
        self.thread_profiles = {}
        import time
        self.time = time
    
    def profile_thread(self, thread_id):
        """Perfila un thread para clasificarlo"""
        profile = {
            'cpu_time': 0,
            'context_switches': 0,
            'io_operations': 0,
            'classification': 'unknown'
        }
        
        try:
            # Monitorear thread por breve período
            start_time = self.time.time()
            initial_stats = self._get_thread_stats(thread_id)
            
            # Esperar breve período
            self.time.sleep(0.5)
            
            final_stats = self._get_thread_stats(thread_id)
            
            # Calcular diferencias
            if initial_stats and final_stats:
                cpu_delta = final_stats['cpu_time'] - initial_stats['cpu_time']
                
                # Clasificar basándose en uso de CPU
                if cpu_delta > 0.4:  # Más del 40% del tiempo
                    profile['classification'] = 'cpu_intensive'
                elif cpu_delta < 0.1:  # Menos del 10%
                    profile['classification'] = 'io_bound'
                else:
                    profile['classification'] = 'interactive'
                
                profile['cpu_time'] = cpu_delta
        
        except Exception as e:
            print(f"Error perfilando thread {thread_id}: {e}")
        
        return profile
    
    def _get_thread_stats(self, thread_id):
        """Obtiene estadísticas de un thread"""
        try:
            # Usar psutil para obtener estadísticas
            for proc in psutil.process_iter(['pid']):
                for thread in proc.threads():
                    if thread.id == thread_id:
                        return {
                            'cpu_time': thread.user_time + thread.system_time
                        }
        except Exception:
            pass
        return None
    
    def optimize_thread(self, thread_id, profile):
        """Optimiza un thread basándose en su perfil"""
        try:
            with core.thread_handle(thread_id) as handle:
                if not handle:
                    return
                
                if profile['classification'] == 'cpu_intensive':
                    # Prioridad alta para threads intensivos en CPU
                    core.kernel32.SetThreadPriority(handle, core.THREAD_PRIORITY_HIGHEST)
                
                elif profile['classification'] == 'io_bound':
                    # Prioridad normal para I/O
                    core.kernel32.SetThreadPriority(handle, core.THREAD_PRIORITY_NORMAL)
                
                elif profile['classification'] == 'interactive':
                    # Prioridad above normal para interactividad
                    core.kernel32.SetThreadPriority(handle, core.THREAD_PRIORITY_ABOVE_NORMAL)
        
        except Exception as e:
            print(f"Error optimizando thread {thread_id}: {e}")


class AMDCCDOptimizer:
    """Optimizador para arquitectura chiplet de AMD (CCDs)"""
    
    def __init__(self):
        self.ccd_topology = self.detect_ccd_layout()
    
    def detect_ccd_layout(self):
        """Detecta layout de CCDs en procesadores AMD"""
        # Detectar número de cores
        cpu_count = psutil.cpu_count(logical=False)
        
        # Configuración típica para Ryzen
        if cpu_count >= 16:
            # Ryzen 9 5950X/5900X: 2 CCDs
            topology = {
                'num_ccds': 2,
                'ccd_mapping': {
                    0: list(range(0, cpu_count // 2)),
                    1: list(range(cpu_count // 2, cpu_count))
                },
                'l3_shared_within_ccd': True
            }
        elif cpu_count >= 8:
            # Ryzen 7: 1 o 2 CCDs
            topology = {
                'num_ccds': 1,
                'ccd_mapping': {
                    0: list(range(0, cpu_count))
                },
                'l3_shared_within_ccd': True
            }
        else:
            # Configuración simple
            topology = {
                'num_ccds': 1,
                'ccd_mapping': {
                    0: list(range(0, cpu_count))
                },
                'l3_shared_within_ccd': True
            }
        
        return topology
    
    def optimize_for_ccd_locality(self, pid):
        """Mantiene proceso dentro de un CCD para mejor localidad de L3"""
        try:
            proc = psutil.Process(pid)
            num_threads = proc.num_threads()
            
            # Si cabe en un CCD, confinarlo ahí para mejor localidad de caché
            for ccd_id, cores in self.ccd_topology['ccd_mapping'].items():
                if num_threads <= len(cores):
                    proc.cpu_affinity(cores)
                    print(f"Proceso {pid} confinado a CCD{ccd_id} para localidad L3")
                    break
        except Exception as e:
            print(f"Error optimizando localidad CCD para PID {pid}: {e}")


class CPUManager:
    """Clase principal que agrupa todas las estrategias de optimización de CPU."""
    def __init__(self, monitor_module):
        self.topology = monitor_module.cpu_topology.topology
        self.hetero_scheduler = HeterogeneousScheduler(self.topology)
        self.smt_optimizer = EnhancedSMTOptimizer(self.topology)
        self.avx_optimizer = AVXInstructionOptimizer()
        self.l3_optimizer = L3CacheOptimizer(self.topology)
        
        # Nuevos optimizadores
        self.cpuid_detector = CPUIDDetector()
        self.thread_scheduler = IntelligentThreadScheduler()
        self.amd_ccd_optimizer = AMDCCDOptimizer()