@echo off

if not exist .venv (
    echo Creating new Python virtual environment in .venv...
    python -m venv .venv
)

echo Activating virtual environment
call .venv\Scripts\activate

echo Installing dependencies

pip show boto3 > nul 2>&1
if %errorlevel% neq 0 (
    pip install --upgrade boto3
)

pip show Flask > nul 2>&1
if %errorlevel% neq 0 (
    pip install --upgrade Flask
)

call aws configure

echo Starting server...
python app.py