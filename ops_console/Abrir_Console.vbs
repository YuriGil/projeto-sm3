Option Explicit
Dim shell, fso, root, server
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
server = fso.BuildPath(root, "server.py")
shell.CurrentDirectory = root
shell.Run "pythonw.exe """ & server & """", 0, False