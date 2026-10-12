#!/usr/bin/env python3
"""
Script de healthcheck pour GitRepoReco API
Vérifie que l'application FastAPI répond correctement
"""

import sys
import time
import urllib.request
import urllib.error
import json
import os
from typing import Optional


def check_endpoint(url: str, timeout: int = 5) -> tuple[bool, str]:
    """
    Vérifie qu'un endpoint répond correctement
    
    Args:
        url: URL à tester
        timeout: Timeout en secondes
        
    Returns:
        Tuple (success, message)
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.getcode() == 200:
                return True, f"✅ {url} - OK ({response.getcode()})"
            else:
                return False, f"❌ {url} - Code: {response.getcode()}"
    except urllib.error.HTTPError as e:
        return False, f"❌ {url} - HTTP Error: {e.code}"
    except urllib.error.URLError as e:
        return False, f"❌ {url} - URL Error: {e.reason}"
    except Exception as e:
        return False, f"❌ {url} - Error: {str(e)}"


def check_api_health(host: str = "localhost", port: int = 8000) -> bool:
    """
    Vérifie la santé de l'API GitRepoReco
    
    Args:
        host: Hôte de l'API
        port: Port de l'API
        
    Returns:
        True si l'API est en bonne santé, False sinon
    """
    base_url = f"http://{host}:{port}"
    
    # Liste des endpoints à tester
    endpoints = [
        "/docs",           # Documentation Swagger
        "/openapi.json",   # Schéma OpenAPI
    ]
    
    print(f"🔍 Vérification de l'API GitRepoReco sur {base_url}")
    
    all_success = True
    
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        success, message = check_endpoint(url)
        print(f"  {message}")
        
        if not success:
            all_success = False
    
    # Fin de la vérification des endpoints
    
    return all_success


def main():
    """Point d'entrée principal"""
    # Récupération des variables d'environnement
    host = os.getenv("HOST", "localhost")
    port = int(os.getenv("PORT", "8000"))
    
    # Arguments en ligne de commande
    if len(sys.argv) > 1:
        if sys.argv[1] in ["-h", "--help"]:
            print("Usage: python healthcheck.py [host] [port]")
            print("Variables d'environnement:")
            print("  HOST (défaut: localhost)")
            print("  PORT (défaut: 8000)")
            sys.exit(0)
        
        if len(sys.argv) >= 2:
            host = sys.argv[1]
        if len(sys.argv) >= 3:
            try:
                port = int(sys.argv[2])
            except ValueError:
                print(f"❌ Port invalide: {sys.argv[2]}")
                sys.exit(1)
    
    # Vérification de la santé
    start_time = time.time()
    is_healthy = check_api_health(host, port)
    duration = time.time() - start_time
    
    print(f"\n⏱️  Durée: {duration:.2f}s")
    
    if is_healthy:
        print("🎉 L'API GitRepoReco est en bonne santé !")
        sys.exit(0)
    else:
        print("💥 L'API GitRepoReco a des problèmes de santé !")
        sys.exit(1)


if __name__ == "__main__":
    main()