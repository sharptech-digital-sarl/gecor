# Guide de Dépannage : Activation MFA ne fonctionne pas

Ce guide vous aide à résoudre les problèmes d'activation MFA en localhost.

## 🔍 Problèmes Courants

### 1. Erreur "Invalid verification code"

**Causes possibles :**
- Le code TOTP utilisé n'est pas le bon (mauvais secret)
- Le code a expiré (change toutes les 30 secondes)
- Problème de synchronisation temporelle
- Le secret n'a pas été correctement sauvegardé après `/mfa/setup`

**Solutions :**

#### A. Vérifier que le secret est correctement sauvegardé

1. **Après `/mfa/setup`**, vérifiez que le secret est dans la base :
```sql
-- Dans pgAdmin ou via Docker
SELECT id, username, mfa_temp_secret, is_mfa_enabled 
FROM users 
WHERE username = 'votre_username';
```

Le champ `mfa_temp_secret` doit contenir le secret retourné par `/mfa/setup`.

#### B. Générer le code avec le bon secret

Utilisez le script helper pour générer le code :

```bash
# Utilisez le secret EXACT retourné par /mfa/setup
python test_mfa_helper.py <secret_du_setup>
```

**Important** : Utilisez le secret retourné par `/mfa/setup`, pas celui de votre app d'authentification.

#### C. Vérifier la synchronisation temporelle

Les codes TOTP dépendent de l'heure système. Vérifiez que :
- L'heure de votre système est correcte
- L'heure du serveur Docker est correcte

```bash
# Vérifier l'heure dans Docker
docker-compose exec backend date
```

#### D. Utiliser un code récent

Les codes TOTP changent toutes les 30 secondes. Assurez-vous d'utiliser un code généré dans les 30 dernières secondes.

### 2. Erreur "No MFA setup in progress"

**Cause :** Le `mfa_temp_secret` n'existe pas ou a été supprimé.

**Solutions :**

1. **Refaire le setup** :
   - Appelez `/mfa/setup` à nouveau
   - Utilisez le nouveau secret pour générer le code

2. **Vérifier dans la base** :
```sql
SELECT mfa_temp_secret FROM users WHERE username = 'votre_username';
```

Si `mfa_temp_secret` est NULL, refaites `/mfa/setup`.

### 3. Erreur "MFA already enabled"

**Cause :** L'utilisateur a déjà le MFA activé.

**Solution :** Désactivez d'abord le MFA :
```bash
POST /api/v1/auth/mfa/disable
Body: {"code": "code_totp_actuel"}
```

## 🛠️ Test Pas à Pas

### Étape 1 : Vérifier le Setup

```bash
# 1. Login
POST /api/v1/auth/login
Body: {"username": "admin", "password": "..."}
→ Sauvegardez l'access_token

# 2. Setup MFA
POST /api/v1/auth/mfa/setup
Headers: Authorization: Bearer <access_token>
→ Réponse: {"secret": "JBSWY3DPEHPK3PXP", "otpauth_url": "..."}
→ ⚠️ SAUVEGARDEZ LE SECRET
```

### Étape 2 : Générer le Code TOTP

**Option A : Utiliser le script helper**
```bash
python test_mfa_helper.py JBSWY3DPEHPK3PXP
```

**Option B : Utiliser Python directement**
```python
import pyotp
secret = "JBSWY3DPEHPK3PXP"  # Le secret de /mfa/setup
totp = pyotp.TOTP(secret)
code = totp.now()
print(f"Code actuel: {code}")
```

**Option C : Utiliser Google Authenticator**
1. Scannez le QR code généré à partir de `otpauth_url`
2. Utilisez le code affiché dans l'app

### Étape 3 : Activer avec le Code

```bash
# Utilisez le code généré IMMÉDIATEMENT (dans les 30 secondes)
POST /api/v1/auth/mfa/activate
Headers: Authorization: Bearer <access_token>
Body: {"code": "123456"}  # Le code généré à l'étape 2
```

## 🔧 Amélioration du Code pour Debugging

Ajoutons plus de logging pour diagnostiquer :

