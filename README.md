<div align="center">

# EGI

<img width="720" alt="Vista previa de EGI en móvil" src="frontend/screenshots/mobile-home.png" />

**EMERGENCIA · GENTE · INFO**

Sistema abierto, offline-first y autohospedable para ayudar a las familias a
encontrarse después de un desastre, incluso cuando el acceso a internet es
limitado o inestable.

Español | [English](docs/README.en.md) | [Português](docs/README.pt.md) | Más idiomas bienvenidos

<br>

![Offline First](https://img.shields.io/badge/offline-first-E5343B?style=for-the-badge)
![PWA](https://img.shields.io/badge/PWA-ready-1A1714?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-server-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Prompture](https://img.shields.io/badge/Prompture-AI%20extraction-8A2BE2?style=for-the-badge)
![Android](https://img.shields.io/badge/Android-planeado-3DDC84?style=for-the-badge&logo=android&logoColor=black)
![BLE](https://img.shields.io/badge/Bluetooth_LE-planeado-0082FC?style=for-the-badge&logo=bluetooth&logoColor=white)

[Funciones](#-funciones) · [Inicio rápido](#-inicio-rápido) · [Capturas](#-capturas) · [Arquitectura](#-arquitectura) · [Ruta](#-ruta-del-proyecto) · [Docs](#-documentación) · [Contribuir](#-contribuir)

</div>

---

## 💡 Por Qué Existe EGI

Después de un desastre, las personas necesitan respuestas rápido:

> ¿Mi familiar está a salvo?  
> ¿Dónde fue visto por última vez?  
> ¿Alguien ya lo reportó?  
> ¿La información puede moverse aunque no haya internet?

En muchas emergencias, la gente termina usando grupos de WhatsApp, capturas,
reposts, listas en papel y hojas de cálculo. Esas herramientas ayudan, pero son
difíciles de buscar, fáciles de duplicar y complicadas de mantener actualizadas.

**EGI** existe para que la información de emergencia sobre personas sea más
fácil de registrar, buscar, sincronizar, traducir y autohospedar.

El nombre significa:

**Emergencia**: creado para situaciones de crisis  
**Gente**: centrado en personas, familias y comunidades  
**Info**: enfocado en información útil y fácil de buscar

Este proyecto nació desde un contexto venezolano, pero está pensado para
cualquier comunidad que necesite un sistema ligero de reunificación familiar.

---

## 📸 Capturas

> Capturas de prototipo/demo. La información mostrada en las capturas debe tratarse como ficticia salvo que se indique lo contrario.

<details open>
<summary><strong>Inicio móvil</strong>: panel de emergencia, búsqueda de personas, reportes y estado offline</summary>

![Inicio móvil de EGI](frontend/screenshots/mobile-home.png)

</details>

<details>
<summary><strong>Modal en escritorio</strong>: flujo en pantalla grande para ver o editar información de emergencia</summary>

![Modal de EGI en escritorio](frontend/screenshots/desktop-modal.png)

</details>

---

## 🎯 Funciones

### 🧭 Registro De Emergencia

**Reportes de personas**: registra a alguien como `missing`, `found`, `safe` o `deceased`

**Búsqueda local**: busca por nombre, estado, ubicación, notas u otras palabras clave

**Contexto por evento**: pensado para un desastre o emergencia específica, no como una base de datos genérica

**Autohospedaje comunitario**: cualquier grupo puede desplegar su propio servidor y manejar sus propios datos

### 📡 Offline First

**Guardado local**: la app web guarda los registros primero en el dispositivo

**Progressive Web App**: funciona desde el navegador y puede instalarse en teléfonos compatibles

**Sincronización al volver internet**: los registros pueden sincronizarse con el servidor cuando haya conexión

**Diseño para baja conectividad**: pensado para teléfonos, datos inestables y condiciones de crisis

### 🔵 Visión Bluetooth Mesh

**Android primero**: la futura app nativa se enfocará en Android porque ofrece mejor acceso a Bluetooth

**Bluetooth Low Energy**: sincronización peer-to-peer planeada entre teléfonos cercanos

**Guardar y reenviar**: los teléfonos pueden intercambiar registros offline y subirlos después cuando alguno tenga internet

**Borrador del protocolo**: ver [`mobile/shared/protocol.md`](mobile/shared/protocol.md)

### 📄 Importar Papel Con OCR + IA

**Tesseract OCR**: extrae texto de fotos de listas, volantes o formularios en papel

**Extracción estructurada con Prompture**: convierte el texto OCR en campos como nombre, edad, ubicación y estado

**Procedencia clara**: cada registro OCR guarda de qué imagen fue extraído y su texto original

**Revisión humana**: los registros OCR entran como borradores (`reviewed=0`) hasta que un moderador los aprueba

**Sin papel obligatorio**: también se pueden seguir creando reportes manuales desde la app

### 🌎 Idiomas

**Español primero**: el proyecto nació desde una emergencia venezolana

**Inglés como segundo idioma**: útil para contribuidores, operadores e iniciativas internacionales

**Más idiomas bienvenidos**: portugués, lenguas indígenas y traducciones de comunidades locales

**Lenguaje claro**: el software de emergencia debe entenderse sin ser técnico

### 🔒 Seguridad Y Privacidad

**Sin publicidad ni tracking**: este proyecto no debe monetizar datos de crisis

**Mínima recolección de datos**: solo se debe pedir información útil para reunificación y respuesta

**Listo para moderación**: los despliegues públicos deben revisar reportes falsos, dañinos, duplicados o abusivos

**Cuidado con datos sensibles**: fotos, teléfonos, cédulas, documentos y direcciones exactas requieren especial atención

---

## 🚀 Inicio Rápido

### App Web

El backend sirve el frontend automáticamente. Con el servidor corriendo en
`http://localhost:3000`, abre:

```text
http://localhost:3000
```

Para desarrollo solo de UI también puedes servir `frontend/` por separado:

```bash
cd frontend
python -m http.server 8081
```

### Servidor

Ejecuta la API de sincronización con Python, FastAPI y SQLite:

```bash
cd server
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python -m db
uvicorn main:app --host 0.0.0.0 --port 3000 --reload
```

URL por defecto de la API:

```text
http://localhost:3000
```

La app web apunta a `http://localhost:3000` por defecto. Para usar un servidor
desplegado, configura la URL de la API en el navegador:

```js
localStorage.setItem('egi_api_url', 'https://tu-servidor.example.com');
```

### Android

La app Android está planeada y parcialmente estructurada. Revisa
[`mobile/android/README.md`](mobile/android/README.md) para ver la dirección
actual.

---

## 🏗️ Arquitectura

```text
                              INTERNET DISPONIBLE
                                     │
                                     ▼
┌──────────────────────┐      ┌──────────────────────┐
│      Web / PWA       │      │      App Android      │
│  sirvida por backend │      │  Base local móvil     │
└──────────┬───────────┘      └──────────┬───────────┘
           │                             │
           │ HTTPS /sync                 │ Sync por Bluetooth LE
           │ + static files              │ (planeado)
           ▼                             ▼
┌─────────────────────────────────────────────────────┐
│                    Servidor EGI                     │
│         Python + FastAPI + SQLite (puerto 3000)     │
│                                                     │
│  GET /               app web                        │
│  GET /persons        buscar registros               │
│  GET /persons/{id}   obtener un registro            │
│  POST /sync          subir registros modificados    │
│  GET /sync           descargar registros modificados│
│  POST /import/paper  OCR + IA en papel escrito      │
└─────────────────────────────────────────────────────┘
```

La app web y la futura app Android deben guardar datos localmente primero. El
servidor funciona como centro de sincronización, no como el único lugar donde
pueden existir los registros.

---

## 🗺️ Ruta Del Proyecto

- [x] Prototipo web offline-first
- [x] Almacenamiento local en el navegador con IndexedDB
- [x] Registro y búsqueda básica de personas
- [x] Servidor de sincronización con Node.js + SQLite
- [x] Archivos públicos de contribución y conducta
- [x] Carpeta Android y borrador del protocolo Bluetooth
- [ ] Estructura multilenguaje para la interfaz
- [ ] Textos de la app en español e inglés
- [ ] Importar y exportar registros locales
- [x] Servidor Python + FastAPI + SQLite
- [x] Endpoint OCR para importar reportes en papel
- [x] Extracción estructurada con Prompture
- [ ] Soporte para fotos con controles cuidadosos de privacidad
- [ ] Detección de duplicados y flujo de unión de registros
- [ ] Cola de moderación para despliegues públicos
- [ ] Wrapper Android WebView
- [ ] Base de datos local nativa en Android
- [ ] Descubrimiento y conexión por Bluetooth LE
- [ ] Intercambio de registros por Bluetooth
- [ ] Guía de despliegue para VPS y servidores comunitarios
- [ ] Revisión de seguridad y privacidad
- [ ] Revisión de accesibilidad

---

## 📖 Documentación

| Documento | Descripción |
|-----------|-------------|
| [`docs/README.en.md`](docs/README.en.md) | README en inglés |
| [`docs/README.pt.md`](docs/README.pt.md) | README en portugués |
| [`frontend/README.md`](frontend/README.md) | Configuración, despliegue y TODOs del prototipo web |
| [`server/README.md`](server/README.md) | Endpoints de la API, OCR y configuración del servidor Python |
| [`mobile/android/README.md`](mobile/android/README.md) | Dirección de la app Android y notas sobre Bluetooth |
| [`mobile/shared/protocol.md`](mobile/shared/protocol.md) | Borrador del protocolo Bluetooth mesh |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Cómo contribuir |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Expectativas de la comunidad |
| [`LICENSE`](LICENSE) | Licencia MIT |

---

## 🧱 Stack Técnico

| Capa | Tecnología |
|------|------------|
| App web | React + Vite (PWA offline-first) |
| Almacenamiento web local | IndexedDB |
| Servidor | Python, FastAPI |
| Base de datos | SQLite |
| OCR / IA | Tesseract + Prompture |
| Móvil | Android planeado, dirección Kotlin |
| Mesh offline | Bluetooth Low Energy planeado |
| Despliegue | Host estático para web, VPS o servidor pequeño para API |

---

## 🔒 Principios De Privacidad

EGI puede manejar información personal sensible. Trátala con cuidado.

- Recolectar solo la información mínima y útil.
- Usar HTTPS en despliegues públicos.
- Respaldar la base de datos de forma segura.
- Evitar publicar teléfonos, cédulas, documentos, direcciones exactas o fotos innecesarias.
- Marcar claramente los reportes no verificados.
- Preferir correcciones e historial antes que borrar datos silenciosamente.
- No agregar analíticas, publicidad ni píxeles de rastreo.
- Remover rápidamente contenido dañino, falso, abusivo o explotador.

EGI es una herramienta de coordinación comunitaria. No reemplaza a servicios de
emergencia, refugios, hospitales, respondedores locales ni organizaciones
humanitarias confiables.

---

## 🤝 Contribuir

Las contribuciones son bienvenidas. Lee [`CONTRIBUTING.md`](CONTRIBUTING.md)
antes de abrir un pull request.

```text
fork -> rama de feature -> commit -> push -> pull request
```

Áreas prioritarias:

- Sincronización Android por Bluetooth Low Energy
- Mejoras a la PWA offline-first
- Traducciones en español e inglés
- Accesibilidad y UX con lenguaje claro
- Revisión de seguridad y privacidad
- Documentación de despliegue
- Detección de duplicados y flujos de moderación
- Pruebas reales en entornos con baja conectividad

Las contribuciones pequeñas importan. Si encuentras un bug, abre un issue. Si
puedes arreglarlo, abre un pull request.

---

## ⚠️ Aviso

EGI es un proyecto comunitario open-source, no un servicio oficial del gobierno
ni una autoridad de emergencia. La información registrada puede estar incompleta,
duplicada, desactualizada o sin verificar.

En una emergencia, sigue las instrucciones oficiales de seguridad cuando estén
disponibles y contacta a servicios de emergencia, refugios, hospitales u
organizaciones humanitarias confiables.

---

<div align="center">

**EGI**: Emergencia · Gente · Info

Hecho por Venezuela, y por cada lugar donde una familia intenta encontrar a los suyos.

</div>
