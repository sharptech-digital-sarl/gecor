# Scripts de Test MFA

Ce document décrit tous les scripts disponibles pour tester le MFA.

## 📋 Scripts Disponibles

### 1. `test_mfa_helper.py` - Générateur de Codes TOTP

**Usage :**
```bash
# Générer le code actuel
python test_mfa_helper.py <secret>

# Vérifier un code
python test_mfa_helper.py <secret> verify <code>

# Générer l'URL pour QR code
python test_mfa_helper.py <secret> url <email>
```

**Exemple :**
```bash
python test_mfa_helper.py KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL
# Affiche: Code TOTP actuel: 123456
```

---

### 2. `test_mfa_activation.py` - Test d'Activation MFA

**Usage :**
```bash
python test_mfa_activation.py <username> <password>
```

**Ce que fait le script :**
1. Se connecte et obtient un token
2. Fait le setup MFA (`/mfa/setup`)
3. Génère automatiquement le code TOTP
4. Active le MFA (`/mfa/activate`)
5. Vérifie que MFA est activé
6. Teste le login avec MFA (obtient `mfa_session_id`)

**Exemple :**
```bash
python test_mfa_activation.py admin Parisi@25
```

**Résultat attendu :**
```
✅ TEST COMPLET RÉUSSI!
  - MFA activé avec succès
  - Login avec MFA fonctionne
```

---

### 3. `test_mfa_verify.py` - Test de Vérification MFA

**Usage :**
```bash
# Avec secret fourni (recommandé)
python test_mfa_verify.py <username> <password> <mfa_secret>

# Sans secret (tentative de récupération depuis DB)
python test_mfa_verify.py <username> <password>
```

**Ce que fait le script :**
1. Fait un login (obtient `mfa_session_id`)
2. Récupère ou utilise le secret MFA fourni
3. Génère le code TOTP
4. Appelle `/mfa/verify`
5. Vérifie que les tokens sont obtenus
6. Teste que le token fonctionne

**Exemple :**
```bash
python test_mfa_verify.py admin Parisi@25 KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL
```

**Résultat attendu :**
```
✅ TEST COMPLET RÉUSSI!
  - Login avec MFA fonctionne
  - Vérification MFA réussie
  - Access token obtenu et valide
  - Refresh token cookie défini
```

---

### 4. `test_mfa_complete.py` - Test Complet du Flux MFA

**Usage :**
```bash
# Test complet (setup + activation + vérification)
python test_mfa_complete.py <username> <password>

# Test uniquement vérification (si MFA déjà activé)
python test_mfa_complete.py <username> <password> --skip-activation
```

**Ce que fait le script :**
1. Se connecte
2. Si MFA non activé : Setup → Activation
3. Login avec MFA (obtient `mfa_session_id`)
4. Génère le code TOTP
5. Vérifie MFA (`/mfa/verify`)
6. Vérifie que les tokens fonctionnent

**Exemple :**
```bash
# Test complet
python test_mfa_complete.py admin Parisi@25

# Test vérification uniquement
python test_mfa_complete.py admin Parisi@25 --skip-activation
```

**Résultat attendu :**
```
✅ FLUX MFA COMPLET RÉUSSI!
  ✓ Setup MFA
  ✓ Activation MFA
  ✓ Login avec MFA
  ✓ Vérification MFA
  ✓ Tokens obtenus et valides
```

---

## 🎯 Quel Script Utiliser ?

| Scénario | Script Recommandé |
|----------|-------------------|
| **Premier test MFA** | `test_mfa_complete.py` |
| **Tester uniquement l'activation** | `test_mfa_activation.py` |
| **Tester uniquement la vérification** | `test_mfa_verify.py` |
| **Générer un code TOTP** | `test_mfa_helper.py` |
| **Vérifier un code TOTP** | `test_mfa_helper.py <secret> verify <code>` |

---

## 📝 Exemples d'Utilisation

### Scénario 1 : Premier Test Complet

```bash
# Teste tout le flux de bout en bout
python test_mfa_complete.py admin Parisi@25
```

### Scénario 2 : MFA Déjà Activé, Tester la Vérification

```bash
# Utilisez le secret de l'activation
python test_mfa_verify.py admin Parisi@25 KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL
```

### Scénario 3 : Générer un Code TOTP Rapidement

```bash
# Utilisez le secret de /mfa/setup
python test_mfa_helper.py KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL
```

### Scénario 4 : Vérifier un Code Avant de l'Utiliser

```bash
python test_mfa_helper.py KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL verify 123456
```

---

## 🔍 Récupération du Secret MFA

Si vous avez oublié le secret MFA, vous pouvez le récupérer depuis la base de données :

### Via pgAdmin (SQL)

```sql
SELECT username, mfa_secret, is_mfa_enabled 
FROM users 
WHERE username = 'admin';
```

### Via Docker

```bash
docker-compose exec db psql -U fpi-admin -d fpi_connect -c "SELECT username, mfa_secret FROM users WHERE username = 'admin';"
```

### Via Python (dans le script)

Les scripts `test_mfa_verify.py` et `test_mfa_complete.py` tentent automatiquement de récupérer le secret depuis la base de données si vous ne le fournissez pas.

---

## 🆘 Dépannage

### Erreur: "Module 'app' not found"

Les scripts doivent être exécutés depuis le répertoire `backend/` :

```bash
cd c:\projects\fpi-connect\backend
python test_mfa_verify.py admin password secret
```

### Erreur: "Connection refused"

Assurez-vous que le serveur backend est démarré :

```bash
docker-compose up -d
# Ou
uvicorn app.main:app --reload
```

### Erreur: "Invalid verification code"

1. Vérifiez que vous utilisez le **bon secret** (celui de l'activation)
2. Utilisez un code **récent** (généré dans les 30 dernières secondes)
3. Vérifiez l'heure système (les codes TOTP dépendent de l'heure)

---

## 📚 Documentation Complète

- **Guide de test** : `MFA_TESTING_GUIDE.md`
- **Guide de configuration** : `MFA_CONFIGURATION_GUIDE.md`
- **Dépannage activation** : `MFA_ACTIVATION_TROUBLESHOOT.md`
- **Solution rapide** : `QUICK_FIX_MFA_ACTIVATION.md`

---

Bon test ! 🚀
