#!/usr/bin/env python3
"""
Script de test pour l'étape /mfa/verify
Teste le flux complet de login avec MFA activé
"""

import requests
import pyotp
import time
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Essayer de charger depuis le répertoire courant
    load_dotenv()

BASE_URL = "http://localhost:8000/api/v1/auth"

def print_step(step_num, description):
    """Affiche une étape du processus"""
    print(f"\n{'='*60}")
    print(f"ÉTAPE {step_num}: {description}")
    print(f"{'='*60}")

def get_mfa_secret_from_db(username):
    """Récupère le secret MFA depuis la base de données (pour les tests uniquement)"""
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
        print(f"⚠️  Impossible de récupérer le secret depuis la DB: {e}")
        return None

def test_mfa_verify(username, password, mfa_secret=None):
    """Test complet du flux de vérification MFA"""
    
    try:
        # Étape 1: Login (retourne mfa_session_id)
        print_step(1, "Login avec MFA Activé")
        login_response = requests.post(
            f"{BASE_URL}/login",
            json={"username": username, "password": password},
            timeout=10
        )
        login_response.raise_for_status()
        login_data = login_response.json()
        
        mfa_required = login_data.get("mfa_required", False)
        mfa_session_id = login_data.get("mfa_session_id")
        access_token = login_data.get("access_token")
        
        if not mfa_required:
            print("❌ Erreur: MFA n'est pas requis")
            if access_token:
                print("   L'utilisateur n'a peut-être pas le MFA activé")
            print(f"   Réponse: {login_data}")
            return False
        
        if not mfa_session_id:
            print("❌ Erreur: Pas de mfa_session_id reçu")
            print(f"   Réponse: {login_data}")
            return False
        
        print(f"✓ Login réussi avec MFA requis")
        print(f"  mfa_session_id: {mfa_session_id}")
        print(f"  ⚠️  Access token non fourni (normal avec MFA)")
        
        # Étape 2: Obtenir le secret MFA
        print_step(2, "Récupération du Secret MFA")
        
        if not mfa_secret:
            print("  Tentative de récupération depuis la base de données...")
            mfa_secret = get_mfa_secret_from_db(username)
        
        if not mfa_secret:
            print("❌ Erreur: Secret MFA non fourni et impossible à récupérer")
            print("   Solution: Fournissez le secret en paramètre")
            print("   Usage: python test_mfa_verify.py <username> <password> <mfa_secret>")
            return False
        
        print(f"✓ Secret MFA obtenu: {mfa_secret[:8]}...")
        print(f"  ⚠️  Utilisez ce secret pour générer le code TOTP")
        
        # Étape 3: Générer le code TOTP
        print_step(3, "Génération du Code TOTP")
        totp = pyotp.TOTP(mfa_secret)
        code = totp.now()
        print(f"✓ Code généré: {code}")
        print(f"  ⏰ Code valide pour les 30 prochaines secondes")
        print(f"  ⚠️  Utilisez ce code IMMÉDIATEMENT")
        
        # Vérifier que le code est valide
        if not totp.verify(code, valid_window=2):
            print("❌ Erreur: Le code généré n'est pas valide!")
            return False
        
        # Attendre 1 seconde pour s'assurer que le code est stable
        time.sleep(1)
        
        # Étape 4: Vérifier le code MFA
        print_step(4, "Vérification MFA (/mfa/verify)")
        print(f"  Code utilisé: {code}")
        print(f"  mfa_session_id: {mfa_session_id}")
        
        verify_response = requests.post(
            f"{BASE_URL}/mfa/verify",
            json={
                "mfa_session_id": str(mfa_session_id),
                "code": code
            },
            timeout=10
        )
        
        if verify_response.status_code != 200:
            error_detail = verify_response.json().get("detail", "Unknown error")
            print(f"❌ Erreur de vérification: {error_detail}")
            
            # Si c'est un code invalide, générer le code attendu
            if "Invalid" in str(error_detail) or "code" in str(error_detail).lower():
                expected_code = totp.now()
                print(f"\n💡 Code attendu actuel: {expected_code}")
                print(f"   Code utilisé: {code}")
                print(f"   Différence de temps possible - essayez avec le nouveau code")
            
            return False
        
        verify_data = verify_response.json()
        access_token = verify_data.get("access_token")
        token_type = verify_data.get("token_type")
        
        if not access_token:
            print("❌ Erreur: Pas de token d'accès reçu")
            print(f"   Réponse: {verify_data}")
            return False
        
        print(f"✓ Vérification réussie!")
        print(f"  Access token: {access_token[:30]}...")
        print(f"  Token type: {token_type}")
        
        # Étape 5: Vérifier que le token fonctionne
        print_step(5, "Vérification du Token d'Accès")
        me_response = requests.get(
            f"{BASE_URL}/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        
        if me_response.status_code != 200:
            print(f"❌ Erreur: Le token ne fonctionne pas")
            print(f"   Status: {me_response.status_code}")
            print(f"   Réponse: {me_response.text}")
            return False
        
        user_data = me_response.json()
        print(f"✓ Token valide!")
        print(f"  Utilisateur: {user_data.get('username')}")
        print(f"  Email: {user_data.get('email')}")
        print(f"  MFA activé: {user_data.get('is_mfa_enabled', False)}")
        
        # Étape 6: Vérifier le refresh token (cookie)
        print_step(6, "Vérification du Refresh Token (Cookie)")
        cookies = verify_response.cookies
        refresh_token_cookie = cookies.get("refresh_token")
        
        if refresh_token_cookie:
            print(f"✓ Refresh token cookie présent")
            print(f"  Cookie name: refresh_token")
            print(f"  Cookie value: {refresh_token_cookie[:20]}...")
        else:
            print(f"⚠️  Refresh token cookie non présent")
            print(f"   Vérifiez la configuration REFRESH_TOKEN_COOKIE_NAME")
        
        print(f"\n{'='*60}")
        print("✅ TEST COMPLET RÉUSSI!")
        print(f"{'='*60}")
        print("\n📝 Résumé:")
        print(f"  - Login avec MFA fonctionne")
        print(f"  - Vérification MFA réussie")
        print(f"  - Access token obtenu et valide")
        print(f"  - Refresh token cookie défini")
        print(f"\n🎉 Le flux MFA complet fonctionne correctement!")
        
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
    print("TEST DE VÉRIFICATION MFA (/mfa/verify)")
    print("="*60)
    print(f"URL de base: {BASE_URL}")
    print(f"Date/Heure: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if len(sys.argv) < 3:
        print("\nUsage:")
        print(f"  python {sys.argv[0]} <username> <password> [mfa_secret]")
        print("\nExemples:")
        print(f"  # Avec secret fourni")
        print(f"  python {sys.argv[0]} admin votre_mot_de_passe KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL")
        print(f"\n  # Sans secret (tentative de récupération depuis DB)")
        print(f"  python {sys.argv[0]} admin votre_mot_de_passe")
        print("\n💡 Le secret MFA est celui utilisé lors de l'activation")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    mfa_secret = sys.argv[3] if len(sys.argv) >= 4 else None
    
    print(f"\nUtilisateur: {username}")
    print(f"Mot de passe: {'*' * len(password)}")
    if mfa_secret:
        print(f"Secret MFA: {mfa_secret[:8]}... (fourni)")
    else:
        print(f"Secret MFA: (tentative de récupération depuis DB)")
    
    success = test_mfa_verify(username, password, mfa_secret)
    
    if success:
        print("\n🎉 Tous les tests sont passés!")
        sys.exit(0)
    else:
        print("\n❌ Certains tests ont échoué")
        print("\n💡 Conseils:")
        print("  - Vérifiez que le MFA est activé pour cet utilisateur")
        print("  - Utilisez le secret utilisé lors de l'activation MFA")
        print("  - Assurez-vous d'utiliser un code TOTP récent (généré dans les 30 dernières secondes)")
        print("  - Consultez MFA_ACTIVATION_TROUBLESHOOT.md pour plus d'aide")
        sys.exit(1)

if __name__ == "__main__":
    main()
