#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para verificar la detección de comunidades y CUPS de Buenavista
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from secret_mappings import MAPEO_CUENTAS_CONTABLES, DIRECCIONES_POR_TIPO

def test_buenavista_detection():
    """Prueba la detección de datos de Buenavista"""
    
    print("🧪 PRUEBAS DE DETECCIÓN BUENAVISTA")
    print("=" * 50)
    
    # Datos de prueba basados en las facturas
    test_cases = [
        {
            "cups": "0039889075",
            "direccion": "COPROPIETARIOS RONDA BUENAVISTA 22",
            "tipo": "Luz",
            "esperado_comunidad": "BUENAVISTA 22 1",
            "esperado_cuenta": "6281777"
        },
        {
            "cups": "0016633368", 
            "direccion": "RONDA BUENAVISTA 22 3",
            "tipo": "Luz",
            "esperado_comunidad": "BUENAVISTA 22 3",
            "esperado_cuenta": "6281666"
        },
        {
            "cups": "0049430214",
            "direccion": "RONDA BUENAVISTA 22 2", 
            "tipo": "Luz",
            "esperado_comunidad": "BUENAVISTA 22 2",
            "esperado_cuenta": "6281444"
        }
    ]
    
    print("\n📋 MAPEO DE CUENTAS CONTABLES:")
    for cups, data in MAPEO_CUENTAS_CONTABLES.items():
        if "BUENAVISTA" in data.get("comunidad", "").upper():
            print(f"  {cups}: {data['comunidad']} -> {data['cuenta']}")
    
    print("\n📋 DIRECCIONES POR TIPO:")
    for (tipo, direccion), data in DIRECCIONES_POR_TIPO.items():
        if "BUENAVISTA" in direccion.upper():
            print(f"  ({tipo}) {direccion}: {data['comunidad']} -> {data['cuenta']}")
    
    print("\n🔍 PRUEBAS DE CASOS:")
    for i, caso in enumerate(test_cases, 1):
        print(f"\nCaso {i}:")
        print(f"  CUPS: {caso['cups']}")
        print(f"  Dirección: {caso['direccion']}")
        print(f"  Tipo: {caso['tipo']}")
        
        # Verificar si está en mapeo de CUPS
        if caso['cups'] in MAPEO_CUENTAS_CONTABLES:
            data = MAPEO_CUENTAS_CONTABLES[caso['cups']]
            print(f"  ✅ Encontrado en MAPEO_CUENTAS_CONTABLES:")
            print(f"     Comunidad: {data['comunidad']}")
            print(f"     Cuenta: {data['cuenta']}")
        else:
            print(f"  ❌ No encontrado en MAPEO_CUENTAS_CONTABLES")
        
        # Verificar direcciones
        clave_direccion = (caso['tipo'], caso['direccion'])
        if clave_direccion in DIRECCIONES_POR_TIPO:
            data = DIRECCIONES_POR_TIPO[clave_direccion]
            print(f"  ✅ Encontrado en DIRECCIONES_POR_TIPO:")
            print(f"     Comunidad: {data['comunidad']}")
            print(f"     Cuenta: {data['cuenta']}")
        else:
            print(f"  ⚠️ No encontrado dirección exacta en DIRECCIONES_POR_TIPO")
    
    print("\n" + "=" * 50)
    print("✅ Pruebas completadas")

if __name__ == "__main__":
    test_buenavista_detection()
