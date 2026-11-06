"""Normaliza los alojamientos temporales de la SNGR para el especial El Niño (PRIMICIAS).

Uso: python scripts/procesar.py <crudo.json> <parroquias_2025.json> <data/out>

Escribe en data/out/:
  albergues_implementados.json  los abiertos por la SNGR (lo que lee Ayuda ya)
  calificados/NN.json           lugares calificados (aptos, NO abiertos), uno por provincia
  albergues_sngr.json           todo, normalizado (sin las observaciones internas de la SNGR)
  estado.json                   última ejecución, totales y hora de la extracción
  cambios.json                  aperturas y cierres de alojamientos implementados (últimos 500)

Si la extracción parece rota (muy pocos registros, o cae más del 40 % frente a la anterior), sale con error y
no toca los archivos publicados: la página sigue mostrando la última versión buena.
"""
import json, os, re, sys, unicodedata, collections

MIN_TOTAL = 1000          # la SNGR tiene ~2.866 registros; menos de esto es una extracción fallida
MAX_CAIDA = 0.40          # caída máxima permitida frente a la ejecución anterior
MAX_CAMBIOS = 500

crudo_p, mapa_p, out = sys.argv[1:4]
crudo = json.load(open(crudo_p, encoding='utf-8'))
R = crudo['registros']
extraido = crudo['extraido']

# ---------- validación ----------
estado_p = os.path.join(out, 'estado.json')
previo = json.load(open(estado_p, encoding='utf-8')) if os.path.exists(estado_p) else None
if len(R) < MIN_TOTAL:
    sys.exit(f'ERROR: solo {len(R)} registros (mínimo {MIN_TOTAL}). No se publica.')
if previo and previo.get('total') and len(R) < previo['total'] * (1 - MAX_CAIDA):
    sys.exit(f"ERROR: {len(R)} registros frente a {previo['total']} de la ejecución anterior. No se publica.")
for x in R:
    if not isinstance(x.get('lat'), (int, float)) or not isinstance(x.get('lon'), (int, float)):
        sys.exit(f"ERROR: registro sin coordenadas: {x.get('id')}")

# ---------- parroquias del CNE (punto en polígono) ----------
G = json.load(open(mapa_p, encoding='utf-8'))['features']
def bbox(g):
    polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
    xs = [c[0] for p in polys for c in p[0]]; ys = [c[1] for p in polys for c in p[0]]
    return min(xs), min(ys), max(xs), max(ys)
F = [(f['properties'], f['geometry'], bbox(f['geometry'])) for f in G]
def en_anillo(x, y, r):
    dentro = False; j = len(r) - 1
    for i in range(len(r)):
        xi, yi = r[i][0], r[i][1]; xj, yj = r[j][0], r[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi): dentro = not dentro
        j = i
    return dentro
def parroquia(lon, lat):
    for p, g, b in F:
        if lon < b[0] or lon > b[2] or lat < b[1] or lat > b[3]: continue
        polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
        for poly in polys:
            dentro = False
            for r in poly:
                if en_anillo(lon, lat, r): dentro = not dentro
            if dentro: return p
    return None

def norm(s): return re.sub(r'\s+', ' ', unicodedata.normalize('NFD', str(s or '')).encode('ascii', 'ignore').decode().upper()).strip()
def limpio(s): return re.sub(r'\s+', ' ', str(s or '')).strip()
def fecha(s):
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', str(s or ''))
    return f'{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}' if m else None

# ---------- normalización ----------
todos = []
for x in R:
    p = parroquia(x['lon'], x['lat'])
    imp = bool(x.get('implementado')) or str(x.get('categoria', '')).upper() == 'IMPLEMENTADO'
    o = {'id': x['id'], 'nombre': limpio(x.get('nombre')), 'tipo': 'implementado' if imp else 'calificado',
         'modalidad': limpio(x.get('modalidad')) or None,
         'provincia_sngr': limpio(x.get('provincia')), 'canton_sngr': limpio(x.get('canton')),
         'parroquia_sngr': limpio(x.get('parroquia')) or None, 'sector': limpio(x.get('sector')) or None,
         'lat': round(x['lat'], 6), 'lon': round(x['lon'], 6),
         'personas': x.get('personas') or None, 'familias': x.get('familias') or None}
    if imp: o['desde'] = fecha(x.get('fechaImplementacion'))
    if p: o.update({'codpro': p['CODPRO'], 'codpar': p['CODPAR'], 'canton': p['CANTON'], 'parroquia': p['PARROQUIA']})
    else: o.update({'codpro': None, 'codpar': None, 'canton': norm(x.get('canton')), 'parroquia': None})
    todos.append(o)   # «observaciones» (notas internas de la SNGR sobre la infraestructura) no se publica

