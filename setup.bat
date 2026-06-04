@echo off
echo Setting up Codebase Intelligence...
echo.

echo Checking Python...
python --version
if %errorlevel% neq 0 (
    echo Python not found. Please install Python 3.11+
    exit /b 1
)

echo.
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate

echo.
echo Installing backend dependencies...
cd backend
pip install -r requirements.txt
cd ..

echo.
echo Installing frontend dependencies...
cd frontend
pip install -r requirements.txt
cd ..

echo.
echo Copying .env file...
if not exist backend\.env (
    copy backend\.env.example backend\.env
    echo Created .env from .env.example
)

echo.
echo Setup complete!
echo.
echo To start the application:
echo   docker-compose up
echo.
echo Or run manually:
echo   Terminal 1: cd backend ^&^& uvicorn app.main:app --reload
echo   Terminal 2: cd frontend ^&^& streamlit run app.py
echo.
