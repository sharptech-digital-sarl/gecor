# Comment Lier Google Authenticator avec le Secret en Base

## 📋 Situation

Vous avez réussi à vous connecter en utilisant le code généré par `diagnose_mfa.py`, ce qui confirme que :
- ✅ Le secret stocké en base est **correct**
- ❌ Le secret dans Google Authenticator est **différent**

## 🎯 Solution : Reconfigurer Google Authenticator

Vous devez reconfigurer Google Authenticator pour utiliser le même secret que celui stocké en base.

### Étape 1 : Récupérer le Secret et Générer le QR Code

Le secret stocké en base est : **`KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL`**

Vous pouvez générer un QR code avec ce secret de deux façons :

#### Option A : Utiliser un Générateur en Ligne

1. Allez sur https://www.qr-code-generator.com/ ou https://www.qrcode-monkey.com/
2. Utilisez cette URL (à encoder en QR code) :

```
otpauth://totp/FPI-CONNECT:joelnyengele%40gmail.com?secret=KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL&issuer=FPI-CONNECT
```

3. Générez le QR code

#### Option B : Utiliser Python Localement

Créez un fichier `generate_qr.py` :

```python
import pyotp
import qrcode

secret = "KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL"
email = "joelnyengele@gmail.com"

totp = pyotp.TOTP(secret)
otpauth_url = totp.provisioning_uri(
    name=email,
    issuer_name="FPI-CONNECT"
)

qr = qrcode.QRCode(version=1, box_size=10, border=4)
qr.add_data(otpauth_url)
qr.make(fit=True)

img = qr.make_image(fill_color="black", back_color="white")
img.save("mfa_qr_admin.png")

print(f"QR code sauvegardé: mfa_qr_admin.png")
print(f"URL: {otpauth_url}")
```

Exécutez :
```bash
pip install qrcode[pil] pyotp
python generate_qr.py
```

### Étape 2 : Supprimer l'Ancienne Entrée dans Google Authenticator

1. Ouvrez Google Authenticator sur votre téléphone
2. Trouvez l'entrée "FPI-CONNECT" (ou similaire)
3. Supprimez-la

### Étape 3 : Scanner le Nouveau QR Code

1. Ouvrez Google Authenticator
2. Appuyez sur "+" (Ajouter)
3. Scannez le QR code généré à l'étape 1

**OU** entrez manuellement :
- Nom : `FPI-CONNECT`
- Secret : `KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL`
- Type : Temps (TOTP)

### Étape 4 : Vérifier la Synchronisation

1. Exécutez le diagnostic pour voir le code attendu :
   ```bash
   docker-compose exec backend python diagnose_mfa.py admin
   ```

2. Comparez avec le code affiché dans Google Authenticator
   - Ils doivent correspondre (ou être très proches, car les codes changent toutes les 30 secondes)

3. Testez la connexion :
   ```bash
   # Login
   curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "votre_mot_de_passe"}'
   
   # Utiliser le mfa_session_id reçu et le code de Google Authenticator
   curl -X POST http://localhost:8000/api/v1/auth/mfa/verify \
     -H "Content-Type: application/json" \
     -d '{"mfa_session_id": "...", "code": "CODE_DU_TELEPHONE"}'
   ```

## 🔍 Vérification Rapide

Pour vérifier que tout fonctionne, utilisez le script de test :

```bash
# Le script récupère automatiquement le secret depuis la base
docker-compose exec backend python test_mfa_verify.py admin votre_mot_de_passe
```

Si le test réussit, c'est que Google Authenticator est maintenant synchronisé ! ✅

## 💡 Résumé

1. ✅ Secret en base : `KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL` (correct)
2. ❌ Google Authenticator : avait un secret différent
3. 🔧 Solution : Supprimer l'ancienne entrée → Scanner le nouveau QR code avec le bon secret
4. ✅ Résultat : Les deux utilisent maintenant le même secret

## 📱 Alternative : Entrée Manuelle

Si vous préférez entrer manuellement dans Google Authenticator :

1. Ouvrez Google Authenticator
2. Appuyez sur "+" → "Entrer une clé de configuration"
3. Entrez :
   - **Nom du compte** : `FPI-CONNECT`
   - **Clé** : `KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL`
   - **Type** : Temps (TOTP)

---

**Note** : Après avoir reconfiguré Google Authenticator, vous devriez pouvoir vous connecter normalement avec le code affiché dans l'application.
