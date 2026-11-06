# Albergues SNGR · El Niño: Ecuador en Alerta (PRIMICIAS)

Este pipeline corre cada 6 horas. Extrae los **alojamientos temporales** de la Secretaría Nacional de Gestión de Riesgos (SNGR), los normaliza y los publica en `data/out/` para la pestaña «Ayuda ya» del especial.

La SNGR no tiene datos abiertos de albergues: los muestra solo en el [Visor Alístate Ecuador – Evento El Niño](https://script.google.com/macros/s/AKfycbz6HA9kKLeksqm49YYPD7i3A40mMK6JwmoDc50vaiv4myVTk0lFYswqnE4IbJXmr9Lm/exec), una app de Google Apps Script.

- **Extracción:** `scripts/extraer.mjs` abre el visor con un navegador sin pantalla (Playwright) y lee la respuesta de la función `obtenerAlojamientosTemporales`, la misma que usa el visor para su mapa.
- **Normalización:** `scripts/procesar.py` hace tres cosas:
  - asigna a cada punto la parroquia del CNE 2025 (cruzando sus coordenadas con los límites de parroquia, punto en polígono);
  - valida la extracción;
  - publica los archivos.

## Archivos publicados (`data/out/`)

| Archivo | Qué es |
|---|---|
| `albergues_implementados.json` | Alojamientos **abiertos** por la SNGR, con fecha de implementación y capacidad. Es lo que lee Ayuda ya. |
| `calificados/NN.json` | Lugares **calificados** (aptos, **no abiertos**), un archivo por provincia (`NN` = codpro). |
| `albergues_sngr.json` | Todo, normalizado. Sin las `observaciones` internas de la SNGR. |
| `cambios.json` | Aperturas (`implementado`) y retiros de alojamientos implementados, del más reciente al más antiguo. Sirve para la cobertura. |
| `estado.json` | Hora de la última extracción y totales. |

URL para la página: `https://raw.githubusercontent.com/<organización>/<repo>/main/data/out/`. Va en la constante `BASE_SNGR` de `02_AYUDA_YA.html`.

## Cron

`.github/workflows/albergues_sngr.yml` corre con `cron: '17 */6 * * *'` (UTC):

| UTC | Ecuador |
|---|---|
| 00:17 | 19:17 |
| 06:17 | 01:17 |
| 12:17 | 07:17 |
| 18:17 | 13:17 |

Para correrlo a mano: pestaña **Actions › Albergues SNGR › Run workflow**.

- **Retraso:** GitHub puede retrasar unos minutos las tareas programadas.
- **Repos sin actividad:** GitHub desactiva el cron de los repos públicos tras 60 días sin actividad. Aquí no pasa, porque cada corrida hace commit: `estado.json` cambia siempre.
- **Si una corrida falla:**
  - no se publica nada y la página sigue con la última versión buena;
  - si la extracción tiene más de 13 horas, Ayuda ya avisa que «puede no estar al día»;
  - GitHub manda un correo a quien activó el workflow.

## Validaciones (no se publica si fallan)

- La extracción trae menos de 1.000 registros (la SNGR tiene unos 2.866).
- El total cae más del 40 % frente a la corrida anterior.
- Hay registros sin coordenadas.

## Puesta en marcha

1. Crea el repo en GitHub, por ejemplo `primicias/nino-albergues-sngr`. Debe ser **público** para que la página lea los archivos con `raw.githubusercontent.com`.
2. Sube esta carpeta:

   ```
   git init && git add . && git commit -m "Pipeline albergues SNGR"
   git branch -M main
   git remote add origin <url del repo>
   git push -u origin main
   ```

3. En **Settings › Actions › General › Workflow permissions**, marca «Read and write permissions».
4. En **Actions**, corre «Albergues SNGR» una vez a mano para comprobarlo.
5. En `03_CÓDIGO/02_AYUDA_YA.html`, pon la URL en `BASE_SNGR`.

## Probar en local

```
npm install
mkdir -p tmp
CHROME_CHANNEL=chrome node scripts/extraer.mjs tmp/crudo.json   # usa el Chrome instalado
curl -fsSL -o tmp/parroquias_2025.json https://raw.githubusercontent.com/tefaceli/fenomeno_nino/main/parroquias/parroquias_2025.json
python3 scripts/procesar.py tmp/crudo.json tmp/parroquias_2025.json data/out
```

## Límites

- **Depende del visor de la SNGR.** Si la SNGR cambia el visor, el nombre de la función o el formato, la extracción falla y lo avisa. Conviene pedir a la SNGR los datos abiertos.
- **No hay estado de cupo.** La SNGR no publica si un albergue está lleno ni la hora de verificación.
- **Errores de origen:**
  - algunos nombres son direcciones;
  - en Guaranda, 8 personas y 35 familias;
  - unos 25 puntos caen en otro cantón;
  - 6 puntos caen fuera de toda parroquia.
- **Atribución obligatoria:** «Fuente: SNGR (Visor Alístate Ecuador). Procesamiento: PRIMICIAS».
