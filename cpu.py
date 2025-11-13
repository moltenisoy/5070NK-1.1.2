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

class CPUManager:
    """Clase principal que agrupa todas las estrategias de optimización de CPU."""
    def __init__(self, monitor_module):
        self.topology = monitor_module.cpu_topology.topology
        self.hetero_scheduler = HeterogeneousScheduler(self.topology)
        self.smt_optimizer = EnhancedSMTOptimizer(self.topology)
        self.avx_optimizer = AVXInstructionOptimizer()
        self.l3_optimizer = L3CacheOptimizer(self.topology)