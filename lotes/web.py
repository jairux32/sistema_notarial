"""Pantalla web del separador: escanear, revisar lo que el programa encontró y guardar en el archivo.

Para la red interna de la notaría: no abre nada hacia afuera. Si se definen SEPARADOR_USUARIO y SEPARADOR_CLAVE en el
entorno (o `SEPARADOR_CLAVE_ARCHIVO`, un archivo con la clave), pide esa clave (HTTP Basic); sin clave solo atiende a
este mismo equipo. Cada formulario lleva una ficha anti-falsificación.

Arranque de prueba:
    SEPARADOR_DATOS=/ruta/datos SEPARADOR_ARCHIVO=/ruta/escaneo SEPARADOR_ESCANER=192.168.1.60 python -m lotes.web
"""
from __future__ import annotations

import hmac
from datetime import date
import os
import secrets
import threading
from pathlib import Path

from jinja2 import DictLoader
from flask import Flask, Response, abort, redirect, render_template_string, request, url_for

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore

from . import entrada, informe as inf, libro as libro_mod
from .aplicar import Bloqueado, aplicar
from .espacio import NOMBRES_MES, Espacio, carpeta_destino, proponer, validar_id
from .kodak import ErrorEscaner, Kodak

ESTILO = """
:root{--fondo:#f6f5f1;--tinta:#1f2328;--suave:#5b6169;--linea:#d9d6cc;--acento:#1d5a8a;--ok:#1f7a4c;--aviso:#9a6700;--mal:#b3261e;--tarjeta:#fff}
@media (prefers-color-scheme:dark){:root{--fondo:#16181b;--tinta:#e8e6e1;--suave:#9aa0a8;--linea:#34383d;--acento:#6fb0e3;--ok:#5cc08a;--aviso:#e0b04a;--mal:#f0786f;--tarjeta:#1f2226}}
*{box-sizing:border-box}body{margin:0;background:var(--fondo);color:var(--tinta);font:16px/1.5 system-ui,Segoe UI,sans-serif}
main{max-width:980px;margin:0 auto;padding:20px 16px 60px}h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.1rem;margin:28px 0 10px}
.sub{color:var(--suave);margin:0 0 20px}.tarjeta{background:var(--tarjeta);border:1px solid var(--linea);border-radius:6px;padding:16px;margin:12px 0}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--linea);vertical-align:top}th{font-size:.8rem;text-transform:uppercase;letter-spacing:.04em;color:var(--suave)}
td.n{font-variant-numeric:tabular-nums}.ok{color:var(--ok)}.aviso{color:var(--aviso)}.mal{color:var(--mal)}
button,.boton{background:var(--acento);color:#fff;border:0;border-radius:5px;padding:10px 18px;font:inherit;cursor:pointer;text-decoration:none;display:inline-block}
button.sec{background:transparent;color:var(--acento);border:1px solid var(--acento)}button:disabled{opacity:.5;cursor:default}
select,input[type=number]{font:inherit;padding:8px;border:1px solid var(--linea);border-radius:5px;background:var(--tarjeta);color:var(--tinta)}
label{margin-right:14px}a{color:var(--acento)}.fila{display:flex;gap:14px;flex-wrap:wrap;align-items:center}
img.mini{width:90px;border:1px solid var(--linea);display:block}code{font-family:ui-monospace,Consolas,monospace;font-size:.92em}
.msg{padding:10px 14px;border-radius:5px;border:1px solid var(--linea);margin:10px 0}.msg.mal{border-color:var(--mal)}.msg.ok{border-color:var(--ok)}.msg.aviso{border-color:var(--aviso)}
ul.p{margin:6px 0;padding-left:20px}
"""

BASE = """<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Separador de escrituras</title><style>{{ estilo|safe }}</style></head><body><main>
<p><a href="{{ url_for('inicio') }}">← Inicio</a></p>{% block c %}{% endblock %}</main></body></html>"""

