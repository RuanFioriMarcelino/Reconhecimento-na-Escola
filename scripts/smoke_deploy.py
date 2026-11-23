"""Teste de fumaça (smoke test) de implantação HTTP ponta a ponta.

Sobe um servidor WSGI Django efêmero em porta livre de localhost contra o banco
PostgreSQL configurado no BackEnd/.env, executa o fluxo real de autenticação,
consultas paginadas, sincronização incremental e autenticação de terminal da
portaria, e finaliza o servidor limpamente.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "BackEnd"
PORTARIA_DIR = ROOT / "portaria"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_health(base_url: str, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    last_err = None
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"{base_url}/api/health/", timeout=2)
            if r.status_code == 200:
                return r.json()
        except Exception as exc:
            last_err = exc
        time.sleep(0.4)
    raise RuntimeError(f"Servidor não respondeu /api/health/ em {timeout}s (último erro: {last_err})")


def main() -> int:
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv(PORTARIA_DIR / ".env")

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    python_exe = sys.executable

    proc = subprocess.Popen(
        [python_exe, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=str(BACKEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        health = _wait_health(base_url)
        assert health.get("status") == "ok", f"Health inesperado: {health}"
        print(f"[SMOKE] 1/9 /api/health/ OK (v{health.get('version')}, db={health.get('database')})")

        # Garante que rotas protegidas exigem Bearer token
        unauth = requests.get(f"{base_url}/api/dashboard/", timeout=5)
        assert unauth.status_code == 401, f"Esperado 401 sem token, veio {unauth.status_code}"
        print("[SMOKE] 2/9 Proteção 401 sem token OK")

        # Login real (conta seed_mock da coordenação)
        login_res = requests.post(
            f"{base_url}/api/login/",
            json={"email": "coordenacao@escola.edu.br", "senha": "Coord@2026"},
            timeout=5,
        )
        assert login_res.status_code == 200, f"Login falhou ({login_res.status_code}): {login_res.text}"
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("[SMOKE] 3/9 /api/login/ Bearer Token OK")

        # /api/me/ e /api/bootstrap/
        me_res = requests.get(f"{base_url}/api/me/", headers=headers, timeout=5)
        assert me_res.status_code == 200 and me_res.json()["user"]["papel"] == "coordenacao"
        boot_res = requests.get(f"{base_url}/api/bootstrap/", headers=headers, timeout=5)
        assert boot_res.status_code == 200 and "cursor" in boot_res.json()
        print("[SMOKE] 4/9 /api/me/ e /api/bootstrap/ OK")

        # /api/dashboard/ e /api/live/
        dash_res = requests.get(f"{base_url}/api/dashboard/", headers=headers, timeout=5)
        assert dash_res.status_code == 200 and "summary" in dash_res.json()
        cursor = dash_res.json()["cursor"]
        live_res = requests.get(
            f"{base_url}/api/live/",
            params={"since_log_id": cursor["lastLogId"], "since_alert_id": cursor["lastAlertId"]},
            headers=headers,
            timeout=5,
        )
        assert live_res.status_code == 200 and live_res.json()["changed"] is False
        print("[SMOKE] 5/9 /api/dashboard/ e /api/live/ incremental OK")

        # Endpoints paginados: /api/people/, /api/logs/, /api/alerts/, /api/audit/
        for path in ("/api/people/?tipo=aluno&page=1&page_size=10", "/api/logs/?page=1&page_size=10", "/api/alerts/?page=1&page_size=10", "/api/audit/?page=1&page_size=10"):
            r = requests.get(f"{base_url}{path}", headers=headers, timeout=5)
            assert r.status_code == 200, f"{path} falhou: {r.status_code}"
            body = r.json()
            assert "items" in body and "pagination" in body, f"Formato paginado inválido em {path}"
        print("[SMOKE] 6/9 Endpoints paginados (/people, /logs, /alerts, /audit) OK")

        # Autenticação de terminal da portaria via X-Portaria-Key
        dev_key = os.getenv("PORTARIA_DEVICE_KEY") or os.getenv("PORTARIA_DEV_KEY") or ""
        if dev_key:
            p_cfg = requests.get(f"{base_url}/api/portaria/config/", headers={"X-Portaria-Key": dev_key}, timeout=5)
            assert p_cfg.status_code == 200, f"/api/portaria/config/ falhou: {p_cfg.status_code}"
            p_gal = requests.get(f"{base_url}/api/portaria/biometrics/", headers={"X-Portaria-Key": dev_key}, timeout=5)
            assert p_gal.status_code == 200 and "version" in p_gal.json()
            print(f"[SMOKE] 7/9 Terminal portaria X-Portaria-Key OK (galeria: {p_gal.json().get('total')} ativos)")
        else:
            print("[SMOKE] 7/9 Aviso: PORTARIA_DEVICE_KEY/PORTARIA_DEV_KEY não definida, pulando checagem de terminal.")

        # Cabeçalhos de segurança obrigatórios
        assert "X-Request-ID" in dash_res.headers
        assert "no-store" in dash_res.headers.get("Cache-Control", "")
        assert dash_res.headers.get("Permissions-Policy") == "camera=(self)"
        print("[SMOKE] 8/9 Cabeçalhos de segurança e Cache-Control OK")

        # Logout revoga o token imediatamente
        out_res = requests.post(f"{base_url}/api/logout/", headers=headers, timeout=5)
        assert out_res.status_code == 200
        after_out = requests.get(f"{base_url}/api/me/", headers=headers, timeout=5)
        assert after_out.status_code == 401
        print("[SMOKE] 9/9 /api/logout/ revogação de token OK")
        print("\n[SMOKE] TODOS OS TESTES DE IMPLANTAÇÃO HTTP PASSARAM COM SUCESSO!")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
