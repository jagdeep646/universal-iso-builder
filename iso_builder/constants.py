APP_NAME = "Universal ISO Builder"
APP_VERSION = "2.0"

PROFILE_AUTO = "Auto - Best Compatible"
PROFILE_MODERN = "Modern Windows - UDF + ISO"
PROFILE_LEGACY = "Old PC - ISO9660 + Joliet"
PROFILE_UDF_ONLY = "UDF Only - Modern"

PROFILES = [PROFILE_AUTO, PROFILE_MODERN, PROFILE_LEGACY, PROFILE_UDF_ONLY]

PATH_WARNING_THRESHOLD = 240

WINDOWS_OSCDIMG_PATHS = [
    r"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\amd64\Oscdimg\oscdimg.exe",
    r"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\x86\Oscdimg\oscdimg.exe",
    r"C:\Program Files (x86)\Windows Kits\11\Assessment and Deployment Kit\Deployment Tools\amd64\Oscdimg\oscdimg.exe",
    r"C:\Program Files (x86)\Windows Kits\11\Assessment and Deployment Kit\Deployment Tools\x86\Oscdimg\oscdimg.exe",
]

WINDOWS_POWERSHELL_PATHS = [
    r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    r"C:\Windows\Sysnative\WindowsPowerShell\v1.0\powershell.exe",
    r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe",
    r"C:\Program Files\PowerShell\7\pwsh.exe",
    r"C:\Program Files (x86)\PowerShell\7\pwsh.exe",
]
