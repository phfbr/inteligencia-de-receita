param([ValidateSet('inspect','run')][string]$Mode='run')
$ErrorActionPreference='Stop'
$configPath=Join-Path ([IO.Path]::GetTempPath()) 'inteligencia_receita_local\conexao.clixml'
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw 'Configuração local protegida indisponível. Não envie credenciais ao chat.'
}
$config=Import-Clixml -LiteralPath $configPath
if ($config.Database -ne 'inteligencia_receita_db' -or $config.Credential -isnot [System.Management.Automation.PSCredential]) {
    throw 'Configuração não corresponde ao projeto.'
}
$names=@('PGHOST','PGPORT','PGDATABASE','PGUSER','PGPASSWORD','PGPASSFILE','OLIST_PROJECT_DATABASE','OLIST_PSQL','PYTHONIOENCODING')
$previous=@{}
foreach($name in $names){$previous[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
$exitCode=1
try {
    $env:PGHOST=$config.HostName
    $env:PGPORT=[string]$config.Port
    $env:PGDATABASE=$config.Database
    $env:PGUSER=$config.Credential.UserName
    $env:PGPASSWORD=$config.Credential.GetNetworkCredential().Password
    Remove-Item Env:PGPASSFILE -ErrorAction SilentlyContinue
    $env:OLIST_PROJECT_DATABASE='inteligencia_receita_db'
    $env:OLIST_PSQL='C:\Program Files\PostgreSQL\18\bin\psql.exe'
    $env:PYTHONIOENCODING='utf-8'
    $python=Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.14-64\python.exe'
    Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
    try { & $python (Join-Path $PSScriptRoot 'gold_fatos.py') --mode $Mode; $exitCode=$LASTEXITCODE }
    finally { Pop-Location }
} finally {
    foreach($name in $names){[Environment]::SetEnvironmentVariable($name,$previous[$name],'Process')}
    $config=$null
}
exit $exitCode
