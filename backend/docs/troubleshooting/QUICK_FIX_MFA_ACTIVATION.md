# Solution Rapide : Activation MFA ne fonctionne pas

## 🔴 Problème

L'activation MFA avec le code OTP ne fonctionne pas en localhost, vous recevez "Invalid verification code".

## ✅ Solution Rapide

### Méthode 1 : Utiliser le Script de Test Automatique (Recommandé)

```bash
# Teste tout le flux automatiquement
python test_mfa_activation.py admin votre_mot_de_passe
```

Ce script :
1. Se connecte
2. Fait le setup MFA
3. Génère automatiquement le code TOTP
4. Active le MFA
5. Vérifie que tout fonctionne

### Méthode 2 : Test Manuel avec Script Helper

```bash
# 1. Login et obtenir token
POST /api/v1/auth/login
Body: {"username": "admin", "password": "..."}
→ Sauvegardez access_token

# 2. Setup MFA
POST /api/v1/auth/mfa/setup
Headers: Authorization: Bearer <access_token>
→ Réponse: {"secret": "JBSWY3DPEHPK3PXP", "otpauth_url": "..."}
→ ⚠️ SAUVEGARDEZ LE SECRET

# 3. Générer le code avec le script helper
python test_mfa_helper.py JBSWY3DPEHPK3PXP
→ Affiche le code actuel

# 4. Activer IMMÉDIATEMENT (dans les 30 secondes)
POST /api/v1/auth/mfa/activate
Headers: Authorization: Bearer <access_token>
Body: {"code": "123456"}  # Le code du script helper
```

## 🔍 Vérifications Importantes

### 1. Utiliser le BON Secret

**❌ MAUVAIS** : Utiliser un secret d'une app d'authentification précédente
**✅ BON** : Utiliser le secret retourné par `/mfa/setup` (celui que vous venez d'obtenir)

### 2. Code Récent

Les codes TOTP changent toutes les 30 secondes. Utilisez un code généré dans les 30 dernières secondes.

### 3. Vérifier le Secret dans la Base

Si vous avez des doutes, vérifiez que le secret est bien sauvegardé :

```sql
-- Dans pgAdmin ou via Docker
SELECT username, mfa_temp_secret, is_mfa_enabled 
FROM users 
WHERE username = 'admin';
```

Le `mfa_temp_secret` doit contenir le secret retourné par `/mfa/setup`.

### 4. Ne pas Faire Plusieurs Setup en Parallèle

Si vous appelez `/mfa/setup` plusieurs fois, seul le dernier secret sera valide.

## 🛠️ Dépannage Étape par Étape

### Étape 1 : Vérifier le Setup

```bash
# Appelez /mfa/setup et sauvegardez le secret
curl -X POST http://localhost:8000/api/v1/auth/mfa/setup \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json"
```

**Réponse attendue** :
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "otpauth_url": "otpauth://totp/..."
}
```

### Étape 2 : Générer le Code avec le MÊME Secret

```bash
# Utilisez le secret EXACT de l'étape 1
python test_mfa_helper.py JBSWY3DPEHPK3PXP
```

**Important** : Utilisez le secret retourné par `/mfa/setup`, pas un autre.

### Étape 3 : Activer Rapidement

```bash
# Utilisez le code IMMÉDIATEMENT (dans les 30 secondes)
curl -X POST http://localhost:8000/api/v1/auth/mfa/activate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"code": "123456"}'
```

## 🐛 Erreurs Courantes et Solutions

### Erreur: "Invalid verification code"

**Causes possibles** :
1. ❌ Secret différent entre setup et activation
2. ❌ Code expiré (> 30 secondes)
3. ❌ Code généré avec un mauvais secret

**Solution** :
1. Vérifiez que vous utilisez le secret de `/mfa/setup`
2. Régénérez le code et utilisez-le immédiatement
3. Utilisez le script helper pour être sûr du secret

### Erreur: "No MFA setup in progress"

**Cause** : Le `mfa_temp_secret` n'existe pas ou a été supprimé.

**Solution** : Refaites `/mfa/setup` et utilisez le nouveau secret.

### Erreur: "MFA already enabled"

**Cause** : L'utilisateur a déjà le MFA activé.

**Solution** : Désactivez d'abord avec `/mfa/disable`.

## 📋 Checklist de Vérification

Avant d'activer le MFA :

- [ ] Le secret de `/mfa/setup` est sauvegardé
- [ ] Le code TOTP est généré avec le **même secret** que `/mfa/setup`
- [ ] Le code est utilisé dans les **30 secondes** après génération
- [ ] Le `mfa_temp_secret` existe dans la base de données
- [ ] Vous utilisez le bon `access_token` (celui obtenu après login)
- [ ] L'heure système est correcte

## 🧪 Test Complet en Une Commande

```bash
# Test automatique complet
python test_mfa_activation.py admin votre_mot_de_passe
```

Ce script teste tout le flux et vous indique exactement où ça bloque.

## 💡 Astuce : Mode Debug

Si vous voulez voir plus de détails, vérifiez les logs Docker :

```bash
docker-compose logs backend | grep -i mfa
```

Les logs affichent maintenant :
- Le code reçu
- Le code attendu
- Le secret utilisé (premiers caractères)

## 🆘 Si Rien ne Fonctionne

1. **Vérifiez les logs** :
   ```bash
   docker-compose logs backend | tail -100
   ```

2. **Vérifiez la base de données** :
   ```sql
   SELECT username, mfa_temp_secret, mfa_secret, is_mfa_enabled 
   FROM users 
   WHERE username = 'admin';
   ```

3. **Réinitialisez le MFA** :
   - Désactivez si activé : `/mfa/disable`
   - Refaites `/mfa/setup`
   - Utilisez le nouveau secret

4. **Utilisez le script de test automatique** :
   ```bash
   python test_mfa_activation.py admin votre_mot_de_passe
   ```

---

**Note** : Le code a été amélioré pour :
- Augmenter la fenêtre de validité à ±60 secondes (`valid_window=2`)
- Afficher le code attendu dans les erreurs
- Ajouter plus de logging pour le debugging
- Rafraîchir l'utilisateur depuis la DB avant vérification
