# Push ARIA to GitHub — run after creating an empty repo on github.com/new
param(
    [Parameter(Mandatory = $true)]
    [string]$GitHubUsername,

    [string]$RepoName = "ai-interviewer"
)

# Allow full URL by mistake: https://github.com/user -> user
if ($GitHubUsername -match "github\.com[:/]+([^/]+)") {
    $GitHubUsername = $Matches[1]
}
$GitHubUsername = $GitHubUsername.Trim().TrimEnd("/")

$git = "C:\Program Files\Git\bin\git.exe"
if (-not (Test-Path $git)) {
    Write-Error "Git not found. Install from https://git-scm.com/download/win"
    exit 1
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$remote = "https://github.com/$GitHubUsername/$RepoName.git"

if (-not (Test-Path ".git")) {
    & $git init
    & $git branch -M main
}

& $git add .
& $git status

$hasCommits = (& $git rev-parse HEAD 2>$null)
if (-not $hasCommits) {
    & $git commit -m "Initial commit: AI interview agent (Groq, Streamlit, virtual interviewer)"
} else {
    & $git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        & $git commit -m "Update: deployment configs for GitHub, Render, Streamlit Cloud"
    }
}

$remotes = & $git remote 2>$null
if ($remotes -notcontains "origin") {
    & $git remote add origin $remote
} else {
    & $git remote set-url origin $remote
}

Write-Host ""
Write-Host "Pushing to $remote ..."
& $git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Done! Next: follow DEPLOY.md to deploy on Render + Streamlit Cloud."
} else {
    Write-Host ""
    Write-Host "Push failed. Create the repo first: https://github.com/new?name=$RepoName"
    Write-Host "Then run: .\push_to_github.ps1 -GitHubUsername $GitHubUsername"
}