```python
# Dans app/api/v1/auth.py, améliorer mfa_activate avec logging
import logging
logger = logging.getLogger(__name__)

@router.post("/mfa/activate")
async def mfa_activate(
    payload: MFAActivateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirm MFA enrollment with the first TOTP code"""
    logger.info(f"MFA activation attempt for user {current_user.id}")
    
    if current_user.is_mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA already enabled"
        )

    if not current_user.mfa_temp_secret:
        logger.warning(f"No mfa_temp_secret for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No MFA setup in progress"
        )

    # Rafraîchir l'utilisateur depuis la DB pour s'assurer d'avoir le dernier secret
    db.refresh(current_user)
    
    totp = pyotp.TOTP(current_user.mfa_temp_secret)
    
    # Générer le code attendu pour debugging (en dev seulement)
    expected_code = totp.now()
    logger.debug(f"Expected code: {expected_code}, Received: {payload.code}")
    
    # Vérifier avec une fenêtre plus large pour le premier code
    if not totp.verify(payload.code, valid_window=2):
        logger.warning(f"Invalid code for user {current_user.id}. Expected: {expected_code}, Got: {payload.code}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. Current code should be: {expected_code}"
        )

    current_user.mfa_secret = current_user.mfa_temp_secret
    current_user.mfa_temp_secret = None
    current_user.is_mfa_enabled = True
    db.commit()
    
    logger.info(f"MFA enabled successfully for user {current_user.id}")
    return {"message": "MFA enabled"}
```

## 📋 Checklist de Vérification

Avant d'activer le MFA, vérifiez :

- [ ] Le secret de `/mfa/setup` est sauvegardé
- [ ] Le code TOTP est généré avec le **même secret** que celui de `/mfa/setup`
- [ ] Le code est utilisé dans les **30 secondes** après génération
- [ ] L'heure système est correcte (serveur et client)
- [ ] Le `mfa_temp_secret` existe dans la base de données
- [ ] Vous utilisez le bon `access_token` (celui obtenu après login)

## 🧪 Test Complet avec Script

Créez un script de test complet :

```python
# test_mfa_activation.py
import requests
import pyotp
import time

BASE_URL = "http://localhost:8000/api/v1/auth"

# 1. Login
login_response = requests.post(
    f"{BASE_URL}/login",
    json={"username": "admin", "password": "votre_mot_de_passe"}
)
access_token = login_response.json()["access_token"]
print(f"✓ Login réussi, token: {access_token[:20]}...")

# 2. Setup MFA
setup_response = requests.post(
    f"{BASE_URL}/mfa/setup",
    headers={"Authorization": f"Bearer {access_token}"}
)
setup_data = setup_response.json()
secret = setup_data["secret"]
print(f"✓ Setup réussi, secret: {secret}")

# 3. Générer le code TOTP
totp = pyotp.TOTP(secret)
code = totp.now()
print(f"✓ Code généré: {code}")

# 4. Activer MFA (dans les 5 secondes)
time.sleep(1)  # Attendre 1 seconde
activate_response = requests.post(
    f"{BASE_URL}/mfa/activate",
    headers={"Authorization": f"Bearer {access_token}"},
    json={"code": code}
)
print(f"✓ Activation: {activate_response.json()}")

# 5. Vérifier que MFA est activé
me_response = requests.get(
    f"{BASE_URL}/me",
    headers={"Authorization": f"Bearer {access_token}"}
)
user_data = me_response.json()
print(f"✓ MFA activé: {user_data.get('is_mfa_enabled', False)}")
```

## 🆘 Solutions Spécifiques

### Problème : Le code change avant que je puisse l'utiliser

**Solution :** Utilisez le script Python pour générer et utiliser le code automatiquement, ou augmentez `valid_window` temporairement.

### Problème : Le secret dans la base est différent

**Solution :** Vérifiez que vous n'avez pas plusieurs sessions ouvertes. Fermez toutes les sessions et refaites `/mfa/setup`.

### Problème : Erreur de synchronisation temporelle

**Solution :** 
```bash
# Synchroniser l'heure dans Docker
docker-compose exec backend ntpdate -s time.nist.gov
```

Ou vérifiez que l'heure système est correcte.

## 📝 Notes Importantes

1. **Le secret doit être identique** : Le secret utilisé pour générer le code doit être **exactement** celui retourné par `/mfa/setup`
2. **Fenêtre de validité** : Le code est valide pendant 30 secondes, avec une tolérance de ±30 secondes (`valid_window=1`)
3. **Un seul setup à la fois** : Ne faites pas plusieurs `/mfa/setup` en parallèle, cela peut écraser le `mfa_temp_secret`
4. **Ordre des opérations** : Setup → Générer code → Activer (rapidement)

---

Si le problème persiste, partagez :
- Les logs du serveur
- Le secret utilisé
- Le code TOTP utilisé
- L'heure système
