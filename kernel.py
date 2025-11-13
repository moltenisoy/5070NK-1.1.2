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