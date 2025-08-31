@echo off
call .venv\Scripts\activate
echo Starting server on http://0.0.0.0:8000
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
