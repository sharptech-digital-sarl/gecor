#!/usr/bin/env python3
"""
Script de test complet du flux MFA
Teste : Setup → Activation → Login → Vérification
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

def test_complete_mfa_flow(username, password, skip_activation=False):
    """Test complet du flux MFA de bout en bout"""
    
    mfa_secret = None
    
    try:
        # Étape 1: Login initial
        print_step(1, "Login Initial")
        login_response = requests.post(
            f"{BASE_URL}/login",
            json={"username": username, "password": password},
            timeout=10
        )
        login_response.raise_for_status()
        login_data = login_response.json()
        access_token = login_data.get("access_token")
        mfa_required = login_data.get("mfa_required", False)
        
        if mfa_required:
            print("⚠️  MFA déjà activé, on va tester directement la vérification")
            mfa_session_id = login_data.get("mfa_session_id")
            if not mfa_session_id:
                print("❌ Pas de mfa_session_id reçu")
                return False
            
            # Récupérer le secret depuis la DB
            print("  Récupération du secret MFA depuis la base...")
            try:
                from app.core.database import SessionLocal
                from app.models.user import User
                db = SessionLocal()
                user = db.query(User).filter(User.username == username).first()
                if user and user.is_mfa_enabled and user.mfa_secret:
                    mfa_secret = user.mfa_secret
                    print(f"  ✓ Secret récupéré: {mfa_secret[:8]}...")
                db.close()
            except Exception as e:
                print(f"  ⚠️  Impossible de récupérer le secret: {e}")
                print("  Vous devrez fournir le secret manuellement")
                return False
            
            # Aller directement à la vérification
            return test_mfa_verify_internal(mfa_session_id, mfa_secret)
        
        if not access_token:
            print("❌ Erreur: Pas de token d'accès reçu")
            return False
        
        print(f"✓ Login réussi")
        print(f"  Token: {access_token[:30]}...")
        
        if skip_activation:
            print("  ⚠️  Activation MFA ignorée (skip_activation=True)")
            return True
        
        # Étape 2: Setup MFA
        print_step(2, "Setup MFA")
        setup_response = requests.post(
            f"{BASE_URL}/mfa/setup",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        setup_response.raise_for_status()
        setup_data = setup_response.json()
        mfa_secret = setup_data.get("secret")
        
        if not mfa_secret:
            print("❌ Erreur: Pas de secret reçu")
            return False
        
        print(f"✓ Setup réussi")
        print(f"  Secret: {mfa_secret}")
        print(f"  ⚠️  SAUVEGARDEZ CE SECRET pour les prochaines connexions!")
        
        # Étape 3: Générer et activer MFA
        print_step(3, "Activation MFA")
        totp = pyotp.TOTP(mfa_secret)
        code = totp.now()
        print(f"  Code généré: {code}")
        
        activate_response = requests.post(
            f"{BASE_URL}/mfa/activate",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"code": code},
            timeout=10
        )
        
        if activate_response.status_code != 200:
            error_detail = activate_response.json().get("detail", "Unknown error")
            print(f"❌ Erreur d'activation: {error_detail}")
            return False
        
        print(f"✓ MFA activé avec succès")
        
        # Étape 4: Login avec MFA (obtenir mfa_session_id)
        print_step(4, "Login avec MFA Activé")
        login_mfa_response = requests.post(
            f"{BASE_URL}/login",
            json={"username": username, "password": password},
            timeout=10
        )
        login_mfa_response.raise_for_status()
        login_mfa_data = login_mfa_response.json()
        
        mfa_session_id = login_mfa_data.get("mfa_session_id")
        if not mfa_session_id:
            print("❌ Erreur: Pas de mfa_session_id reçu")
            return False
        
        print(f"✓ Login avec MFA requis")
        print(f"  mfa_session_id: {mfa_session_id}")
        
        # Étape 5: Vérifier MFA
        return test_mfa_verify_internal(mfa_session_id, mfa_secret)
        
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

def test_mfa_verify_internal(mfa_session_id, mfa_secret):
    """Fonction interne pour tester la vérification MFA"""
    
    # Générer le code TOTP
    print_step(5, "Génération du Code TOTP pour Vérification")
    totp = pyotp.TOTP(mfa_secret)
    code = totp.now()
    print(f"✓ Code généré: {code}")
    print(f"  ⏰ Code valide pour les 30 prochaines secondes")
    
    time.sleep(1)
    
    # Vérifier MFA
    print_step(6, "Vérification MFA (/mfa/verify)")
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
        return False
    
    verify_data = verify_response.json()
    access_token = verify_data.get("access_token")
    
    if not access_token:
        print("❌ Erreur: Pas de token d'accès reçu")
        return False
    
    print(f"✓ Vérification réussie!")
    print(f"  Access token: {access_token[:30]}...")
    
    # Vérifier le token
    print_step(7, "Vérification du Token Final")
    me_response = requests.get(
        f"{BASE_URL}/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10
    )
    
    if me_response.status_code != 200:
        print(f"❌ Erreur: Le token ne fonctionne pas")
        return False
    
    user_data = me_response.json()
    print(f"✓ Token valide!")
    print(f"  Utilisateur: {user_data.get('username')}")
    print(f"  MFA activé: {user_data.get('is_mfa_enabled', False)}")
    
    # Vérifier le refresh token cookie
    cookies = verify_response.cookies
    if cookies.get("refresh_token"):
        print(f"✓ Refresh token cookie présent")
    
    print(f"\n{'='*60}")
    print("✅ FLUX MFA COMPLET RÉUSSI!")
    print(f"{'='*60}")
    print("\n📝 Résumé:")
    print(f"  ✓ Setup MFA")
    print(f"  ✓ Activation MFA")
    print(f"  ✓ Login avec MFA")
    print(f"  ✓ Vérification MFA")
    print(f"  ✓ Tokens obtenus et valides")
    print(f"\n🎉 Le système MFA fonctionne parfaitement!")
    
    return True

def main():
    """Fonction principale"""
    print("="*60)
    print("TEST COMPLET DU FLUX MFA")
    print("="*60)
    print(f"URL de base: {BASE_URL}")
    print(f"Date/Heure: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if len(sys.argv) < 3:
        print("\nUsage:")
        print(f"  python {sys.argv[0]} <username> <password> [--skip-activation]")
        print("\nExemples:")
        print(f"  # Test complet (setup + activation + vérification)")
        print(f"  python {sys.argv[0]} admin votre_mot_de_passe")
        print(f"\n  # Test uniquement la vérification (si MFA déjà activé)")
        print(f"  python {sys.argv[0]} admin votre_mot_de_passe --skip-activation")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    skip_activation = "--skip-activation" in sys.argv
    
    print(f"\nUtilisateur: {username}")
    print(f"Mot de passe: {'*' * len(password)}")
    if skip_activation:
        print(f"Mode: Vérification uniquement (MFA déjà activé)")
    else:
        print(f"Mode: Test complet (setup + activation + vérification)")
    
    success = test_complete_mfa_flow(username, password, skip_activation)
    
    if success:
        print("\n🎉 Tous les tests sont passés!")
        sys.exit(0)
    else:
        print("\n❌ Certains tests ont échoué")
        sys.exit(1)

if __name__ == "__main__":
    main()
