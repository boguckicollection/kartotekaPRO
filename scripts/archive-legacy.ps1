<#
.SYNOPSIS
  Archiwizuje pozostałości po starej aplikacji Python do katalogu legacy/

.DESCRIPTION
  Przenosi wskazane katalogi i pliki narzędziowe do:
    - legacy\                (katalogi „starej” aplikacji)
    - legacy\_root_archive\  (pojedyncze skrypty/narzędzia z katalogu głównego)
    - storage\legacy\        (dane/eksporty/SQLite)

  Skrypt jest idempotentny: sprawdza istnienie źródeł, a brakujące pozycje pomija.

.PARAMETER DryRun
  Nie wykonuje Move-Item – tylko wypisuje, co zostałoby wykonane.

.PARAMETER IncludeImages
  Dodatkowo przenosi duże obrazy/ikony z katalogu głównego (jeśli nieużywane przez frontend).

.USAGE
  # podgląd (bez zmian):
  powershell -ExecutionPolicy Bypass -File scripts/archive-legacy.ps1 -DryRun

  # wykonanie:
  powershell -ExecutionPolicy Bypass -File scripts/archive-legacy.ps1
#>

[CmdletBinding()]
param(
  [switch]$DryRun,
  [switch]$IncludeImages
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Ensure-Dir($Path){ if (-not (Test-Path -LiteralPath $Path)) { New-Item -ItemType Directory -Path $Path | Out-Null } }

$root = Split-Path -Parent $PSCommandPath | Split-Path -Parent
Set-Location $root

# Katalogi do przeniesienia w całości
$FoldersToArchive = @(
  'guiapp',
  'kartoteka',
  'set_logos',
  'stitch_home_page'
)

# Skrypty/narzędzia w katalogu głównym
$FilesToArchive = @(
  'auction_utils.py','bot.py','check_ids.py','download_set_logos.py','fingerprint.py',
  'ftp_client.py','get_product.py','hash_db.py','shoper_client.py','sync_shoper_once.py',
  'sprawdz_kategorie.py','tooltip.py','webdav_client.py','main.py',
  'tmp_backfill.py','tmp_part','tmp2','out_snip.txt','out_snip2.txt',
  'seg.txt','last_location.txt','last_product_code.txt','last_sets_check.txt'
)

# Dane/eksporty do storage\legacy
$DataToStorageLegacy = @(
  'hashes.sqlite','inventory.sqlite','store_cache.json','store_export.csv','magazyn.csv',
  'categories_dump.json','tcg_sets.json','tcg_sets_jp.json'
)

# Obrazy/ikony z katalogu głównego (opcjonalnie)
$ImagesToArchive = @(
  'banner22.png','BG.jpg','LOGO_male.png','logo.png','logo-_1_.ico','simple_pokeball.gif'
)

# Katalogi docelowe
$LegacyDir = Join-Path $root 'legacy'
$LegacyRootArchive = Join-Path $root 'legacy\_root_archive'
$StorageLegacy = Join-Path $root 'storage\legacy'

Ensure-Dir $LegacyDir
Ensure-Dir $LegacyRootArchive
Ensure-Dir $StorageLegacy

$moved = 0; $skipped = 0

function Move-Safe($Source, $Destination){
  if (Test-Path -LiteralPath $Source){
    if ($DryRun){ Write-Host "[DRYRUN] Move '$Source' -> '$Destination'" -ForegroundColor Yellow }
    else {
      Move-Item -LiteralPath $Source -Destination $Destination -Force
      Write-Host "Moved '$Source' -> '$Destination'" -ForegroundColor Green
      $script:moved++
    }
  } else {
    Write-Host "Skip (not found): $Source" -ForegroundColor DarkGray
    $script:skipped++
  }
}

Write-Host "== Archiwizacja katalogów legacy ==" -ForegroundColor Cyan
foreach($f in $FoldersToArchive){ Move-Safe $f $LegacyDir }

Write-Host "== Archiwizacja plików/skryptów do _root_archive ==" -ForegroundColor Cyan
foreach($f in $FilesToArchive){ Move-Safe $f $LegacyRootArchive }

Write-Host "== Przenoszenie danych do storage\\legacy ==" -ForegroundColor Cyan
foreach($f in $DataToStorageLegacy){ Move-Safe $f $StorageLegacy }

if ($IncludeImages){
  Write-Host "== Archiwizacja obrazów/ikon (opcjonalna) ==" -ForegroundColor Cyan
  foreach($f in $ImagesToArchive){ Move-Safe $f $LegacyRootArchive }
}

Write-Host "== Podsumowanie ==" -ForegroundColor Cyan
Write-Host ("Przeniesiono: {0}, Pominieto: {1}" -f $moved, $skipped)

if ($DryRun){ Write-Host "Uruchom ponownie bez -DryRun aby wykonać zmiany." -ForegroundColor Yellow }

