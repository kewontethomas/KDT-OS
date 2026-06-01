@echo off
title FieldSeed Collector Mode
cd /d "%~dp0"
python -m fieldseed.modes.collector
pause
