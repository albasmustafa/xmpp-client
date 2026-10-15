#!/usr/bin/env python3
"""XMPP istemcisi MCP sunucusu başlatıcısı (stdio).

Kayıt (Claude Code):
    claude mcp add xmpp -- <proje>/.venv-xmpp/bin/python <proje>/xmpp_mcp.py

Erişim, istemcide ✨ → AI Ayarları → "MCP erişimi" açılana kadar kapalıdır.
Ayrıntılar: xmppcore/mcp_server.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xmppcore.mcp_server import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
