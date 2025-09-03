#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para verificar la detección mejorada de direcciones y CUPS
"""

import sys
import os
import re
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from secret_mappings import MAPEO_CUENTAS_CONTABLES, DIRECCIONES_POR_TIPO

def test_nueva_factura():
    """Prueba con los datos de la nueva factura de luz"""
    
    print("🧪 PRUEBA FACTURA LUZ BUENAVISTA 22 1 BAJO")
    print("=" * 60)
    
    # Datos de la factura real
    cups_real = "ES0021000007566411DB"
    direccion_suministro = "BUENAVISTA 22 1 BAJO"
    razon_social = "COPROPIETARIOS RONDA BUENAVISTA 22"
    
    print(f"📋 CUPS: {cups_real}")
    print(f"📋 Dirección de suministro: {direccion_suministro}")
    print(f"📋 Razón social: {razon_social}")
    
    print("\n🔍 VERIFICANDO MAPEOS:")
    
    # 1. Verificar CUPS en mapeo
    if cups_real in MAPEO_CUENTAS_CONTABLES:
        data = MAPEO_CUENTAS_CONTABLES[cups_real]
        print(f"✅ CUPS encontrado en mapeo:")
        print(f"   Comunidad: {data['comunidad']}")
        print(f"   Cuenta: {data['cuenta']}")
        print(f"   Dirección ref: {data['direccion_referencia']}")
    else:
        print(f"❌ CUPS {cups_real} NO encontrado en mapeo")
    
    # 2. Verificar dirección por tipo
    clave_direccion = ('Luz', direccion_suministro)
    if clave_direccion in DIRECCIONES_POR_TIPO:
        data = DIRECCIONES_POR_TIPO[clave_direccion]
        print(f"✅ Dirección por tipo encontrada:")
        print(f"   Comunidad: {data['comunidad']}")
        print(f"   Cuenta: {data['cuenta']}")
    else:
        print(f"❌ Dirección por tipo ({clave_direccion}) NO encontrada")
    
    # 3. Verificar todas las entradas de Buenavista
    print(f"\n📋 TODAS LAS ENTRADAS DE BUENAVISTA:")
    for key, value in MAPEO_CUENTAS_CONTABLES.items():
        if 'BUENAVISTA' in value.get('comunidad', '').upper():
            print(f"  {key}: {value['comunidad']} -> {value['cuenta']}")
    
    print(f"\n📋 DIRECCIONES POR TIPO DE BUENAVISTA:")
    for (tipo, direccion), value in DIRECCIONES_POR_TIPO.items():
        if 'BUENAVISTA' in direccion.upper():
            print(f"  ({tipo}) {direccion}: {value['comunidad']} -> {value['cuenta']}")

def test_deteccion_direccion():
    """Prueba la función de detección de dirección"""
    
    print(f"\n🧪 PRUEBA DETECCIÓN DE DIRECCIÓN")
    print("=" * 40)
    
    # Simular texto de factura
    texto_factura = """
    DATOS DEL TITULAR DEL CONTRATO
    CUPS: ES0021000007566411DB
    Potencia contratada: 1,5 15,0 kW
    Dirección de suministro: BUENAVISTA 22 1 BAJO, TOLEDO, Toledo, 45005
    
    DIRECCIÓN POSTAL DE ENVÍO
    Nombre/Razón social: COPROPIETARIOS RONDA BUENAVISTA 22
    """
    
    # Simular la función de detección
    def detectar_direccion_test(texto):
        if not texto:
            return None
        
        # Buscar "Dirección de suministro:"
        m_dir_suministro = re.search(r'Direcci[óo]n\s+de\s+suministro[:\s]*([^,\n\r]+)', texto, re.IGNORECASE)
        if m_dir_suministro:
            direccion = m_dir_suministro.group(1).strip()
            # Limpiar la dirección
            direccion = re.sub(r'\s+', ' ', direccion)
            # Remover ciudad y código postal del final
            direccion = re.sub(r',?\s*TOLEDO.*$', '', direccion, flags=re.IGNORECASE)
            direccion = re.sub(r',?\s*\d{5}.*$', '', direccion)
            return direccion.strip()
        
        return None
    
    direccion_detectada = detectar_direccion_test(texto_factura)
    print(f"🔍 Dirección detectada: '{direccion_detectada}'")
    
    if direccion_detectada == "BUENAVISTA 22 1 BAJO":
        print("✅ Detección correcta!")
    else:
        print("❌ Detección incorrecta")

if __name__ == "__main__":
    test_nueva_factura()
    test_deteccion_direccion()
    print(f"\n" + "=" * 60)
    print("✅ Pruebas completadas")
