#!/usr/bin/env python3
"""
Script de DEBUG - Salva HTML da página para análise
"""
import sys
from cnvsweb_scraper import CNVSWebScraper

def debug_page_structure():
    """
    Acessa uma página e salva o HTML completo para análise
    """
    TOKEN = "2E9RCU0B"
    
    print("\n" + "="*80)
    print("DEBUG: Análise de Estrutura da Página")
    print("="*80 + "\n")
    
    scraper = CNVSWebScraper(TOKEN)
    
    # Login
    print("🔐 Fazendo login...")
    if not scraper.login():
        print("❌ Falha no login!")
        return False
    print("✅ Login bem-sucedido!\n")
    
    # URL de teste
    test_url = "https://cnvsweb.stream/watch/velozes-e-furiosos"
    
    print(f"🎬 Testando: {test_url}")
    print("-" * 80 + "\n")
    
    # Chama get_player_url com debug ativado
    player_url = scraper.get_player_url(test_url, save_debug_html=True)
    
    print("\n" + "="*80)
    print("RESULTADO:")
    print("="*80)
    
    if player_url:
        print(f"✅ Player URL encontrada: {player_url}")
    else:
        print(f"❌ Player URL NÃO encontrada")
        print(f"\n💡 Verifique o arquivo HTML salvo para análise manual")
    
    print("="*80 + "\n")
    
    return player_url is not None

if __name__ == "__main__":
    success = debug_page_structure()
    sys.exit(0 if success else 1)
