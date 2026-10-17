Test-NetConnection -ComputerName 127.0.0.1 -Port 9876 -InformationLevel Quiet
Get-Process blender -ErrorAction SilentlyContinue | Select-Object Id, MainWindowTitle
