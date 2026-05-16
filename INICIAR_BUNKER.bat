@echo off
title SERVIDOR DEL BUNKER (MT5 + PYTHON)
color 0A
echo =======================================================
echo INICIANDO SERVIDOR EN SESION GRAFICA MT5 (SESION 1)
echo =======================================================
C:
cd "C:\Users\daya\Documents\broker_analisis\backend"
call venv\Scripts\activate.bat
python -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
