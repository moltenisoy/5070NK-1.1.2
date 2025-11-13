"""
Test script para verificar las correcciones implementadas
"""

import sys
import os

print("="*60)
print("Test de Correcciones - Motor de Optimización")
print("="*60)

# Test 1: ConfigManager
print("\n[Test 1] ConfigManager - Persistencia de configuración")
try:
    from config_manager import ConfigManager
    
    # Crear instancia
    config = ConfigManager("test_config.json")
    
    # Test de umbrales térmicos
    test_thresholds = {'soft': 75, 'hard': 85, 'shutdown': 95}
    config.set_thermal_thresholds(test_thresholds)
    
    # Verificar que se guardó
    loaded_thresholds = config.get_thermal_thresholds()
    assert loaded_thresholds == test_thresholds, "Umbrales no coinciden"
    
    # Limpiar archivo de test
    if os.path.exists("test_config.json"):
        os.remove("test_config.json")
    
    print("  ✓ ConfigManager funciona correctamente")
    print(f"  ✓ Umbrales guardados y cargados: {loaded_thresholds}")
except Exception as e:
    print(f"  ✗ Error en ConfigManager: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Subprocess sin shell=True
print("\n[Test 2] Seguridad - subprocess sin shell=True")
try:
    from monitoring import HardwareDetector
    import subprocess
    
    # Verificar que el código no usa shell=True
    with open('monitoring.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if 'shell=True' in content:
            print("  ✗ ADVERTENCIA: shell=True todavía presente en monitoring.py")
        else:
            print("  ✓ No se encontró shell=True en monitoring.py")
    
    # Test básico de HardwareDetector
    detector = HardwareDetector()
    print(f"  ✓ HardwareDetector inicializado")
    print(f"    - CPU: {detector.cpu_info.get('name', 'Unknown')[:50]}")
    print(f"    - Intel: {detector.is_intel}, AMD: {detector.is_amd}")
    
except Exception as e:
    print(f"  ✗ Error en test de seguridad: {e}")

# Test 3: Excepciones apropiadas
print("\n[Test 3] Manejo de excepciones - Sin bare except")
try:
    import core
    
    # Verificar que no hay bare except en core.py
    with open('core.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        bare_excepts = []
        for i, line in enumerate(lines, 1):
            if line.strip() == 'except:':
                bare_excepts.append(i)
        
        if bare_excepts:
            print(f"  ✗ Se encontraron bare except en líneas: {bare_excepts}")
        else:
            print("  ✓ No se encontraron bare except en core.py")
    
    # Test de ProcessHandleCache
    cache = core.ProcessHandleCache()
    print(f"  ✓ ProcessHandleCache creado correctamente")
    
except Exception as e:
    print(f"  ✗ Error en test de excepciones: {e}")

# Test 4: Documentación de dependencias
print("\n[Test 4] Documentación de dependencias externas")
try:
    # Verificar documentación en temperature_monitor.py
    with open('temperature_monitor.py', 'r', encoding='utf-8') as f:
        content = f.read()
        has_clr_doc = 'clr (pythonnet)' in content
        has_dll_doc = 'LibreHardwareMonitorLib.dll' in content
        
        if has_clr_doc and has_dll_doc:
            print("  ✓ temperature_monitor.py: Dependencias documentadas")
        else:
            print("  ✗ Falta documentación de dependencias")
    
    # Verificar documentación en core.py
    with open('core.py', 'r', encoding='utf-8') as f:
        content = f.read()
        has_winapi_doc = 'Dependencias de Windows API' in content
        
        if has_winapi_doc:
            print("  ✓ core.py: Windows API documentada")
        else:
            print("  ✗ Falta documentación de Windows API")
            
except Exception as e:
    print(f"  ✗ Error en test de documentación: {e}")

# Test 5: GestorModulos - set_thermal_thresholds
print("\n[Test 5] GestorModulos - método set_thermal_thresholds")
try:
    # Verificar que el método existe
    with open('gestor_modulos.py', 'r', encoding='utf-8') as f:
        content = f.read()
        has_method = 'def set_thermal_thresholds' in content
        
        if has_method:
            print("  ✓ Método set_thermal_thresholds implementado")
        else:
            print("  ✗ Método set_thermal_thresholds no encontrado")
    
    # Verificar callbacks de foreground
    has_on_foreground_change = 'def on_foreground_change' in content
    has_on_foreground_stable = 'def _on_foreground_stable' in content
    
    if has_on_foreground_change and has_on_foreground_stable:
        print("  ✓ Callbacks de foreground implementados")
    else:
        print("  ✗ Faltan callbacks de foreground")
            
except Exception as e:
    print(f"  ✗ Error en test de GestorModulos: {e}")

# Test 6: GUI - FineTuningTab con persistencia
print("\n[Test 6] GUI - FineTuningTab con ConfigManager")
try:
    with open('gui.py', 'r', encoding='utf-8') as f:
        content = f.read()
        has_config_manager = 'from config_manager import ConfigManager' in content
        has_load_settings = '_load_saved_settings' in content
        has_save = 'config_manager.set_thermal_thresholds' in content
        
        if has_config_manager and has_load_settings and has_save:
            print("  ✓ GUI integrado con ConfigManager")
            print("  ✓ Carga y guardado de ajustes implementado")
        else:
            print("  ✗ Integración incompleta con ConfigManager")
            
    # Verificar actualización de estado en ControlPanelTab
    has_real_status = 'getattr(self.module_manager' in content
    if has_real_status:
        print("  ✓ ControlPanelTab usa estado real del módulo")
    else:
        print("  ✗ ControlPanelTab todavía usa valores hardcoded")
            
except Exception as e:
    print(f"  ✗ Error en test de GUI: {e}")

print("\n" + "="*60)
print("Tests completados")
print("="*60)
