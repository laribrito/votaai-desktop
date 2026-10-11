"""
Centralizador de rotas da API do VotaAí Desktop.

Disponibiliza o dicionário `API_ROUTES` para acesso centralizado,
carregando as URLs a partir de `app/resources/api_routes.json`.
"""

import json
import os
from typing import Any, Dict

ROUTES_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "resources", "api_routes.json")
)


def _load_routes() -> Dict[str, Any]:
    if not os.path.exists(ROUTES_FILE):
        raise FileNotFoundError(f"Arquivo de rotas não encontrado em '{ROUTES_FILE}'")

    with open(ROUTES_FILE, "r", encoding="utf-8") as f:
        routes: Dict[str, Any] = json.load(f)

    # Mapeamento de atalhos em maiúsculas a partir das rotas carregadas do JSON
    shortcut_map = {
        "PRE_CADASTRO": ("auth", "pre_cadastro"),
        "CONFIRMAR_PRE_CADASTRO": ("auth", "confirmar_pre_cadastro"),
        "LOGIN": ("auth", "login"),
        "ELECTION_CREATE": ("election", "create"),
        "ELECTION_AVAILABLE": ("election", "list_available"),
        "ELECTION_START": ("election", "start"),
        "PING": ("system", "ping"),
        "PING_DESKTOP": ("system", "ping"),
    }

    for alias, (section, key) in shortcut_map.items():
        routes[alias] = routes.get(section, {}).get(key, "")

    return routes


API_ROUTES: Dict[str, Any] = _load_routes()
