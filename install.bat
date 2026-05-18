@echo off
set VENV_DIR=venv

echo.
echo === Comprobacion / Creacion venv ===
if exist "%VENV_DIR%\Scripts\python.exe" (
    echo Usando entorno virtual existente: %VENV_DIR%
) else (
    echo Creando entorno virtual...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo ERROR: fallo creando venv
        exit /b 1
    )
)

echo.
echo === Activar venv ===
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: no se pudo activar el entorno virtual.
    exit /b 1
)

echo.
echo === Actualizar pip/setuptools/wheel desde repositories ===
python -m pip install --upgrade --no-index --find-links repositories pip setuptools wheel
if errorlevel 1 (
    echo ERROR: fallo actualizando pip/setuptools/wheel
    exit /b 1
)

echo.
echo === Instalar requirements desde repositories ===
python -m pip install --no-index --find-links repositories -r requirements.txt
if errorlevel 1 (
    echo ERROR: fallo instalando requirements
    exit /b 1
)

echo.
echo === Instalacion completada ===
echo Entorno virtual creado en "%VENV_DIR%"
echo Para activar el entorno use:
echo    "%VENV_DIR%\Scripts\activate.bat"
exit /b 0
