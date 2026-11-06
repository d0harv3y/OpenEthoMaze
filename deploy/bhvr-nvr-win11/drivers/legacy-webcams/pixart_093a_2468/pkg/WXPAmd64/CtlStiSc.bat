@Echo Off
reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\Run" /v Monitor /t REG_SZ /d "%WinDir%\PixArt\PAC207\Monitor.exe" /f
start %WinDir%\PixArt\PAC207\Monitor.exe
exit
@Echo On

