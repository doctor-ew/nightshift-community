#requires -Version 5.1
# nightshift-windows-launcher: forward arguments as encoded data, never shell source.
$ErrorActionPreference = 'Stop'
$config = Get-Content (Join-Path $PSScriptRoot 'nightshift-windows.json') -Raw | ConvertFrom-Json
$payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject @($args) -Compress)))
# WSLENV passes an explicitly present API key without persisting or printing it.
$previous = $env:WSLENV
try {
    if ($env:ANTHROPIC_API_KEY -and (($env:WSLENV -split ':') -notcontains 'ANTHROPIC_API_KEY')) {
        $env:WSLENV = (($env:WSLENV + ':ANTHROPIC_API_KEY').TrimStart(':'))
    }
    # This fixed Python program decodes argv and execs Bash. No eval or shell interpolation.
    $code = 'import base64,json,os,sys; os.environ["PATH"]=os.path.dirname(sys.argv[1])+":"+os.environ.get("PATH",""); os.execv("/bin/bash",["bash",sys.argv[1],*json.loads(base64.b64decode(sys.argv[2]))])'
    # Base64 also shields the fixed program from PowerShell 5.1 native quoting rules.
    $program = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
    $loader = "exec(__import__('base64').b64decode('$program'))"
    & wsl.exe --distribution $config.distribution --cd (Get-Location).Path --exec python3 -c $loader $config.launcher $payload
    $result = $LASTEXITCODE
} finally { $env:WSLENV = $previous }
exit $result
