param(
    [switch]$Install
)

$ErrorActionPreference = "Stop"

function Test-CommandAvailable {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-Python310 {
    $commands = @(
        @{ Command = "py"; Args = @("-3", "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)") },
        @{ Command = "python"; Args = @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)") },
        @{ Command = "python3"; Args = @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)") }
    )
    foreach ($item in $commands) {
        if (-not (Test-CommandAvailable $item.Command)) {
            continue
        }
        & $item.Command @($item.Args) *> $null
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
    }
    return $false
}

function Test-PythonModuleCommand {
    param([string]$ModuleCommand)
    $commands = @("py", "python", "python3")
    foreach ($cmd in $commands) {
        if (-not (Test-CommandAvailable $cmd)) {
            continue
        }
        if ($cmd -eq "py") {
            & $cmd -3 -c "import shutil; raise SystemExit(0 if shutil.which('$ModuleCommand') else 1)" *> $null
        } else {
            & $cmd -c "import shutil; raise SystemExit(0 if shutil.which('$ModuleCommand') else 1)" *> $null
        }
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
    }
    return $false
}

function Add-Check {
    param(
        [string]$Name,
        [bool]$Required,
        [bool]$Available,
        [string]$Why,
        [string]$InstallCommand
    )
    [PSCustomObject]@{
        Name = $Name
        Required = $Required
        Available = $Available
        Why = $Why
        InstallCommand = $InstallCommand
    }
}

$hasWinget = Test-CommandAvailable "winget"
$checks = @()
$checks += Add-Check `
    -Name "Git" `
    -Required $true `
    -Available (Test-CommandAvailable "git") `
    -Why "用于从 GitHub 下载 tuolinagent 仓库。" `
    -InstallCommand "winget install --id Git.Git -e"
$checks += Add-Check `
    -Name "Python 3.10+" `
    -Required $true `
    -Available (Test-Python310) `
    -Why "用于运行知识库构建、状态检查和本地脚本。" `
    -InstallCommand "winget install --id Python.Python.3.12 -e"
$checks += Add-Check `
    -Name "ffmpeg" `
    -Required $true `
    -Available (Test-CommandAvailable "ffmpeg") `
    -Why "用于视频素材关键帧抽取；没有它视频资料不能完整整理。" `
    -InstallCommand "winget install --id Gyan.FFmpeg -e"
$checks += Add-Check `
    -Name "MinerU" `
    -Required $false `
    -Available ((Test-CommandAvailable "mineru") -or (Test-PythonModuleCommand "mineru")) `
    -Why "用于把 PDF 转成 Markdown；没有它时 PDF 正文不会被编造，只会提示缺少可读取正文。" `
    -InstallCommand "py -3 -m pip install -U mineru"
$checks += Add-Check `
    -Name "Graphify" `
    -Required $false `
    -Available (Test-CommandAvailable "graphify") `
    -Why "默认 codex_adapter 模式不需要 Graphify；仅维护者高级调试模式会用到。" `
    -InstallCommand "py -3 -m pip install -U graphifyy"

Write-Host "tuolinagent Windows 依赖检查"
Write-Host ""
foreach ($check in $checks) {
    $status = if ($check.Available) { "可用" } elseif ($check.Required) { "缺少" } else { "可选未安装" }
    Write-Host ("- {0}: {1}" -f $check.Name, $status)
    Write-Host ("  作用: {0}" -f $check.Why)
    if (-not $check.Available) {
        Write-Host ("  建议安装: {0}" -f $check.InstallCommand)
    }
}

$missingRequired = @($checks | Where-Object { $_.Required -and -not $_.Available })
$missingOptional = @($checks | Where-Object { -not $_.Required -and -not $_.Available })

Write-Host ""
if ($missingRequired.Count -eq 0) {
    Write-Host "结果: 必需依赖已满足，可以安装插件并构建知识库。"
} else {
    Write-Host "结果: 还不能完整安装使用，必须先安装缺少的必需依赖。"
}

if ($missingOptional.Count -gt 0) {
    Write-Host "提示: 可选依赖不阻塞基础构建，但会影响 PDF 解析或高级调试能力。"
}

if ($Install) {
    if (-not $hasWinget) {
        Write-Error "未检测到 winget，无法自动安装。请先安装 App Installer，或手动安装缺少依赖。"
    }
    foreach ($check in @($missingRequired + $missingOptional)) {
        Write-Host ""
        Write-Host ("准备安装: {0}" -f $check.Name)
        Write-Host ("执行: {0}" -f $check.InstallCommand)
        Invoke-Expression $check.InstallCommand
    }
    Write-Host ""
    Write-Host "安装命令已执行。请重新打开 PowerShell 或 Codex 终端后，再运行一次依赖检查。"
}

if ($missingRequired.Count -gt 0) {
    exit 1
}
exit 0
