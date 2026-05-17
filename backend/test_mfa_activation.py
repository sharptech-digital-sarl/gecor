#!/usr/bin/env python3
"""
Script de test complet pour l'activation MFA
Utilisez ce script pour tester le flux MFA de bout en bout
"""

import requests
import pyotp
import time
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1/auth"

def print_step(step_num, description):
    """Affiche une étape du processus"""
    print(f"\n{'='*60}")
    print(f"ÉTAPE {step_num}: {description}")
    print(f"{'='*60}")

def test_mfa_activation(username, password):
    """Test complet du flux d'activation MFA"""
    
    try:
        # Étape 1: Login
        print_step(1, "Login")
        login_response = requests.post(
            f"{BASE_URL}/login",
            json={"username": username, "password": password},
            timeout=10
        )
        login_response.raise_for_status()
        login_data = login_response.json()
        access_token = login_data.get("access_token")
        
        if not access_token:
            print("❌ Erreur: Pas de token d'accès reçu")
            print(f"Réponse: {login_data}")
            return False
        
        print(f"✓ Login réussi")
        print(f"  Token: {access_token[:30]}...")
        print(f"  MFA requis: {login_data.get('mfa_required', False)}")
        
        # Étape 2: Setup MFA
        print_step(2, "Setup MFA")
        setup_response = requests.post(
            f"{BASE_URL}/mfa/setup",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        setup_response.raise_for_status()
        setup_data = setup_response.json()
        secret = setup_data.get("secret")
        otpauth_url = setup_data.get("otpauth_url")
        
        if not secret:
            print("❌ Erreur: Pas de secret reçu")
            print(f"Réponse: {setup_data}")
            return False
        
        print(f"✓ Setup réussi")
        print(f"  Secret: {secret}")
        print(f"  otpauth_url: {otpauth_url[:50]}...")
        print(f"\n💡 Utilisez ce secret pour générer le code TOTP")
        
        # Étape 3: Générer le code TOTP
        print_step(3, "Génération du Code TOTP")
        totp = pyotp.TOTP(secret)
        code = totp.now()
        print(f"✓ Code généré: {code}")
        print(f"  ⏰ Code valide pour les 30 prochaines secondes")
        print(f"  ⚠️  Utilisez ce code IMMÉDIATEMENT")
        
        # Attendre 1 seconde pour s'assurer que le code est stable
        time.sleep(1)
        
        # Vérifier que le code est toujours valide
        if not totp.verify(code, valid_window=2):
            print("❌ Erreur: Le code généré n'est pas valide!")
            return False
        
        # Étape 4: Activer MFA
        print_step(4, "Activation MFA")
        print(f"  Code utilisé: {code}")
        
        activate_response = requests.post(
            f"{BASE_URL}/mfa/activate",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"code": code},
            timeout=10
        )
        
        if activate_response.status_code != 200:
            error_detail = activate_response.json().get("detail", "Unknown error")
            print(f"❌ Erreur d'activation: {error_detail}")
            
            # Si c'est un code invalide, générer le code attendu
            if "Invalid verification code" in str(error_detail):
                expected_code = totp.now()
                print(f"\n💡 Code attendu actuel: {expected_code}")
                print(f"   Code utilisé: {code}")
                print(f"   Différence de temps possible - essayez avec le nouveau code")
            
            return False
        
        activate_data = activate_response.json()
        print(f"✓ Activation réussie!")
        print(f"  Message: {activate_data.get('message', 'N/A')}")
        
        # Étape 5: Vérifier que MFA est activé
        print_step(5, "Vérification MFA Activé")
        me_response = requests.get(
            f"{BASE_URL}/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        me_response.raise_for_status()
        user_data = me_response.json()
        is_mfa_enabled = user_data.get("is_mfa_enabled", False)
        
        if is_mfa_enabled:
            print(f"✓ MFA est activé pour l'utilisateur {user_data.get('username')}")
        else:
            print(f"⚠️  MFA n'est pas activé (is_mfa_enabled={is_mfa_enabled})")
            return False
        
        # Étape 6: Tester le login avec MFA
        print_step(6, "Test Login avec MFA")
        print("  Tentative de login avec MFA activé...")
        
        login_mfa_response = requests.post(
            f"{BASE_URL}/login",
            json={"username": username, "password": password},
            timeout=10
        )
        login_mfa_response.raise_for_status()
        login_mfa_data = login_mfa_response.json()
        
        if login_mfa_data.get("mfa_required"):
            mfa_session_id = login_mfa_data.get("mfa_session_id")
            print(f"✓ Login avec MFA requis")
            print(f"  mfa_session_id: {mfa_session_id}")
            print(f"  ⚠️  Vous devez maintenant appeler /mfa/verify avec un code TOTP")
        else:
            print(f"❌ Erreur: MFA n'est pas requis après activation")
            return False
        
        print(f"\n{'='*60}")
        print("✅ TEST COMPLET RÉUSSI!")
        print(f"{'='*60}")
        print("\n📝 Résumé:")
        print(f"  - MFA activé avec succès")
        print(f"  - Login avec MFA fonctionne")
        print(f"  - Prochaine étape: Utiliser /mfa/verify avec mfa_session_id")
        
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
    print("TEST D'ACTIVATION MFA")
    print("="*60)
    print(f"URL de base: {BASE_URL}")
    print(f"Date/Heure: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if len(sys.argv) < 3:
        print("\nUsage:")
        print(f"  python {sys.argv[0]} <username> <password>")
        print("\nExemple:")
        print(f"  python {sys.argv[0]} admin votre_mot_de_passe")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    print(f"\nUtilisateur: {username}")
    print(f"Mot de passe: {'*' * len(password)}")
    
    success = test_mfa_activation(username, password)
    
    if success:
        print("\n🎉 Tous les tests sont passés!")
        sys.exit(0)
    else:
        print("\n❌ Certains tests ont échoué")
        print("\n💡 Consultez MFA_ACTIVATION_TROUBLESHOOT.md pour plus d'aide")
        sys.exit(1)

if __name__ == "__main__":
    main()
