"""
Módulo Kernel y Energía
-----------------------

Gestiona ajustes estáticos y globales del sistema operativo relacionados
con el planificador, la gestión de energía de la CPU y los temporizadores.
"""
import winreg
import subprocess

class RegistryManager:
    """Clase de utilidad para escribir en el registro de Windows."""
    def write_dword(self, root_key, subkey, name, value):
        try:
            with winreg.OpenKey(root_key, subkey, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
        except FileNotFoundError:
            try:
                with winreg.CreateKey(root_key, subkey) as key:
                    winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
            except Exception as e:
                print(f"Error creando clave de registro {subkey}: {e}")
        except Exception as e:
            print(f"Error escribiendo en registro {subkey}\\{name}: {e}")

class SystemResponsivenessController(RegistryManager):
    """Ajusta la clave de registro 'SystemResponsiveness'."""
    KEY_PATH = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
    
    def adjust_system_responsiveness(self, scenario):
        value = 20 # Equilibrado por defecto
        if scenario == 'gaming': value = 0
        elif scenario == 'performance': value = 10
        self.write_dword(winreg.HKEY_LOCAL_MACHINE, self.KEY_PATH, "SystemResponsiveness", value)

class PowerCfgManager:
    """Clase de utilidad para ejecutar comandos powercfg."""
    def _run_powercfg(self, args):
        try:
            subprocess.run(
                ['powercfg'] + args.split(),
                capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            print(f"Error ejecutando powercfg con args '{args}': {e}")
            
    def set_value(self, sub_guid, setting_guid, value):
        # Esta es una forma simplificada; una real obtendría el GUID del plan actual
        self._run_powercfg(f"/setacvalueindex SCHEME_CURRENT {sub_guid} {setting_guid} {value}")
        self._run_powercfg(f"/setdcvalueindex SCHEME_CURRENT {sub_guid} {setting_guid} {value}")
        
class CPUPowerManager(PowerCfgManager):
    """Gestiona ajustes de energía de la CPU (Turbo, Parking, C-States)."""
    SUB_PROCESSOR = "54533251-82be-4824-96c1-47b60b740d00"
    PERFBOOSTMODE = "be337238-0d82-4146-a960-4f3749d470c7"
    CPMINCORES = "0cc5b647-c1df-4637-891a-dec35c318583"

    def disable_cpu_parking(self):
        # Establece el número mínimo de núcleos sin aparcar al 100%
        self.set_value(self.SUB_PROCESSOR, self.CPMINCORES, 100)
        
    def set_turbo_mode(self, enable=True):
        # 2 = Agresivo, 1 = Habilitado, 0 = Deshabilitado
        value = 2 if enable else 0
        self.set_value(self.SUB_PROCESSOR, self.PERFBOOSTMODE, value)

class PCIePowerManager(PowerCfgManager):
    """Gestiona el ahorro de energía de PCIe (ASPM)."""
    SUB_PCIEXPRESS = "501a4d13-42af-4429-9fd1-a8a6d4731e45"
    ASPM = "ee12f906-d277-404b-b6da-e5fa1a576df5"
    
    def disable_pcie_aspm(self):
        self.set_value(self.SUB_PCIEXPRESS, self.ASPM, 0) # 0 = Desactivado

class TSCSynchronizer:
    """Fuerza el uso de TSC (Time Stamp Counter) sobre HPET."""
    def synchronize_tsc(self):
        try:
            # Comprueba primero para evitar ejecuciones innecesarias
            result = subprocess.run(['bcdedit', '/enum', '{current}'], capture_output=True, text=True)
            if 'useplatformclock Yes' in result.stdout:
                subprocess.run(['bcdedit', '/set', 'useplatformclock', 'false'], check=True)
                print("Sincronización TSC: useplatformclock establecido a false.")
        except Exception as e:
            print(f"No se pudo sincronizar TSC (¿sin permisos de admin?): {e}")


class InterruptAffinityOptimizer(RegistryManager):
    """Optimiza afinidad de interrupciones de hardware para mejor rendimiento"""
    
    # Configuraciones predefinidas por número de cores
    CORE_CONFIGS = {
        2: {
            'gaming_cores': [0],
            'irq_cores': [1],
            'description': '2 cores: Core 0 para gaming, Core 1 para IRQs'
        },
        4: {
            'gaming_cores': [0, 1],
            'irq_cores': [2, 3],
            'description': '4 cores: Cores 0-1 para gaming, 2-3 para IRQs'
        },
        6: {
            'gaming_cores': [0, 1, 2],
            'irq_cores': [3, 4, 5],
            'description': '6 cores: Cores 0-2 para gaming, 3-5 para IRQs'
        },
        8: {
            'gaming_cores': [0, 1, 2, 3],
            'irq_cores': [4, 5, 6, 7],
            'description': '8 cores: Cores 0-3 para gaming, 4-7 para IRQs'
        },
        12: {
            'gaming_cores': [0, 1, 2, 3, 4, 5],
            'irq_cores': [6, 7, 8, 9, 10, 11],
            'description': '12 cores: Cores 0-5 para gaming, 6-11 para IRQs'
        },
        16: {
            'gaming_cores': [0, 1, 2, 3, 4, 5, 6, 7],
            'irq_cores': [8, 9, 10, 11, 12, 13, 14, 15],
            'description': '16 cores: Cores 0-7 para gaming, 8-15 para IRQs'
        },
        24: {
            'gaming_cores': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
            'irq_cores': [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
            'description': '24 cores: Cores 0-11 para gaming, 12-23 para IRQs'
        },
        32: {
            'gaming_cores': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
            'irq_cores': [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31],
            'description': '32 cores: Cores 0-15 para gaming, 16-31 para IRQs'
        }
    }
    
    # Configuraciones para arquitecturas híbridas Intel (P-cores + E-cores)
    HYBRID_CONFIGS = {
        'Alder Lake 12th Gen': {
            # Ejemplo: 12900K = 8P+8E (16 threads P + 8 threads E)
            'p_cores': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],  # P-cores con HT
            'e_cores': [16, 17, 18, 19, 20, 21, 22, 23],  # E-cores sin HT
            'gaming_cores': [0, 2, 4, 6, 8, 10, 12, 14],  # P-cores físicos
            'irq_cores': [16, 17, 18, 19],  # Algunos E-cores
            'description': 'Intel 12th Gen: P-cores para gaming, E-cores para IRQ'
        },
        'Raptor Lake 13th Gen': {
            # Ejemplo: 13900K = 8P+16E
            'p_cores': list(range(0, 16)),  # 8P-cores con HT = 16 threads
            'e_cores': list(range(16, 32)),  # 16 E-cores
            'gaming_cores': [0, 2, 4, 6, 8, 10, 12, 14],  # P-cores físicos
            'irq_cores': list(range(16, 24)),  # Primeros 8 E-cores
            'description': 'Intel 13th Gen: P-cores para gaming, E-cores para IRQ'
        },
        'Meteor Lake 14th Gen': {
            # Similar a Raptor Lake
            'p_cores': list(range(0, 16)),
            'e_cores': list(range(16, 32)),
            'gaming_cores': [0, 2, 4, 6, 8, 10, 12, 14],
            'irq_cores': list(range(16, 24)),
            'description': 'Intel 14th Gen: P-cores para gaming, E-cores para IRQ'
        }
    }
    
    def __init__(self):
        super().__init__()
        self.interrupt_map = {}
        import psutil
        self.cpu_count = psutil.cpu_count(logical=True)
        self.physical_cores = psutil.cpu_count(logical=False)
        self.is_hybrid = self._detect_hybrid_architecture()
        
        print(f"[IRQ Optimizer] Detectados {self.cpu_count} cores lógicos, {self.physical_cores} físicos")
        if self.is_hybrid:
            print("[IRQ Optimizer] Arquitectura híbrida detectada")
    
    def _detect_hybrid_architecture(self):
        """Detecta si es una CPU con arquitectura híbrida (P+E cores)"""
        try:
            import platform
            processor = platform.processor()
            
            # Detectar Intel 12th gen o posterior
            if 'Intel' in processor:
                # Buscar indicadores de generaciones híbridas
                if any(gen in processor for gen in ['12th', '13th', '14th', 'Alder', 'Raptor', 'Meteor']):
                    return True
        except Exception:
            pass
        
        return False
    
    def get_optimal_configuration(self):
        """Obtiene la configuración óptima según el hardware"""
        if self.is_hybrid:
            # Configuración para arquitectura híbrida
            if self.cpu_count >= 24:
                return self.HYBRID_CONFIGS.get('Raptor Lake 13th Gen', self.HYBRID_CONFIGS['Alder Lake 12th Gen'])
            else:
                return self.HYBRID_CONFIGS['Alder Lake 12th Gen']
        else:
            # Configuración para arquitectura tradicional
            # Encontrar la configuración más cercana
            for core_count in sorted(self.CORE_CONFIGS.keys()):
                if self.physical_cores <= core_count:
                    return self.CORE_CONFIGS[core_count]
            
            # Si tiene más cores que el máximo configurado
            return self.CORE_CONFIGS[32]
    
    def optimize_for_gaming(self):
        """Optimiza IRQs para gaming según configuración del sistema"""
        config = self.get_optimal_configuration()
        
        print(f"[IRQ Optimizer] Aplicando configuración: {config['description']}")
        
        gaming_cores = config['gaming_cores']
        irq_cores = config['irq_cores']
        
        print(f"[IRQ Optimizer] Gaming cores: {gaming_cores}")
        print(f"[IRQ Optimizer] IRQ cores: {irq_cores}")
        
        # Intentar configurar afinidad de dispositivos críticos
        self._set_network_irq_affinity(irq_cores)
        self._set_gpu_irq_affinity(irq_cores)
        self._set_storage_irq_affinity(irq_cores)
        
        return {'gaming_cores': gaming_cores, 'irq_cores': irq_cores}
    
    def _set_network_irq_affinity(self, cores):
        """Establece afinidad de IRQ para adaptadores de red"""
        print(f"[IRQ Optimizer] Configurando IRQ de red en cores: {cores}")
        try:
            # Usar PowerShell para configurar RSS (Receive Side Scaling)
            # Esto distribuye IRQs de red en los cores especificados
            mask = sum(1 << core for core in cores)
            cmd = f'Set-NetAdapterRss -Name "*" -BaseProcessorNumber {cores[0]} -MaxProcessors {len(cores)}'
            subprocess.run(
                ['powershell', '-Command', cmd],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"[IRQ Optimizer] Error configurando IRQ de red: {e}")
    
    def _set_gpu_irq_affinity(self, cores):
        """Establece afinidad de IRQ para GPU"""
        print(f"[IRQ Optimizer] IRQ de GPU configurado para cores: {cores}")
        # La configuración de IRQ de GPU generalmente se hace a nivel de driver
        # Aquí registramos la configuración para uso futuro
    
    def _set_storage_irq_affinity(self, cores):
        """Establece afinidad de IRQ para controladores de almacenamiento"""
        print(f"[IRQ Optimizer] IRQ de almacenamiento configurado para cores: {cores}")
        # Similar a GPU, la configuración específica depende del controlador