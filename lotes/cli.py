"""Línea de comandos del motor por lotes:  python -m lotes <orden> …

    inventario RAIZ        recorre el archivo y cuenta por año y tipo (NO abre ningún PDF, salvo con --paginas)
    simular PDF            analiza un libro y muestra qué actos encontraría; no escribe nada
    serie RAIZ             simula todos los libros de un año+tipo en orden, encadenando la numeración; no escribe nada
    dividir PDF            corta el libro en una carpeta de PREPARACIÓN, la verifica y guarda el informe (no toca el original)
    aplicar-libro PDF      divide un libro VIEJO y coloca cada acto en su carpeta (con --si); el original se aparta, no se borra
    verificar CARPETA      vuelve a comprobar una preparación contra el original y las sumas guardadas
    informe CARPETA        muestra el informe guardado

Reglas que no se rompen: nada de esto borra ni modifica un original (solo `aplicar-libro --si` lo aparta, tras verificar). Salida 0 = todo bien; 1 = hay algo que revisar;
2 = error de uso.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from . import analisis, antiguos, informe as inf
from .aplicar import Bloqueado
from .deteccion import detectar_pdf
from .division import ArchivoGenerado, dividir, puede_borrar_original, verificar
from .espacio import Espacio, carpeta_destino
from .codigos import NOTARIA_PROPIA, parse_codigo
from .reglas import Resultado, armar_actos, secuenciales_validos
from .rutas import parse_ruta

GIB = 1024 ** 3


def _error(msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return 2


def _bajar_prioridad(n: int) -> None:
    try:
        os.nice(n)
    except (AttributeError, OSError):  # Windows o sin permiso: se sigue
        pass


def _serie_de(args, pdf: Path) -> tuple[int, str] | None:
    anio, tipo = args.anio, (args.tipo or "").upper() or None
    if (anio is None or tipo is None) and args.raiz:
        try:
            rel = pdf.resolve().relative_to(Path(args.raiz).resolve()).as_posix()
        except ValueError:
            return None
        r = parse_ruta(rel)
        anio = anio if anio is not None else r.anio
        tipo = tipo or r.tipo
    return (anio, tipo) if anio is not None and tipo else None


def _analizar(pdf: Path, anio: int, tipo: str, ultimo_previo, dpi: int, siguientes=None, leido=None,
              manuales=None, recuperar: bool = True) -> Resultado:
    return analisis.analizar(pdf, anio, tipo, ultimo_previo=ultimo_previo, siguientes=siguientes, dpi=dpi,
                             manuales=manuales, recuperar=recuperar, leido=leido)


def _manuales(items, anio: int, tipo: str) -> dict[int, str]:
    """`--codigo-manual 769=1181` (o con el código entero): {hoja: código}. Falla con un mensaje claro si no sirve."""
    salida: dict[int, str] = {}
    for item in items or []:
        try:
            hoja_txt, cod_txt = item.split("=", 1)
            hoja = int(hoja_txt)
        except ValueError:
            raise ValueError(f"«{item}»: use HOJA=CÓDIGO, por ejemplo 769=1181") from None
        cod_txt = cod_txt.strip()
        if cod_txt.isdigit() and len(cod_txt) <= 5:
            cod_txt = f"{anio}{NOTARIA_PROPIA}{tipo}{int(cod_txt):05d}"
        cod = parse_codigo(cod_txt)
        if hoja < 1 or cod is None or cod.notaria != NOTARIA_PROPIA or cod.anio != anio or cod.tipo != tipo:
            raise ValueError(f"«{item}»: debe ser una hoja y un código de la Notaría Séptima, año {anio}, tipo {tipo}")
        salida[hoja] = cod.texto
    return salida


def _resumen_resultado(res: Resultado) -> list[str]:
    d = inf.resultado_a_dict(res)
    info = {
        "original": {"ruta": "", "bytes": 0, "sha256": "0" * 64}, "anio": 0, "tipo": "", "resultado": d,
        "puede_borrar_original": False, "motivos": [],
    }
    t = inf.texto(info).splitlines()
    i = t.index("ACTOS DETECTADOS:")
    fin = next((k for k, x in enumerate(t) if x.startswith("¿SE PUEDE BORRAR")), len(t))
    return t[i:fin]


# ------------------------------------------------------------------ inventario
def cmd_inventario(args) -> int:
    raiz = Path(args.raiz)
    if not raiz.is_dir():
        return _error(f"no existe la carpeta {raiz}")
    series: dict[tuple, dict] = defaultdict(lambda: {"archivos": 0, "bytes": 0, "libros": set(), "paginas": 0, "de_1": 0})
    irregulares: list[tuple[str, str]] = []
    otros: dict[str, int] = defaultdict(int)
    abiertos = 0
    for base, dirs, files in os.walk(raiz, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != "lost+found" and not d.startswith("."))
        for nombre in sorted(files):
            if nombre.startswith("."):
                continue
            ruta = Path(base) / nombre
            ext = ruta.suffix.lower().lstrip(".") or "(sin extensión)"
            if ext != "pdf":
                otros[ext] += 1
                continue
            rel = ruta.relative_to(raiz).as_posix()
            r = parse_ruta(rel)
            if not r.ok:
                irregulares.append((rel, "; ".join(r.problemas)))
                continue
            s = series[(r.anio, r.tipo)]
            s["archivos"] += 1
            s["bytes"] += ruta.stat().st_size
            s["libros"].add((r.mes, r.libro or r.archivo))
            if args.paginas:
                import pymupdf as fitz  # solo aquí se abre un PDF

                try:
                    with fitz.open(str(ruta)) as doc:
                        s["paginas"] += doc.page_count
                        s["de_1"] += doc.page_count == 1
                        abiertos += 1
                except Exception as e:  # PDF dañado: se informa, no se detiene
                    irregulares.append((rel, f"no se pudo abrir: {e}"))
    print(f"INVENTARIO de {raiz}  ({'se abrieron ' + str(abiertos) + ' PDF para contar páginas' if args.paginas else 'no se abrió ningún PDF'})")
    cab = f"  {'año':<5}{'tipo':<5}{'archivos':>9}{'GiB':>9}{'libros/carp.':>14}" + (f"{'páginas':>10}{'de 1 pág.':>11}" if args.paginas else "")
    print(cab)
    tot_a = tot_b = 0
    for (anio, tipo), s in sorted(series.items()):
        linea = f"  {anio:<5}{tipo:<5}{s['archivos']:>9}{s['bytes'] / GIB:>9.2f}{len(s['libros']):>14}"
        if args.paginas:
            linea += f"{s['paginas']:>10}{s['de_1']:>11}"
        print(linea)
        tot_a += s["archivos"]
        tot_b += s["bytes"]
    print(f"  TOTAL: {tot_a} PDF, {tot_b / GIB:.2f} GiB")
    if otros:
        print("  Otros archivos (se ignoran): " + ", ".join(f"{e}: {n}" for e, n in sorted(otros.items())))
    if irregulares:
        print(f"\nIRREGULARES ({len(irregulares)}): no se pueden asignar a año/tipo; hay que revisarlos a mano")
        for rel, why in irregulares[: args.maximo]:
            print(f"  {rel}  —  {why}")
        if len(irregulares) > args.maximo:
            print(f"  … y {len(irregulares) - args.maximo} más")
    return 1 if irregulares else 0


# ------------------------------------------------------------------ simular
def cmd_simular(args) -> int:
    pdf = Path(args.pdf)
    if not pdf.is_file():
        return _error(f"no existe {pdf}")
    serie = _serie_de(args, pdf)
    if not serie:
        return _error("indique --anio y --tipo (o --raiz para sacarlos de la ruta)")
    try:
        manuales = _manuales(args.codigo_manual, serie[0], serie[1])
    except ValueError as e:
        return _error(str(e))
    _bajar_prioridad(args.nice)
    res = _analizar(pdf, serie[0], serie[1], args.ultimo_previo, args.dpi, manuales=manuales,
                    recuperar=not args.sin_recuperar)
    print(f"SIMULACIÓN (no se escribió nada) — {pdf.name} · {res.total_paginas} páginas · serie {serie[0]} {serie[1]}")
    print("\n".join(_resumen_resultado(res)))
    if res.ajenos:
        print("\nNo abren acto:")
        print("\n".join(f"  página {p}: {c} — {m}" for p, c, m in res.ajenos))
    for bloque, titulo in ((res.saltos, "Huecos de numeración"), (res.avisos, "Avisos")):
        if bloque:
            print(f"\n{titulo}:")
            print("\n".join(f"  {x}" for x in bloque))
    return 1 if res.requiere_revision else 0


# ------------------------------------------------------------------ serie
def _libros_de_serie(raiz: Path, anio: int, tipo: str) -> list:
    """Los PDF de una serie (año+tipo) en su orden natural: [(orden, ruta, RutaLibro)]."""
    libros = []
    for base, dirs, files in os.walk(raiz, followlinks=False):
        dirs[:] = [d for d in dirs if d != "lost+found" and not d.startswith(".")]
        for nombre in files:
            if nombre.lower().endswith(".pdf") and not nombre.startswith("."):
                p = Path(base) / nombre
                r = parse_ruta(p.relative_to(raiz).as_posix())
                if r.ok and r.serie == (anio, tipo):
                    libros.append((r.orden, p, r))
    libros.sort(key=lambda x: x[0])
    return libros


def cmd_serie(args) -> int:
    raiz = Path(args.raiz)
    if not raiz.is_dir():
        return _error(f"no existe la carpeta {raiz}")
    tipo = args.tipo.upper()
    libros = _libros_de_serie(raiz, args.anio, tipo)
    if not libros:
        return _error(f"no hay PDF de la serie {args.anio} {tipo} en {raiz}")
    _bajar_prioridad(args.nice)
    ultimo = args.ultimo_previo
    print(f"SERIE {args.anio} {tipo}: {len(libros)} PDF en orden (no se escribe nada)")
    pendientes = 0
    leido = detectar_pdf(libros[0][1], dpi=args.dpi, usar_texto=True)
    for i, (_, p, r) in enumerate(libros):
        # Se lee también el libro que sigue: su comienzo permite reconocer un código suelto al final de este.
        siguiente = detectar_pdf(libros[i + 1][1], dpi=args.dpi, usar_texto=True) if i + 1 < len(libros) else None
        sig = secuenciales_validos(siguiente[1], args.anio, tipo) if siguiente else None
        res = _analizar(p, args.anio, tipo, ultimo, args.dpi, siguientes=sig, leido=leido, recuperar=not args.sin_recuperar)
        leido = siguiente
        marca = "REVISAR" if res.requiere_revision else "ok"
        rango = (f"{res.actos[0].codigo.secuencial:05d}–{res.actos[-1].codigo.secuencial:05d}" if res.actos else "sin actos")
        print(f"  [{marca:>7}] {r.relativa}: {res.total_paginas} pág., {len(res.actos)} actos ({rango})")
        for s in res.saltos + res.avisos:
            print(f"            · {s}")
        if res.huerfanas:
            print(f"            · páginas {res.huerfanas[0]}-{res.huerfanas[1]} sin código al inicio")
        pendientes += res.requiere_revision
        if res.ultimo_secuencial is not None:
            ultimo = res.ultimo_secuencial
    print(f"\n{len(libros) - pendientes} libros sin observaciones, {pendientes} para revisar. Último secuencial: "
          + (f"{ultimo:05d}" if ultimo is not None else "—"))
    return 1 if pendientes else 0


# ------------------------------------------------------------------ dividir
def cmd_dividir(args) -> int:
    pdf = Path(args.pdf)
    if not pdf.is_file():
        return _error(f"no existe {pdf}")
    serie = _serie_de(args, pdf)
    if not serie:
        return _error("indique --anio y --tipo (o --raiz para sacarlos de la ruta)")
    prep = Path(args.preparacion) if args.preparacion else pdf.parent / f"_division_{pdf.stem}"
    if prep.exists() and any(prep.iterdir()):
        return _error(f"la carpeta de preparación {prep} ya existe y no está vacía: no se sobrescribe")
    try:
        manuales = _manuales(args.codigo_manual, serie[0], serie[1])
    except ValueError as e:
        return _error(str(e))
    _bajar_prioridad(args.nice)
    st0 = pdf.stat()
    sha0 = inf.sha256_archivo(pdf)
    res = _analizar(pdf, serie[0], serie[1], args.ultimo_previo, args.dpi, manuales=manuales,
                    recuperar=not args.sin_recuperar)
    if not res.actos:
        print("No se encontró ningún código de acto en el libro: no se divide (revise la simulación).")
        return 1
    generados = dividir(pdf, res, prep)
    ver = verificar(pdf, res, generados)
    st1 = pdf.stat()
    if (st1.st_size, st1.st_mtime_ns) != (st0.st_size, st0.st_mtime_ns):
        ver.problemas.append("el original cambió mientras se dividía")
    puede, motivos = puede_borrar_original(res, ver)
    info = {
        "version": inf.VERSION,
        "creado": datetime.now().isoformat(timespec="seconds"),
        "original": {"ruta": str(pdf), "bytes": st0.st_size, "sha256": sha0, "paginas": res.total_paginas},
        "anio": serie[0], "tipo": serie[1], "ultimo_previo": args.ultimo_previo,
        "preparacion": str(prep),
        "resultado": inf.resultado_a_dict(res),
        "generados": [
            {"nombre": g.nombre, "inicio": g.inicio, "fin": g.fin, "bytes": g.ruta.stat().st_size, "sha256": inf.sha256_archivo(g.ruta)}
            for g in generados
        ],
        "verificacion": {"correcta": ver.correcta, "problemas": ver.problemas,
                         "paginas_originales": ver.paginas_originales, "paginas_generadas": ver.paginas_generadas},
        "puede_borrar_original": puede, "motivos": motivos,
    }
    inf.guardar(prep, info)
    print(inf.texto(info))
    return 0 if puede else 1


# ------------------------------------------------------------------ aplicar-libro
def cmd_aplicar_libro(args) -> int:
    """Libro VIEJO: sin --si solo muestra el plan; con --si divide, verifica, coloca los actos y aparta el original."""
    pdf, raiz, datos = Path(args.pdf), Path(args.raiz), Path(args.datos)
    if not pdf.is_file():
        return _error(f"no existe {pdf}")
    if not raiz.is_dir():
        return _error(f"no existe la raíz del archivo {raiz}")
    esp = Espacio(datos, raiz)
    try:
        anio, tipo, mes, libro_p = antiguos.deducir(esp, pdf)
    except ValueError as e:
        return _error(f"no se pudo ubicar el libro en el archivo: {e}")
    try:
        manuales = _manuales(args.codigo_manual, anio, tipo)
    except ValueError as e:
        return _error(str(e))
    mes, libro = args.mes or mes, args.libro or libro_p
    if mes is None or libro is None:
        return _error("no se pudo deducir el " + ("mes" if mes is None else "número de libro")
                      + " del nombre: indíquelo con --" + ("mes" if mes is None else "libro"))
    try:
        destino = carpeta_destino(esp, anio, tipo, mes, libro)
    except ValueError as e:
        return _error(str(e))
    siguientes = None
    if args.auto_siguiente:
        libros = _libros_de_serie(raiz, anio, tipo)
        rutas = [p.resolve() for _, p, _ in libros]
        i = rutas.index(pdf.resolve()) if pdf.resolve() in rutas else -1
        if 0 <= i + 1 < len(libros):
            _, det_sig = detectar_pdf(libros[i + 1][1], dpi=args.dpi, usar_texto=True)
            siguientes = secuenciales_validos(det_sig, anio, tipo)
    _bajar_prioridad(args.nice)

    if not args.si:
        res = _analizar(pdf, anio, tipo, args.ultimo_previo, args.dpi, siguientes=siguientes, manuales=manuales,
                        recuperar=not args.sin_recuperar)
        print(f"PLAN (no se escribió nada) — {pdf.name} · {res.total_paginas} páginas · serie {anio} {tipo}")
        print(f"Los actos se colocarían en: {destino}")
        print(f"El original se apartaría en: {esp.espera / 'originales' / antiguos._relativa(esp, pdf)}")
        print("\n".join(_resumen_resultado(res)))
        for bloque, titulo in ((res.ajenos, "No abren acto"), (res.saltos, "Huecos de numeración"), (res.avisos, "Avisos")):
            if bloque:
                print(f"\n{titulo}:")
                print("\n".join(f"  {x if isinstance(x, str) else 'página %s: %s — %s' % x}" for x in bloque))
        print("\nPara colocarlo de verdad, repita la orden con --si" + (" --aceptar-revision" if res.requiere_revision else "") + ".")
        return 1 if res.requiere_revision else 0

    esp.asegurar()
    try:
        info = antiguos.preparar(esp, pdf, anio, tipo, args.ultimo_previo, siguientes, args.dpi, manuales=manuales,
                                 recuperar=not args.sin_recuperar, rehacer=bool(manuales))
    except ValueError as e:
        return _error(str(e))
    if info.get("sin_actos"):
        print("No se encontró ningún código de acto en el libro: no se divide ni se coloca nada.")
        return 1
    print(inf.texto(info))
    try:
        hecho = antiguos.aplicar(esp, info["lote"], mes, libro, args.aceptar_revision)
    except Bloqueado as e:
        print("\nNO SE COLOCÓ NADA:\n" + "\n".join(f"  · {m}" for m in e.motivos))
        print(f"La preparación quedó en {esp.preparacion / info['lote']} (se puede revisar con «informe»).")
        return 1
    print(f"\nCOLOCADO: {len(hecho['archivos'])} archivos en {hecho['destino']}")
    print(f"El original quedó apartado en {hecho.get('original_en_espera')} (no se borró).")
    return 0


# ------------------------------------------------------------------ verificar / informe
def cmd_verificar(args) -> int:
    carpeta = Path(args.carpeta)
    try:
        info = inf.cargar(carpeta)
    except (OSError, ValueError) as e:
        return _error(f"no se pudo leer el informe de {carpeta}: {e}")
    original = Path(info["original"]["ruta"])
    problemas: list[str] = []
    res = inf.resultado_desde_dict(info["resultado"])
    generados = [ArchivoGenerado(g["nombre"], carpeta / g["nombre"], g["inicio"], g["fin"]) for g in info["generados"]]
    if not original.is_file():
        problemas.append(f"el original ya no está en {original}")
    else:
        if original.stat().st_size != info["original"]["bytes"] or inf.sha256_archivo(original) != info["original"]["sha256"]:
            problemas.append("el original no es el mismo que se dividió (cambió su contenido)")
    for g, esperado in zip(generados, info["generados"]):
        if not g.ruta.is_file():
            problemas.append(f"{g.nombre}: no existe")
        elif inf.sha256_archivo(g.ruta) != esperado["sha256"]:
            problemas.append(f"{g.nombre}: su suma sha256 ya no coincide con la guardada (se dañó o lo cambiaron)")
    if original.is_file() and not problemas:
        v = verificar(original, res, generados)
        problemas += v.problemas
        info["verificacion"] = {"correcta": v.correcta, "problemas": v.problemas,
                                "paginas_originales": v.paginas_originales, "paginas_generadas": v.paginas_generadas}
    else:
        info["verificacion"] = {"correcta": False, "problemas": problemas, "paginas_originales": 0, "paginas_generadas": 0}
    info["verificacion"]["problemas"] = problemas
    info["verificacion"]["correcta"] = not problemas
    from .division import Verificacion

    puede, motivos = puede_borrar_original(res, Verificacion(problemas=problemas))
    info["puede_borrar_original"], info["motivos"] = puede, motivos
    info["verificado"] = datetime.now().isoformat(timespec="seconds")
    inf.guardar(carpeta, info)
    print(inf.texto(info))
    return 0 if puede else 1


def cmd_informe(args) -> int:
    try:
        info = inf.cargar(args.carpeta)
    except (OSError, ValueError) as e:
        return _error(f"no se pudo leer el informe: {e}")
    print(inf.texto(info))
    return 0


# ------------------------------------------------------------------ main
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m lotes", description="Divide libros escaneados por acto (solo lectura sobre los originales).")
    sub = p.add_subparsers(dest="orden", required=True)

    def comunes(sp, pdf=False):
        sp.add_argument("--anio", type=int, help="año del libro (si no, sale de la ruta con --raiz)")
        sp.add_argument("--tipo", help="P, D, C, A u O (si no, sale de la ruta con --raiz)")
        sp.add_argument("--ultimo-previo", type=int, default=None, help="último secuencial del libro anterior de la serie")
        sp.add_argument("--dpi", type=int, default=200, help="resolución para leer los códigos de barras (200)")
        sp.add_argument("--nice", type=int, default=10, help="baja la prioridad del proceso (0 = normal)")
        if pdf:
            sp.add_argument("--raiz", help="raíz del archivo, para deducir año y tipo de la ruta del PDF")
            sp.add_argument("--codigo-manual", action="append", metavar="HOJA=CÓDIGO",
                            help="código de una hoja que el programa no leyó, p. ej. 769=1181 (se puede repetir)")
        sp.add_argument("--sin-recuperar", action="store_true",
                        help="no volver a leer con más esfuerzo las hojas de los huecos de numeración")

    s = sub.add_parser("inventario", help="cuenta lo que hay por año y tipo")
    s.add_argument("raiz")
    s.add_argument("--paginas", action="store_true", help="ABRE cada PDF para contar sus páginas (más lento)")
    s.add_argument("--maximo", type=int, default=40, help="cuántos irregulares listar")
    s.set_defaults(f=cmd_inventario)

    s = sub.add_parser("simular", help="qué actos encontraría en un libro")
    s.add_argument("pdf")
    comunes(s, pdf=True)
    s.set_defaults(f=cmd_simular)

    s = sub.add_parser("serie", help="simula todos los libros de un año y tipo, en orden")
    s.add_argument("raiz")
    s.add_argument("--anio", type=int, required=True)
    s.add_argument("--tipo", required=True)
    s.add_argument("--ultimo-previo", type=int, default=None)
    s.add_argument("--dpi", type=int, default=200)
    s.add_argument("--nice", type=int, default=10)
    s.add_argument("--sin-recuperar", action="store_true", help="no volver a leer con más esfuerzo las hojas de los huecos")
    s.set_defaults(f=cmd_serie)

    s = sub.add_parser("dividir", help="corta un libro en una carpeta de preparación y la verifica")
    s.add_argument("pdf")
    s.add_argument("--preparacion", help="carpeta de salida (por omisión «_division_<nombre>» junto al PDF)")
    comunes(s, pdf=True)
    s.set_defaults(f=cmd_dividir)

    s = sub.add_parser("aplicar-libro", help="divide un libro viejo y coloca sus actos (con --si)")
    s.add_argument("pdf")
    s.add_argument("--raiz", required=True, help="raíz del archivo escaneado (donde están las carpetas de los años)")
    s.add_argument("--datos", required=True, help="carpeta de trabajo (preparación y espera)")
    s.add_argument("--libro", type=int, default=None, help="número de libro (por omisión, el que diga el nombre del archivo)")
    s.add_argument("--mes", type=int, default=None, help="mes 1-12 (por omisión, el de la carpeta)")
    s.add_argument("--ultimo-previo", type=int, default=None, help="último secuencial del libro anterior de la serie")
    s.add_argument("--auto-siguiente", action="store_true", help="lee también el libro que sigue para reconocer un suelto al final")
    s.add_argument("--si", action="store_true", help="ejecuta de verdad (sin esto solo muestra el plan)")
    s.add_argument("--aceptar-revision", action="store_true", help="coloca aunque el libro tenga huecos, avisos u hojas sin código")
    s.add_argument("--codigo-manual", action="append", metavar="HOJA=CÓDIGO",
                   help="código de una hoja que el programa no leyó, p. ej. 769=1181 (se puede repetir)")
    s.add_argument("--sin-recuperar", action="store_true", help="no volver a leer con más esfuerzo las hojas de los huecos")
    s.add_argument("--dpi", type=int, default=200)
    s.add_argument("--nice", type=int, default=10)
    s.set_defaults(f=cmd_aplicar_libro)

    s = sub.add_parser("verificar", help="vuelve a comprobar una preparación")
    s.add_argument("carpeta")
    s.set_defaults(f=cmd_verificar)

    s = sub.add_parser("informe", help="muestra el informe de una preparación")
    s.add_argument("carpeta")
    s.set_defaults(f=cmd_informe)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if getattr(args, "tipo", None) and args.tipo.upper() not in {"P", "D", "C", "A", "O"}:
        return _error("el tipo debe ser P, D, C, A u O")
    return args.f(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
