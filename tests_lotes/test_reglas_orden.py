"""Código suelto con número adelantado: no abre acto ni hace perder los actos reales que siguen (caso real 2026)."""
from lotes.reglas import DeteccionPagina, _cadena_creciente, armar_actos, secuenciales_validos

A, T = 2026, "D"


def c(sec, anio=A, tipo=T):
    return f"{anio}1101007{tipo}{sec:05d}"


def libro(secuencia, paso=3):
    """Una página con código cada `paso` páginas; `secuencia` = secuenciales en orden."""
    dets = [DeteccionPagina(pagina=1 + i * paso, barras=(c(s),)) for i, s in enumerate(secuencia)]
    return dets, 1 + len(secuencia) * paso


def secs(res):
    return [a.codigo.secuencial for a in res.actos]


def test_codigo_suelto_adelantado_en_medio_no_abre_acto():
    dets, total = libro([113, 114, 115, 260, 116, 117])  # el 260 está en la 4.ª posición (caso «dili 3 enero»)
    res = armar_actos(dets, total, A, T)
    assert secs(res) == [113, 114, 115, 116, 117]
    assert [(p, t[-5:]) for p, t, _ in res.ajenos] == [(10, "00260")]
    assert "fuera de orden" in res.ajenos[0][2]
    assert res.requiere_revision and any("fuera de orden" in a for a in res.avisos)  # no se calla
    assert not res.saltos  # la numeración quedó seguida: 113…117
    assert res.ultimo_secuencial == 117
    # la página del suelto no se pierde: queda dentro del acto 115
    assert (res.actos[2].inicio, res.actos[2].fin) == (7, 12)  # el acto 115 incluye la hoja 10 del suelto


def test_el_libro_siguiente_ya_no_pierde_sus_actos_por_el_suelto_del_anterior():
    # Libro 1: …157, [260 suelto], 158. Libro 2 empieza en 159. (Antes salía «sin actos».)
    l1, t1 = libro([155, 156, 157, 260, 158])
    r1 = armar_actos(l1, t1, A, T)
    assert secs(r1) == [155, 156, 157, 158] and r1.ultimo_secuencial == 158
    l2, t2 = libro([159, 160, 161])
    r2 = armar_actos(l2, t2, A, T, ultimo_previo=r1.ultimo_secuencial)
    assert secs(r2) == [159, 160, 161] and not r2.requiere_revision


def test_suelto_al_final_del_libro_se_reconoce_con_el_comienzo_del_siguiente():
    l1, t1 = libro([10, 11, 12, 900])
    sin = armar_actos(l1, t1, A, T)  # sin ver el siguiente no se puede saber
    assert secs(sin) == [10, 11, 12, 900] and sin.saltos
    l2, _ = libro([13, 14, 15])
    con = armar_actos(l1, t1, A, T, siguientes=secuenciales_validos(l2, A, T))
    assert secs(con) == [10, 11, 12] and con.ultimo_secuencial == 12
    assert con.requiere_revision and not con.saltos


def test_empate_gana_el_menor_sin_conocer_el_siguiente():
    dets, total = libro([157, 260, 158])
    res = armar_actos(dets, total, A, T, ultimo_previo=156)
    assert secs(res) == [157, 158]


def test_un_salto_real_sin_regreso_sigue_siendo_salto_y_no_suelto():
    dets, total = libro([1, 2, 50, 51, 52])
    res = armar_actos(dets, total, A, T)
    assert secs(res) == [1, 2, 50, 51, 52]
    assert res.saltos == ["faltan 00003–00049 antes de 20261101007D00050 (página 7)"]
    assert not res.ajenos


def test_secuencia_normal_no_cambia_nada():
    dets, total = libro(list(range(1, 11)))
    res = armar_actos(dets, total, A, T)
    assert secs(res) == list(range(1, 11)) and not res.requiere_revision and not res.ajenos


def test_el_repetido_se_queda_con_el_primero():
    dets = [DeteccionPagina(1, (c(5),)), DeteccionPagina(4, (c(5),)), DeteccionPagina(7, (c(6),))]
    res = armar_actos(dets, 9, A, T)
    assert secs(res) == [5, 6]
    assert [a.inicio for a in res.actos] == [1, 7]


def test_suelto_antes_del_primer_acto_queda_como_huerfana_y_se_avisa():
    dets, total = libro([900, 1, 2, 3])
    res = armar_actos(dets, total, A, T)
    assert secs(res) == [1, 2, 3] and res.huerfanas == (1, 3)
    assert res.requiere_revision


def test_los_habilitantes_menores_siguen_como_antes():
    dets = [DeteccionPagina(1, (c(20),)), DeteccionPagina(3, (c(5),)), DeteccionPagina(6, (c(21),))]
    res = armar_actos(dets, 8, A, T, ultimo_previo=19)
    assert secs(res) == [20, 21]
    assert "no supera al último" in res.ajenos[0][2]
    assert not res.avisos  # un habilitante menor es normal: no deja el libro en revisión


def test_cobertura_completa_con_suelto():
    dets, total = libro([1, 2, 800, 3, 4])
    res = armar_actos(dets, total - 1, A, T)
    paginas = []
    for ini, fin, _ in res.cobertura():
        paginas += range(ini, fin + 1)
    assert paginas == list(range(1, res.total_paginas + 1))


def test_secuenciales_validos_ignora_otras_notarias_y_otros_tipos():
    dets = [DeteccionPagina(1, (c(7),)), DeteccionPagina(2, (c(8, tipo="P"),)),
            DeteccionPagina(3, ("20261101010D00009",)), DeteccionPagina(5, (c(9),))]
    assert secuenciales_validos(dets, A, T) == [7, 9]


def test_entre_cadenas_igual_de_largas_gana_la_mas_apretada():
    # [20, 40] y [10, 11] miden 2; la segunda sigue la numeración casi sin saltos
    assert _cadena_creciente([(1, 20), (2, 40), (3, 10), (4, 11)]) == {3, 4}


def test_la_cadena_arranca_en_el_ultimo_del_libro_anterior():
    dets, total = libro([900, 101])  # el último del libro anterior fue el 100
    res = armar_actos(dets, total, A, T, ultimo_previo=100)
    assert secs(res) == [101] and [t[-5:] for _, t, _ in res.ajenos] == ["00900"]
