@echo off
:: Build script for creating standalone .exe from disassembler.py
:: Requires PyInstaller: pip install pyinstaller

cd /d "%~dp0"

echo ============================================================================
echo Building NeHe Atari 2600 Smart Disassembler
echo ============================================================================
echo Working directory: %CD%
echo.

:: Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install PyInstaller!
        echo Please run: pip install pyinstaller
        pause
        exit /b 1
    )
    echo PyInstaller installed successfully!
    echo.
)

:: Build the executable
echo Building executable...
python -m PyInstaller --onefile --console --name "NeHe-Atari2600-Disassembler" disassembler.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo Build complete!
echo.
echo The executable can be found in the 'dist' folder:
echo   dist\NeHe-Atari2600-Disassembler.exe
echo.
echo Usage:
echo   NeHe-Atari2600-Disassembler.exe rom\game.a26
echo   NeHe-Atari2600-Disassembler.exe rom\game.a26 --comments --cycles
echo   NeHe-Atari2600-Disassembler.exe rom\game.a26 -o output.asm
echo ============================================================================
pause
