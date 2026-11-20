"""Libro abierto: escaneo en vivo que se divide solo, acto por acto, mientras se escanea.

Se abre UN libro (año, tipo, mes, número) y todas las tandas de hojas que se escaneen se unen a él:

  · Un acto se cierra y se guarda en el archivo cuando aparece el código del siguiente.
  · El último acto de cada tanda queda ABIERTO (sus páginas se conservan en `libro/abierto.pdf`): la tanda siguiente
    puede traer sus últimas hojas, que no llevan código, y así un acto partido entre dos tandas sale completo.
  · «Fin de libro» cierra y guarda el acto que quedó abierto.
  · Si la tanda está limpia (numeración seguida, sin avisos, sin hojas pegadas ni páginas sin código) se guarda sola.
    Si algo no cuadra queda «por revisar»: no se guarda ni se pierde nada hasta que una persona la apruebe o la descarte.
  · Mientras haya una tanda por revisar no se escanea otra (el orden de las hojas importa para el acto abierto).

Garantías: nada se borra (los PDF escaneados se apartan en `espera/`), nada se sobrescribe, cada copia se compara con su
sha256, y repetir una orden tras un corte a mitad termina el trabajo sin duplicar (cada tanda queda anotada en el estado).
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore

from . import informe as inf
from .aplicar import Bloqueado, _copiar_sin_pisar
from .codigos import parse_codigo
from .deteccion import detectar_pdf
from .division import Verificacion, dividir, verificar
from .entrada import aviso, listar
from .espacio import Espacio, carpeta_destino, validar_id
from .reglas import DeteccionPagina, armar_actos


def _carpeta(espacio: Espacio) -> Path:
    return espacio.datos / "libro"


def _escribir_json(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name("." + ruta.name + ".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ruta)


def estado(espacio: Espacio) -> dict | None:
    """El libro abierto, o None si no hay ninguno."""
    try:
        return json.loads((_carpeta(espacio) / "estado.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def abrir_libro(espacio: Espacio, anio: int, tipo: str, mes: int, libro: int) -> dict:
    if estado(espacio):
        raise ValueError("ya hay un libro abierto; ciérrelo con «Fin de libro» antes de abrir otro")
    carpeta_destino(espacio, anio, tipo, mes, libro)  # valida año, tipo, mes y libro
    s = {
        "anio": anio, "tipo": tipo, "mes": mes, "libro": libro,
        "abierto_en": datetime.now().isoformat(timespec="seconds"),
        "ultimo_antes_abierto": espacio.ultimo(anio, tipo),
        "acto_abierto": None,   # {"codigo": …, "paginas": n} mientras haya un acto sin cerrar
        "guardados": [],        # [{"codigo", "paginas", "lote"}]
        "lotes": [],            # tandas ya procesadas (para no repetir tras un corte)
        "tandas": 0,
    }
    _escribir_json(_carpeta(espacio) / "estado.json", s)
    return s


def pendientes(espacio: Espacio) -> list[dict]:
    """Tandas en la carpeta de entrada que todavía no se procesan, en el orden en que se escanearon."""
    s = estado(espacio)
    hechos = set(s["lotes"]) if s else set()
    return [l for l in listar(espacio) if l["id"] not in hechos]


def _terminar_aparte(espacio: Espacio, lote_id: str) -> None:
    """Aparta el PDF escaneado (y su aviso) en `espera/`. Nunca borra."""
    origen = espacio.entrada / f"{lote_id}.pdf"
    if not origen.is_file():
        return
    destino = espacio.espera / f"{lote_id}.pdf"
    n = 1
    while destino.exists():
        n += 1
        destino = espacio.espera / f"{lote_id}_{n}.pdf"
    shutil.move(str(origen), str(destino))
    nota = espacio.entrada / f"{lote_id}.aviso"
    if nota.is_file():
        shutil.move(str(nota), str(destino.with_suffix(".aviso")))


def _combinar(espacio: Espacio, s: dict, pdf: Path, destino: Path) -> int:
    """Une las páginas del acto abierto con las de la tanda nueva. Devuelve cuántas páginas venían del acto abierto."""
    n0 = 0
    doc = fitz.open()
    try:
        if s["acto_abierto"]:
            with fitz.open(str(_carpeta(espacio) / "abierto.pdf")) as previo:
                n0 = previo.page_count
                doc.insert_pdf(previo)
        with fitz.open(str(pdf)) as nuevo:
            doc.insert_pdf(nuevo)
        doc.save(str(destino), garbage=0, deflate=False)
    finally:
        doc.close()
    return n0


def procesar(espacio: Espacio, lote_id: str, aceptar: bool = False) -> dict:
    """Une la tanda al libro abierto, cierra los actos completos y guarda los que estén limpios.

    Devuelve {"estado": "guardado" | "revision" | "error", "guardados": [códigos], "abierto": código | None,
              "motivos": [...], "lote": id}.
    """
    validar_id(lote_id)
    s = estado(espacio)
    if not s:
        raise ValueError("no hay un libro abierto")
    if lote_id in s["lotes"]:  # ya estaba procesada; si el corte fue antes de apartarla, se termina ahora
        _terminar_aparte(espacio, lote_id)
        return {"estado": "guardado", "lote": lote_id, "guardados": [], "abierto": (s["acto_abierto"] or {}).get("codigo"),
                "motivos": [], "repetido": True}
    pdf = espacio.entrada / f"{lote_id}.pdf"
    if not pdf.is_file():
        raise FileNotFoundError(f"no existe la tanda {lote_id}")

    prep = espacio.preparacion / lote_id
    if prep.exists():
        shutil.rmtree(prep)  # solo lo derivado; el PDF escaneado no se toca
    prep.mkdir(parents=True)
    comb = prep / "combinado.pdf"
    n0 = _combinar(espacio, s, pdf, comb)

    total_b, det_b = detectar_pdf(pdf, dpi=200, usar_texto=True)
    det = [DeteccionPagina(d.pagina + n0, d.barras, d.textos) for d in det_b]
    if n0:  # la primera página del acto abierto ya trae su código conocido
        det.insert(0, DeteccionPagina(1, barras=(s["acto_abierto"]["codigo"],)))
    total = n0 + total_b
    res = armar_actos(det, total, s["anio"], s["tipo"], ultimo_previo=s["ultimo_antes_abierto"])

    nota = aviso(espacio, lote_id)
    revision: list[str] = []
    if not res.actos:
        revision.append("no se encontró ningún código de acto en esta tanda")
    if res.huerfanas and res.actos:
        revision.append(f"las páginas {res.huerfanas[0]}–{res.huerfanas[1]} quedan antes del primer código")
    revision += res.saltos + res.avisos
    if any(a.confianza == "baja" for a in res.actos):
        revision.append("hay actos con lectura de código dudosa")
    if nota:
        revision.append(nota)

    generados = dividir(comb, res, prep) if res.actos else []
    ver = verificar(comb, res, generados) if generados else Verificacion()
    info = {
        "version": inf.VERSION, "creado": datetime.now().isoformat(timespec="seconds"), "lote": lote_id,
        "libro_abierto": True, "n0": n0,
        "original": {"ruta": str(comb), "bytes": comb.stat().st_size, "sha256": inf.sha256_archivo(comb), "paginas": total},
        "anio": s["anio"], "tipo": s["tipo"], "ultimo_previo": s["ultimo_antes_abierto"],
        "resultado": inf.resultado_a_dict(res),
        "generados": [{"nombre": g.nombre, "inicio": g.inicio, "fin": g.fin, "bytes": g.ruta.stat().st_size,
                       "sha256": inf.sha256_archivo(g.ruta)} for g in generados],
        "verificacion": {"correcta": ver.correcta, "problemas": ver.problemas,
                         "paginas_originales": ver.paginas_originales, "paginas_generadas": ver.paginas_generadas},
        "motivos_revision": revision,
    }
    inf.guardar(prep, info)
    base = {"lote": lote_id, "guardados": [], "abierto": None, "motivos": revision}
    if ver.problemas:  # esto no se puede aceptar: algo salió mal al cortar
        return {**base, "estado": "error", "motivos": ver.problemas}
    if not res.actos:  # sin ningún código no hay nada que cerrar ni abrir: solo se puede descartar y volver a escanear
        return {**base, "estado": "revision", "puede_aceptar": False}
    if revision and not aceptar:
        return {**base, "estado": "revision", "puede_aceptar": True}
    return _confirmar(espacio, s, lote_id, res, prep, info, aceptada=bool(revision))


def _confirmar(espacio: Espacio, s: dict, lote_id: str, res, prep: Path, info: dict, aceptada: bool) -> dict:
    cerrados = res.actos[:-1]
    abierto = res.actos[-1] if res.actos else None
    destino = carpeta_destino(espacio, s["anio"], s["tipo"], s["mes"], s["libro"])
    destino.mkdir(parents=True, exist_ok=True)
    generados = {g["nombre"]: g for g in info["generados"]}
    copiados = []
    for a in cerrados:
        nombre = a.codigo.texto + ".pdf"
        _copiar_sin_pisar(prep / nombre, destino / nombre, generados[nombre]["sha256"])
        copiados.append({"codigo": a.codigo.texto, "paginas": a.paginas, "lote": lote_id})
    if res.huerfanas and "SIN_CODIGO.pdf" in generados:
        _copiar_sin_pisar(prep / "SIN_CODIGO.pdf", destino / f"SIN_CODIGO_{lote_id}.pdf", generados["SIN_CODIGO.pdf"]["sha256"])

    nuevo = dict(s)
    if abierto:
        ruta_ab = _carpeta(espacio) / "abierto.pdf"
        tmp = ruta_ab.with_name(".abierto.pdf.tmp")
        shutil.copyfile(prep / f"{abierto.codigo.texto}.pdf", tmp)
        if inf.sha256_archivo(tmp) != generados[f"{abierto.codigo.texto}.pdf"]["sha256"]:
            tmp.unlink(missing_ok=True)
            raise Bloqueado(["no se pudo conservar el acto abierto; no se guardó nada nuevo en el estado"])
        os.replace(tmp, ruta_ab)
        nuevo["acto_abierto"] = {"codigo": abierto.codigo.texto, "paginas": abierto.paginas}
        if len(res.actos) >= 2:
            nuevo["ultimo_antes_abierto"] = res.actos[-2].codigo.secuencial
    else:  # tanda sin ningún acto (solo se llega aquí si la persona aceptó guardar las páginas sin código)
        (_carpeta(espacio) / "abierto.pdf").unlink(missing_ok=True)
        nuevo["acto_abierto"] = None
    nuevo["guardados"] = s["guardados"] + copiados
    nuevo["lotes"] = (s["lotes"] + [lote_id])[-500:]
    nuevo["tandas"] = s["tandas"] + 1
    _escribir_json(_carpeta(espacio) / "estado.json", nuevo)  # desde aquí la tanda cuenta como procesada

    if cerrados:
        espacio.registrar_ultimo(s["anio"], s["tipo"], cerrados[-1].codigo.secuencial)
    _escribir_json(prep / "aplicado.json", {
        "lote": lote_id, "fecha": datetime.now().isoformat(timespec="seconds"), "anio": s["anio"], "tipo": s["tipo"],
        "mes": s["mes"], "libro": s["libro"], "destino": str(destino), "guardados": copiados,
        "abierto": abierto.codigo.texto if abierto else None, "revision_aceptada": aceptada,
        "motivos_revision": info.get("motivos_revision", []),
    })
    _terminar_aparte(espacio, lote_id)
    return {"estado": "guardado", "lote": lote_id, "guardados": [c["codigo"] for c in copiados],
            "abierto": abierto.codigo.texto if abierto else None, "motivos": info.get("motivos_revision", [])}


def procesar_pendientes(espacio: Espacio) -> list[dict]:
    """Procesa en orden las tandas que esperan; se detiene en la primera que quede por revisar o falle."""
    salidas = []
    for l in pendientes(espacio):
        r = procesar(espacio, l["id"])
        salidas.append(r)
        if r["estado"] != "guardado":
            break
    return salidas


def descartar(espacio: Espacio, lote_id: str) -> Path:
    """Aparta una tanda que no se va a usar (por ejemplo, para escanearla de nuevo). No cambia el libro ni borra nada."""
    validar_id(lote_id)
    s = estado(espacio)
    if s and lote_id in s["lotes"]:
        raise ValueError("esta tanda ya se guardó en el libro")
    origen = espacio.entrada / f"{lote_id}.pdf"
    if not origen.is_file():
        raise FileNotFoundError(lote_id)
    carpeta = espacio.espera / "descartadas"
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{lote_id}.pdf"
    n = 1
    while destino.exists():
        n += 1
        destino = carpeta / f"{lote_id}_{n}.pdf"
    shutil.move(str(origen), str(destino))
    for sufijo in (".aviso",):
        extra = espacio.entrada / f"{lote_id}{sufijo}"
        if extra.is_file():
            shutil.move(str(extra), str(destino.with_suffix(sufijo)))
    prep = espacio.preparacion / lote_id
    if prep.exists() and not (prep / "aplicado.json").exists():
        shutil.rmtree(prep)
    return destino


def cerrar_libro(espacio: Espacio) -> dict:
    """«Fin de libro»: guarda el acto que quedó abierto y deja el sistema sin libro abierto."""
    s = estado(espacio)
    if not s:
        raise ValueError("no hay un libro abierto")
    if pendientes(espacio):
        raise Bloqueado(["hay tandas por revisar: apruébelas o descártelas antes de cerrar el libro"])
    destino = carpeta_destino(espacio, s["anio"], s["tipo"], s["mes"], s["libro"])
    guardado = None
    a = s["acto_abierto"]
    if a:
        destino.mkdir(parents=True, exist_ok=True)
        origen = _carpeta(espacio) / "abierto.pdf"
        nombre = a["codigo"] + ".pdf"
        _copiar_sin_pisar(origen, destino / nombre, inf.sha256_archivo(origen))
        cod = parse_codigo(a["codigo"])
        espacio.registrar_ultimo(s["anio"], s["tipo"], cod.secuencial)
        guardado = {"codigo": a["codigo"], "paginas": a["paginas"], "lote": "fin_de_libro"}
        s["guardados"] = s["guardados"] + [guardado]
        extra = espacio.espera / f"acto_abierto_{a['codigo']}.pdf"
        shutil.move(str(origen), str(extra))
    s["cerrado_en"] = datetime.now().isoformat(timespec="seconds")
    s["acto_abierto"] = None
    _escribir_json(_carpeta(espacio) / "historial" / f"{s['cerrado_en'].replace(':', '')}_{s['anio']}{s['tipo']}_libro{s['libro']}.json", s)
    (_carpeta(espacio) / "estado.json").unlink(missing_ok=True)
    return {"libro": s["libro"], "actos": len(s["guardados"]), "ultimo": guardado, "destino": str(destino)}