meta = {'generado': extraido, 'fuente': 'SNGR · Visor Alístate Ecuador – Evento El Niño',
        'fuente_url': 'https://script.google.com/macros/s/AKfycbz6HA9kKLeksqm49YYPD7i3A40mMK6JwmoDc50vaiv4myVTk0lFYswqnE4IbJXmr9Lm/exec',
        'procesamiento': 'PRIMICIAS'}
imp = [o for o in todos if o['tipo'] == 'implementado']
K_IMP = ['id', 'nombre', 'tipo', 'codpro', 'codpar', 'canton', 'parroquia', 'lat', 'lon', 'personas', 'familias', 'desde']
K_CAL = ['id', 'nombre', 'modalidad', 'codpar', 'canton', 'parroquia', 'sector', 'lat', 'lon', 'personas', 'familias']
def solo(o, ks): return {k: o[k] for k in ks if o.get(k) is not None}

# ---------- cambios: aperturas y cierres de implementados ----------
imp_p = os.path.join(out, 'albergues_implementados.json')
antes = {a['id']: a for a in json.load(open(imp_p, encoding='utf-8'))['albergues']} if os.path.exists(imp_p) else None
ahora = {a['id']: a for a in imp}
cambios_p = os.path.join(out, 'cambios.json')
cambios = json.load(open(cambios_p, encoding='utf-8'))['cambios'] if os.path.exists(cambios_p) else []
nuevos = []
if antes is not None:
    for i in sorted(set(ahora) - set(antes)):
        a = ahora[i]; nuevos.append({'hora': extraido, 'cambio': 'implementado', 'id': i, 'nombre': a['nombre'], 'codpro': a.get('codpro'), 'canton': a.get('canton')})
    for i in sorted(set(antes) - set(ahora)):
        a = antes[i]; nuevos.append({'hora': extraido, 'cambio': 'retirado', 'id': i, 'nombre': a['nombre'], 'codpro': a.get('codpro'), 'canton': a.get('canton')})
cambios = (nuevos + cambios)[:MAX_CAMBIOS]

# ---------- escritura ----------
os.makedirs(os.path.join(out, 'calificados'), exist_ok=True)
def guardar(nombre, obj, compacto=True):
    ruta = os.path.join(out, nombre)
    with open(ruta + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':') if compacto else None, indent=None if compacto else 1)
    os.replace(ruta + '.tmp', ruta)

guardar('albergues_implementados.json', dict(meta, descripcion='Alojamientos temporales implementados (abiertos) por la SNGR. desde: fecha de implementación. personas/familias: cifra de la SNGR. canton/parroquia: CNE 2025 (punto en polígono). La SNGR no publica si están llenos.', total=len(imp), albergues=[solo(o, K_IMP) for o in imp]), compacto=False)
por_prov = collections.defaultdict(list)
for o in todos:
    if o['tipo'] == 'calificado' and o['codpro']: por_prov[o['codpro']].append(solo(o, K_CAL))
for c, l in por_prov.items():
    guardar(f'calificados/{c}.json', dict(meta, codpro=c, descripcion='Lugares calificados por la SNGR como aptos para alojamiento temporal. NO están abiertos.', total=len(l), calificados=l))
guardar('albergues_sngr.json', dict(meta, total=len(todos), albergues=todos))
guardar('cambios.json', {'descripcion': 'Aperturas (implementado) y retiros de alojamientos temporales de la SNGR, del más reciente al más antiguo.', 'cambios': cambios}, compacto=False)
cnt = collections.Counter(o['tipo'] for o in todos)
guardar('estado.json', {'generado': extraido, 'total': len(todos), 'implementados': cnt['implementado'], 'calificados': cnt['calificado'],
                        'fuera_de_parroquias': sum(1 for o in todos if not o['codpro']), 'cambios_esta_ejecucion': len(nuevos)}, compacto=False)
print(f"OK · {len(todos)} registros · {cnt['implementado']} implementados · {cnt['calificado']} calificados · {len(nuevos)} cambios")
