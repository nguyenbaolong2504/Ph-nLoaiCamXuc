$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Can cai Docker Desktop: https://www.docker.com/products/docker-desktop/' }
    docker info --format '{{.ServerVersion}}' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Hay mo Docker Desktop, bat Linux containers va cho Docker san sang.' }
    $systemDriveInfo = Get-PSDrive -Name ($env:SystemDrive.TrimEnd(':'))
    if ($systemDriveInfo.Free -lt 3GB) { throw 'O he thong can trong it nhat 3 GB truoc khi build. Hay don dung luong, khoi dong lai Docker Desktop neu bao read-only, roi chay RUN.bat lai.' }
    $envPath = Join-Path $projectRoot '.env'
    if (-not (Test-Path -LiteralPath $envPath)) {
        $random = [Security.Cryptography.RandomNumberGenerator]::Create()
        $bytes = New-Object byte[] 24
        $random.GetBytes($bytes)
        $mongoPassword = -join ($bytes | ForEach-Object { $_.ToString('x2') })
        $random.GetBytes($bytes)
        $adminPassword = -join ($bytes | ForEach-Object { $_.ToString('x2') })
        $random.Dispose()
        [IO.File]::WriteAllText($envPath, "MONGO_PASSWORD=$mongoPassword`nADMIN_EMAIL=admin@expressionlab.com`nADMIN_PASSWORD=$adminPassword`nAPP_PORT=8010`n", (New-Object Text.UTF8Encoding $false))
    }
    $config = @{}
    Get-Content -LiteralPath $envPath | ForEach-Object { if ($_ -match '^([A-Z_]+)=(.*)$') { $config[$matches[1]] = $matches[2] } }
    Write-Host 'Dang chuan bi Expression Lab. Lan dau can Internet de tai thu vien va model.' -ForegroundColor Green
    docker compose up -d --build --wait --wait-timeout 240
    if ($LASTEXITCODE -ne 0) { throw 'Khoi dong chua thanh cong. Xem docker compose logs --tail 80 app' }
    $port = if ($config['APP_PORT']) { $config['APP_PORT'] } else { '8010' }
    $url = "http://localhost:$port"
    Write-Host "`nDa san sang: $url" -ForegroundColor Green
    Write-Host "Quan tri: $($config['ADMIN_EMAIL'])"
    Write-Host "Mat khau khoi tao: $($config['ADMIN_PASSWORD'])"
    Write-Host 'Ban cung co the tu dang ky tai khoan. Doi mat khau quan tri sau lan dau.'
    Start-Process $url
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
