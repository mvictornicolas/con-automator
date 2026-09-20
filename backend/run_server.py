import sys
import os

os.chdir(r"C:\con-automator\backend")
sys.path.insert(0, r"C:\con-automator\backend")

# Gravar logs num arquivo para não perdermos os prints do python
log_file = open(r"C:\con-automator\backend\python_logs.txt", "w", encoding="utf-8")
if sys.stdout is None:
    sys.stdout = log_file
if sys.stderr is None:
    sys.stderr = log_file

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000)
