#!/usr/bin/env python3
"""
Script pour corriger un problème de secret MFA qui ne correspond pas
Entre le secret stocké en base et celui dans Google Authenticator
"""

import sys
import requests
import pyotp
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

BASE_URL = "http://localhost:8000/api/v1/auth"

def print_step(step_num, description):
    """Affiche une étape du processus"""
    print(f"\n{'='*60}")
    print(f"ÉTAPE {step_num}: {description}")
    print(f"{'='*60}")

def get_current_secret(username):
    """Récupère le secret actuel depuis la base de données"""
    try:
        from app.core.database import SessionLocal
        from app.models.user import User
        
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            if user and user.is_mfa_enabled and user.mfa_secret:
                return user.mfa_secret
            return None
        finally:
            db.close()
    except Exception as e:
        print(f"⚠️  Erreur lors de la récupération du secret: {e}")
        return None

def fix_mfa_secret_mismatch(username, password):
    """Corrige le problème de secret MFA en reconfigurant complètement"""
    
    try:
        # Étape 1: Se connecter (sans MFA si possible, sinon on devra désactiver d'abord)
        print_step(1, "Connexion Initiale")
        print("⚠️  Note: Si MFA est activé, vous devrez d'abord le désactiver")
        print("   ou utiliser un token d'accès existant")
        
        # Essayer de se connecter
        login_response = requests.post(
            f"{BASE_URL}/login",
            json={"username": username, "password": password},
            timeout=10
        )
        login_response.raise_for_status()
        login_data = login_response.json()
        
        mfa_required = login_data.get("mfa_required", False)
        access_token = login_data.get("access_token")
        
        if mfa_required:
            print("❌ MFA est activé, mais le secret ne correspond pas")
            print("\n💡 Solution: Vous devez d'abord désactiver le MFA")
            print("   Option 1: Utiliser un token d'accès existant")
            print("   Option 2: Désactiver via SQL (voir instructions ci-dessous)")
            print("\n   Pour désactiver via SQL:")
            print("   UPDATE users SET is_mfa_enabled = false, mfa_secret = NULL WHERE username = 'admin';")
            return False
        
        if not access_token:
            print("❌ Erreur: Pas de token d'accès reçu")
            return False
        
        print(f"✓ Connexion réussie")
        print(f"  Token: {access_token[:30]}...")
        
        # Étape 2: Récupérer le secret actuel
        print_step(2, "Vérification du Secret Actuel")
        current_secret = get_current_secret(username)
        if current_secret:
            print(f"Secret actuel en base: {current_secret}")
            print(f"  ⚠️  Ce secret ne correspond PAS à celui dans Google Authenticator")
        else:
            print("  Aucun secret trouvé en base")
        
        # Étape 3: Désactiver le MFA
        print_step(3, "Désactivation du MFA")
        print("  ⚠️  Pour désactiver, vous devez fournir un code valide")
        print("  Si vous n'avez pas le bon code, utilisez SQL:")
        print("  UPDATE users SET is_mfa_enabled = false, mfa_secret = NULL WHERE username = 'admin';")
        
        # Essayer de désactiver (nécessite un code, donc probablement échouera)
        disable_code = input("\n  Entrez un code de Google Authenticator (ou 'skip' pour ignorer): ")
        if disable_code.lower() != 'skip':
            disable_response = requests.post(
                f"{BASE_URL}/mfa/disable",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"code": disable_code},
                timeout=10
            )
            if disable_response.status_code == 200:
                print("  ✓ MFA désactivé avec succès")
            else:
                print(f"  ⚠️  Impossible de désactiver avec le code fourni")
                print(f"     Erreur: {disable_response.json().get('detail', 'Unknown')}")
                print(f"     Vous devrez désactiver manuellement via SQL")
                return False
        
        # Étape 4: Nouveau setup MFA
        print_step(4, "Nouveau Setup MFA")
        setup_response = requests.post(
            f"{BASE_URL}/mfa/setup",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        setup_response.raise_for_status()
        setup_data = setup_response.json()
        new_secret = setup_data.get("secret")
        otpauth_url = setup_data.get("otpauth_url")
        
        if not new_secret:
            print("❌ Erreur: Pas de secret reçu")
            return False
        
        print(f"✓ Nouveau secret généré")
        print(f"\n{'='*60}")
        print("NOUVEAU SECRET MFA")
        print(f"{'='*60}")
        print(f"Secret: {new_secret}")
        print(f"URL: {otpauth_url}")
        print(f"\n⚠️  IMPORTANT: SAUVEGARDEZ CE SECRET!")
        print(f"\nActions à faire:")
        print(f"  1. Supprimez l'ancienne entrée 'FPI-CONNECT' dans Google Authenticator")
        print(f"  2. Scannez le NOUVEAU QR code (générez-le avec l'URL ci-dessus)")
        print(f"     Ou entrez manuellement le secret: {new_secret}")
        print(f"  3. Utilisez le code généré pour activer le MFA")
        
        # Générer un QR code si possible
        try:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(otpauth_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            qr_filename = f"mfa_qr_{username}.png"
            img.save(qr_filename)
            print(f"\n  ✓ QR code sauvegardé dans: {qr_filename}")
        except ImportError:
            print(f"\n  ⚠️  qrcode non installé, utilisez un générateur en ligne")
            print(f"     URL: {otpauth_url}")
        
        # Étape 5: Activer avec le nouveau code
        print_step(5, "Activation MFA avec Nouveau Secret")
        activation_code = input("\n  Entrez le code à 6 chiffres de Google Authenticator: ")
        
        activate_response = requests.post(
            f"{BASE_URL}/mfa/activate",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"code": activation_code},
            timeout=10
        )
        
        if activate_response.status_code != 200:
            error_detail = activate_response.json().get("detail", "Unknown error")
            print(f"❌ Erreur d'activation: {error_detail}")
            print(f"\n💡 Vérifiez que:")
            print(f"   - Vous avez scanné le NOUVEAU QR code")
            print(f"   - Le code est récent (généré dans les 30 dernières secondes)")
            return False
        
        print(f"✓ MFA activé avec succès!")
        
        # Étape 6: Vérifier que ça fonctionne
        print_step(6, "Vérification")
        print("  Test du login avec MFA...")
        
        login_mfa_response = requests.post(
            f"{BASE_URL}/login",
            json={"username": username, "password": password},
            timeout=10
        )
        login_mfa_response.raise_for_status()
        login_mfa_data = login_mfa_response.json()
        
        if login_mfa_data.get("mfa_required"):
            print("  ✓ Login avec MFA fonctionne correctement!")
            print(f"  mfa_session_id: {login_mfa_data.get('mfa_session_id')}")
        else:
            print("  ⚠️  MFA ne semble pas être requis")
        
        print(f"\n{'='*60}")
        print("✅ RECONFIGURATION MFA RÉUSSIE!")
        print(f"{'='*60}")
        print(f"\n📝 Résumé:")
        print(f"  - Ancien secret supprimé")
        print(f"  - Nouveau secret généré: {new_secret}")
        print(f"  - MFA réactivé avec le nouveau secret")
        print(f"  - Le secret correspond maintenant à Google Authenticator")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Erreur de requête: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Détails: {error_data}")
            except:
                print(f"   Réponse: {e.response.text}")
        return False
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Fonction principale"""
    print("="*60)
    print("CORRECTION DU PROBLÈME DE SECRET MFA")
    print("="*60)
    print("\nCe script vous aide à reconfigurer le MFA lorsque")
    print("le secret stocké ne correspond pas à celui dans Google Authenticator.")
    
    if len(sys.argv) < 3:
        print("\nUsage:")
        print(f"  python {sys.argv[0]} <username> <password>")
        print("\nExemple:")
        print(f"  python {sys.argv[0]} admin votre_mot_de_passe")
        print("\n⚠️  Note: Si MFA est activé, vous devrez peut-être")
        print("   le désactiver d'abord via SQL si le code ne fonctionne pas.")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    print(f"\nUtilisateur: {username}")
    print(f"Mot de passe: {'*' * len(password)}")
    
    success = fix_mfa_secret_mismatch(username, password)
    
    if success:
        print("\n🎉 Le problème est résolu!")
        sys.exit(0)
    else:
        print("\n❌ La correction a échoué")
        print("\n💡 Solutions alternatives:")
        print("  1. Désactiver MFA via SQL:")
        print("     UPDATE users SET is_mfa_enabled = false, mfa_secret = NULL WHERE username = 'admin';")
        print("  2. Puis refaire le setup MFA normalement")
        sys.exit(1)

if __name__ == "__main__":
    main()
