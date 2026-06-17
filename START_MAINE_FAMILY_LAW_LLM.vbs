Set shell = CreateObject("WScript.Shell")
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.Run "cmd /c """" & root & "\START_MAINE_FAMILY_LAW_LLM.cmd""""", 1, False
