#!/bin/bash
# Gera Karaoke.app (bundle de macOS) a partir deste repositório.
#
#   packaging/build_mac_app.sh
#
# O .app é um lançador fino: abre o backend novo (karaoke.app) pelo venv leve do
# repositório e mostra a interface numa janela nativa (WebView). O ambiente de IA
# (~2 GB) continua sendo instalado no primeiro uso, na tela de configuração do
# próprio app.
#
# Saída: dist/Karaoke.app
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$REPO/dist"
APP="$DIST/Karaoke.app"
PY="$REPO/.venv/bin/python"
BACKEND="$REPO/backend"

if [[ ! -x "$PY" ]]; then
  echo "venv leve não encontrado em $PY" >&2
  echo "crie com: python3.11 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

if ! "$PY" - <<'PY' >/dev/null 2>&1
import webview
PY
then
  echo "pywebview não encontrado no venv leve" >&2
  echo "instale com: .venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

# Atualiza o build do frontend se houver node_modules (senão usa o build já commitado).
if [[ -d "$REPO/frontend/node_modules" ]] && command -v npm >/dev/null 2>&1; then
  echo "▶ buildando frontend (vite)"
  (cd "$REPO/frontend" && npm run build)
else
  echo "· pulando build do frontend (use o build já existente em backend/karaoke/static)"
fi

echo "▶ montando $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# Ícone do app (Dock/Finder): AppIcon.icns ao lado deste script.
if [[ -f "$REPO/packaging/AppIcon.icns" ]]; then
  cp "$REPO/packaging/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
else
  echo "· AppIcon.icns não encontrado (o app fica com o ícone padrão)"
fi

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Karaoke</string>
  <key>CFBundleDisplayName</key><string>Karaokê</string>
  <key>CFBundleIdentifier</key><string>br.local.karaoke</string>
  <key>CFBundleExecutable</key><string>Karaoke</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>LSMultipleInstancesProhibited</key><true/>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>O Karaokê usa o microfone para medir a afinação e calcular o score.</string>
  <key>NSAppTransportSecurity</key>
  <dict>
    <key>NSAllowsArbitraryLoadsInWebContent</key><true/>
    <key>NSAllowsLocalNetworking</key><true/>
  </dict>
</dict>
</plist>
PLIST

# Lançador: aponta para o venv leve e o backend deste repositório.
cat > "$APP/Contents/MacOS/Karaoke" <<EOF
#!/bin/bash
export PYTHONPATH="$BACKEND\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$PY" -m karaoke.app "\$@"
EOF
chmod +x "$APP/Contents/MacOS/Karaoke"

echo "✔ pronto: $APP"
echo "  abra com: open \"$APP\""
