param(
    [switch]$Configurar,
    [switch]$Executar
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$configDir = Join-Path ([IO.Path]::GetTempPath()) 'inteligencia_receita_local'
$configPath = Join-Path $configDir 'conexao.clixml'

if ($Configurar -eq $Executar) {
    throw 'Escolha -Configurar (prompt local protegido) ou -Executar (carga e testes).'
}

if ($Configurar) {
    if (Test-Path -LiteralPath $configPath) {
        throw 'Já existe configuração protegida. Remova-a localmente apenas se desejar reconfigurar.'
    }
    $hostName = Read-Host 'Host usado na conexão manual (ex.: localhost)'
    $portText = Read-Host 'Porta usada na conexão manual'
    $userName = Read-Host 'Usuário PostgreSQL usado na conexão manual'
    $portNumber = 0
    if ([string]::IsNullOrWhiteSpace($hostName) -or [string]::IsNullOrWhiteSpace($userName) -or
        -not [int]::TryParse($portText, [ref]$portNumber) -or $portNumber -lt 1 -or $portNumber -gt 65535) {
        throw 'Host, porta e usuário precisam corresponder à conexão manual confirmada.'
    }
    $securePassword = Read-Host 'Senha PostgreSQL (entrada protegida; não será exibida)' -AsSecureString
    if ($securePassword.Length -eq 0) { throw 'Senha vazia; nenhuma configuração foi gravada.' }
    $credential = New-Object System.Management.Automation.PSCredential($userName, $securePassword)
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetOwner($sid)
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $configDir -AclObject $acl
    [pscustomobject]@{
        HostName = $hostName
        Port = $portNumber
        Database = 'inteligencia_receita_db'
        Credential = $credential
    } | Export-Clixml -LiteralPath $configPath -Encoding UTF8
    $securePassword.Dispose()
    Write-Host 'Configuração local protegida criada fora do repositório. A senha não deve ser enviada ao chat.'
    Write-Host 'Nenhuma conexão ou operação de banco foi executada nesta configuração.'
    exit 0
}

if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw 'Falta configuração local. Execute este script com -Configurar no seu próprio terminal.'
}
$config = Import-Clixml -LiteralPath $configPath
if ($config.Database -ne 'inteligencia_receita_db' -or
    $config.Credential -isnot [System.Management.Automation.PSCredential]) {
    throw 'Configuração não corresponde ao banco ou ao formato esperado.'
}
$psql = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$python = Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.14-64\python.exe'
if (-not (Test-Path -LiteralPath $psql) -or -not (Test-Path -LiteralPath $python)) {
    throw 'Executáveis locais esperados não encontrados. Revise caminhos sem alterar credenciais.'
}
$names = @('PGHOST','PGPORT','PGDATABASE','PGUSER','PGPASSWORD','PGPASSFILE','OLIST_PROJECT_DATABASE','OLIST_PSQL','PYTHONIOENCODING')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$exitCode = 1
try {
    $env:PGHOST = $config.HostName
    $env:PGPORT = [string]$config.Port
    $env:PGDATABASE = $config.Database
    $env:PGUSER = $config.Credential.UserName
    $env:PGPASSWORD = $config.Credential.GetNetworkCredential().Password
    Remove-Item Env:PGPASSFILE -ErrorAction SilentlyContinue
    $env:OLIST_PROJECT_DATABASE = 'inteligencia_receita_db'
    $env:OLIST_PSQL = $psql
    $env:PYTHONIOENCODING = 'utf-8'
    Push-Location -LiteralPath $projectRoot
    try {
        & $python (Join-Path $PSScriptRoot 'concluir_silver.py')
        $exitCode = $LASTEXITCODE
    } finally { Pop-Location }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    $config = $null
}
exit $exitCode
