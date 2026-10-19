#!/usr/bin/env bash
# XMPP Web arayüzü başlatıcı — venv içindeki Python ile webapp.server'ı çalıştırır.
# Tarayıcıdan: http://127.0.0.1:8420/
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -x "$DIR/.venv-xmpp/bin/python" ]; then
    echo "Hata: .venv-xmpp bulunamadı. Kurulum için:" >&2
    echo "  python3 -m venv '$DIR/.venv-xmpp'" >&2
    echo "  '$DIR/.venv-xmpp/bin/python' -m pip install -r '$DIR/requirements.txt'" >&2
    exit 1
fi

# -m ile modül araması çalışma dizinine bakar; hangi klasörden
# çağrılırsa çağrılsın proje kökünden çalıştır.
cd "$DIR"
exec "$DIR/.venv-xmpp/bin/python" -m webapp.server "$@"
