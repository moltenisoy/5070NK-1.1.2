@echo off
echo ============================================
echo  INSTALADOR DE MODULOS - Motor de Optimizacion
echo ============================================
echo.

:: Verificar si Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python no esta instalado en el sistema.
    echo Por favor, instale Python 3.8 o superior desde https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python detectado correctamente
echo.

:: Actualizar pip
echo Actualizando pip...
python -m pip install --upgrade pip
echo.

:: Instalar modulos requeridos
echo Instalando modulos de Python necesarios...
echo.

echo [1/8] Instalando psutil (monitoreo de sistema)...
pip install psutil

echo [2/8] Instalando ttkbootstrap (interfaz grafica moderna)...
pip install ttkbootstrap

echo [3/8] Instalando Pillow (manejo de imagenes)...
pip install Pillow

echo [4/8] Instalando pystray (icono en bandeja del sistema)...
pip install pystray

echo [5/8] Instalando pythonnet (integracion con .NET para LibreHardwareMonitor)...
pip install pythonnet

echo [6/8] Instalando pywin32 (API de Windows - opcional)...
pip install pywin32

echo [7/8] Instalando requests (utilidades de red - opcional)...
pip install requests

echo [8/8] Instalando colorama (utilidades de consola - opcional)...
pip install colorama

echo.
echo ============================================
echo  INSTALACION COMPLETADA
echo ============================================
echo.
echo Todos los modulos han sido instalados correctamente.
echo.
echo NOTAS IMPORTANTES:
echo - LibreHardwareMonitorLib.dll debe estar en el mismo directorio
echo - El programa debe ejecutarse con privilegios de administrador
echo - Windows 10/11 es requerido para funcionalidad completa
echo.
echo Para ejecutar el programa, use:
echo    python gui.py
echo.
pause
