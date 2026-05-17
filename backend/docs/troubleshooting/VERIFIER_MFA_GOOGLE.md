# Comment Vérifier et Corriger la Configuration MFA avec Google Authenticator

## 🔍 Vérification Actuelle

**Secret stocké en base** : `KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL`
**Code actuel attendu** : Vérifiez avec `diagnose_mfa.py admin`

## 📱 Étapes pour Corriger Google Authenticator

### Option 1 : Scanner le QR Code (Recommandé)

1. **Supprimer l'ancienne entrée** :
   - Ouvrez Google Authenticator
   - Trouvez l'entrée "FPI-CONNECT" (ou similaire)
   - **Supprimez-la complètement** (appuyez longuement → Supprimer)

2. **Ouvrir le QR code** :
   - Le fichier `mfa_qr_admin.png` se trouve dans le dossier backend
   - Ouvrez-le sur votre ordinateur (il devrait s'afficher)

3. **Scanner avec Google Authenticator** :
   - Ouvrez Google Authenticator
   - Appuyez sur **"+"** (en bas à droite)
   - Sélectionnez **"Scanner un code QR"**
   - **Pointez la caméra vers le QR code** sur votre écran d'ordinateur
   - Attendez que l'app détecte et ajoute le compte

4. **Vérifier** :
   - Une nouvelle entrée "FPI-CONNECT" devrait apparaître
   - Elle devrait afficher un code à 6 chiffres

### Option 2 : Entrée Manuelle (Si le scan ne fonctionne pas)

1. **Supprimer l'ancienne entrée** :
   - Ouvrez Google Authenticator
   - Supprimez l'ancienne entrée "FPI-CONNECT"

2. **Ajouter manuellement** :
   - Appuyez sur **"+"** → **"Entrer une clé de configuration"**
   - Remplissez :
     - **Nom du compte** : `FPI-CONNECT`
     - **Votre clé** : `KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL`
     - **Type** : Sélectionnez **"Temps"** (TOTP)
   - Appuyez sur **"Ajouter"**

3. **Vérifier** :
   - Une nouvelle entrée devrait apparaître avec un code

## ✅ Comment Vérifier que Ça Fonctionne

### Méthode 1 : Comparaison des Codes

1. Exécutez le diagnostic pour voir le code attendu :
   ```bash
   docker-compose exec backend python diagnose_mfa.py admin
   ```

2. Regardez le code affiché dans Google Authenticator

3. **Ils doivent correspondre** (ou être très proches, car les codes changent toutes les 30 secondes)

   Par exemple, si le diagnostic montre :
   ```
   Code actuel: 163215
   Code précédent: 454055
   Code suivant: 023096
   ```
   
   Le code dans Google Authenticator devrait être **163215** (ou 454055/023096 si vous regardez au moment du changement)

### Méthode 2 : Test de Connexion

1. Faites un login :
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "votre_mot_de_passe"}'
   ```

2. Vous obtiendrez un `mfa_session_id`

3. Utilisez le code affiché dans Google Authenticator :
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/mfa/verify \
     -H "Content-Type: application/json" \
     -d '{"mfa_session_id": "VOTRE_SESSION_ID", "code": "CODE_DU_TELEPHONE"}'
   ```

4. Si ça fonctionne, vous obtiendrez un `access_token` ✅

### Méthode 3 : Script Automatique

```bash
docker-compose exec backend python test_mfa_verify.py admin votre_mot_de_passe
```

Ce script :
- Fait le login
- Récupère le secret depuis la base
- Génère le code TOTP
- Teste la vérification MFA
- Vous dira si c'est OK ou non

## 🚨 Problèmes Courants

### Le code ne correspond toujours pas

**Causes possibles** :
1. L'ancienne entrée n'a pas été supprimée
2. Le QR code n'a pas été correctement scanné
3. Le secret a été mal entré manuellement

**Solution** :
- **Supprimez TOUTES les entrées** liées à FPI-CONNECT dans Google Authenticator
- Recommencez depuis le début (Option 1 ou 2)
- Vérifiez que le secret est exactement : `KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL`

### Je ne peux pas scanner le QR code

**Solution** :
- Utilisez l'**Option 2 : Entrée Manuelle** ci-dessus
- Assurez-vous de sélectionner **"Temps"** (TOTP) comme type

### Le code change trop vite

**C'est normal !** Les codes TOTP changent toutes les 30 secondes. 
- Utilisez un code récent (généré dans les 30 dernières secondes)
- La fenêtre de validité est de ±60 secondes

## 📝 Résumé des Actions

1. ✅ **Secret en base** : `KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL` (correct)
2. ❌ **Google Authenticator** : A un secret différent
3. 🔧 **Action** : Supprimer l'ancienne entrée → Scanner le QR code ou entrer manuellement
4. ✅ **Résultat attendu** : Les codes correspondent

## 🎯 Checklist

- [ ] Ancienne entrée "FPI-CONNECT" supprimée dans Google Authenticator
- [ ] Nouvelle entrée ajoutée (via QR code OU manuellement)
- [ ] Code dans Google Authenticator correspond au code du diagnostic
- [ ] Test de connexion réussi

---

**Fichier QR code** : `c:\projects\fpi-connect\backend\mfa_qr_admin.png`

**Secret** : `KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL`
