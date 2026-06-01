@echo off
title FieldSeed Rescue Mode
:MENU
cls
echo ==========================================
echo FIELDSEED RESCUE MODE
echo ==========================================
echo 1. Smart Windows Update Recovery
echo 2. List Volumes
echo 3. Offline SFC Helper
echo 4. CHKDSK Helper
echo 0. Exit
set /p CHOICE=Choose: 
if "%CHOICE%"=="1" call "%~dp0SMART_WINDOWS_UPDATE_RECOVERY.bat"
if "%CHOICE%"=="2" goto VOLUMES
if "%CHOICE%"=="3" goto SFC
if "%CHOICE%"=="4" goto CHKDSK
if "%CHOICE%"=="0" exit /b 0
goto MENU
:VOLUMES
echo Run: diskpart then list volume
pause
goto MENU
:SFC
set /p WDRIVE=Windows drive, example C: 
echo sfc /scannow /offbootdir=%WDRIVE%\ /offwindir=%WDRIVE%\Windows
pause
goto MENU
:CHKDSK
set /p CDRIVE=Drive, example C: 
echo chkdsk %CDRIVE%
echo chkdsk %CDRIVE% /f
pause
goto MENU
