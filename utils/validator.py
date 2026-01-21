class ValidadorNotarial:
    def validar_secuenciales(self, codigos):
        """Valida la continuidad de los secuenciales"""
        if not codigos:
            return {'error': 'No hay códigos para validar'}
        
        # Extraer secuenciales (últimos 5 dígitos)
        secuenciales = []
        for codigo in codigos:
            try:
                secuencial = int(codigo[-5:])
                secuenciales.append(secuencial)
            except:
                continue
        
        secuenciales.sort()
        
        # Encontrar faltantes
        faltantes = []
        for i in range(len(secuenciales) - 1):
            actual = secuenciales[i]
            siguiente = secuenciales[i + 1]
            
            if siguiente - actual > 1:
                for faltante in range(actual + 1, siguiente):
                    faltantes.append(str(faltante).zfill(5))
        
        # Encontrar duplicados
        duplicados = []
        visto = set()
        for sec in secuenciales:
            if sec in visto:
                duplicados.append(str(sec).zfill(5))
            visto.add(sec)
        
        return {
            'total_encontrados': len(secuenciales),
            'primer_secuencial': str(secuenciales[0]).zfill(5) if secuenciales else 'N/A',
            'ultimo_secuencial': str(secuenciales[-1]).zfill(5) if secuenciales else 'N/A',
            'rango_esperado': f"{str(secuenciales[0]).zfill(5)} - {str(secuenciales[-1]).zfill(5)}" if secuenciales else 'N/A',
            'faltantes': faltantes,
            'duplicados': duplicados,
            'es_continuo': len(faltantes) == 0
        }