INICIO = """{% extends "base.html" %}{% block c %}
<h1>Separador de escrituras</h1><p class="sub">Escanee: cada acto se separa solo por su código y se guarda en el libro abierto.</p>
{% if libro %}
<div class="tarjeta"><div class="fila"><strong>Libro abierto:</strong> {{ tipos[libro.tipo] }} {{ libro.anio }} · {{ meses[libro.mes-1] }} · libro {{ libro.libro }}</div>
<p class="sub">{{ libro.guardados|length }} actos guardados en {{ libro.tandas }} tandas{% if libro.acto_abierto %} · acto abierto: <code>{{ libro.acto_abierto.codigo }}</code> ({{ libro.acto_abierto.paginas }} pág.), se guarda cuando aparezca el siguiente código o al terminar el libro{% endif %}.</p>
<form method="post" action="{{ url_for('cerrar_libro') }}" onsubmit="return confirm('¿Terminó este libro? Se guardará el último acto que quedó abierto.')">
<input type="hidden" name="ficha" value="{{ ficha }}"><button class="sec">Fin de libro</button></form></div>
{% else %}
<div class="tarjeta"><form method="post" action="{{ url_for('abrir_libro') }}"><input type="hidden" name="ficha" value="{{ ficha }}">
<div class="fila"><strong>Abrir un libro</strong>
<label>Año <input type="number" name="anio" value="{{ propuesta.anio }}" min="1990" max="2200" style="width:90px"></label>
<label>Tipo <select name="tipo">{% for t, n in tipos.items() %}<option value="{{ t }}" {% if t == propuesta.tipo %}selected{% endif %}>{{ n }}</option>{% endfor %}</select></label>
<label>Mes <select name="mes">{% for m in meses %}<option value="{{ loop.index }}" {% if loop.index == propuesta.mes %}selected{% endif %}>{{ m }}</option>{% endfor %}</select></label>
<label>Libro n.º <input type="number" name="libro" min="1" max="999" value="{{ propuesta.libro }}" style="width:90px"></label>
<button>Abrir libro</button></div>
<p class="sub" style="margin:8px 0 0">Con el libro abierto, lo que escanee se divide solo por código. Sin libro abierto, cada pila queda como un lote que usted revisa a mano.</p></form></div>
{% endif %}
<div class="tarjeta"><form method="post" action="{{ url_for('escanear') }}" id="f-esc">
<input type="hidden" name="ficha" value="{{ ficha }}">
<div class="fila"><strong>Escanear una pila de hojas</strong>
<label><input type="radio" name="caras" value="Simplex" checked> Una cara</label>
<label><input type="radio" name="caras" value="Duplex"> Dos caras (quita dorsos en blanco)</label>
<label>Hojas que puso (para comprobar) <input type="number" name="hojas" min="1" max="999" style="width:90px"></label>
<button id="b-esc" {% if escaneo.en_curso or bloqueado %}disabled{% endif %}>Escanear ahora</button></div>
{% if bloqueado %}<p class="mal">Hay una tanda por revisar: resuélvala (guardarla o descartarla) antes de escanear otra.</p>{% endif %}
<p class="sub" style="margin:8px 0 0">Ponga las hojas en el alimentador, en orden, con el extracto (código de barras) delante de cada escritura. Un tipo de acto por pila.</p>
</form><p id="estado" class="{{ 'aviso' if escaneo.en_curso else ('mal' if escaneo.error else 'ok') }}">
{{ escaneo.mensaje }}{% if escaneo.hojas %} ({{ escaneo.hojas }} hojas){% endif %}{% if escaneo.error %}{{ escaneo.error }}{% endif %}</p></div>
<h2>Por revisar</h2>
{% if lotes %}<table><tr><th>Lote</th><th>Fecha</th><th>Tamaño</th><th></th></tr>
{% for l in lotes %}<tr><td><code>{{ l.id }}</code></td><td class="n">{{ l.fecha.strftime('%d-%m-%Y %H:%M') }}</td>
<td class="n">{{ '%.1f'|format(l.bytes/1048576) }} MB{% if l.aviso %} <span class="mal">· ¡posibles hojas sin escanear!</span>{% endif %}</td><td><a class="boton" href="{{ l.enlace }}">Revisar</a></td></tr>{% endfor %}</table>
{% else %}<p class="sub">No hay lotes esperando.</p>{% endif %}
<h2>Guardados recientemente</h2>
{% if libro and libro.guardados %}<table><tr><th>Código</th><th>Páginas</th></tr>
{% for g in libro.guardados[-12:]|reverse %}<tr><td><code>{{ g.codigo }}</code></td><td class="n">{{ g.paginas }}</td></tr>{% endfor %}</table>
{% elif hechos %}<table><tr><th>Fecha</th><th>Dónde</th><th>Actos</th></tr>
{% for h in hechos %}<tr><td class="n">{{ h.fecha[:16].replace('T',' ') }}</td><td>{{ h.anio }} · {{ h.tipo }} · {{ meses[h.mes-1] }} · libro {{ h.libro }}</td>
<td class="n">{{ h.archivos|length }}</td></tr>{% endfor %}</table>
{% else %}<p class="sub">Todavía no se ha guardado ningún lote.</p>{% endif %}
<script>
const est=document.getElementById('estado'),btn=document.getElementById('b-esc');let activo={{ 'true' if escaneo.en_curso else 'false' }};
async function mirar(){try{const r=await fetch('{{ url_for("escaneo_json") }}');const d=await r.json();
est.textContent=d.mensaje+(d.hojas?' ('+d.hojas+' hojas)':'')+(d.error?d.error:'');est.className=d.en_curso?'aviso':(d.error?'mal':'ok');
if(activo&&!d.en_curso){location.reload();return}activo=d.en_curso;btn.disabled=d.en_curso}catch(e){}}
if(activo)setInterval(mirar,2000);
</script>{% endblock %}"""

