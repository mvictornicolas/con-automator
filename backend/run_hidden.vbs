Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd.exe /c ""C:\con-automator\backend\run_uvicorn.bat""", 0, False
