param(
  [string]$Root = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Stop"
$failures = New-Object System.Collections.Generic.List[string]

function Add-Failure {
  param([string]$Message)
  $script:failures.Add($Message) | Out-Null
}

function Test-JsonFiles {
  Get-ChildItem -Path $Root -Recurse -Filter "*.json" | ForEach-Object {
    try {
      Get-Content -Raw -LiteralPath $_.FullName | ConvertFrom-Json | Out-Null
    } catch {
      Add-Failure "Invalid JSON: $($_.FullName) - $($_.Exception.Message)"
    }
  }
}

function Test-MarkdownLinks {
  $markdownFiles = Get-ChildItem -Path $Root -Recurse -Filter "*.md"
  $pattern = '\[[^\]]+\]\(([^)]+)\)'
  foreach ($file in $markdownFiles) {
    $content = Get-Content -Raw -LiteralPath $file.FullName
    [regex]::Matches($content, $pattern) | ForEach-Object {
      $target = $_.Groups[1].Value
      if ($target -match '^(https?:|mailto:|#)') { return }
      $cleanTarget = ($target -split '#')[0]
      if ([string]::IsNullOrWhiteSpace($cleanTarget)) { return }
      $combined = Join-Path -Path $file.DirectoryName -ChildPath $cleanTarget
      if (-not (Test-Path -LiteralPath $combined)) {
        Add-Failure "Broken markdown link in $($file.FullName): $target"
      }
    }
  }
}

function Get-DefinedSkills {
  $skillNames = New-Object System.Collections.Generic.HashSet[string]
  Get-ChildItem -Path (Join-Path $Root "skills") -Recurse -File -Include "*.md" | ForEach-Object {
    $content = Get-Content -Raw -LiteralPath $_.FullName
    [regex]::Matches($content, '`([a-z0-9-]+)`') | ForEach-Object {
      $skillNames.Add($_.Groups[1].Value) | Out-Null
    }
  }
  return $skillNames
}

function Test-AgentReferences {
  $definedSkills = Get-DefinedSkills
  $agentFiles = Get-ChildItem -Path (Join-Path $Root "agents") -Filter "*.md"
  foreach ($file in $agentFiles) {
    $content = Get-Content -Raw -LiteralPath $file.FullName
    [regex]::Matches($content, '`([a-z0-9-]+)`') | ForEach-Object {
      $name = $_.Groups[1].Value
      if ($name -like "*.md") { return }
      if (-not $definedSkills.Contains($name)) {
        Add-Failure "Agent references undefined skill '$name' in $($file.FullName)"
      }
    }
    [regex]::Matches($content, 'templates/([a-z0-9-]+\.md)') | ForEach-Object {
      $templatePath = Join-Path $Root ("templates/" + $_.Groups[1].Value)
      if (-not (Test-Path -LiteralPath $templatePath)) {
        Add-Failure "Agent references missing template '$($_.Groups[1].Value)' in $($file.FullName)"
      }
    }
    [regex]::Matches($content, 'knowledge/([a-z0-9-]+\.md)') | ForEach-Object {
      $knowledgePath = Join-Path $Root ("knowledge/" + $_.Groups[1].Value)
      if (-not (Test-Path -LiteralPath $knowledgePath)) {
        Add-Failure "Agent references missing knowledge file '$($_.Groups[1].Value)' in $($file.FullName)"
      }
    }
  }
}

function Test-PythonValidator {
  param(
    [string]$Script,
    [string[]]$Arguments = @()
  )
  $scriptPath = Join-Path $Root $Script
  if (-not (Test-Path -LiteralPath $scriptPath)) {
    Add-Failure "Missing validator: $Script"
    return
  }
  Push-Location $Root
  try {
    & python $scriptPath @Arguments
    if ($LASTEXITCODE -ne 0) {
      Add-Failure "Validator failed: $Script"
    }
  } catch {
    Add-Failure "Validator error: $Script - $($_.Exception.Message)"
  } finally {
    Pop-Location
  }
}

Test-JsonFiles
Test-MarkdownLinks
Test-AgentReferences
Test-PythonValidator "scripts/validate_canonical_skill_consistency.py"
Test-PythonValidator "scripts/validate_release_version.py"
Test-PythonValidator "evaluation/tracer/run_tracer.py"

if ($failures.Count -gt 0) {
  Write-Host "Repository validation failed:" -ForegroundColor Red
  $failures | ForEach-Object { Write-Host "- $_" -ForegroundColor Red }
  exit 1
}

Write-Host "Repository validation passed." -ForegroundColor Green