LOTE = """{% extends "base.html" %}{% block c %}
<h1>Lote <code>{{ lote_id }}</code></h1>
{% if info.sin_serie %}<div class="msg mal">No se encontró ningún código de la Notaría Séptima en este lote. Revise que las hojas
traigan el extracto con su código de barras y vuelva a escanear.</div>
{% elif info.sin_actos %}<div class="msg mal">No se pudo armar ningún acto con el año {{ info.anio }} y el tipo {{ info.tipo }}. Pruebe con otro año o tipo:</div>
{{ rehacer_form|safe }}
{% else %}
{% set r = info.resultado %}
<p class="sub">{{ r.total_paginas }} páginas · año <strong>{{ info.anio }}</strong> · tipo <strong>{{ tipos[info.tipo] }}</strong>
{% if info.ultimo_previo %}· continúa después del acto {{ '%05d'|format(info.ultimo_previo) }}{% endif %}</p>
{% if aviso %}<div class="msg mal"><strong>Atención:</strong> {{ aviso }}</div>{% endif %}
{% if problemas %}<div class="msg mal"><strong>No se puede guardar todavía:</strong><ul class="p">{% for p in problemas %}<li>{{ p }}</li>{% endfor %}</ul></div>{% endif %}
{% if r.huerfanas %}<div class="msg aviso">Las páginas {{ r.huerfanas[0] }}–{{ r.huerfanas[1] }} están antes del primer código. Se guardarán aparte, como «SIN_CODIGO».</div>{% endif %}
{% for s in r.saltos + r.avisos %}<div class="msg aviso">{{ s }}</div>{% endfor %}
<h2>Actos encontrados ({{ r.actos|length }})</h2>
<table><tr><th>Primera hoja</th><th>Código</th><th>Páginas</th><th>Seguridad</th></tr>
{% for a in r.actos %}<tr><td><img class="mini" src="{{ url_for('miniatura', lote_id=lote_id, pagina=a.inicio) }}" alt="primera hoja del acto"></td>
<td><code>{{ a.codigo }}</code></td><td class="n">{{ a.inicio }}–{{ a.fin }} ({{ a.fin - a.inicio + 1 }})</td>
<td class="{{ 'ok' if a.confianza=='alta' else ('aviso' if a.confianza=='media' else 'mal') }}">{{ a.confianza }}</td></tr>{% endfor %}</table>
{% if r.ajenos %}<h2>Códigos que no abren acto</h2><ul class="p">{% for p,c,m in r.ajenos %}<li>página {{ p }}: <code>{{ c }}</code> — {{ m }}</li>{% endfor %}</ul>{% endif %}
{% if not problemas %}
<h2>Guardar en el archivo</h2>
<form method="post" action="{{ url_for('guardar', lote_id=lote_id) }}" class="tarjeta">
<input type="hidden" name="ficha" value="{{ ficha }}">
<div class="fila"><label>Mes <select name="mes">{% for m in meses %}<option value="{{ loop.index }}" {% if loop.index==mes %}selected{% endif %}>{{ m }}</option>{% endfor %}</select></label>
<label>Libro n.º <input type="number" name="libro" min="1" max="999" value="{{ libro }}" style="width:90px"></label></div>
<p class="sub">Se guardará en <code>{{ destino }}</code>. El PDF escaneado no se borra: queda apartado en la carpeta de espera.</p>
{% if necesita_revision %}<p class="aviso"><label><input type="checkbox" name="acepto" value="1"> Revisé los avisos de arriba y quiero guardar de todos modos.</label></p>{% endif %}
<button>Guardar en el archivo</button></form>
<details><summary>Cambiar año o tipo</summary>{{ rehacer_form|safe }}</details>
{% endif %}{% endif %}{% endblock %}"""

