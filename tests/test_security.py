"""Tests para protección CSRF de formularios.

Verifica que:
- GET forms incluyen el token CSRF
- POST sin token es rechazado con 400
- POST con token (obtenido de un GET previo) es aceptado
"""
import re
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app import app


def _extract_csrf_token(html: str) -> str:
    """Extrae el valor del csrf_token del HTML renderizado."""
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    if not m:
        m = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', html)
    assert m, f"csrf_token no encontrado en HTML:\n{html[:500]}"
    return m.group(1)


class TestCsrfProtection:
    """Tests para la protección CSRF de formularios POST."""

    def test_get_form_incluye_csrf_token(self):
        """GET a un form POST debe incluir el input csrf_token oculto."""
        with app.test_client() as c:
            r = c.get("/productos/nuevo")
            assert r.status_code == 200
            token = _extract_csrf_token(r.get_data(as_text=True))
            assert len(token) > 20  # tokens CSRF son largos

    def test_post_sin_token_es_rechazado(self):
        """POST sin csrf_token debe retornar 400."""
        with app.test_client() as c:
            r = c.post("/productos/nuevo", data={
                "nombre": "X",
                "codigo_barras": "X",
                "categoria": "Leche",
            })
            assert r.status_code == 400

    def test_post_con_token_es_aceptado(self):
        """POST con csrf_token válido (obtenido de GET previo) es aceptado."""
        import uuid
        codigo = f"CSRF-{uuid.uuid4().hex[:8]}"  # único por run
        with app.test_client() as c:
            r = c.get("/productos/nuevo")
            token = _extract_csrf_token(r.get_data(as_text=True))

            r = c.post("/productos/nuevo", data={
                "nombre": "Prod CSRF Test",
                "codigo_barras": codigo,
                "categoria": "Leche",
                "csrf_token": token,
            })
            # 302 = redirect tras éxito
            assert r.status_code == 302

    def test_post_con_token_inventado_es_rechazado(self):
        """Un csrf_token falso (no generado por la app) debe ser rechazado."""
        with app.test_client() as c:
            r = c.post("/productos/nuevo", data={
                "nombre": "X",
                "codigo_barras": "X",
                "categoria": "Leche",
                "csrf_token": "esto-no-es-un-token-valido",
            })
            assert r.status_code == 400

    def test_ajax_post_puede_usar_header_csrf(self):
        """POSTs con header X-CSRFToken (típico de AJAX) también son aceptados."""
        import uuid
        codigo = f"AJAX-{uuid.uuid4().hex[:8]}"
        with app.test_client() as c:
            r = c.get("/productos/nuevo")
            token = _extract_csrf_token(r.get_data(as_text=True))

            r = c.post("/productos/nuevo",
                       data={"nombre": "AJAX", "codigo_barras": codigo, "categoria": "Leche"},
                       headers={"X-CSRFToken": token})
            assert r.status_code == 302


class TestSecurityHeaders:
    """Tests para headers de seguridad en respuestas HTTP."""

    def test_x_content_type_options(self):
        with app.test_client() as c:
            r = c.get("/")
            assert r.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self):
        with app.test_client() as c:
            r = c.get("/")
            assert r.headers.get("X-Frame-Options") == "DENY"

    def test_referrer_policy(self):
        with app.test_client() as c:
            r = c.get("/")
            assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


class TestSecretKeyRequired:
    """Tests para la exigencia de SECRET_KEY en config."""

    def test_secret_key_sin_variable_falla(self, monkeypatch):
        """Sin SECRET_KEY en env, importar config debe fallar."""
        import importlib
        monkeypatch.delenv("SECRET_KEY", raising=False)
        # Forzar recarga de config
        if "config" in sys.modules:
            del sys.modules["config"]
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            importlib.import_module("config")
        # Restaurar para no afectar otros tests
        os.environ["SECRET_KEY"] = "test-secret-key-not-for-production-32-chars"
        sys.modules.pop("config", None)
        importlib.import_module("config")  # reimport
