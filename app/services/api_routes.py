"""
Centralizador de rotas da API do VotaAí Desktop.

Disponibiliza o dicionário `API_ROUTES` e a classe `ApiRoutes` para acesso
centralizado, prevenindo duplicação de URLs e facilitando manutenção.
Os valores padrão são sincronizados com `app/resources/api_routes.json`.
"""

import json
import os
from typing import Any, Dict

ROUTES_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "resources", "api_routes.json")
)

DEFAULT_ROUTES: Dict[str, Any] = {
    "auth": {
        "pre_cadastro": "/api/admin/pre-registration/",
        "confirmar_pre_cadastro": "/api/admin/pre-registration/confirm/",
        "login": "/api/auth/login/",
    },
    "election": {
        "create": "/api/election/create/",
        "list_available": "/api/election/available/",
        "start": "/api/election/start/",
    },
    "system": {
        "ping": "/api/ping-desktop/",
    },
}


def _load_routes() -> Dict[str, Any]:
    routes: Dict[str, Any] = json.loads(json.dumps(DEFAULT_ROUTES))
    if os.path.exists(ROUTES_FILE):
        try:
            with open(ROUTES_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    routes.update(loaded)
        except Exception as e:
            print(f"[Aviso] Falha ao carregar '{ROUTES_FILE}': {e}. Usando rotas padrão.")

    # Atalhos diretos em maiúsculas para praticidade
    auth_routes = routes.get("auth", {})
    election_routes = routes.get("election", {})
    system_routes = routes.get("system", {})

    routes["PRE_CADASTRO"] = auth_routes.get("pre_cadastro", "/api/admin/pre-cadastro/")
    routes["CONFIRMAR_PRE_CADASTRO"] = auth_routes.get("confirmar_pre_cadastro", "/api/admin/pre-cadastro/confirmar/")
    routes["LOGIN"] = auth_routes.get("login", "/api/auth/login/")
    routes["ELECTION_CREATE"] = election_routes.get("create", "/api/election/create/")
    routes["ELECTION_AVAILABLE"] = election_routes.get("list_available", "/api/election/available/")
    routes["ELECTION_START"] = election_routes.get("start", "/api/election/start/")
    routes["PING"] = system_routes.get("ping", "/api/ping-desktop/")
    routes["PING_DESKTOP"] = routes["PING"]

    return routes


API_ROUTES: Dict[str, Any] = _load_routes()


class ApiRoutes:
    """Atributos estáticos das rotas para autocompletar na IDE."""

    PRE_CADASTRO: str = API_ROUTES["PRE_CADASTRO"]
    CONFIRMAR_PRE_CADASTRO: str = API_ROUTES["CONFIRMAR_PRE_CADASTRO"]
    LOGIN: str = API_ROUTES["LOGIN"]
    ELECTION_CREATE: str = API_ROUTES["ELECTION_CREATE"]
    ELECTION_AVAILABLE: str = API_ROUTES["ELECTION_AVAILABLE"]
    ELECTION_START: str = API_ROUTES["ELECTION_START"]
    PING: str = API_ROUTES["PING"]
