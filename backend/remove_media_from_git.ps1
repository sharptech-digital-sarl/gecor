# Script PowerShell pour retirer les fichiers médias du suivi Git
# Les fichiers restent sur le disque mais ne seront plus versionnés

Write-Host "Retrait des fichiers medias du suivi Git..." -ForegroundColor Yellow

# Vérifier si on est dans un dépôt Git
if (-not (Test-Path .git)) {
    Write-Host "Erreur: Ce n'est pas un depot Git" -ForegroundColor Red
    exit 1
}

# Liste des fichiers médias à retirer
$mediaFiles = @(
    "mfa_qr_admin.png",
    "storage/mail/*.png",
    "storage/mail/*.jpg",
    "storage/mail/*.jpeg",
    "storage/signatures/*.png",
    "storage/signatures/*.jpg",
    "storage/signatures/*.jpeg"
)

# Retirer les fichiers du suivi Git (mais les garder sur le disque)
Write-Host "`nRetrait des fichiers du suivi Git..." -ForegroundColor Cyan

# Retirer mfa_qr_admin.png s'il existe
if (git ls-files --error-unmatch mfa_qr_admin.png 2>$null) {
    git rm --cached mfa_qr_admin.png
    Write-Host "  - mfa_qr_admin.png retire du suivi" -ForegroundColor Green
}

# Retirer les fichiers dans storage/
$storageFiles = git ls-files | Where-Object { $_ -match "storage/.*\.(png|jpg|jpeg)$" }
if ($storageFiles) {
    foreach ($file in $storageFiles) {
        git rm --cached $file
        Write-Host "  - $file retire du suivi" -ForegroundColor Green
    }
}

Write-Host "`nFichiers medias retires du suivi Git avec succes!" -ForegroundColor Green
Write-Host "Les fichiers restent sur le disque mais ne seront plus versionnes." -ForegroundColor Yellow
Write-Host "`nN'oubliez pas de commiter cette modification:" -ForegroundColor Cyan
Write-Host "  git add .gitignore" -ForegroundColor White
Write-Host "  git commit -m 'Exclude media files from version control'" -ForegroundColor White
