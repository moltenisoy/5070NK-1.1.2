"""
Módulo de Monitoreo de Temperatura
----------------------------------

Utiliza LibreHardwareMonitorLib.dll para monitorear temperaturas
del sistema en tiempo real.
"""

import clr
import sys
import os
import logging

logger = logging.getLogger("TemperatureMonitor")

class TemperatureMonitor:
    """
    Clase para monitorear temperaturas usando LibreHardwareMonitorLib.dll
    """
    
    def __init__(self):
        self.computer = None
        self.initialized = False
        self._initialize_hardware_monitor()
    
    def _initialize_hardware_monitor(self):
        """Inicializa LibreHardwareMonitorLib.dll"""
        try:
            # Intentar cargar la DLL
            dll_path = os.path.join(os.path.dirname(__file__), "LibreHardwareMonitorLib.dll")
            
            if not os.path.exists(dll_path):
                logger.warning(f"⚠️  LibreHardwareMonitorLib.dll no encontrado en {dll_path}")
                logger.info("→ Usando fallback con psutil para temperaturas")
                return False
            
            # Agregar referencia a la DLL
            clr.AddReference(dll_path)
            
            # Importar los tipos necesarios
            from LibreHardwareMonitor import Hardware
            
            # Crear instancia del Computer
            self.computer = Hardware.Computer()
            self.computer.IsCpuEnabled = True
            self.computer.IsGpuEnabled = True
            self.computer.IsMotherboardEnabled = True
            self.computer.IsStorageEnabled = True
            
            # Abrir el hardware
            self.computer.Open()
            
            self.initialized = True
            logger.info("✓ LibreHardwareMonitorLib inicializado correctamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error al inicializar LibreHardwareMonitorLib: {e}")
            logger.info("→ Usando fallback con psutil para temperaturas")
            self.initialized = False
            return False
    
    def get_cpu_temperature(self):
        """
        Obtiene la temperatura actual de la CPU.
        
        :return: Temperatura en grados Celsius o None si no está disponible
        """
        if not self.initialized:
            return self._get_cpu_temperature_fallback()
        
        try:
            # Actualizar los valores de hardware
            self.computer.Accept(HardwareVisitor())
            
            # Buscar el hardware de CPU
            for hardware in self.computer.Hardware:
                if hardware.HardwareType.ToString() in ['Cpu', 'CPU']:
                    hardware.Update()
                    
                    # Buscar el sensor de temperatura del paquete
                    for sensor in hardware.Sensors:
                        if sensor.SensorType.ToString() == 'Temperature':
                            # Buscar "CPU Package" o "Core (Tctl/Tdie)" para AMD
                            sensor_name = sensor.Name.lower()
                            if 'package' in sensor_name or 'tctl' in sensor_name or 'tdie' in sensor_name:
                                if sensor.Value is not None:
                                    return float(sensor.Value)
                    
                    # Si no encontramos el package, usar el primer sensor de temperatura
                    for sensor in hardware.Sensors:
                        if sensor.SensorType.ToString() == 'Temperature' and sensor.Value is not None:
                            return float(sensor.Value)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error al obtener temperatura de CPU: {e}")
            return self._get_cpu_temperature_fallback()
    
    def get_all_temperatures(self):
        """
        Obtiene todas las temperaturas disponibles del sistema.
        
        :return: Diccionario con temperaturas {nombre: valor}
        """
        if not self.initialized:
            return self._get_all_temperatures_fallback()
        
        temperatures = {}
        
        try:
            self.computer.Accept(HardwareVisitor())
            
            for hardware in self.computer.Hardware:
                hardware.Update()
                hardware_type = hardware.HardwareType.ToString()
                
                for sensor in hardware.Sensors:
                    if sensor.SensorType.ToString() == 'Temperature' and sensor.Value is not None:
                        sensor_key = f"{hardware_type}_{hardware.Name}_{sensor.Name}"
                        temperatures[sensor_key] = float(sensor.Value)
            
            return temperatures
            
        except Exception as e:
            logger.debug(f"Error al obtener todas las temperaturas: {e}")
            return self._get_all_temperatures_fallback()
    
    def get_cpu_max_temperature(self):
        """
        Obtiene la temperatura máxima entre todos los cores de la CPU.
        
        :return: Temperatura máxima en grados Celsius o None
        """
        if not self.initialized:
            return self._get_cpu_temperature_fallback()
        
        try:
            max_temp = None
            self.computer.Accept(HardwareVisitor())
            
            for hardware in self.computer.Hardware:
                if hardware.HardwareType.ToString() in ['Cpu', 'CPU']:
                    hardware.Update()
                    
                    for sensor in hardware.Sensors:
                        if sensor.SensorType.ToString() == 'Temperature' and sensor.Value is not None:
                            temp = float(sensor.Value)
                            if max_temp is None or temp > max_temp:
                                max_temp = temp
            
            return max_temp
            
        except Exception as e:
            logger.debug(f"Error al obtener temperatura máxima de CPU: {e}")
            return self._get_cpu_temperature_fallback()
    
    def is_overheating(self, thresholds):
        """
        Verifica si el sistema está sobrecalentando según los umbrales.
        
        :param thresholds: Diccionario con 'soft', 'hard', 'shutdown'
        :return: Tupla (is_overheating, level, temperature)
                 level: 'normal', 'soft', 'hard', 'critical'
        """
        temp = self.get_cpu_max_temperature()
        
        if temp is None:
            return (False, 'unknown', None)
        
        if temp >= thresholds.get('shutdown', 100):
            return (True, 'critical', temp)
        elif temp >= thresholds.get('hard', 95):
            return (True, 'hard', temp)
        elif temp >= thresholds.get('soft', 85):
            return (True, 'soft', temp)
        else:
            return (False, 'normal', temp)
    
    def _get_cpu_temperature_fallback(self):
        """Fallback usando psutil si LibreHardwareMonitorLib no está disponible"""
        try:
            import psutil
            temps = psutil.sensors_temperatures()
            
            if not temps:
                return None
            
            # Intentar obtener temperatura de coretemp (Intel) o k10temp (AMD)
            for sensor_name in ['coretemp', 'k10temp', 'zenpower']:
                if sensor_name in temps:
                    sensor_list = temps[sensor_name]
                    if sensor_list:
                        # Buscar el paquete o usar el primer sensor
                        for sensor in sensor_list:
                            if 'package' in sensor.label.lower():
                                return sensor.current
                        return sensor_list[0].current
            
            # Si no encontramos nada específico, usar el primer sensor disponible
            first_key = next(iter(temps))
            if temps[first_key]:
                return temps[first_key][0].current
            
            return None
            
        except Exception as e:
            logger.debug(f"Error en fallback de temperatura: {e}")
            return None
    
    def _get_all_temperatures_fallback(self):
        """Fallback usando psutil para obtener todas las temperaturas"""
        try:
            import psutil
            temps = psutil.sensors_temperatures()
            
            result = {}
            for sensor_name, sensor_list in temps.items():
                for i, sensor in enumerate(sensor_list):
                    key = f"{sensor_name}_{sensor.label}_{i}"
                    result[key] = sensor.current
            
            return result
            
        except Exception as e:
            logger.debug(f"Error en fallback de todas las temperaturas: {e}")
            return {}
    
    def close(self):
        """Cierra el monitor de hardware"""
        if self.initialized and self.computer:
            try:
                self.computer.Close()
                logger.info("✓ Monitor de temperatura cerrado")
            except Exception as e:
                logger.error(f"Error al cerrar monitor de temperatura: {e}")
    
    def __del__(self):
        """Destructor"""
        self.close()


class HardwareVisitor:
    """Visitor para actualizar el hardware"""
    def VisitComputer(self, computer):
        computer.Traverse(self)
    
    def VisitHardware(self, hardware):
        hardware.Update()
        for subHardware in hardware.SubHardware:
            subHardware.Accept(self)
    
    def VisitSensor(self, sensor):
        pass
    
    def VisitParameter(self, parameter):
        pass


# Singleton global
_temperature_monitor = None

def get_temperature_monitor():
    """Obtiene la instancia global del monitor de temperatura"""
    global _temperature_monitor
    if _temperature_monitor is None:
        _temperature_monitor = TemperatureMonitor()
    return _temperature_monitor