REVISION = """{% extends "base.html" %}{% block c %}
<h1>Tanda por revisar <code>{{ lote_id }}</code></h1>
<p class="sub">Libro {{ tipos[info.tipo] }} {{ info.anio }} · {{ info.resultado.total_paginas }} páginas contando las del acto que venía abierto.</p>
<div class="msg aviso"><strong>No se guardó nada todavía.</strong><ul class="p">{% for m in info.motivos_revision %}<li>{{ m }}</li>{% endfor %}</ul></div>
{% if info.verificacion.problemas %}<div class="msg mal"><strong>Falló la comprobación del corte:</strong><ul class="p">{% for p in info.verificacion.problemas %}<li>{{ p }}</li>{% endfor %}</ul></div>{% endif %}
{% set r = info.resultado %}
{% if r.actos %}<h2>Actos ({{ r.actos|length }})</h2>
<table><tr><th>Primera hoja</th><th>Código</th><th>Páginas</th><th>Qué pasará</th></tr>
{% for a in r.actos %}<tr><td><img class="mini" src="{{ url_for('miniatura', lote_id=lote_id, pagina=a.inicio) }}" alt="primera hoja"></td>
<td><code>{{ a.codigo }}</code></td><td class="n">{{ a.inicio }}–{{ a.fin }} ({{ a.fin - a.inicio + 1 }})</td>
<td>{% if loop.last %}queda abierto hasta el siguiente código{% else %}se guarda{% endif %}{% if info.n0 and loop.first %} · continúa el acto que venía abierto{% endif %}</td></tr>{% endfor %}</table>
{% endif %}
{% if r.ajenos %}<h2>Códigos que no abren acto</h2><ul class="p">{% for p,c,m in r.ajenos %}<li>página {{ p }}: <code>{{ c }}</code> — {{ m }}</li>{% endfor %}</ul>{% endif %}
<div class="fila" style="margin-top:20px">
{% if puede_aceptar %}<form method="post" action="{{ url_for('aprobar', lote_id=lote_id) }}"><input type="hidden" name="ficha" value="{{ ficha }}"><button>Guardar de todos modos</button></form>{% endif %}
<form method="post" action="{{ url_for('descartar', lote_id=lote_id) }}" onsubmit="return confirm('Se aparta este escaneo sin guardarlo. Tendrá que volver a escanear esas hojas. ¿Continuar?')"><input type="hidden" name="ficha" value="{{ ficha }}"><button class="sec">Descartar y volver a escanear</button></form></div>
{% if not puede_aceptar %}<p class="sub">Esta tanda no se puede guardar así. Descártela y escanee otra vez esas hojas.</p>{% endif %}
{% endblock %}"""

