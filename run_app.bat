@echo off
setlocal

if not exist "python_embed\python.exe" (
    echo ERROR: No se encuentra el interprete de Python.
    echo Reinstala la aplicacion o contacta con el equipo tecnico.
    pause
    exit /b 1
)

if not exist "db.sqlite3" (
    echo ERROR: No se encuentra la base de datos.
    echo Reinstala la aplicacion o contacta con el equipo tecnico.
    pause
    exit /b 1
)

echo Iniciando Casa de la Cultura...
echo NO cierres esta ventana mientras uses la aplicacion.
echo.

:: Abrir el navegador tras 3 segundos (en segundo plano)
start "" cmd /c "timeout /t 3 >nul && start http://127.0.0.1:8000"

:: Iniciar el servidor (esta ventana debe quedarse abierta)
python_embed\python.exe manage.py runserver 127.0.0.1:8000 --noreload
