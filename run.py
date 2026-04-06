"""
Run this from the backend directory:
  python run.py

Or from the project root:
  python resultkraft/backend/run.py
"""
import os
import sys

# Ensure we're in the backend directory so `app` module is found
backend_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

import uvicorn

if __name__ == "__main__":
    is_dev = os.environ.get("ENVIRONMENT", "development") != "production"
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=is_dev,
        reload_dirs=[backend_dir] if is_dev else None,
    )
