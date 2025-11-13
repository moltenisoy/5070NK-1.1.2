"""
Módulo de Gestión de Configuración
----------------------------------

Maneja la persistencia de configuraciones del sistema de optimización.
"""

import json
import os
import logging
from typing import Dict, Any

logger = logging.getLogger("ConfigManager")

class ConfigManager:
    """Gestiona la carga y guardado de configuraciones."""
    
    def __init__(self, config_file="optimizer_config.json"):
        self.config_file = config_file
        self.config = self._load_default_config()
        self.load()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Retorna la configuración por defecto."""
        return {
            'thermal_thresholds': {
                'soft': 80,
                'hard': 90,
                'shutdown': 100
            },
            'autostart': False,
            'last_mode': 'normal',
            'game_mode_enabled': False,
            'ahorro_mode_enabled': False,
            'extremo_mode_enabled': False,
            'module_manager_enabled': True
        }
    
    def load(self) -> bool:
        """
        Carga la configuración desde el archivo.
        
        :return: True si se cargó exitosamente, False en caso contrario
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # Merge con valores por defecto para asegurar integridad
                    self.config.update(loaded_config)
                    logger.info(f"✓ Configuración cargada desde {self.config_file}")
                    return True
            else:
                logger.info(f"Archivo de configuración no encontrado, usando valores por defecto")
                return False
        except Exception as e:
            logger.error(f"Error al cargar configuración: {e}")
            return False
    
    def save(self) -> bool:
        """
        Guarda la configuración actual al archivo.
        
        :return: True si se guardó exitosamente, False en caso contrario
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            logger.info(f"✓ Configuración guardada en {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error al guardar configuración: {e}")
            return False
    
    def get(self, key: str, default=None) -> Any:
        """Obtiene un valor de configuración."""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Establece un valor de configuración y guarda automáticamente."""
        self.config[key] = value
        self.save()
    
    def get_thermal_thresholds(self) -> Dict[str, int]:
        """Obtiene los umbrales térmicos configurados."""
        return self.config.get('thermal_thresholds', self._load_default_config()['thermal_thresholds'])
    
    def set_thermal_thresholds(self, thresholds: Dict[str, int]) -> None:
        """Establece los umbrales térmicos."""
        self.config['thermal_thresholds'] = thresholds
        self.save()
        logger.info(f"Umbrales térmicos actualizados: {thresholds}")
