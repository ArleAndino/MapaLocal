"""Native folder dialog, launched explicitly by the user; never scans on selection."""
import json
import os
import subprocess

if os.name=='nt':
    script=r'''
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$picker = New-Object System.Windows.Forms.FolderBrowserDialog
$picker.Description = 'Grapho Ma - Abrir proyecto'
$picker.ShowNewFolderButton = $false
$chosen = ''
if ($picker.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $chosen = $picker.SelectedPath }
$picker.Dispose()
@{path=$chosen} | ConvertTo-Json -Compress
'''
    result=subprocess.run(['powershell.exe','-NoProfile','-STA','-WindowStyle','Hidden','-Command',script],capture_output=True,text=True,encoding='utf-8',check=True)
    print(result.stdout.strip())
else:
    import tkinter as tk
    from tkinter import filedialog
    root=tk.Tk();root.withdraw()
    try:
        folder=filedialog.askdirectory(title='Grapho Ma — Abrir proyecto',parent=root,mustexist=True)
        print(json.dumps({'path':folder},ensure_ascii=True))
    finally:
        root.destroy()
