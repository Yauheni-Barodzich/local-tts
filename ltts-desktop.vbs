' Запуск ltts desktop без окна консоли (двойной щелчок в проводнике).
Option Explicit

Dim fso, sh, root, pyw, uvPyw, trayBat

Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("Wscript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)

pyw = root & "\.venv\Scripts\pythonw.exe"
If fso.FileExists(pyw) Then
  sh.Run """" & pyw & """ -m ltts.cli desktop", 0, False
  WScript.Quit 0
End If

uvPyw = sh.ExpandEnvironmentStrings("%APPDATA%") & "\uv\tools\ltts\Scripts\pythonw.exe"
If fso.FileExists(uvPyw) Then
  sh.Run """" & uvPyw & """ -m ltts.cli desktop", 0, False
  WScript.Quit 0
End If

trayBat = root & "\ltts-tray.bat"
If fso.FileExists(trayBat) Then
  sh.Run """" & trayBat & """ nopause", 0, False
  WScript.Quit 0
End If

MsgBox "Не найден pythonw (.venv или uv tool ltts)." & vbCrLf & "Сначала: ltts-update.bat", vbExclamation, "ltts"
