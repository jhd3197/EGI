<div align="center">

# EGI

<img width="720" alt="EGI — Emergencia · Gente · Info" src="../assets/banner.png" />

**EMERGENCIA · GENTE · INFO**

Sistema abierto, offline-first y autohospedable para ayudar a las familias a
encontrarse después de un desastre, incluso cuando el acceso a internet es
limitado o inestable.

[English](../README.md) | Español | [Português](README.pt.md)

<br>

![Offline First](https://img.shields.io/badge/offline-first-E5343B?style=for-the-badge)
![PWA](https://img.shields.io/badge/PWA-ready-1A1714?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-server-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Prompture](https://img.shields.io/badge/Prompture-AI%20extraction-8A2BE2?style=for-the-badge)
![Android](https://img.shields.io/badge/Android-en%20desarrollo-3DDC84?style=for-the-badge&logo=android&logoColor=black)
![BLE](https://img.shields.io/badge/Bluetooth_LE-en%20desarrollo-0082FC?style=for-the-badge&logo=bluetooth&logoColor=white)

[Funciones](#-funciones) · [Inicio rápido](#-inicio-rápido) · [Arquitectura](#-arquitectura) · [Roadmap](#-roadmap) · [Docs](#-documentación) · [Contribuir](#-contribuir)

</div>

---

## 💡 Por Qué Estoy Construyendo Esto

*Este es un proyecto personal, así que déjame contarlo de la forma personal.*

En **diciembre de 1999**, Vargas, Venezuela fue golpeada por uno de los peores
desastres naturales de la historia del país. Días de lluvia convirtieron las
montañas en lodo y agua, y barrios enteros desaparecieron. Yo era apenas un bebé
entonces. Mi familia sobrevivió, gracias a Dios, pero crecí dentro de su memoria.
Mi abuelo, mis bisabuelas y prácticamente cualquiera en Vargas con edad para
recordarlo hablaban del *deslave* durante años. Esa tragedia fue parte del aire
que respiré al crecer.

Cuando tenía como catorce o quince años, hablaba mucho con mi abuelastro,
**Capitán Miguel V**, un viejo bombero. Me enseñó sobre el **terremoto de Caracas
de 1967** y lo que vivió ese día. Edificios partidos en pedazos. Edificios que
cayeron como un mazo de cartas. Vi algunas de las fotos e intenté imaginarlo, y
era espantoso. Mi bisabuela también hablaba de 1967. Para quienes lo contaban no
eran lecciones de historia. Eran recuerdos.

Y sigue vivo. Hace apenas dos o tres meses estaba hablando con la abuela de mi
novia. Ella estuvo ahí en 1967. Es de Chile, pero en ese momento vivía en
Venezuela, y hasta el día de hoy habla de ese día como si hubiera sido ayer.
Creció con terremotos en Chile, estaba acostumbrada a ellos, y aun así me contó
que de verdad pensó que no iba a sobrevivir ese día. Ese fue un 6.6.

En **2010** ocurrió el terremoto de Haití. Yo tenía trece años. Recuerdo juntar y
enviar cosas desde la escuela para ayudar, aunque a esa edad todavía no entendía
de verdad lo que era una tragedia.

Ahora es **2026**, y está pasando otra vez, y esta vez es cerca. Este no fue un
solo terremoto. Fueron dos, uno de 7.5 y otro de 7.2, más réplicas de magnitud 4
y 5 que siguen llegando, una y otra vez, incluso ahora. Vivimos en la era de la
IA y, sin embargo, como sociedad todavía no logramos unirnos para llevar algo de
paz y algo de ayuda a un país en necesidad cuando golpea un desastre. Un miembro
de mi propia familia está desaparecido, y no ha sido encontrado. Estoy lejos, en
otro país, y no hay nada que pueda hacer desde aquí para sacar a nadie de los
escombros. Así que hago lo único que de verdad sé hacer. Escribo código. Este
proyecto es parte de eso, una forma de mantener las manos ocupadas y la cabeza en
otra cosa que no sea lo peor de todo esto.

Porque esto es lo que pasa: con toda la tecnología que tenemos, ¿dónde está la app
para *esto*? Las grandes organizaciones no tienen una lista. Las grandes empresas
de tecnología casi no lo han pensado (gracias, Google, por enviar alertas de
sismo a algunas personas antes del temblor, pero el *después* casi no se
considera). Cuando golpeó el desastre, la respuesta oficial fue un sitio web tipo
ChatGPT. Está bien, y es fácil de montar, pero es la herramienta equivocada para
esto. En un desastre real normalmente **no hay wifi**. La gente no puede reportar.
La gente no puede mantenerse conectada. Y mantenerse conectados, poder **contar** a
las personas, saber quién está vivo, es justo lo que más importa.

Desde la distancia, he hecho todo lo que se me ocurrió: compartir y volver a
compartir publicaciones de personas desaparecidas, sus últimas ubicaciones
conocidas, historias de Instagram, listas de edificios que circulan para ver
quién logró salir con vida. Funciona, un poco. Pero es un caos. Son capturas y
reposts y hojas de cálculo, y nada de eso puede moverse cuando se va el internet.

Por eso estoy construyendo EGI. Lo construyo con lo mejor de mi conocimiento y la
ayuda de la IA, con la **esperanza de que nadie tenga que usarlo nunca**. Pero si
lo necesitan, está listo para funcionar. Si un país lo necesita, si una comunidad
lo necesita, pueden correrlo en un servidor y darle acceso a la gente. Mi
esperanza es que en momentos de tragedia las personas se unan para sostener los
costos del servidor, o que organizaciones donen un servidor, para que este
software se mantenga vivo y accesible cuando más se necesite.

Esa es toda la razón de que esto exista.

---

### Qué hace, en una frase

Después de un desastre, las personas necesitan respuestas rápido:

> ¿Mi familiar está a salvo?  
> ¿Dónde fue visto por última vez?  
> ¿Alguien ya lo reportó?  
> ¿La información puede moverse aunque no haya internet?

**EGI** existe para que la información de emergencia sobre personas sea más fácil
de registrar, buscar, sincronizar, traducir y autohospedar, sobre todo cuando no
hay conectividad y los teléfonos quizá solo puedan alcanzarse entre sí por
Bluetooth.

El nombre significa:

**Emergencia**: creado para situaciones de crisis  
**Gente**: centrado en personas, familias y comunidades  
**Info**: enfocado en información útil y fácil de buscar

Este proyecto nació desde un contexto venezolano, pero está pensado para cualquier
comunidad, en cualquier lugar, que necesite una forma ligera de encontrar a los
suyos.

---

## 🔗 ¿Cómo Funciona la Red Mesh?

En un desastre real normalmente **no hay wifi**, pero casi todo el mundo todavía
lleva un teléfono con Bluetooth en el bolsillo. La app Android de EGI convierte
esos teléfonos en una **cadena humana** que mueve información sin una conexión a
internet que funcione.

Funciona así:

- Los teléfonos Android con EGI que están cerca intercambian registros por
  **Bluetooth**, sin necesidad de internet.
- Un registro salta de teléfono en teléfono, de persona en persona, hasta llegar
  a un teléfono que *sí* tiene internet. Ese teléfono —un **gateway** (puente)—
  sube todo a la nube de EGI. Las actualizaciones de la nube regresan **por la
  misma cadena** hasta los teléfonos que nunca se conectan.
- Si te paras cerca de alguien cuyo teléfono tiene internet (un gateway), tus
  registros se sincronizan con la nube más rápido.

```text
        ☁  Nube / servidor de EGI
        ▲
        │  internet
        │
   ┌─────────┐      ┌─────────┐      ┌─────────┐
   │ Tel. A  │◄─BLE─►│ Tel. B  │◄─BLE─►│ Tel. C  │
   │ GATEWAY │      │ offline │      │ offline │
   │ en línea│      │         │      │         │
   └─────────┘      └─────────┘      └─────────┘

Un registro creado en el Tel. C salta C → B → A por Bluetooth.
El Tel. A (el gateway) lo sube a la nube, y cualquier
actualización de la nube baja por la misma cadena: A → B → C.
```

Esto es **guardar y reenviar** (store-and-forward), no una conexión a internet en
vivo. Nada se transmite en tiempo real. Funciona porque **las personas se mueven y
se agrupan físicamente** —en un punto de agua, una clínica, una camioneta que
reparte víveres— y cada teléfono por el que pasan lleva los datos un poco más
lejos.

### Lo que el mesh no puede hacer (los límites)

- **Solo Android.** El mesh funciona en Android. iOS no es compatible porque
  Apple restringe el Bluetooth en segundo plano: un iPhone no puede anunciar ni
  escanear el protocolo de intercambio de registros de EGI mientras la app está
  en segundo plano, que es justo lo que necesita un relevo en crisis.
- **Alcance corto.** El Bluetooth llega a unos **10–40 metros**. Dos teléfonos
  tienen que acercarse bastante para que los registros salten entre ellos.
- **No es instantáneo.** Cada salto añade demora. Un registro puede tardar
  minutos u horas en llegar a un gateway, según cómo se muevan las personas.
- **Más batería.** Mantener el mesh encendido gasta más batería que un teléfono
  en reposo, porque el Bluetooth está escuchando y reenviando todo el tiempo.
- **Privacidad.** Los registros viajan **de dispositivo a dispositivo** entre
  teléfonos cercanos. El mesh es opcional y está cifrado, pero la marca de
  gateway sí revela que un dispositivo tiene acceso a la nube en ese momento. No
  ingreses información que no estés dispuesto a compartir con desconocidos que
  puedan estar cerca.

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

### 🔵 Bluetooth Mesh (En Desarrollo)

**Solo Android**: el mesh funciona en Android porque ofrece el acceso a Bluetooth en segundo plano que necesita un relevo en crisis; iOS no es compatible (ver [¿Cómo funciona la red mesh?](#-cómo-funciona-la-red-mesh))

**Bluetooth Low Energy**: sincronización peer-to-peer funcional entre teléfonos cercanos (intercambio GATT + bloom filter + guardar y reenviar)

**Guardar y reenviar**: los teléfonos intercambian registros offline y los suben después cuando alguno tenga internet

**Wi-Fi Direct planeado**: transferencia bulk para fotos y grandes lotes de registros

**Borrador del protocolo**: ver [`mobile/shared/protocol.md`](../mobile/shared/protocol.md)

### 📄 Importar Papel Con OCR + IA

**Tesseract OCR**: extrae texto de fotos de listas, volantes o formularios en papel

**Extracción estructurada con Prompture**: convierte el texto OCR en campos como nombre, edad, ubicación y estado

**Procedencia clara**: cada registro OCR guarda de qué imagen fue extraído y su texto original

**Revisión humana**: los registros OCR entran como borradores (`reviewed=0`) hasta que un moderador los aprueba

**Sin papel obligatorio**: también se pueden seguir creando reportes manuales desde la app

### 🧑‍⚖️ Moderación Y Calidad De Datos

**Fila de moderación**: registros de OCR, IA, PFIF y SMS entran como no confiables hasta su revisión (`/moderation/pending`)

**Detección de duplicados**: clustering fuzzy por cédula, nombre+edad y ubicación+tiempo; merge suave con historial preservado

**Confianza de reportes**: los reportes tienen niveles (`self`, `official`, `witness`, `ocr`) y el estado mostrado se deriva del reporte más confiable y reciente

**SMS fallback**: check-in de emergencia vía texto para zonas sin datos (`EGI CHECKIN ...`)

### 🌎 Idiomas

**Español primero**: el proyecto nació desde una emergencia venezolana

**Inglés como segundo idioma**: útil para contribuidores, operadores e iniciativas internacionales

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

La app Android está en desarrollo activo: BLE advertise/scan, intercambio GATT,
Room DB, sincronización con la nube y el bridge a la PWA ya están implementados.
El modo mesh funciona entre dispositivos cercanos; la transferencia bulk por
Wi-Fi Direct y el servicio en primer plano están en progreso. Revisa
[`mobile/android/README.md`](../mobile/android/README.md).

---

## 🏗️ Arquitectura

```text
                              INTERNET DISPONIBLE
                                     │
                                     ▼
┌──────────────────────┐      ┌──────────────────────┐
│      Web / PWA       │      │      App Android      │
│  servida por backend │      │  Base local móvil     │
└──────────┬───────────┘      └──────────┬───────────┘
           │                             │
           │ HTTPS /sync                 │ Sync por Bluetooth LE
           │ + static files              │ (en desarrollo)
           │                             │ Wi-Fi Direct (planeado)
           ▼                             ▼
┌─────────────────────────────────────────────────────┐
│                    Servidor EGI                     │
│         Python + FastAPI + SQLite (puerto 3000)     │
│                                                     │
│  GET  /                app web                      │
│  GET  /persons         buscar registros             │
│  GET  /persons/{id}    obtener un registro          │
│  POST /sync            subir registros modificados  │
│  GET  /sync            descargar registros          │
│  POST /import/paper    OCR + IA en papel escrito    │
│  GET|POST /moderation  fila de revisión             │
│  GET|POST /duplicates  detección de duplicados      │
│  POST /sms/webhook     check-in por SMS             │
└─────────────────────────────────────────────────────┘
```

La app web y la app Android guardan datos localmente primero. El servidor
funciona como centro de sincronización, no como el único lugar donde pueden
existir los registros.

---

## 🗺️ Roadmap

Ver el roadmap completo y actualizado en [`docs/roadmap.md`](roadmap.md). A
continuación, un resumen del estado actual:

### Hecho
- [x] Prototipo web offline-first
- [x] Almacenamiento local en el navegador (actualmente `localStorage`; migración a IndexedDB en progreso, ver plan-06)
- [x] Registro y búsqueda básica de personas
- [x] Archivos públicos de contribución y conducta
- [x] Servidor Python + FastAPI + SQLite
- [x] Sincronización con last-write-wins por timestamp
- [x] Endpoint OCR para importar reportes en papel
- [x] Extracción estructurada con Prompture / LLM local
- [x] Fila de moderación (`/moderation`)
- [x] Detección fuzzy de duplicados y merge suave (`/duplicates`)
- [x] Derivación de estado por confianza (`self > official > witness > ocr`)
- [x] Check-in por SMS (`/sms/webhook`)
- [x] CLI `egi` (backend, frontend, build, seed, unseed, export/import, synthetic)
- [x] Carpeta Android con BLE advertise/scan, GATT exchange, Room DB, cloud sync y JS bridge
- [x] Tests servidor + frontend + CI

### En Progreso
- [ ] Migrar cache PWA de `localStorage` a IndexedDB
- [ ] Cifrado del mesh Bluetooth y aviso de privacidad
- [ ] UI del mesh en la PWA
- [ ] Reportes (PFIF notes) sobre el mesh
- [ ] Transferencia bulk por Wi-Fi Direct

### Pendiente
- [ ] Estructura multilenguaje para la interfaz
- [ ] Textos de la app en español, inglés y portugués
- [ ] Importar y exportar registros locales (CLI parcial; UI pendiente)
- [ ] Soporte para fotos con controles cuidadosos de privacidad
- [ ] WebView wrapper de Android completamente integrado
- [ ] Guía de despliegue para VPS y servidores comunitarios
- [ ] Revisión de seguridad y privacidad (CORS, rate limiting, auth de operadores)
- [ ] Revisión de accesibilidad

---

## 📖 Documentación

| Documento | Descripción |
|-----------|-------------|
| [`README.md`](../README.md) | README en inglés (raíz) |
| [`docs/README.en.md`](README.en.md) | README en inglés |
| [`docs/README.pt.md`](README.pt.md) | README en portugués |
| [`docs/roadmap.md`](roadmap.md) | Roadmap consolidado de planes 01-07 |
| [`frontend/README.md`](../frontend/README.md) | Configuración, despliegue y TODOs del prototipo web |
| [`server/README.md`](../server/README.md) | Endpoints de la API, OCR y configuración del servidor Python |
| [`mobile/android/README.md`](../mobile/android/README.md) | Dirección de la app Android y notas sobre Bluetooth |
| [`mobile/shared/protocol.md`](../mobile/shared/protocol.md) | Borrador del protocolo Bluetooth mesh |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | Cómo contribuir |
| [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) | Expectativas de la comunidad |
| [`LICENSE`](../LICENSE) | Licencia MIT |

---

## 🧱 Stack Técnico

| Capa | Tecnología |
|------|------------|
| App web | React + Vite (PWA offline-first) |
| Almacenamiento web local | `localStorage` actualmente (migración a IndexedDB planificada) |
| Servidor | Python, FastAPI |
| Base de datos | SQLite |
| OCR / IA | Tesseract + Prompture / Ollama / OpenAI |
| Móvil | Android (Kotlin + Room + BLE) |
| Mesh offline | Bluetooth Low Energy + Wi-Fi Direct (planeado), solo Android |
| Despliegue | Backend único sirve web + API; VPS o servidor comunitario |
| Tests | pytest (servidor), vitest (frontend), tests unitarios JVM (Android) |

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

Las contribuciones son bienvenidas. Lee [`CONTRIBUTING.md`](../CONTRIBUTING.md)
antes de abrir un pull request.

```text
fork -> rama de feature -> commit -> push -> pull request
```

Áreas prioritarias:

- Migración del cache PWA de `localStorage` a IndexedDB
- Cifrado del mesh Bluetooth y aviso de privacidad
- UI del mesh en la PWA
- Reportes (PFIF notes) sobre el mesh
- Transferencia bulk por Wi-Fi Direct
- Interfaz multilenguaje (es/en/pt) y lenguas comunitarias
- Accesibilidad y UX con lenguaje claro
- Revisión de seguridad y privacidad (CORS, rate limiting, auth de operadores)
- Documentación de despliegue para VPS y servidores comunitarios
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
