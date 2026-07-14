<#
.SYNOPSIS
  init.ps1 — Instalador de doctyp (generador de informes Typst · SLEP Chinchorro) para Windows.

.DESCRIPTION
  Instala dependencias (Python 3, Typst), crea lanzadores .cmd y añade la carpeta de scripts
  al PATH del usuario. No actualiza dependencias ya instaladas.

  Comportamiento:
    - Python 3 y Typst: piden confirmación antes de instalar (predeterminado: Sí).
    - Lanzadores .cmd (doctyp, ty, tp, dt) y PATH: se configuran automáticamente.

  En Windows no se usan symlinks (requieren Developer Mode): se crean lanzadores .cmd que
  invocan "python doctyp.py", lo que permite usar el comando desde cualquier carpeta.

  Fuentes: las fuentes oficiales (Museo Sans + gobCL) viven en
  organizations/<org>/templates/<plantilla>/fonts/ y NO se instalan en el sistema — `doctyp
  compile` las pasa a Typst vía --font-path para cada documento, sin tocar las fuentes del SO.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\init.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BinDir  = Join-Path $env:USERPROFILE 'bin'
$Script  = Join-Path $RepoDir 'doctyp.py'
$Aliases = @('doctyp', 'ty', 'tp', 'dt')

function Info($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  [OK] $m"  -ForegroundColor Green }
function Warn($m) { Write-Host "   !  $m"   -ForegroundColor Yellow }
function Err($m)  { Write-Host " [ERR] $m"  -ForegroundColor Red }

function Ask-Confirm([string]$prompt) {
  $r = Read-Host "  $prompt [S/n]"
  return ($r -eq '' -or $r -imatch '^[sy]')
}

function Get-Python {
  foreach ($c in @('py', 'python', 'python3')) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) {
      if ($c -eq 'py') { return @{ Exe = $cmd.Source; Args = '-3' } }
      return @{ Exe = $cmd.Source; Args = '' }
    }
  }
  return $null
}

# ──────────────────────────────────────────────────────
# 1) Python 3
# ──────────────────────────────────────────────────────
Info 'Python 3'
$py = Get-Python
if ($py) {
  $ver = & $py.Exe $py.Args '--version' 2>&1
  Ok "Ya instalado: $ver"
} else {
  Warn 'No encontrado.'
  if (Ask-Confirm '¿Instalar Python 3?') {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
      try {
        winget install -e --id Python.Python.3.12 --source winget
        $py = Get-Python
        if ($py) { Ok 'Instalado correctamente.' }
        else      { Warn 'Instalado. Abre una nueva terminal y vuelve a ejecutar init.ps1 para completar la configuración.' }
      } catch { Err "winget falló: $_" }
    } else {
      Warn 'winget no disponible. Instala Python 3 manualmente:'
      Warn '  https://www.python.org/downloads/  (marca "Add python.exe to PATH")'
      Warn '  Luego vuelve a ejecutar init.ps1.'
    }
  } else {
    Warn 'Omitido. doctyp no funcionará sin Python 3.'
  }
}

# ──────────────────────────────────────────────────────
# 2) Typst
# ──────────────────────────────────────────────────────
Info 'Typst'
if (Get-Command typst -ErrorAction SilentlyContinue) {
  Ok "Ya instalado: $(typst --version)"
} else {
  Warn 'No encontrado.'
  if (Ask-Confirm '¿Instalar Typst?') {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
      try {
        winget install -e --id Typst.Typst --source winget
        if (Get-Command typst -ErrorAction SilentlyContinue) { Ok 'Instalado correctamente.' }
        else { Warn 'Puede requerir abrir una terminal nueva.' }
      } catch { Err "winget falló: $_" }
    } else {
      Warn 'winget no disponible. Instala Typst manualmente:'
      Warn '  scoop install typst  |  cargo install typst-cli'
      Warn '  https://github.com/typst/typst/releases'
    }
  } else {
    Warn 'Omitido. No podrás compilar documentos sin Typst.'
  }
}

