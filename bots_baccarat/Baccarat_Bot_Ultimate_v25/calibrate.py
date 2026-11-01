import sys
import time
import requests
import config
from core.scraper import StakeBaccaratScraper

def main():
    print("=" * 60)
    print("       CALIBRADOR Y DIAGN?STICO DE MESAS STAKE        ")
    print("=" * 60)
    
    scraper = StakeBaccaratScraper()
    connected, ws_url = scraper.check_chrome_connection()
    
    print(f"\n1. Comprobando conexi?n con Chrome (Puerto 9222)...")
    if connected:
        print(f"   [OK] Conectado a Chrome exitosamente.")
        print(f"   URL de Depuracion: {ws_url[:40]}...")
        
        tabs = scraper.get_open_tabs()
        print(f"\n2. Pesta?as detectadas en Chrome ({len(tabs)} abiertas):")
        stake_tabs = []
        for i, tab in enumerate(tabs):
            title = tab.get('title', 'Sin titulo')
            url = tab.get('url', '')
            print(f"   [{i+1}] {title[:45]} -> {url[:50]}")
            if "stake" in url.lower() or "baccarat" in url.lower():
                stake_tabs.append(tab)
                
        if stake_tabs:
            print(f"\n   [!] Se detectaron {len(stake_tabs)} pesta?a(s) de Casino/Stake.")
        else:
            print(f"\n   [i] Abre la pesta?a de Stake en Chrome para capturar datos en vivo.")
    else:
        print("   [!] Chrome no est? ejecut?ndose en modo depuraci?n.")
        print("   -> Para abrir Chrome en modo depuraci?n ejecuta:")
        print("      start_chrome_debug.bat")
        print("   -> Mientras tanto, el bot puede ejecutarse en modo Aut?nomo/Simulado.")

    print(f"\n3. Verificando Mesas Objetivo Configuradas:")
    for table in config.TARGET_TABLES:
        data = scraper.get_table_data(table)
        hist_str = ' '.join(data['history'][-8:])
        print(f"   - {table:<15} | Estado: Activa | ?ltimos resultados: [{hist_str}]")

    print("\n" + "=" * 60)
    print("Calibraci?n completada con ?xito.")
    print("Para iniciar el bot ejecuta: python main.py o start_bot.bat")
    print("=" * 60)

if __name__ == '__main__':
    main()
