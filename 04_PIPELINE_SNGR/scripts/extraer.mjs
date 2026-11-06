// Extrae los alojamientos temporales del Visor Alístate Ecuador (SNGR).
// El visor es una app de Google Apps Script: no tiene API pública. Abrimos la página con un navegador sin
// pantalla (Playwright) y leemos la respuesta del lote que trae la función obtenerAlojamientosTemporales,
// la misma que usa el visor para pintar su mapa.
//
// Uso: node scripts/extraer.mjs <salida.json>
// Variables: CHROME_CHANNEL=chrome para usar el Chrome instalado (pruebas locales).
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';

const VISOR = 'https://script.google.com/macros/s/AKfycbz6HA9kKLeksqm49YYPD7i3A40mMK6JwmoDc50vaiv4myVTk0lFYswqnE4IbJXmr9Lm/exec';
const FUNCION = 'obtenerAlojamientosTemporales';
const salida = process.argv[2] || 'crudo.json';
const ESPERA_MS = 120000;

function leerRespuesta(postData, texto) {
  // Cuerpo: request=[ "obtenerLote", "[[{\"n\":\"fn1\"},{\"n\":\"fn2\"},…]]", … ]&token=…
  const req = decodeURIComponent(postData.replace(/&token=.*$/, '').replace(/^request=/, '').replace(/\+/g, ' '));
  if (!req.includes(FUNCION)) return null;
  const fns = JSON.parse(JSON.parse(req)[1])[0].map((o) => o.n);
  const externo = JSON.parse(texto.replace(/^\)\]\}'\s*/, ''));
  const exec = externo.find((e) => e[0] === 'op.exec');
  if (!exec) throw new Error('La respuesta no trae op.exec');
  const res = JSON.parse(exec[1][1]);
  const r = res[fns.indexOf(FUNCION)];
  if (!r || !r.ok) throw new Error(`${FUNCION} respondió con error`);
  return r.v;
}

const navegador = await chromium.launch({ channel: process.env.CHROME_CHANNEL || undefined });
try {
  const pagina = await navegador.newPage({ locale: 'es-EC' });
  const datos = await new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`No llegó ${FUNCION} en ${ESPERA_MS / 1000} s`)), ESPERA_MS);
    pagina.on('response', async (resp) => {
      try {
        const pd = resp.request().postData() || '';
        if (!resp.url().includes('/callback') || !decodeURIComponent(pd).includes(FUNCION)) return;
        const v = leerRespuesta(pd, await resp.text());
        if (v) { clearTimeout(t); resolve(v); }
      } catch (e) { clearTimeout(t); reject(e); }
    });
    pagina.goto(VISOR, { waitUntil: 'domcontentloaded', timeout: ESPERA_MS }).catch(reject);
  });
  if (!Array.isArray(datos)) throw new Error('El resultado no es una lista');
  writeFileSync(salida, JSON.stringify({ extraido: new Date().toISOString(), fuente: `SNGR · Visor Alístate Ecuador – Evento El Niño (función ${FUNCION})`, registros: datos }));
  console.log(`Extraídos ${datos.length} registros → ${salida}`);
} finally {
  await navegador.close();
}
