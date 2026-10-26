# Karaoke

Aplicativo de karaokê com backend em Python e interface em Svelte, pensado para rodar localmente no Mac com janela nativa via `pywebview` e também expor um controle remoto pela rede local para celular ou tablet.

## O que o projeto faz

- Reproduz músicas com interface principal estilo TV
- Expõe um controle remoto em `/remote` para celular/tablet via QR code
- Faz download/processamento de músicas
- Separa stems como voz e instrumental
- Sincroniza e exibe letras
- Suporta score de afinação por microfone
- Gera um app macOS em `dist/Karaoke.app`

## Stack usada

- Backend: Python 3.11, FastAPI, Uvicorn, pywebview
- Frontend: Svelte 5 + Vite
- Processamento de áudio/IA: `yt-dlp`, `demucs`, `openai-whisper`, `stable-ts`, `imageio-ffmpeg`
- Empacotamento macOS: script shell em `packaging/build_mac_app.sh`

## Estrutura do projeto

```text
karaoke/
├── backend/                 # servidor, pipeline, setup e lógica principal
│   └── karaoke/
│       └── static/          # build versionado do frontend usado pelo app
├── frontend/                # interface Svelte e build do remoto/TV
├── packaging/               # ícone e script de build do app macOS
└── dist/                    # saída gerada do app empacotado
```

## Requisitos

### Para desenvolvimento

- macOS de preferência, especialmente para o app nativo
- Python 3.11
- Node.js + npm

### Dependências do sistema

- `ffmpeg` e `ffprobe`
  - no macOS, o caminho mais simples é via Homebrew:

```bash
brew install ffmpeg
```

Observação: o app já tenta encontrar binários em `/opt/homebrew/bin` e `/usr/local/bin`, o que ajuda quando ele é aberto pelo Finder.

## Instalação

### 1. Criar o ambiente Python do backend

Na raiz do projeto:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

Esse é o ambiente "leve" do app, usado para rodar o servidor local e a janela nativa.

### 2. Instalar dependências do frontend

```bash
npm --prefix frontend install
```

### 3. Gerar o build do frontend

```bash
npm --prefix frontend run build
```

O build é enviado para `backend/karaoke/static`.

## Como rodar

### Opção 1: servidor web local

```bash
PYTHONPATH=backend .venv/bin/python -m karaoke.server
```

Por padrão ele sobe em `http://localhost:8765`.

### Opção 2: app nativo no macOS

```bash
PYTHONPATH=backend .venv/bin/python -m karaoke.app
```

Isso abre a interface em uma janela nativa via `pywebview`.

## Primeiro uso e ambiente de IA

O processamento pesado de áudio não roda no `.venv` leve. No primeiro uso, o app prepara um ambiente separado em:

- macOS: `~/Library/Application Support/karaoke/ai-venv`

Esse setup instala:

- `torch`
- `torchaudio`
- `yt-dlp`
- `demucs`
- `openai-whisper`
- `stable-ts`
- `imageio-ffmpeg`

Também baixa modelos como:

- `htdemucs`
- `whisper small`

Existe suporte opcional para o modo de 3 faixas, que instala `audio-separator` e modelos extras.

## Build do app macOS

Com o `.venv` criado e o frontend pronto:

```bash
packaging/build_mac_app.sh
```

Se `frontend/node_modules` existir, o script atualiza o build do frontend antes de
montar o app. Se não existir, ele reutiliza o build já presente em
`backend/karaoke/static`.

Saída:

```text
dist/Karaoke.app
```

Depois você pode abrir com:

```bash
open "dist/Karaoke.app"
```

## Fluxo recomendado para empacotar

1. Instalar o backend leve em `.venv`
2. Instalar dependências do frontend
3. Rodar `npm --prefix frontend run build`
4. Rodar `packaging/build_mac_app.sh`

## Git e limpeza do repositório

Foi adicionado um `.gitignore` base para evitar subir arquivos locais e gerados, como:

- `.DS_Store`
- `.venv/`
- `frontend/node_modules/`
- `dist/`

### Importante

O diretório `backend/karaoke/static` **não** está ignorado, porque ele é a saída do build do frontend e pode ser útil manter versionado caso você queira gerar o app sem depender de `node_modules` na máquina de destino.

O repositório foi limpo para conter apenas os arquivos do app novo necessários
para rodar e empacotar o Karaoke.app.

## Comandos úteis

```bash
# instalar backend leve
python3.11 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# instalar frontend
npm --prefix frontend install

# build frontend
npm --prefix frontend run build

# rodar servidor local
PYTHONPATH=backend .venv/bin/python -m karaoke.server

# abrir app nativo
PYTHONPATH=backend .venv/bin/python -m karaoke.app

# gerar bundle macOS
packaging/build_mac_app.sh
```
