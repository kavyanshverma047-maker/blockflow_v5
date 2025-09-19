@echo off
REM ================================
REM Blockflow v5 Quickstart (Windows)
REM ================================

REM Step 1: Create virtual environment if not exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Step 2: Activate venv
call venv\Scripts\activate.bat

REM Step 3: Install dependencies
echo Installing requirements...
pip install --upgrade pip
pip install fastapi uvicorn sqlalchemy pydantic pytest



REM Step 5: Start the API
echo Starting Blockflow API server at http://127.0.0.1:8000 ...
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

pause
