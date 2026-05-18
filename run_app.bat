@echo off
setlocal

if not exist "venv\Scripts\python.exe" (
    echo ERROR: No se encuentra el entorno virtual 'venv'.
    echo Ejecuta install.bat primero.
    pause
    exit /b 1
)

if not exist "db.sqlite3" (
    echo ERROR: No se encuentra la base de datos 'db.sqlite3'.
    echo Asegurate de tener la base de datos poblada antes de ejecutar esta aplicacion.
    pause
    exit /b 1
)

call "venv\Scripts\activate.bat"

echo Iniciando Casa de la Cultura...
echo NO cierres esta ventana mientras uses la aplicacion.
echo.

:: Abrir el navegador tras 3 segundos (en segundo plano)
start "" cmd /c "timeout /t 3 >nul && start http://127.0.0.1:8000"

:: Iniciar el servidor (esta ventana debe quedarse abierta)
python manage.py runserver 127.0.0.1:8000 --noreload
