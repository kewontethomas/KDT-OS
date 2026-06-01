@echo off
title FieldSeed Smart Windows Update Recovery
set MODE=LIVE
if /I "%SystemDrive%"=="X:" set MODE=WINRE
if exist X:\Windows\System32\wpeinit.exe set MODE=WINRE
echo Mode: %MODE%
if /I "%MODE%"=="WINRE" goto WINRE
net stop wuauserv /y
net stop bits /y
if exist C:\Windows\SoftwareDistribution ren C:\Windows\SoftwareDistribution SoftwareDistribution.old.FieldSeed
dism /online /cleanup-image /restorehealth
sfc /scannow
pause
exit /b 0
:WINRE
set /p TARGET=Offline Windows drive, example C: 
dism /image:%TARGET%\ /cleanup-image /revertpendingactions
if exist %TARGET%\Windows\WinSxS\pending.xml del /f /q %TARGET%\Windows\WinSxS\pending.xml
pause
