Option Explicit

Dim shell, fso, root, launcher, comspec, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = fso.BuildPath(root, "START_MAINE_FAMILY_LAW_LLM.cmd")
comspec = shell.ExpandEnvironmentStrings("%ComSpec%")
command = Chr(34) & comspec & Chr(34) & " /d /s /c " & _
    Chr(34) & Chr(34) & launcher & Chr(34) & Chr(34)

shell.Run command, 1, False