LISTO_LIBRO = """{% extends "base.html" %}{% block c %}<h1>Guardado</h1>
<div class="msg ok">{% if r.guardados %}Se guardaron {{ r.guardados|length }} actos en el libro.{% else %}No se cerró ningún acto nuevo.{% endif %}
{% if r.abierto %} Queda abierto <code>{{ r.abierto }}</code>.{% endif %}</div>
<ul class="p">{% for c in r.guardados %}<li><code>{{ c }}</code></li>{% endfor %}</ul>
<p><a class="boton" href="{{ url_for('inicio') }}">Volver al inicio</a></p>{% endblock %}"""

LISTO = """{% extends "base.html" %}{% block c %}<h1>Guardado</h1>
<div class="msg ok">Se guardaron {{ h.archivos|length }} archivos en <code>{{ h.destino }}</code>.</div>
<ul class="p">{% for a in h.archivos %}<li><code>{{ a.nombre }}</code> — páginas {{ a.inicio }}–{{ a.fin }} ({{ a.estado }})</li>{% endfor %}</ul>
<p>El PDF escaneado quedó apartado en la carpeta de espera; no se borró nada.</p><p><a class="boton" href="{{ url_for('inicio') }}">Volver al inicio</a></p>{% endblock %}"""


def credenciales() -> tuple[str | None, str | None]:
    """Usuario y clave de acceso. La clave puede venir de `SEPARADOR_CLAVE` o, mejor, de un archivo (`SEPARADOR_CLAVE_ARCHIVO`)
    que solo lee el servicio: así no queda en el entorno ni en las órdenes de arranque."""
    usuario = os.environ.get("SEPARADOR_USUARIO")
    clave = os.environ.get("SEPARADOR_CLAVE")
    ruta = os.environ.get("SEPARADOR_CLAVE_ARCHIVO")
    if not clave and ruta:
        try:
            clave = Path(ruta).read_text(encoding="utf-8").strip()
        except OSError:
            clave = None
    return usuario or None, clave or None


def comprobar_acceso(host: str, usuario: str | None, clave: str | None) -> None:
    """Se niega a abrir la pantalla a la red si no hay usuario y clave: sin clave solo se atiende a este mismo equipo."""
    if host not in ("127.0.0.1", "localhost", "::1") and not (usuario and clave):
        raise SystemExit("No se abre la pantalla a la red sin usuario y clave "
                         "(defina SEPARADOR_USUARIO y SEPARADOR_CLAVE_ARCHIVO, o use SEPARADOR_HOST=127.0.0.1).")


