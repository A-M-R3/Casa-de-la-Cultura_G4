@echo off
setlocal

if not exist "python_embed\python.exe" (
    echo ERROR: No se encuentra el interprete de Python.
    echo Reinstala la aplicacion o contacta con el equipo tecnico.
    pause
    exit /b 1
)

if not exist ".env" (
    echo ERROR: No se encuentra el archivo de configuracion .env.
    echo Crea el archivo .env a partir de .env.example y configura PostgreSQL.
    pause
    exit /b 1
)

echo Comprobando configuracion de la aplicacion...
python_embed\python.exe manage.py check

if errorlevel 1 (
    echo.
    echo ERROR: La aplicacion no ha superado la comprobacion de Django.
    echo Revisa la configuracion y la conexion con PostgreSQL.
    pause
    exit /b 1
)

echo.
echo Iniciando Casa de la Cultura...
echo NO cierres esta ventana mientras uses la aplicacion.
echo.

:: Abrir el navegador tras 3 segundos
start "" cmd /c "timeout /t 3 >nul && start http://127.0.0.1:8000"

:: Iniciar el servidor
python_embed\python.exe manage.py runserver 127.0.0.1:8000 --noreload