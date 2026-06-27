<div align="center">

# EGI

<img width="720" alt="Prévia do EGI no celular" src="../frontend/screenshots/mobile-home.png" />

**EMERGENCIA · GENTE · INFO**

Sistema aberto, offline-first e auto-hospedável para ajudar famílias a se
reencontrarem depois de um desastre, mesmo quando o acesso à internet é limitado
ou instável.

[English](../README.md) | [Español](README.es.md) | Português | Mais idiomas bem-vindos

<br>

![Offline First](https://img.shields.io/badge/offline-first-E5343B?style=for-the-badge)
![PWA](https://img.shields.io/badge/PWA-ready-1A1714?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-server-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Prompture](https://img.shields.io/badge/Prompture-AI%20extraction-8A2BE2?style=for-the-badge)
![Android](https://img.shields.io/badge/Android-in%20development-3DDC84?style=for-the-badge&logo=android&logoColor=black)
![BLE](https://img.shields.io/badge/Bluetooth_LE-in%20development-0082FC?style=for-the-badge&logo=bluetooth&logoColor=white)

[Recursos](#-recursos) · [Início rápido](#-início-rápido) · [Capturas](#-capturas) · [Arquitetura](#-arquitetura) · [Roteiro](#-roteiro) · [Docs](#-documentação) · [Contribuir](#-contribuir)

</div>

---

## 💡 Por Que O EGI Existe

Depois de um desastre, as pessoas precisam de respostas rapidamente:

> Meu familiar está em segurança?  
> Onde ele foi visto pela última vez?  
> Alguém já fez um registro?  
> A informação ainda consegue circular se a internet cair?

Em muitas emergências, as pessoas acabam usando grupos de WhatsApp, capturas de
tela, reposts, listas em papel e planilhas. Essas ferramentas ajudam, mas são
difíceis de pesquisar, fáceis de duplicar e complicadas de manter atualizadas.

**EGI** existe para tornar informações de emergência sobre pessoas mais fáceis
de registrar, buscar, sincronizar, traduzir e auto-hospedar.

O nome significa:

**Emergencia**: criado para situações de crise  
**Gente**: centrado em pessoas, famílias e comunidades  
**Info**: focado em informação útil e pesquisável

Este projeto nasceu de um contexto venezuelano, mas foi pensado para qualquer
comunidade que precise de um sistema leve de reunificação familiar.

---

## 📸 Capturas

> Capturas de protótipo/demo. As informações mostradas nas imagens devem ser tratadas como fictícias, salvo indicação em contrário.

<details open>
<summary><strong>Início no celular</strong>: painel de emergência, busca de pessoas, ações de registro e estado offline</summary>

![Início móvel do EGI](../frontend/screenshots/mobile-home.png)

</details>

<details>
<summary><strong>Modal no desktop</strong>: fluxo em tela maior para ver ou editar informações de emergência</summary>

![Modal do EGI no desktop](../frontend/screenshots/desktop-modal.png)

</details>

---

## 🎯 Recursos

### 🧭 Registro De Emergência

**Registros de pessoas**: registre alguém como `missing`, `found`, `safe` ou `deceased`

**Busca local**: pesquise por nome, status, localização, notas ou outras palavras-chave

**Contexto por evento**: pensado para um desastre ou emergência específica, não como uma base de dados genérica

**Hospedagem comunitária**: qualquer grupo pode implantar seu próprio servidor e gerenciar seus próprios dados

### 📡 Offline First

**Armazenamento local**: o app web salva os registros primeiro no dispositivo

**Progressive Web App**: funciona pelo navegador e pode ser instalado em celulares compatíveis

**Sincronização ao voltar a internet**: os registros podem sincronizar com o servidor quando houver conexão

**Design para baixa conectividade**: pensado para celulares, dados instáveis e condições de crise

### 🔵 Mesh Bluetooth (Em Desenvolvimento)

**Android primeiro**: o app nativo tem foco em Android porque a plataforma oferece melhor acesso a Bluetooth

**Bluetooth Low Energy**: sincronização peer-to-peer funcional entre celulares próximos (troca de índice GATT + bloom filter + store-and-forward)

**Armazenar e encaminhar**: celulares podem trocar registros offline e enviar depois quando algum tiver internet

**Wi-Fi Direct planejado**: transferência bulk para fotos e grandes lotes de registros

**Rascunho do protocolo**: veja [`mobile/shared/protocol.md`](../mobile/shared/protocol.md)

### 📄 Importar Papel Com OCR + IA

**Tesseract OCR**: extrai texto de fotos de listas, volantes ou formulários em papel

**Extração estruturada com Prompture**: converte o texto OCR em campos como nome, idade, localização e status

**Procedência clara**: cada registro OCR guarda de qual imagem foi extraído e seu texto original

**Revisão humana**: os registros OCR entram como rascunhos (`reviewed=0`) até que um moderador os aprove

**Papel não é obrigatório**: também se podem seguir criando relatórios manuais pelo app

### 🧑‍⚖️ Moderação E Qualidade De Dados

**Fila de moderação**: registros de OCR, IA, PFIF e SMS entram como não confiáveis até revisão (`/moderation/pending`)

**Detecção de duplicados**: agrupamento fuzzy por cédula, nome+idade e localização+tempo; merge suave com histórico preservado

**Confiança dos relatórios**: relatórios têm níveis (`self`, `official`, `witness`, `ocr`) e o status mostrado deriva do relatório mais confiável e recente

**Fallback por SMS**: check-in de emergência via texto para zonas sem dados (`EGI CHECKIN ...`)

### 🌎 Idiomas

**Espanhol primeiro**: o projeto nasceu a partir de uma emergência venezuelana

**Inglês como segundo idioma**: útil para contribuidores, operadores e equipes internacionais

**Mais idiomas são bem-vindos**: português, línguas indígenas e traduções de comunidades locais

**Linguagem clara**: software de emergência deve ser compreensível sem conhecimento técnico

### 🔒 Segurança E Privacidade

**Sem anúncios nem rastreamento**: este projeto não deve monetizar dados de crise

**Coleta mínima de dados**: peça apenas informações úteis para reunificação e resposta

**Pronto para moderação**: implantações públicas devem revisar registros falsos, prejudiciais, duplicados ou abusivos

**Cuidado com dados sensíveis**: fotos, telefones, documentos, números de identidade e endereços exatos exigem atenção especial

---

## 🚀 Início Rápido

### App Web

O backend serve o frontend automaticamente. Com o servidor rodando em
`http://localhost:3000`, abra:

```text
http://localhost:3000
```

Para desenvolvimento apenas da UI, você também pode servir `frontend/` separadamente:

```bash
cd frontend
python -m http.server 8081
```

### Servidor

Execute a API de sincronização com Python, FastAPI e SQLite:

```bash
cd server
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
python -m db
uvicorn main:app --host 0.0.0.0 --port 3000 --reload
```

URL padrão (frontend + API):

```text
http://localhost:3000
```

Para usar um servidor implantado, configure a URL da API no navegador:

```js
localStorage.setItem('egi_api_url', 'https://seu-servidor.example.com');
```

### Android

O app Android está em desenvolvimento ativo: BLE advertise/scan, troca GATT,
Room DB, sincronização com a nuvem e o bridge para a PWA já estão implementados.
O modo mesh funciona entre dispositivos próximos; a transferência bulk por Wi-Fi
Direct e o serviço em primeiro plano estão em progresso. Veja
[`mobile/android/README.md`](../mobile/android/README.md) para a direção atual.

---

## 🏗️ Arquitetura

```text
                              INTERNET DISPONÍVEL
                                     │
                                     ▼
┌──────────────────────┐      ┌──────────────────────┐
│      Web / PWA       │      │      App Android      │
│  servida pelo backend│      │  Base local móvel     │
└──────────┬───────────┘      └──────────┬───────────┘
           │                             │
           │ HTTPS /sync                 │ Sync por Bluetooth LE
           │ + arquivos estáticos        │ (em desenvolvimento)
           │                             │ Wi-Fi Direct (planejado)
           ▼                             ▼
┌─────────────────────────────────────────────────────┐
│                    Servidor EGI                     │
│         Python + FastAPI + SQLite (porta 3000)      │
│                                                     │
│  GET /                app web                       │
│  GET /persons         buscar registros              │
│  GET /persons/{id}    obter um registro             │
│  POST /sync           subir registros modificados   │
│  GET /sync            baixar registros modificados  │
│  POST /import/paper   OCR + IA em papel escrito     │
│  GET|POST /moderation fila de revisão               │
│  GET|POST /duplicates detecção de duplicados        │
│  POST /sms/webhook    check-in por SMS              │
└─────────────────────────────────────────────────────┘
```

O app web e o app Android devem manter dados localmente primeiro. O
servidor funciona como centro de sincronização, não como o único lugar onde os
registros podem existir.

---

## 🗺️ Roteiro

Veja o roadmap completo e atualizado em [`docs/roadmap.md`](roadmap.md). Abaixo,
um resumo do estado atual:

### Feito
- [x] Protótipo web offline-first
- [x] Armazenamento local no navegador (atualmente `localStorage`; migração para IndexedDB em andamento, ver plan-06)
- [x] Registro e busca básica de pessoas
- [x] Arquivos públicos de contribuição e conduta
- [x] Servidor Python + FastAPI + SQLite
- [x] Sincronização do servidor com last-write-wins protegido por timestamp
- [x] Endpoint OCR para importar relatórios em papel
- [x] Extração estruturada com Prompture / LLM local fallback
- [x] Fila de moderação (`/moderation`)
- [x] Detecção fuzzy de duplicados e fluxo de merge suave (`/duplicates`)
- [x] Status derivado por confiança (`self > official > witness > ocr`)
- [x] Check-in por SMS fallback (`/sms/webhook`)
- [x] CLI `egi` (backend, frontend, build, seed, unseed, export/import, synthetic)
- [x] Pasta Android com BLE advertise/scan, troca GATT, Room DB, sync cloud, bridge JS
- [x] Suítes de testes do servidor e frontend + CI

### Em Progresso
- [ ] Migrar cache PWA de `localStorage` para IndexedDB
- [ ] Criptografia do mesh Bluetooth e aviso de privacidade
- [ ] UI do mesh na PWA
- [ ] Relatórios (notas PFIF) sobre o mesh
- [ ] Transferência bulk por Wi-Fi Direct

### Pendente
- [ ] Estrutura multilíngue da interface
- [ ] Textos do app em espanhol, inglês e português
- [ ] Importação e exportação de registros locais (CLI parcial; UI pendente)
- [ ] Suporte a fotos com controles cuidadosos de privacidade
- [ ] Wrapper Android WebView totalmente integrado
- [ ] Guia de implantação para VPS e servidores comunitários
- [ ] Revisão de segurança e privacidade (CORS, rate limiting, auth de operadores)
- [ ] Revisão de acessibilidade

---

## 📖 Documentação

| Documento | Descrição |
|-----------|-----------|
| [`README.md`](../README.md) | README em inglês (raiz) |
| [`docs/README.en.md`](README.en.md) | README em inglês |
| [`docs/README.es.md`](README.es.md) | README em espanhol |
| [`docs/roadmap.md`](roadmap.md) | Roadmap consolidado dos planos 01-07 |
| [`frontend/README.md`](../frontend/README.md) | Configuração, implantação e TODOs do app web |
| [`server/README.md`](../server/README.md) | Endpoints da API, OCR e configuração do servidor Python |
| [`mobile/android/README.md`](../mobile/android/README.md) | Direção do app Android e notas sobre Bluetooth |
| [`mobile/shared/protocol.md`](../mobile/shared/protocol.md) | Rascunho do protocolo Bluetooth mesh |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | Como contribuir |
| [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) | Expectativas da comunidade |
| [`LICENSE`](../LICENSE) | Licença MIT |

---

## 🧱 Stack Técnico

| Camada | Tecnologia |
|--------|------------|
| App web | React + Vite (PWA offline-first) |
| Armazenamento web local | `localStorage` (migração para IndexedDB planejada) |
| Servidor | Python, FastAPI |
| Banco de dados | SQLite |
| OCR / IA | Tesseract + Prompture / Ollama / OpenAI |
| Mobile | Android (Kotlin + Room + BLE) |
| Mesh offline | Bluetooth Low Energy + Wi-Fi Direct (planejado) |
| Implantação | Backend único serve web + API; VPS ou servidor pequeno |
| Testes | pytest (servidor), vitest (frontend), testes unitários JVM (Android), GitHub Actions CI |

---

## 🔒 Princípios De Privacidade

EGI pode lidar com informações pessoais sensíveis. Trate-as com cuidado.

- Coletar apenas a informação mínima e útil.
- Usar HTTPS em implantações públicas.
- Fazer backup seguro do banco de dados.
- Evitar publicar telefones, documentos, endereços exatos ou fotos desnecessárias.
- Marcar claramente registros não verificados.
- Preferir correções e histórico em vez de apagar dados silenciosamente.
- Não adicionar analytics, publicidade nem pixels de rastreamento.
- Remover rapidamente conteúdo prejudicial, falso, abusivo ou exploratório.

EGI é uma ferramenta de coordenação comunitária. Não substitui serviços de
emergência, abrigos, hospitais, equipes locais nem organizações humanitárias
confiáveis.

---

## 🤝 Contribuir

Contribuições são bem-vindas. Leia [`CONTRIBUTING.md`](../CONTRIBUTING.md)
antes de abrir um pull request.

```text
fork -> branch de feature -> commit -> push -> pull request
```

Áreas prioritárias:

- Migrar cache PWA de `localStorage` para IndexedDB
- Criptografia do mesh Bluetooth e aviso de privacidade
- UI do mesh na PWA
- Relatórios (notas PFIF) sobre o mesh
- Transferência bulk por Wi-Fi Direct
- Interface multilíngue (es/en/pt) e línguas comunitárias
- Acessibilidade e UX com linguagem clara
- Revisão de segurança e privacidade (CORS, rate limiting, auth de operadores)
- Documentação de implantação para VPS e servidores comunitários
- Testes reais em ambientes com baixa conectividade

Pequenas contribuições importam. Se encontrar um bug, abra uma issue. Se puder
corrigir, abra um pull request.

---

## ⚠️ Aviso

EGI é um projeto comunitário open-source, não um serviço oficial do governo nem
uma autoridade de emergência. As informações registradas podem estar
incompletas, duplicadas, desatualizadas ou não verificadas.

Em uma emergência, siga as instruções oficiais de segurança quando disponíveis e
entre em contato com serviços de emergência, abrigos, hospitais ou organizações
humanitárias confiáveis.

---

<div align="center">

**EGI**: Emergencia · Gente · Info

Feito pela Venezuela, e por todo lugar onde uma família tenta encontrar os seus.

</div>