def crear_app(espacio: Espacio, escaner: Kodak | None = None) -> Flask:
    espacio.asegurar()
    app = Flask(__name__)
    app.jinja_loader = DictLoader({"base.html": BASE})
    app.config["FICHA"] = secrets.token_hex(16)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    estado = {"en_curso": False, "mensaje": "Listo para escanear.", "hojas": 0, "error": ""}
    cerrojo = threading.Lock()
    usuario, clave = credenciales()

    @app.before_request
    def _acceso():
        if usuario and clave:
            a = request.authorization
            if not (a and hmac.compare_digest(a.username or "", usuario) and hmac.compare_digest(a.password or "", clave)):
                return Response("Se necesita usuario y clave.", 401, {"WWW-Authenticate": 'Basic realm="Separador"'})
        if request.method == "POST" and not hmac.compare_digest(request.form.get("ficha", ""), app.config["FICHA"]):
            abort(400)

    def pagina(plantilla: str, **ctx):
        return render_template_string(plantilla, estilo=ESTILO, ficha=app.config["FICHA"], **ctx)

    @app.get("/")
    def inicio():
        libro = libro_mod.estado(espacio)
        if libro:
            lotes = [{**l, "enlace": url_for("revision", lote_id=l["id"])} for l in libro_mod.pendientes(espacio)]
        else:
            lotes = [{**l, "enlace": url_for("lote", lote_id=l["id"])} for l in entrada.listar(espacio)]
        hoy = date.today()
        propuesta = {"anio": hoy.year, "tipo": "P", "mes": hoy.month,
                     "libro": proponer(espacio, hoy.year, "P", hoy)[1]}
        return pagina(INICIO, lotes=lotes, hechos=entrada.aplicados(espacio), escaneo=dict(estado), meses=NOMBRES_MES,
                      libro=libro, tipos=TIPOS_NOMBRE, propuesta=propuesta, bloqueado=bool(libro and lotes))

    @app.get("/escaneo.json")
    def escaneo_json():
        return dict(estado)

    def _procesar_en_libro(lote_id: str) -> str:
        try:
            r = libro_mod.procesar(espacio, lote_id)
        except Bloqueado as e:
            return "NO SE GUARDÓ: " + "; ".join(e.motivos)
        if r["estado"] == "guardado":
            n = len(r["guardados"])
            return (f"Se guardaron {n} actos." if n else "No se cerró ningún acto nuevo.") + (
                f" Queda abierto {r['abierto']}." if r["abierto"] else "")
        return "QUEDÓ POR REVISAR (no se guardó nada): " + "; ".join(r["motivos"])

    def _trabajo_escaneo(caras: str, hojas_puestas: int | None):
        def avance(mensaje: str, hojas: int):
            estado["mensaje"], estado["hojas"] = mensaje, hojas

        try:
            imagenes = escaner.escanear(caras=caras, avance=avance)
            lote_id = entrada.nuevo_id(espacio=espacio)
            entrada.jpegs_a_pdf(imagenes, espacio.entrada / f"{lote_id}.pdf")
            texto = f"Listo: {len(imagenes)} hojas guardadas como {lote_id}."
            avisos = []
            if getattr(escaner, "quedaron_hojas", False):
                avisos.append(entrada.AVISO_HOJAS)
                texto += " ATENCIÓN: quedaron hojas sin escanear dentro del alimentador; revíselas."
            if hojas_puestas:
                crudas = getattr(escaner, "imagenes_crudas", 0) or len(imagenes)
                esperadas = hojas_puestas * (2 if caras == "Duplex" else 1)
                if crudas != esperadas:
                    avisos.append(entrada.aviso_por_conteo(esperadas, crudas))
                    texto += f" ATENCIÓN: puso {esperadas} y se escanearon {crudas}."
            if avisos:
                entrada.marcar_aviso(espacio, lote_id, " ".join(avisos))
            if libro_mod.estado(espacio):
                texto += " " + _procesar_en_libro(lote_id)
            estado.update(mensaje=texto, hojas=0, error="")
        except ErrorEscaner as e:
            estado.update(mensaje="", hojas=0, error=str(e))
        except Exception as e:  # nunca dejar la pantalla «escaneando» para siempre
            estado.update(mensaje="", hojas=0, error=f"error inesperado al escanear ({type(e).__name__})")
        finally:
            estado["en_curso"] = False

    @app.post("/escanear")
    def escanear():
        if escaner is None:
            estado.update(mensaje="", error="No hay escáner configurado (SEPARADOR_ESCANER).")
            return redirect(url_for("inicio"))
        caras = "Duplex" if request.form.get("caras") == "Duplex" else "Simplex"
        if libro_mod.estado(espacio) and libro_mod.pendientes(espacio):
            estado.update(mensaje="", error="Hay una tanda por revisar: resuélvala antes de escanear otra.")
            return redirect(url_for("inicio"))
        with cerrojo:
            if estado["en_curso"]:
                return redirect(url_for("inicio"))
            estado.update(en_curso=True, mensaje="Empezando…", hojas=0, error="")
        try:
            puestas = int(request.form.get("hojas", "") or 0) or None
        except ValueError:
            puestas = None
        threading.Thread(target=_trabajo_escaneo, args=(caras, puestas), daemon=True).start()
        return redirect(url_for("inicio"))

    def _forma_rehacer(lote_id, anio, tipo):
        tipos = "".join(f'<option value="{t}"{" selected" if t == tipo else ""}>{n}</option>' for t, n in TIPOS_NOMBRE.items())
        return (f'<form method="post" action="{url_for("rehacer", lote_id=lote_id)}" class="fila">'
                f'<input type="hidden" name="ficha" value="{app.config["FICHA"]}">'
                f'<label>Año <input type="number" name="anio" value="{anio or ""}" min="1990" max="2200" style="width:90px"></label>'
                f'<label>Tipo <select name="tipo">{tipos}</select></label><button class="sec">Volver a analizar</button></form>')

    @app.get("/lote/<lote_id>")
    def lote(lote_id):
        try:
            validar_id(lote_id)
            info = entrada.preparar(espacio, lote_id)
        except (ValueError, FileNotFoundError):
            abort(404)
        return _ver_lote(lote_id, info)

    def _ver_lote(lote_id, info):
        problemas, necesita, mes, libro, destino = [], False, 1, 1, ""
        if "generados" in info:
            from .aplicar import revalidar
            from .division import Verificacion, puede_borrar_original
            from . import informe as inf

            _, problemas = revalidar(espacio, lote_id)
            res = inf.resultado_desde_dict(info["resultado"])
            necesita = bool(entrada.aviso(espacio, lote_id)) or not puede_borrar_original(res, Verificacion())[0]
            mes, libro = proponer(espacio, info["anio"], info["tipo"])
            destino = str(carpeta_destino(espacio, info["anio"], info["tipo"], mes, libro))
        return pagina(LOTE, lote_id=lote_id, info=info, problemas=problemas, necesita_revision=necesita, aviso=entrada.aviso(espacio, lote_id), mes=mes,
                      libro=libro, destino=destino, meses=NOMBRES_MES, tipos=TIPOS_NOMBRE,
                      rehacer_form=_forma_rehacer(lote_id, info.get("anio"), info.get("tipo")))

    @app.post("/lote/<lote_id>/rehacer")
    def rehacer(lote_id):
        try:
            validar_id(lote_id)
            anio, tipo = int(request.form["anio"]), request.form["tipo"]
            if tipo not in TIPOS_NOMBRE or not 1990 <= anio <= 2200:
                raise ValueError
            info = entrada.preparar(espacio, lote_id, anio=anio, tipo=tipo, rehacer=True)
        except (ValueError, KeyError, FileNotFoundError):
            abort(400)
        if "generados" not in info:  # con ese año y tipo no salió nada: se muestra tal cual, sin volver a la propuesta
            return _ver_lote(lote_id, info)
        return redirect(url_for("lote", lote_id=lote_id))

    @app.post("/lote/<lote_id>/guardar")
    def guardar(lote_id):
        try:
            validar_id(lote_id)
            mes, libro = int(request.form["mes"]), int(request.form["libro"])
        except (ValueError, KeyError):
            abort(400)
        with cerrojo:
            try:
                hecho = aplicar(espacio, lote_id, mes, libro, aceptar_revision=request.form.get("acepto") == "1")
            except Bloqueado as e:
                return pagina(LOTE_BLOQUEADO, volver=url_for('lote', lote_id=lote_id), motivos=e.motivos), 409
            except (ValueError, FileNotFoundError, OSError):
                abort(400)
        return pagina(LISTO, h=hecho)

    @app.post("/libro/abrir")
    def abrir_libro():
        try:
            libro_mod.abrir_libro(espacio, int(request.form["anio"]), request.form["tipo"], int(request.form["mes"]),
                                  int(request.form["libro"]))
            estado.update(mensaje="Libro abierto. Ya puede escanear.", error="")
        except (ValueError, KeyError) as e:
            estado.update(mensaje="", error=f"No se pudo abrir el libro: {e}")
        return redirect(url_for("inicio"))

    @app.post("/libro/cerrar")
    def cerrar_libro():
        with cerrojo:
            try:
                r = libro_mod.cerrar_libro(espacio)
            except Bloqueado as e:
                return pagina(LOTE_BLOQUEADO, volver=url_for("inicio"), motivos=e.motivos), 409
            except ValueError as e:
                estado.update(mensaje="", error=str(e))
                return redirect(url_for("inicio"))
        estado.update(mensaje=f"Libro cerrado: {r['actos']} actos guardados.", error="")
        return redirect(url_for("inicio"))

    @app.get("/revision/<lote_id>")
    def revision(lote_id):
        try:
            validar_id(lote_id)
            info = inf.cargar(espacio.preparacion / lote_id)
        except (ValueError, OSError):
            abort(404)
        if not info.get("libro_abierto") or (espacio.preparacion / lote_id / "aplicado.json").exists():
            abort(404)
        puede = bool(info["resultado"]["actos"]) and info["verificacion"]["correcta"]
        return pagina(REVISION, lote_id=lote_id, info=info, tipos=TIPOS_NOMBRE, puede_aceptar=puede)

    @app.post("/revision/<lote_id>/aprobar")
    def aprobar(lote_id):
        try:
            validar_id(lote_id)
        except ValueError:
            abort(404)
        with cerrojo:
            try:
                r = libro_mod.procesar(espacio, lote_id, aceptar=True)
            except Bloqueado as e:
                return pagina(LOTE_BLOQUEADO, volver=url_for("revision", lote_id=lote_id), motivos=e.motivos), 409
            except (ValueError, FileNotFoundError, OSError):
                abort(400)
        if r["estado"] != "guardado":
            return pagina(LOTE_BLOQUEADO, volver=url_for("inicio"), motivos=r["motivos"] or ["no se pudo guardar"]), 409
        return pagina(LISTO_LIBRO, r=r)

    @app.post("/revision/<lote_id>/descartar")
    def descartar(lote_id):
        try:
            validar_id(lote_id)
            with cerrojo:
                libro_mod.descartar(espacio, lote_id)
        except (ValueError, FileNotFoundError):
            abort(400)
        estado.update(mensaje="Tanda descartada: vuelva a escanear esas hojas.", error="")
        return redirect(url_for("inicio"))

    @app.get("/miniatura/<lote_id>/<int:pagina>.png")
    def miniatura(lote_id, pagina):
        try:
            validar_id(lote_id)
        except ValueError:
            abort(404)
        pdf = espacio.preparacion / lote_id / "combinado.pdf"  # tandas del libro abierto: páginas del acto abierto + nuevas
        if not pdf.is_file():
            pdf = espacio.entrada / f"{lote_id}.pdf"
        if not pdf.is_file():
            abort(404)
        with fitz.open(str(pdf)) as doc:
            if not 1 <= pagina <= doc.page_count:
                abort(404)
            pix = doc[pagina - 1].get_pixmap(matrix=fitz.Matrix(0.35, 0.35), colorspace=fitz.csGRAY)
            return Response(pix.tobytes("png"), mimetype="image/png", headers={"Cache-Control": "private, max-age=300"})

    return app


from .codigos import TIPOS as TIPOS_NOMBRE  # noqa: E402

LOTE_BLOQUEADO = """{% extends "base.html" %}{% block c %}<h1>No se guardó</h1>
<div class="msg mal"><ul class="p">{% for m in motivos %}<li>{{ m }}</li>{% endfor %}</ul></div>
<p><a class="boton" href="{{ volver }}">Volver</a></p>{% endblock %}"""


def main() -> None:  # pragma: no cover
    espacio = Espacio(Path(os.environ["SEPARADOR_DATOS"]), Path(os.environ["SEPARADOR_ARCHIVO"]))
    ip = os.environ.get("SEPARADOR_ESCANER")
    host = os.environ.get("SEPARADOR_HOST", "127.0.0.1")
    puerto = int(os.environ.get("SEPARADOR_PUERTO", "5055"))
    comprobar_acceso(host, *credenciales())
    app = crear_app(espacio, Kodak(ip) if ip else None)
    try:
        from waitress import serve
    except ImportError:
        app.run(host=host, port=puerto)
    else:
        serve(app, host=host, port=puerto, threads=6)


if __name__ == "__main__":  # pragma: no cover
    main()
