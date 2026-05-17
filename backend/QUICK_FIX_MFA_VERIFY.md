# Solution Rapide : Erreur 401 lors de la Vérification MFA

## 🔍 Problème

Vous obtenez une erreur `401 Unauthorized` lors de l'appel à `/api/v1/auth/mfa/verify` même avec un code OTP valide de Google Authenticator.

## ✅ Solutions Appliquées

1. **Fenêtre de validité augmentée** : De ±30 secondes à ±60 secondes
2. **Logging amélioré** : Les logs montrent maintenant le code reçu vs le code attendu
3. **Rafraîchissement de l'utilisateur** : S'assure d'utiliser le dernier secret en base

## 🧪 Diagnostic

### Étape 1 : Vérifier le Secret

Exécutez le script de diagnostic pour vérifier que le secret stocké correspond à celui dans Google Authenticator :

```bash
python diagnose_mfa.py admin
```

Cela affichera :
- Le secret stocké en base
- Le code TOTP actuel généré avec ce secret
- L'URL de provisioning

### Étape 2 : Vérifier un Code Spécifique

Si vous avez un code de Google Authenticator, testez-le :

```bash
python diagnose_mfa.py admin 123456
```

Cela vous dira si le code correspond au secret stocké.

## 🔧 Causes Possibles et Solutions

### 1. Secret Incorrect dans Google Authenticator

**Symptôme** : Le code généré ne correspond jamais

**Solution** :
1. Vérifiez le secret stocké en base avec `diagnose_mfa.py`
2. Supprimez l'entrée "FPI-CONNECT" dans Google Authenticator
3. Reconfigurez MFA :
   ```bash
   # 1. Désactiver MFA (si possible)
   curl -X POST http://localhost:8000/api/v1/auth/mfa/disable \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"code": "CODE_ACTUEL"}'
   
   # 2. Refaire le setup
   curl -X POST http://localhost:8000/api/v1/auth/mfa/setup \
     -H "Authorization: Bearer <token>"
   
   # 3. Scanner le NOUVEAU QR code
   # 4. Activer avec le nouveau code
   ```

### 2. Problème de Synchronisation d'Heure

**Symptôme** : Les codes fonctionnent parfois mais pas toujours

**Solution** :
- Vérifiez que l'heure système de votre serveur est correcte
- Vérifiez que l'heure de votre téléphone est correcte
- Les codes TOTP dépendent de l'heure système

### 3. Code Entré Trop Tard

**Symptôme** : Le code change pendant que vous l'entrez

**Solution** :
- Entrez le code rapidement (dans les 30 secondes)
- La fenêtre de validité est maintenant de ±60 secondes (amélioration appliquée)

### 4. MFA Session Expirée

**Symptôme** : Erreur "Invalid or expired MFA session"

**Solution** :
- Les sessions MFA expirent après 10 minutes
- Refaites un login pour obtenir un nouveau `mfa_session_id`

## 📝 Test Complet

Utilisez le script de test pour vérifier tout le flux :

```bash
# Si MFA est déjà activé
python test_mfa_verify.py admin votre_mot_de_passe

# Ou avec le secret explicitement
python test_mfa_verify.py admin votre_mot_de_passe KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL
```

## 🔍 Vérification des Logs

Après les modifications, les logs du backend afficheront maintenant :

```
WARNING: Invalid MFA code for user 1 (username: admin). 
         Received: 123456, Expected (current): 654321, 
         Session ID: 550e8400-e29b-41d4-a716-446655440000
```

Cela vous permet de voir :
- Le code que vous avez entré
- Le code attendu par le serveur
- L'ID de session utilisé

## 💡 Conseils

1. **Utilisez le script de diagnostic** : `diagnose_mfa.py` pour vérifier que tout correspond
2. **Vérifiez les logs** : Les nouveaux logs sont plus détaillés
3. **Testez avec le script automatique** : `test_mfa_verify.py` pour éviter les erreurs de saisie
4. **Synchronisez l'heure** : Assurez-vous que l'heure système est correcte

## 🚨 Problème : Secret Ne Correspond Pas

**Symptôme** : Les logs montrent :
```
Invalid MFA code for user ... Received: 801306, Expected (current): 552694
```

**Cause** : Le secret dans Google Authenticator ne correspond pas au secret stocké en base.

### Solution Rapide : Désactiver via SQL puis Reconfigurer

Si vous ne pouvez pas vous connecter (car MFA est activé), désactivez directement via SQL :

```sql
-- Se connecter à la base de données
-- Via Docker:
docker-compose exec db psql -U fpi-admin -d fpi_connect

-- Désactiver MFA pour l'utilisateur
UPDATE users 
SET is_mfa_enabled = false, 
    mfa_secret = NULL, 
    mfa_temp_secret = NULL 
WHERE username = 'admin';
```

Puis refaites le setup MFA normalement :
1. Login → obtenir token
2. `/mfa/setup` → obtenir nouveau secret
3. Scanner le NOUVEAU QR code dans Google Authenticator
4. `/mfa/activate` → activer avec le nouveau code

### Solution Automatique : Script de Correction

Utilisez le script de correction (nécessite un token d'accès valide) :

```bash
python fix_mfa_secret_mismatch.py admin votre_mot_de_passe
```

Ce script :
- Désactive le MFA (si possible)
- Génère un nouveau secret
- Vous guide pour reconfigurer Google Authenticator
- Réactive le MFA avec le nouveau secret

## 🚨 Si Rien Ne Fonctionne

1. Vérifiez que le secret en base correspond à celui dans Google Authenticator :
   ```bash
   python diagnose_mfa.py admin
   ```

2. Vérifiez les logs du backend pour voir le code attendu

3. Testez avec le script automatique :
   ```bash
   python test_mfa_verify.py admin votre_mot_de_passe
   ```

4. Si nécessaire, reconfigurez complètement le MFA (désactiver → setup → activer)

---

**Note** : Les modifications apportées au code augmentent la tolérance temporelle et améliorent le logging. Redémarrez le backend pour que les changements prennent effet.