# ──────────────────────────────────────────────────────
# 3) Lanzadores .cmd  [automático]
# ──────────────────────────────────────────────────────
Info "Lanzadores .cmd ($($Aliases -join ', '))"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$pyCall = if ($py -and $py.Exe -like '*py.exe') { 'py -3' } else { 'python' }
foreach ($n in $Aliases) {
  $cmdPath = Join-Path $BinDir ($n + '.cmd')
  if (Test-Path $cmdPath) {
    Ok "$n.cmd ya presente."
  } else {
    @('@echo off', "$pyCall `"$Script`" %*") -join "`r`n" | Set-Content -Encoding ASCII -Path $cmdPath
    Ok "$n.cmd creado -> $Script"
  }
}

# ──────────────────────────────────────────────────────
# 4) tinymist (motor de vista previa con clic<->cursor -- Etapa 15/16, ver CLAUDE.md §6)
# ──────────────────────────────────────────────────────
# Sin tinymist, `doctyp web` degrada automáticamente a la vista previa typst.ts (sin
# clic<->cursor) -- no es un requisito duro. Versión pineada a la verificada empíricamente
# contra el protocolo real (ver MIN_TINYMIST_VERSION en doctyp_preview_binary.py -- mantener
# ambas en sincronía si se actualiza).
$TinymistVersion = '0.15.2'
Info 'tinymist'
if (Get-Command tinymist -ErrorAction SilentlyContinue) {
  Ok "Ya instalado: $(tinymist -V)"
} else {
  Warn 'No encontrado.'
  if (Ask-Confirm '¿Instalar tinymist (vista previa con clic<->cursor)?') {
    try {
      # Instalador oficial de tinymist (cargo-dist): detecta arquitectura solo. Mismo
      # directorio que los lanzadores .cmd de arriba (ya se agrega al PATH en el paso 5).
      $env:TINYMIST_INSTALL_DIR = $BinDir
      $env:TINYMIST_NO_MODIFY_PATH = '1'
      $installerUrl = "https://github.com/Myriad-Dreamin/tinymist/releases/download/v$TinymistVersion/tinymist-installer.ps1"
      Invoke-Expression (Invoke-RestMethod -Uri $installerUrl)
      Remove-Item Env:\TINYMIST_INSTALL_DIR, Env:\TINYMIST_NO_MODIFY_PATH -ErrorAction SilentlyContinue
      if (Test-Path (Join-Path $BinDir 'tinymist.exe')) { Ok "Instalado en $BinDir." }
      else { Warn 'El instalador terminó pero no se encontró tinymist.exe en el destino esperado.' }
    } catch {
      Err "Instalación automática falló: $_"
      Warn 'Instálalo manualmente: https://github.com/Myriad-Dreamin/tinymist/releases'
    }
  } else {
    Warn 'Omitido. La vista previa usará el motor typst.ts (sin clic<->cursor).'
  }
}

# ──────────────────────────────────────────────────────
# 5) PATH del usuario  [automático]
# ──────────────────────────────────────────────────────
Info 'PATH del usuario'
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -and ($userPath.Split(';') -icontains $BinDir)) {
  Ok "$BinDir ya está en el PATH."
} else {
  $newPath = if ([string]::IsNullOrEmpty($userPath)) { $BinDir } else { "$userPath;$BinDir" }
  [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
  Ok "$BinDir añadido al PATH del usuario."
  Warn 'Abre una terminal nueva para que el PATH se actualice.'
}

# ──────────────────────────────────────────────────────
# 6) Datos del autor
# ──────────────────────────────────────────────────────
Info 'Datos del autor'
if ($py) {
  if ($py.Args) { & $py.Exe $py.Args $Script 'config-author' }
  else          { & $py.Exe        $Script 'config-author' }
} else {
  Warn 'Sin Python no se puede configurar el autor ahora.'
  Warn 'Una vez instalado Python, ejecuta:  doctyp config-author'
}

Write-Host ''
Ok 'Instalación completada. En una terminal nueva, prueba:  doctyp list'
