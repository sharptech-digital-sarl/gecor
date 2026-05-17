# Guide de Test MFA (Multi-Factor Authentication)

Ce guide vous explique comment tester la fonctionnalité MFA avec TOTP (Time-based One-Time Password).

## Prérequis

1. Un utilisateur créé dans la base de données
2. Un outil pour générer des codes TOTP (Google Authenticator, Authy, ou un générateur en ligne)
3. Un client HTTP (Postman, curl, ou votre application frontend)

## Étapes de Test

### Étape 1 : Se connecter pour obtenir un token d'accès

**Endpoint:** `POST /api/v1/auth/login`

**Format JSON:**
```json
{
  "username": "admin",
  "password": "votre_mot_de_passe"
}
```

**Format Form Data:**
```
username=admin
password=votre_mot_de_passe
```

**Réponse attendue:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "mfa_required": false,
  "mfa_session_id": null
}
```

**Note:** Sauvegardez le `access_token` pour les prochaines étapes.

---

### Étape 2 : Configurer le MFA (Setup)

**Endpoint:** `POST /api/v1/auth/mfa/setup`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Réponse attendue:**
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "otpauth_url": "otpauth://totp/FPI%20Connect:admin@example.com?secret=JBSWY3DPEHPK3PXP&issuer=FPI%20Connect"
}
```

**Actions à faire:**
1. Copiez le `secret` ou l'`otpauth_url`
2. Utilisez un générateur de QR code en ligne (par exemple: https://www.qr-code-generator.com/)
3. Scannez le QR code avec Google Authenticator, Authy, ou une autre app TOTP
4. OU entrez manuellement le `secret` dans votre app d'authentification

**Alternative:** Vous pouvez aussi générer un QR code côté frontend en utilisant la bibliothèque `qrcode` (déjà dans requirements.txt).

---

### Étape 3 : Activer le MFA (Activation)

**Endpoint:** `POST /api/v1/auth/mfa/activate`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body:**
```json
{
  "code": "123456"
}
```

**Note:** `code` est le code à 6 chiffres généré par votre app d'authentification (Google Authenticator, etc.)

**Réponse attendue:**
```json
{
  "message": "MFA enabled"
}
```

**Si le code est incorrect:**
```json
{
  "detail": "Invalid verification code"
}
```

**Important:** Le code TOTP change toutes les 30 secondes. Assurez-vous d'utiliser un code récent.

---

### Étape 4 : Tester le Login avec MFA activé

Maintenant que le MFA est activé, testons le flux de login complet.

#### 4.1 : Premier login (retourne mfa_session_id)

**Endpoint:** `POST /api/v1/auth/login`

**Body (JSON):**
```json
{
  "username": "admin",
  "password": "votre_mot_de_passe"
}
```

**Réponse attendue:**
```json
{
  "access_token": null,
  "token_type": null,
  "mfa_required": true,
  "mfa_session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Note:** 
- `mfa_required` est `true`
- `mfa_session_id` est fourni pour l'étape suivante
- `access_token` est `null` car le MFA n'est pas encore vérifié

#### 4.2 : Vérifier le code MFA

**Endpoint:** `POST /api/v1/auth/mfa/verify`

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "mfa_session_id": "550e8400-e29b-41d4-a716-446655440000",
  "code": "123456"
}
```

**Note:** 
- `mfa_session_id` vient de l'étape précédente
- `code` est le code à 6 chiffres actuel de votre app d'authentification

**Réponse attendue:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Important:** 
- Le `mfa_session_id` expire après 10 minutes (configurable via `MFA_SESSION_EXPIRE_MINUTES`)
- Le cookie `refresh_token` est également défini automatiquement

---

### Étape 5 : Désactiver le MFA (Optionnel)

**Endpoint:** `POST /api/v1/auth/mfa/disable`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body:**
```json
{
  "code": "123456"
}
```

**Réponse attendue:**
```json
{
  "message": "MFA disabled"
}
```

---

## Exemples avec cURL

### 1. Login initial
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "votre_mot_de_passe"}'
```

### 2. Setup MFA
```bash
curl -X POST http://localhost:8000/api/v1/auth/mfa/setup \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json"
```

### 3. Activer MFA
```bash
curl -X POST http://localhost:8000/api/v1/auth/mfa/activate \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"code": "123456"}'
```

### 4. Login avec MFA (étape 1)
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "votre_mot_de_passe"}'
```

