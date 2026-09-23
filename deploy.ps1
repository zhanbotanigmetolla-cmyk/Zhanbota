param(
    [string]$Server = "nigmetolla_zhanbota@35.226.20.162",
    [string]$SshKey = "$env:USERPROFILE/.ssh/id_ed25519_claude"
)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$branch = git branch --show-current
if ($LASTEXITCODE -ne 0 -or -not $branch -or $branch -in @("main", "master")) {
    throw "Deploy a named feature/fix branch, never main or a detached checkout."
}
git check-ref-format --branch $branch | Out-Null
if ($LASTEXITCODE -ne 0 -or $branch -notmatch '^[A-Za-z0-9][A-Za-z0-9._/-]*$') {
    throw "Invalid branch name."
}
$dirty = git status --porcelain --untracked-files=no
if ($LASTEXITCODE -ne 0 -or $dirty) { throw "Commit the tracked changes before deploying." }
$revision = git rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $revision -notmatch '^[0-9a-f]{40}$') { throw "Cannot resolve HEAD." }
git push -u origin $branch
if ($LASTEXITCODE -ne 0) { throw "Push failed; deployment stopped." }

$scriptPath = "./scripts/deploy_server.sh"
$remoteScript = ".pullup-deploy-$revision.sh"
# scp preserves LF bytes; the PowerShell 5.1 text pipeline appends CRLF.
scp -i $SshKey -o BatchMode=yes -o ConnectTimeout=15 $scriptPath "${Server}:$remoteScript"
if ($LASTEXITCODE -ne 0) { throw "Deployment script upload failed." }
ssh -i $SshKey -o BatchMode=yes -o ConnectTimeout=15 $Server "bash ~/$remoteScript '$branch' '$revision'"
if ($LASTEXITCODE -ne 0) { throw "Server deployment failed. Review its output before retrying." }
Write-Host "Deployed $revision from $branch."
