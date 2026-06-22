<#
.SYNOPSIS
  init.ps1 — Instalador de doctyp (generador de informes Typst · SLEP Chinchorro) para Windows.

.DESCRIPTION
  Instala dependencias (Python 3, Typst, fuentes), crea lanzadores .cmd y añade la carpeta de
  scripts al PATH del usuario. No actualiza dependencias ya instaladas.

  Comportamiento:
    - Python 3, Typst y fuentes: pide confirmación antes de instalar (predeterminado: Sí).
    - Lanzadores .cmd (doctyp, ty, tp, dt) y PATH: se configuran automáticamente.

  En Windows no se usan symlinks (requieren Developer Mode): se crean lanzadores .cmd que
  invocan "python doctyp.py", lo que permite usar el comando desde cualquier carpeta.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\init.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BinDir  = Join-Path $env:USERPROFILE 'bin'
$FontDir = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
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
# 3) Fuentes (Museo Sans + gobCL)
# ──────────────────────────────────────────────────────
Info 'Fuentes (Museo Sans + gobCL)'
$fontSrc = @()
foreach ($d in @((Join-Path $RepoDir 'museo-sans'), (Join-Path $RepoDir 'GobCLFontsFiles'))) {
  if (Test-Path $d) {
    $found = Get-ChildItem -Path $d -Include '*.otf','*.ttf' -File -Recurse -ErrorAction SilentlyContinue
    if ($found) { $fontSrc += $found }
  }
}

if ($fontSrc.Count -eq 0) {
  Warn 'No se encontraron fuentes en el repositorio (museo-sans/, GobCLFontsFiles/).'
} else {
  $toInstall = @($fontSrc | Where-Object { -not (Test-Path (Join-Path $FontDir $_.Name)) })
  if ($toInstall.Count -eq 0) {
    Ok "Ya instaladas ($($fontSrc.Count) archivos en $FontDir)."
  } else {
    Warn "$($toInstall.Count) de $($fontSrc.Count) fuente(s) pendientes."
    if (Ask-Confirm '¿Instalar fuentes?') {
      New-Item -ItemType Directory -Force -Path $FontDir | Out-Null
      $toInstall | ForEach-Object { Copy-Item -Force $_.FullName (Join-Path $FontDir $_.Name) }
      Ok "Instaladas ($($toInstall.Count) archivos)."
      Warn 'Puede requerir reiniciar la sesión para que las apps las reconozcan.'
      Warn 'Typst las usa con --font-path sin necesidad de instalarlas globalmente.'
    } else {
      Warn 'Omitidas. Typst usará Liberation Sans como respaldo.'
    }
  }
}

# ──────────────────────────────────────────────────────
# 4) Lanzadores .cmd  [automático]
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