### 5. Vérifier MFA (étape 2)
```bash
curl -X POST http://localhost:8000/api/v1/auth/mfa/verify \
  -H "Content-Type: application/json" \
  -d '{"mfa_session_id": "<mfa_session_id>", "code": "123456"}'
```

---

## 🧪 Scripts de Test Automatiques

### Script 1 : Test d'Activation MFA

Teste le flux complet d'activation MFA (setup + activation) :

```bash
python test_mfa_activation.py admin votre_mot_de_passe
```

Ce script :
- Se connecte
- Fait le setup MFA
- Génère automatiquement le code TOTP
- Active le MFA
- Vérifie que l'activation a réussi

### Script 2 : Test de Vérification MFA

Teste l'étape `/mfa/verify` (login avec MFA activé) :

```bash
# Avec secret fourni
python test_mfa_verify.py admin votre_mot_de_passe KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL

# Sans secret (tentative de récupération depuis DB)
python test_mfa_verify.py admin votre_mot_de_passe
```

Ce script :
- Fait un login (obtient mfa_session_id)
- Génère le code TOTP avec le secret MFA
- Appelle /mfa/verify
- Vérifie que les tokens sont obtenus

### Script 3 : Test Complet du Flux MFA

Teste tout le flux de bout en bout (setup + activation + login + vérification) :

```bash
# Test complet
python test_mfa_complete.py admin votre_mot_de_passe

# Test uniquement vérification (si MFA déjà activé)
python test_mfa_complete.py admin votre_mot_de_passe --skip-activation
```

### Script Helper : Générateur de Code TOTP

Génère et vérifie des codes TOTP :

```bash
# Générer le code actuel
python test_mfa_helper.py <secret>

# Vérifier un code
python test_mfa_helper.py <secret> verify <code>

# Générer l'URL pour QR code
python test_mfa_helper.py <secret> url <email>
```

## Générateur de Code TOTP pour Test

Si vous n'avez pas d'app d'authentification, vous pouvez utiliser Python pour générer des codes:

```python
import pyotp
import time

# Utilisez le secret obtenu de /mfa/setup
secret = "JBSWY3DPEHPK3PXP"
totp = pyotp.TOTP(secret)

# Générer le code actuel
current_code = totp.now()
print(f"Code TOTP actuel: {current_code}")

# Le code change toutes les 30 secondes
# Vous pouvez aussi vérifier un code:
code_to_verify = "123456"
is_valid = totp.verify(code_to_verify, valid_window=1)
print(f"Code valide: {is_valid}")
```

---

## Dépannage

### Erreur: "MFA already enabled"
- L'utilisateur a déjà le MFA activé
- Solution: Désactivez d'abord le MFA avec `/mfa/disable`

### Erreur: "Invalid verification code"
- Le code TOTP est incorrect ou expiré
- Solution: Utilisez un code récent (généré dans les 30 dernières secondes)
- Note: `valid_window=1` permet une tolérance de ±30 secondes

### Erreur: "Invalid or expired MFA session"
- Le `mfa_session_id` a expiré (10 minutes)
- Solution: Refaites un login pour obtenir un nouveau `mfa_session_id`

### Erreur: "No MFA setup in progress"
- Vous essayez d'activer le MFA sans avoir fait `/mfa/setup` d'abord
- Solution: Appelez `/mfa/setup` avant `/mfa/activate`

---

## Notes Importantes

1. **Sécurité:** Le `secret` ne doit jamais être exposé dans les logs ou les réponses en production
2. **Expiration:** Les sessions MFA expirent après 10 minutes (configurable)
3. **Tolérance:** Les codes TOTP ont une fenêtre de validité de ±30 secondes
4. **Refresh Tokens:** Les refresh tokens sont automatiquement créés après une vérification MFA réussie
5. **Cookies:** Le refresh token est stocké dans un cookie HTTP-only sécurisé

---

## Flux Complet Résumé

```
1. Login → Obtenir access_token
2. /mfa/setup → Obtenir secret et otpauth_url
3. Scanner QR code ou entrer secret dans app d'authentification
4. /mfa/activate → Activer MFA avec un code TOTP
5. Login → Retourne mfa_session_id (pas d'access_token)
6. /mfa/verify → Vérifier code TOTP et obtenir access_token + refresh_token
```

---

## Test avec Postman

1. Créez une collection "MFA Testing"
2. Créez des requêtes pour chaque endpoint
3. Utilisez les variables d'environnement pour stocker:
   - `access_token`
   - `mfa_session_id`
   - `secret`
4. Configurez les tests automatiques pour vérifier les réponses

---

Bon test ! 🚀
