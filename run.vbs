' Silent launcher — no console window
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
app = dir & "\app.py"

pythonw = ""
On Error Resume Next
pythonw = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe")
If Not fso.FileExists(pythonw) Then pythonw = "pythonw"
On Error GoTo 0

sh.Run """" & pythonw & """ """ & app & """", 0, False
