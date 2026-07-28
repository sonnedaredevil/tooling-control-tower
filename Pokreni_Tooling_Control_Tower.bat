@echo off
title Tooling Control Tower

REM ==========================================
REM  Pokretanje programa Tooling Control Tower
REM ==========================================

cd /d "%~dp0"

echo.
echo Pokrecem Tooling Control Tower...
echo Folder programa: %cd%
echo.

REM Provera da li postoji app.py
if not exist "app.py" (
    echo GRESKA: Fajl app.py nije pronadjen u ovom folderu.
    echo.
    echo Ovaj BAT fajl mora da bude u istom folderu gde je app.py.
    echo.
    pause
    exit /b
)

REM Prvo pokusaj sa py launcher-om
py --version >nul 2>&1
if %errorlevel%==0 (
    echo Koristim Python launcher: py
    echo.
    py -m streamlit run app.py
    pause
    exit /b
)

REM Ako py ne postoji, pokusaj sa python komandom
python --version >nul 2>&1
if %errorlevel%==0 (
    echo Koristim Python komandu: python
    echo.
    python -m streamlit run app.py
    pause
    exit /b
)

echo GRESKA: Python nije pronadjen.
echo.
echo Proveri da li je Python instaliran i dodat u PATH.
echo Ako instaliras ponovo Python, obavezno cekiraj opciju:
echo Add python.exe to PATH
echo.
pause
