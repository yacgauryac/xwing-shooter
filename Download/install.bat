@echo off
echo === X-Wing Shooter - Installation des fichiers ===
echo.

set DEST=C:\Projets\xwing-shooter

:: Trouve le zip dans le meme dossier que ce script
set SCRIPT_DIR=%~dp0
set ZIP_FILE=""

for %%f in ("%SCRIPT_DIR%*.zip") do set ZIP_FILE=%%f

if %ZIP_FILE%=="" (
    echo Aucun fichier .zip trouve dans %SCRIPT_DIR%
    echo Place ce script a cote du zip telecharge depuis Claude.
    pause
    exit /b 1
)

echo ZIP trouve : %ZIP_FILE%
echo Destination : %DEST%
echo.

:: Cree un dossier temporaire pour extraire
set TEMP_DIR=%SCRIPT_DIR%_xwing_temp
if exist "%TEMP_DIR%" rmdir /S /Q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"

:: Dezippe
echo Extraction...
powershell -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%TEMP_DIR%' -Force"

:: Copie les fichiers Python src
echo Copie des fichiers...
for %%f in ("%TEMP_DIR%\*.py") do (
    echo   %%~nxf
    copy /Y "%%f" "%DEST%\src\%%~nxf" >nul 2>&1
)

:: Cherche aussi dans les sous-dossiers (au cas ou le zip a un dossier src/)
for /R "%TEMP_DIR%" %%f in (*.py) do (
    set "FNAME=%%~nxf"
    setlocal enabledelayedexpansion
    :: Fichiers racine
    if "!FNAME!"=="main.py" (
        echo   main.py [racine]
        copy /Y "%%f" "%DEST%\main.py" >nul 2>&1
    )
    :: Fichiers src
    if not "!FNAME!"=="main.py" (
        echo   !FNAME! [src]
        copy /Y "%%f" "%DEST%\src\!FNAME!" >nul 2>&1
    )
    endlocal
)

:: Copie requirements.txt et autres fichiers racine si presents
for /R "%TEMP_DIR%" %%f in (requirements.txt README.md .gitignore) do (
    echo   %%~nxf [racine]
    copy /Y "%%f" "%DEST%\%%~nxf" >nul 2>&1
)

:: Nettoie
rmdir /S /Q "%TEMP_DIR%"

echo.
echo === Installation terminee ! ===
echo Tu peux lancer : cd %DEST% ^& python main.py
echo.
pause
