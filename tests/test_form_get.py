"""Tests para los helpers form_get y handle_form_errors de app.py."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from flask import Flask, request, redirect, url_for, flash, get_flashed_messages
from app import form_get, handle_form_errors, app


# ============================================================
# form_get
# ============================================================

class TestFormGet:
    """Tests para el helper form_get."""

    def _post(self, client, data):
        return client.post("/__test/form_get", data=data, headers={"Referer": "/some/page"})

    def test_devuelve_string_por_defecto(self, client=None):
        """Si no se especifica cast, devuelve string."""
        with app.test_request_context("/__test/form_get", method="POST", data={"x": "hola"}):
            assert form_get("x") == "hola"

    def test_cast_a_int_ok(self):
        with app.test_request_context("/__test", method="POST", data={"n": "42"}):
            assert form_get("n", int) == 42

    def test_cast_a_float_ok(self):
        with app.test_request_context("/__test", method="POST", data={"p": "10.5"}):
            assert form_get("p", float) == 10.5

    def test_cast_a_int_falla_con_valor_invalido(self):
        """Levanta ValueError con mensaje descriptivo."""
        with app.test_request_context("/__test", method="POST", data={"n": "abc"}):
            with pytest.raises(ValueError) as exc_info:
                form_get("n", int)
            assert "n" in str(exc_info.value)
            assert "abc" in str(exc_info.value)

    def test_cast_a_float_falla_con_valor_invalido(self):
        with app.test_request_context("/__test", method="POST", data={"p": "no-numero"}):
            with pytest.raises(ValueError):
                form_get("p", float)

    def test_campo_vacio_retorna_default(self):
        with app.test_request_context("/__test", method="POST", data={}):
            assert form_get("ausente", int, default=0) == 0
            assert form_get("ausente", str, default="N/A") == "N/A"
            assert form_get("ausente") is None

    def test_campo_ausente_retorna_default(self):
        with app.test_request_context("/__test", method="POST", data={"otro": "valor"}):
            assert form_get("ausente", int, default=99) == 99

    def test_strip_antes_de_cast(self):
        """Tolerar whitespace accidental en inputs."""
        with app.test_request_context("/__test", method="POST", data={"n": "  42  "}):
            assert form_get("n", int) == 42

    def test_string_vacio_se_trata_como_ausente(self):
        """Un string vacío ('') cuenta como ausente → default."""
        with app.test_request_context("/__test", method="POST", data={"n": "   "}):
            assert form_get("n", int, default=10) == 10

    def test_soporta_unicode(self):
        with app.test_request_context("/__test", method="POST", data={"s": "  María  "}):
            assert form_get("s") == "María"


# ============================================================
# handle_form_errors
# ============================================================

class TestHandleFormErrors:
    """Tests para el decorator handle_form_errors."""

    def test_value_error_se_convierte_en_flash(self):
        """Un ValueError se captura y se flashea con redirect."""
        with app.test_request_context("/__test", method="POST", data={"x": "abc"},
                                      headers={"Referer": "/some/page"}):
            @handle_form_errors
            def view():
                form_get("x", int)
                return "ok"

            result = view()
            # Devuelve un redirect (no 500)
            assert result.status_code == 302
            # Y el mensaje está en flashed
            messages = get_flashed_messages(with_categories=True)
            assert any("x" in msg for cat, msg in messages)

    def test_view_normal_pasa_sin_interceptar(self):
        """Si la view no lanza, el decorator no hace nada."""
        with app.test_request_context("/__test", method="GET"):
            @handle_form_errors
            def view():
                return "resultado"

            assert view() == "resultado"

    def test_keyerror_de_request_form_se_convierte_en_flash(self):
        """Un campo ausente genera BadRequestKeyError → flash."""
        from werkzeug.exceptions import BadRequestKeyError
        with app.test_request_context("/__test", method="POST", data={}):
            @handle_form_errors
            def view():
                request.form["campo_que_no_existe"]
                return "ok"

            result = view()
            assert result.status_code == 302
            messages = get_flashed_messages(with_categories=True)
            assert any("campo_que_no_existe" in msg for cat, msg in messages)
