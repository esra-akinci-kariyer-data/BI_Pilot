import os
import time
import subprocess
import shutil
import ctypes

def get_short_path(long_path):
    """Returns the Windows short path (8.3) for a given long path to avoid encoding issues with SendKeys."""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        ctypes.windll.kernel32.GetShortPathNameW(long_path, buf, 1024)
        return buf.value
    except:
        return long_path

def Log_py(msg):
    print(f"python_pbi_robot: {msg}")

def normalize_title(text):
    """Replaces Turkish characters with English equivalents for better AppActivate compatibility."""
    replacements = {
        'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
        'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U'
    }
    for char, rep in replacements.items():
        text = text.replace(char, rep)
    return text

# Common locations for Power BI Desktop
PBI_POSSIBLE_PATHS = [
    r"C:\Program Files\Microsoft Power BI Desktop RS\bin\PBIDesktop.exe",
    r"C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
    r"C:\Program Files (x86)\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
]

def cleanup_orphaned_processes():
    """Kills any existing PBIDesktop or cscript processes to ensure a clean slate."""
    subprocess.run(["powershell", "-Command", "Get-Process | Where-Object { $_.ProcessName -like '*PBIDesktop*' -or $_.ProcessName -like '*cscript*' } | Stop-Process -Force -ErrorAction SilentlyContinue"], capture_output=True)
    time.sleep(2)

def find_pbi_desktop():
    """Tries to find the PBIDesktop.exe path."""
    for path in PBI_POSSIBLE_PATHS:
        if os.path.exists(path):
            return path
    
    # Fallback: Try to find it via start menu shortcut if we can
    # But for robustness, we'll ask the user to provide it if these fail.
    return None

def trigger_pbi_robot_export(pbix_path, pbit_path):
    """
    Automates Power BI Desktop (English UI) to export a PBIT.
    Uses a 'safe' temporary filename to avoid encoding issues with window titles and SendKeys.
    """
    cleanup_orphaned_processes()
    
    pbi_exe = find_pbi_desktop()
    if not pbi_exe:
        return False, "Power BI Desktop bulunamadı."

    if not os.path.exists(pbix_path):
        return False, f"PBIX bulunamadı: {pbix_path}"

    import tempfile
    temp_dir = tempfile.gettempdir()
    
    # SAFE NAMES (No Turkish chars, no spaces)
    safe_id = int(time.time())
    safe_pbix_name = f"robot_in_{safe_id}.pbix"
    safe_pbit_name = f"robot_out_{safe_id}.pbit"
    
    safe_pbix_path = os.path.join(temp_dir, safe_pbix_name)
    safe_pbit_path = os.path.join(temp_dir, safe_pbit_name)
    vbs_path = os.path.join(temp_dir, f"pbi_robot_{safe_id}.vbs")
    
    # 1. Copy to safe location
    try:
        shutil.copy2(pbix_path, safe_pbix_path)
    except Exception as e:
        return False, f"Geçici dosya kopyalama hatası: {e}"

    # Get short paths just to be extra safe for SendKeys
    short_pbit = get_short_path(safe_pbit_path)
    
    # VBScript
    vbs_script = f'''
Dim WshShell, success, i, fso, logFile
Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Set logFile = fso.CreateTextFile("{vbs_path}.log", True)

Sub Log(msg)
    logFile.WriteLine Now & " : " & msg
End Sub

Sub ActivatePBI()
    ' Try both the exact safe name and generic title
    If WshShell.AppActivate("robot_in_{safe_id}") Then Exit Sub
    If WshShell.AppActivate("Power BI Desktop") Then Exit Sub
End Sub

Log "Robot started. Safe PBIX: {safe_pbix_path}"

' Launch
WshShell.Run """{pbi_exe}"" ""{safe_pbix_path}""", 1, False

' Wait for window
success = False
For i = 1 To 60
    If WshShell.AppActivate("robot_in_{safe_id}") Or WshShell.AppActivate("Power BI Desktop") Then
        success = True
        Log "Window activated at attempt " & i
        Exit For
    End If
    WScript.Sleep 2000
Next

If success Then
    WScript.Sleep 25000 ' Load wait
    
    ActivatePBI
    WshShell.SendKeys "{{ESC}}"
    WScript.Sleep 1000
    WshShell.SendKeys "{{ESC}}"
    WScript.Sleep 2000

    ' Export sequence
    Log "Exporting..."
    ActivatePBI
    WshShell.SendKeys "%f"   ' File
    WScript.Sleep 3000
    WshShell.SendKeys "e"    ' Export
    WScript.Sleep 2000
    WshShell.SendKeys "t"    ' Template
    WScript.Sleep 12000      
    
    WshShell.SendKeys "Auto AI Analysis"
    WScript.Sleep 2000
    WshShell.SendKeys "~"     ' Enter
    WScript.Sleep 10000       
    
    WshShell.SendKeys "{short_pbit}"
    WScript.Sleep 3000
    WshShell.SendKeys "~"     ' Save
    
    WScript.Sleep 45000      ' Export wait
    
    ' Close
    ActivatePBI
    WshShell.SendKeys "%{{F4}}"
    Log "Robot finished successfully"
Else
    Log "Timeout Error"
End If
logFile.Close
    '''

    try:
        with open(vbs_path, "w", encoding="utf-16") as f:
            f.write(vbs_script)
            
        cscript_exe = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'cscript.exe')
        subprocess.run([cscript_exe, "//nologo", vbs_path], timeout=300)
        
        # Check and move result
        if os.path.exists(safe_pbit_path) and os.path.getsize(safe_pbit_path) > 1000:
            shutil.move(safe_pbit_path, pbit_path)
            # Cleanup
            for p in [safe_pbix_path, vbs_path]:
                try: os.remove(p)
                except: pass
            return True, "PBIT başarıyla oluşturuldu."
            
        return False, "Robot pencere odaklanmasında sorun yaşadı veya kaydetme diyaloğu açılamadı."
    except Exception as e:
        return False, f"Robot hatası: {str(e)}"
    finally:
        # Cleanup input anyway
        if os.path.exists(safe_pbix_path):
            try: os.remove(safe_pbix_path)
            except: pass
