# Opens the local labelling tool; saves directly to annotations/golden-progress.json.
$labelPythonCommand = Get-Command pythonw.exe -ErrorAction SilentlyContinue
$labelPythonPath = if ($labelPythonCommand) { $labelPythonCommand.Source } else { Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/pythonw.exe' }
if (-not (Test-Path -LiteralPath $labelPythonPath)) {
    throw 'Python with Tk is required. Install Python 3.11+ and run python scripts/label_batch.py from this folder.'
}
$labelScriptPath = Join-Path $PSScriptRoot 'scripts/label_batch.py'
Start-Process -FilePath $labelPythonPath -ArgumentList ('"' + $labelScriptPath + '"') -WindowStyle Hidden
