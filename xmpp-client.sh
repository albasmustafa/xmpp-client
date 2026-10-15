#!/usr/bin/env bash
# XMPP İstemcisi başlatıcı — venv içindeki Python ile xmpp.py'yi çalıştırır.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -x "$DIR/.venv-xmpp/bin/python" ]; then
    echo "Hata: .venv-xmpp bulunamadı. Kurulum için:" >&2
    echo "  python3 -m venv '$DIR/.venv-xmpp'" >&2
    echo "  '$DIR/.venv-xmpp/bin/python' -m pip install -r '$DIR/requirements.txt'" >&2
    exit 1
fi

exec "$DIR/.venv-xmpp/bin/python" "$DIR/xmpp.py" "$@"
