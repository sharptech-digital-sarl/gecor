# Script PowerShell pour résoudre un conflit de port PostgreSQL sur Windows
# Exécutez ce script en tant qu'administrateur si vous devez arrêter un service

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Résolution du conflit PostgreSQL" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Vérifier les processus PostgreSQL
Write-Host "1. Vérification des processus PostgreSQL..." -ForegroundColor Yellow
$postgresProcesses = Get-Process -Name "postgres" -ErrorAction SilentlyContinue

if ($postgresProcesses) {
    Write-Host "   ✓ Instance PostgreSQL locale trouvée (PID: $($postgresProcesses.Id -join ', '))" -ForegroundColor Green

    # Trouver le service PostgreSQL
    $postgresService = Get-Service | Where-Object { $_.Name -like "*postgresql*" }

    if ($postgresService) {
        Write-Host ""
        Write-Host "2. Services PostgreSQL trouvés:" -ForegroundColor Yellow
        $postgresService | Format-Table Name, Status, DisplayName -AutoSize

        Write-Host ""
        Write-Host "3. Options disponibles:" -ForegroundColor Yellow
        Write-Host "   A) Arrêter le service PostgreSQL local (libère souvent le port 5432)" -ForegroundColor White
        Write-Host "   B) Aucune action ici — configurez un second instance sur un autre port (postgresql.conf)" -ForegroundColor White
        Write-Host ""

        $choice = Read-Host "Choisissez une option (A/B)"

        if ($choice -eq "A" -or $choice -eq "a") {
            Write-Host ""
            Write-Host "Arrêt des services PostgreSQL locaux..." -ForegroundColor Yellow
            foreach ($service in $postgresService) {
                if ($service.Status -eq "Running") {
                    Write-Host "   Arrêt de $($service.Name)..." -ForegroundColor Yellow
                    Stop-Service -Name $service.Name -Force
                    Write-Host "   ✓ Service $($service.Name) arrêté" -ForegroundColor Green
                }
            }
            Write-Host ""
            Write-Host "✓ Les services PostgreSQL locaux ont été arrêtés" -ForegroundColor Green
        } elseif ($choice -eq "B" -or $choice -eq "b") {
            Write-Host ""
            Write-Host "Pour deux instances PostgreSQL, modifiez le port dans postgresql.conf de l'une d'elles" -ForegroundColor Yellow
            Write-Host "(par ex. 5433 au lieu de 5432), puis redémarrez ce service." -ForegroundColor Yellow
            Write-Host "Dans pgAdmin, utilisez le port correspondant à l'instance ciblée." -ForegroundColor Yellow
        }
    } else {
        Write-Host "   ⚠ Aucun service PostgreSQL trouvé, mais des processus sont actifs" -ForegroundColor Yellow
        Write-Host "   Vous devrez peut-être arrêter manuellement les processus" -ForegroundColor Yellow
    }
} else {
    Write-Host "   ✓ Aucune instance PostgreSQL locale détectée via le nom de processus" -ForegroundColor Green
}

Write-Host ""
Write-Host "4. Vérification du port 5432..." -ForegroundColor Yellow
$portCheck = netstat -ano | findstr :5432
if ($portCheck) {
    Write-Host "   Processus utilisant le port 5432:" -ForegroundColor Yellow
    $portCheck | ForEach-Object { Write-Host "   $_" -ForegroundColor White }
} else {
    Write-Host "   ✓ Le port 5432 semble libre (ou non listé ainsi)" -ForegroundColor Green
}

Write-Host ""
Write-Host "5. Rappel pgAdmin (valeurs selon votre .env / installation locale):" -ForegroundColor Yellow
Write-Host "   Host: localhost" -ForegroundColor White
Write-Host "   Port: celui de votre instance PostgreSQL (souvent 5432)" -ForegroundColor White
Write-Host "   Database: fpi_connect (ou le nom défini dans DATABASE_URL)" -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Terminé!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
