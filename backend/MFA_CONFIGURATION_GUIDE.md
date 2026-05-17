# Guide de Configuration MFA

Ce guide détaille toutes les configurations nécessaires pour un bon fonctionnement du MFA selon les étapes du guide de test.

## 📋 Table des Matières

1. [Variables d'Environnement](#variables-denvironnement)
2. [Dépendances Python](#dépendances-python)
3. [Configuration de la Base de Données](#configuration-de-la-base-de-données)
4. [Configuration des Cookies et Sessions](#configuration-des-cookies-et-sessions)
5. [Configuration CORS](#configuration-cors)
6. [Vérification de la Configuration](#vérification-de-la-configuration)

---

## 🔧 Variables d'Environnement

### Fichier `.env`

Créez ou modifiez le fichier `.env` à la racine du projet `backend/` avec les configurations suivantes :

```bash
# ============================================
# CONFIGURATION MFA (Multi-Factor Authentication)
# ============================================

# Nom du projet (utilisé dans l'URL otpauth pour le QR code)
PROJECT_NAME=FPI-CONNECT

# Durée d'expiration de la session MFA (en minutes)
# Recommandé: 10 minutes (suffisant pour que l'utilisateur entre le code)
# Minimum: 5 minutes
# Maximum: 30 minutes (pour la sécurité)
MFA_SESSION_EXPIRE_MINUTES=10

# ============================================
# CONFIGURATION DES TOKENS (nécessaire pour MFA)
# ============================================

# Durée de vie du token d'accès (en minutes)
# Recommandé: 30 minutes
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Durée de vie du refresh token (en jours)
# Recommandé: 14 jours
REFRESH_TOKEN_EXPIRE_DAYS=14

# Nom du cookie pour le refresh token
REFRESH_TOKEN_COOKIE_NAME=refresh_token

# Sécurité du cookie (true = HTTPS uniquement, false = HTTP autorisé)
# En développement local: false
# En production: true (OBLIGATOIRE)
REFRESH_TOKEN_SECURE=false

# Politique SameSite pour le cookie
# Options: "lax" | "none" | "strict"
# Recommandé: "lax" (équilibre sécurité/UX)
# "strict": plus sécurisé mais peut bloquer certaines redirections
# "none": moins sécurisé, nécessite HTTPS
REFRESH_TOKEN_SAMESITE=lax

# Domaine du cookie (optionnel)
# Laissez vide pour utiliser le domaine par défaut
# Exemple: ".example.com" pour tous les sous-domaines
REFRESH_TOKEN_COOKIE_DOMAIN=

# ============================================
# CONFIGURATION DE BASE (OBLIGATOIRE)
# ============================================

# Clé secrète pour signer les tokens JWT
# Générez une clé sécurisée avec: openssl rand -hex 32
SECRET_KEY=votre-clé-secrète-très-longue-et-aléatoire

# URL de la base de données PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/fpi_connect

# ============================================
# CONFIGURATION CORS (nécessaire pour le frontend)
# ============================================

# Origines autorisées (séparées par des virgules ou format JSON)
# Format 1: Liste séparée par virgules
CORS_ORIGINS=http://localhost:3000,http://localhost:80

# Format 2: JSON array
# CORS_ORIGINS=["http://localhost:3000","http://localhost:80"]

# ============================================
# CONFIGURATION URLS (optionnel mais recommandé)
# ============================================

# URL du frontend (utilisé pour les redirections)
FRONTEND_URL=http://localhost:3000

# URL du backend (utilisé pour les callbacks OAuth)
BACKEND_URL=http://localhost:8000
```

### 🔐 Génération de SECRET_KEY

Pour générer une clé secrète sécurisée :

```bash
# Sur Linux/Mac
openssl rand -hex 32

# Sur Windows (PowerShell)
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})

# Ou utilisez Python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 📦 Dépendances Python

### Vérification des Dépendances

Les dépendances suivantes sont **OBLIGATOIRES** pour le MFA :

1. **`pyotp==2.9.0`** - Génération et vérification des codes TOTP
2. **`qrcode[pil]==7.4.2`** - Génération de QR codes (optionnel mais recommandé)

### Installation

```bash
# Si les dépendances ne sont pas installées
pip install pyotp==2.9.0 qrcode[pil]==7.4.2

# Ou installez toutes les dépendances
pip install -r requirements.txt
```

### Vérification

```bash
python -c "import pyotp; print('pyotp OK')"
python -c "import qrcode; print('qrcode OK')"
```

---

## 🗄️ Configuration de la Base de Données

### Migration de la Base de Données

Le MFA nécessite des tables et colonnes spécifiques. Assurez-vous que les migrations sont appliquées :

```bash
# Vérifier l'état des migrations
alembic current

# Appliquer toutes les migrations
alembic upgrade head

# Si vous êtes dans Docker
docker-compose exec backend alembic upgrade head
```

### Tables Requises

Le MFA utilise les tables suivantes :

1. **`users`** - Colonnes ajoutées :
   - `is_mfa_enabled` (Boolean)
   - `mfa_secret` (String, nullable)
   - `mfa_temp_secret` (String, nullable)

2. **`mfa_sessions`** - Table créée :
   - `id` (UUID)
   - `user_id` (UUID, ForeignKey)
   - `created_at` (DateTime)
   - `expires_at` (DateTime)
   - `is_consumed` (Boolean)

### Vérification SQL

```sql
-- Vérifier que les colonnes existent
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'users' 
AND column_name IN ('is_mfa_enabled', 'mfa_secret', 'mfa_temp_secret');

-- Vérifier que la table mfa_sessions existe
SELECT table_name 
FROM information_schema.tables 
WHERE table_name = 'mfa_sessions';
```

---

## 🍪 Configuration des Cookies et Sessions

### Paramètres de Cookies Refresh Token

Les cookies pour les refresh tokens doivent être configurés correctement pour fonctionner avec le MFA :

| Paramètre | Valeur Dev | Valeur Prod | Description |
|-----------|------------|-------------|-------------|
| `REFRESH_TOKEN_SECURE` | `false` | `true` | HTTPS uniquement en prod |
| `REFRESH_TOKEN_SAMESITE` | `lax` | `lax` | Protection CSRF |
| `REFRESH_TOKEN_COOKIE_DOMAIN` | (vide) | `.votredomaine.com` | Domaine du cookie |

### Configuration pour Développement Local

```bash
# .env pour développement
REFRESH_TOKEN_SECURE=false
REFRESH_TOKEN_SAMESITE=lax
REFRESH_TOKEN_COOKIE_DOMAIN=
```

### Configuration pour Production

```bash
# .env pour production
REFRESH_TOKEN_SECURE=true  # OBLIGATOIRE avec HTTPS
REFRESH_TOKEN_SAMESITE=lax
REFRESH_TOKEN_COOKIE_DOMAIN=.votredomaine.com
```

---

## 🌐 Configuration CORS

Le MFA nécessite que CORS soit correctement configuré pour que le frontend puisse :
- Envoyer les requêtes de login
- Recevoir les cookies de refresh token
- Faire des requêtes cross-origin

### Configuration CORS dans `.env`

```bash
# Format 1: Liste séparée par virgules
CORS_ORIGINS=http://localhost:3000,http://localhost:80

# Format 2: JSON array (recommandé pour plusieurs origines)
CORS_ORIGINS=["http://localhost:3000","http://localhost:80","https://votredomaine.com"]
```

### Vérification CORS

Le middleware CORS doit être configuré dans `app/main.py` :

```python
# Vérifiez que cette configuration existe
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,  # IMPORTANT pour les cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## ✅ Vérification de la Configuration

### Script de Vérification

Créez un script `verify_mfa_config.py` :

```python
#!/usr/bin/env python3
"""Script de vérification de la configuration MFA"""

import sys
from app.core.config import settings
from app.core.database import SessionLocal, engine
from sqlalchemy import inspect

def check_env_vars():
    """Vérifie les variables d'environnement"""
    print("🔍 Vérification des variables d'environnement...")
    
    required_vars = [
        'SECRET_KEY',
        'DATABASE_URL',
        'PROJECT_NAME',
    ]
    
    optional_vars = [
        'MFA_SESSION_EXPIRE_MINUTES',
        'ACCESS_TOKEN_EXPIRE_MINUTES',
        'REFRESH_TOKEN_EXPIRE_DAYS',
        'REFRESH_TOKEN_SECURE',
        'REFRESH_TOKEN_SAMESITE',
    ]
    
    errors = []
    warnings = []
    
    for var in required_vars:
        value = getattr(settings, var, None)
        if not value:
            errors.append(f"❌ {var} est manquant")
        else:
            print(f"  ✓ {var}: {'***' if 'SECRET' in var or 'PASSWORD' in var else value}")
    
    for var in optional_vars:
        value = getattr(settings, var, None)
        if value is None:
            warnings.append(f"⚠️  {var} utilise la valeur par défaut")
        else:
            print(f"  ✓ {var}: {value}")
    
    return errors, warnings

def check_dependencies():
    """Vérifie les dépendances Python"""
    print("\n🔍 Vérification des dépendances...")
    
    dependencies = {
        'pyotp': 'pyotp',
        'qrcode': 'qrcode',
    }
    
    errors = []
    
    for module_name, package_name in dependencies.items():
        try:
            __import__(module_name)
            print(f"  ✓ {package_name} est installé")
        except ImportError:
            errors.append(f"❌ {package_name} n'est pas installé")
    
    return errors

def check_database():
    """Vérifie la structure de la base de données"""
    print("\n🔍 Vérification de la base de données...")
    
    errors = []
    
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # Vérifier la table users
        if 'users' not in tables:
            errors.append("❌ Table 'users' n'existe pas")
        else:
            print("  ✓ Table 'users' existe")
            columns = [col['name'] for col in inspector.get_columns('users')]
            required_columns = ['is_mfa_enabled', 'mfa_secret', 'mfa_temp_secret']
            for col in required_columns:
                if col in columns:
                    print(f"    ✓ Colonne '{col}' existe")
                else:
                    errors.append(f"❌ Colonne '{col}' manquante dans 'users'")
        
        # Vérifier la table mfa_sessions
        if 'mfa_sessions' not in tables:
            errors.append("❌ Table 'mfa_sessions' n'existe pas")
        else:
            print("  ✓ Table 'mfa_sessions' existe")
    
    except Exception as e:
        errors.append(f"❌ Erreur de connexion à la base de données: {str(e)}")
    
    return errors

def main():
    """Fonction principale"""
    print("=" * 60)
    print("VÉRIFICATION DE LA CONFIGURATION MFA")
    print("=" * 60)
    
    all_errors = []
    all_warnings = []
    
    # Vérifier les variables d'environnement
    errors, warnings = check_env_vars()
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    # Vérifier les dépendances
    errors = check_dependencies()
    all_errors.extend(errors)
    
    # Vérifier la base de données
    errors = check_database()
    all_errors.extend(errors)
    
    # Résumé
    print("\n" + "=" * 60)
    print("RÉSUMÉ")
    print("=" * 60)
    
    if all_warnings:
        print(f"\n⚠️  {len(all_warnings)} avertissement(s):")
        for warning in all_warnings:
            print(f"  {warning}")
    
    if all_errors:
        print(f"\n❌ {len(all_errors)} erreur(s) trouvée(s):")
        for error in all_errors:
            print(f"  {error}")
        print("\n⚠️  Le MFA ne fonctionnera pas correctement avec ces erreurs.")
        sys.exit(1)
    else:
        print("\n✅ Toutes les vérifications sont passées !")
        print("✅ Le MFA est correctement configuré.")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

### Exécution de la Vérification

```bash
# Exécuter le script de vérification
python verify_mfa_config.py

# Ou dans Docker
docker-compose exec backend python verify_mfa_config.py
```

---

## 🚀 Checklist de Configuration

Avant de tester le MFA, vérifiez que :

- [ ] Le fichier `.env` existe et contient toutes les variables nécessaires
- [ ] `SECRET_KEY` est défini et sécurisé
- [ ] `DATABASE_URL` est correctement configuré
- [ ] `PROJECT_NAME` est défini (utilisé dans les QR codes)
- [ ] `MFA_SESSION_EXPIRE_MINUTES` est configuré (défaut: 10)
- [ ] Les dépendances `pyotp` et `qrcode` sont installées
- [ ] Les migrations de base de données sont appliquées
- [ ] Les tables `users` et `mfa_sessions` existent
- [ ] CORS est configuré pour autoriser votre frontend
- [ ] `REFRESH_TOKEN_SECURE` est `false` en dev, `true` en prod
- [ ] Le serveur backend est démarré et accessible

---

## 🔧 Configuration Avancée

### Personnalisation du Nom du Projet

Le `PROJECT_NAME` est utilisé dans l'URL `otpauth://` pour identifier votre application dans les apps d'authentification :

```bash
PROJECT_NAME=FPI-CONNECT
```

Cela génère des URLs comme :
```
otpauth://totp/FPI-CONNECT:user@example.com?secret=...&issuer=FPI-CONNECT
```

### Ajustement de l'Expiration des Sessions MFA

```bash
# Session très courte (5 minutes) - Plus sécurisé
MFA_SESSION_EXPIRE_MINUTES=5

# Session standard (10 minutes) - Recommandé
MFA_SESSION_EXPIRE_MINUTES=10

# Session longue (30 minutes) - Moins sécurisé
MFA_SESSION_EXPIRE_MINUTES=30
```

### Configuration pour Plusieurs Environnements

Créez des fichiers `.env` séparés :

```bash
# .env.development
REFRESH_TOKEN_SECURE=false
MFA_SESSION_EXPIRE_MINUTES=10

# .env.production
REFRESH_TOKEN_SECURE=true
MFA_SESSION_EXPIRE_MINUTES=5
CORS_ORIGINS=["https://votredomaine.com"]
```

---

## 📝 Notes Importantes

1. **Sécurité en Production** :
   - `REFRESH_TOKEN_SECURE=true` est **OBLIGATOIRE** en production
   - Utilisez HTTPS pour toutes les communications
   - Ne commitez jamais le fichier `.env` dans Git

2. **Performance** :
   - Les sessions MFA sont automatiquement nettoyées après expiration
   - Les sessions consommées sont marquées mais pas supprimées immédiatement
   - Considérez un job de nettoyage périodique pour les anciennes sessions

3. **Compatibilité** :
   - Le MFA fonctionne avec toutes les apps TOTP standard (Google Authenticator, Authy, Microsoft Authenticator, etc.)
   - Les codes TOTP suivent le standard RFC 6238

---

## 🆘 Dépannage

### Erreur: "Module 'pyotp' not found"
```bash
pip install pyotp==2.9.0
```

### Erreur: "Table 'mfa_sessions' does not exist"
```bash
alembic upgrade head
```

### Erreur: "Column 'is_mfa_enabled' does not exist"
```bash
alembic upgrade head
```

### Les cookies ne sont pas envoyés
- Vérifiez `REFRESH_TOKEN_SECURE=false` en développement
- Vérifiez que CORS `allow_credentials=True`
- Vérifiez que le frontend envoie `credentials: 'include'` dans les requêtes

---

## ✅ Configuration Complète

Une fois toutes ces configurations effectuées, vous pouvez suivre le guide de test dans `MFA_TESTING_GUIDE.md` pour tester le MFA.

Bon test ! 🚀
