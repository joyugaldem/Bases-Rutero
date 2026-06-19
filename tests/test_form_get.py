"""Tests para los helpers form_get y handle_form_errors de app.py."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from flask import Flask, request, redirect, url_for, flash, get_flashed_messages
from app import form_get, handle_form_errors, paginate, app


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


# ============================================================
# paginate
# ============================================================

class TestPaginate:
    """Tests para el helper paginate()."""

    def test_pagina_1_por_defecto(self):
        """Sin parámetro page, devuelve la primera página."""
        with app.test_request_context("/__test"):
            items = list(range(50))
            page_items, pager = paginate(items, per_page=10)
            assert page_items == list(range(0, 10))
            assert pager["page"] == 1
            assert pager["pages"] == 5
            assert pager["total"] == 50
            assert pager["has_next"] is True
            assert pager["has_prev"] is False
            assert pager["next_page"] == 2
            assert pager["prev_page"] == 0

    def test_pagina_intermedia(self):
        with app.test_request_context("/__test?page=3"):
            items = list(range(50))
            page_items, pager = paginate(items, per_page=10)
            assert page_items == list(range(20, 30))
            assert pager["page"] == 3
            assert pager["has_next"] is True
            assert pager["has_prev"] is True

    def test_ultima_pagina(self):
        with app.test_request_context("/__test?page=5"):
            items = list(range(50))
            page_items, pager = paginate(items, per_page=10)
            assert page_items == list(range(40, 50))
            assert pager["has_next"] is False

    def test_lista_vacia(self):
        with app.test_request_context("/__test"):
            page_items, pager = paginate([], per_page=10)
            assert page_items == []
            assert pager["total"] == 0
            assert pager["pages"] == 1  # al menos 1 página
            assert pager["has_next"] is False

    def test_lista_menor_que_per_page(self):
        """Si hay menos items que per_page, cabe en 1 página."""
        with app.test_request_context("/__test"):
            items = [1, 2, 3]
            page_items, pager = paginate(items, per_page=10)
            assert page_items == [1, 2, 3]
            assert pager["pages"] == 1

    def test_page_negativo_se_clampea_a_1(self):
        """Un page negativo o 0 se trata como página 1."""
        with app.test_request_context("/__test?page=-5"):
            items = list(range(50))
            page_items, pager = paginate(items, per_page=10)
            assert pager["page"] == 1

    def test_page_mayor_a_total_se_clampea(self):
        """Un page mayor al total se clamea a la última página."""
        with app.test_request_context("/__test?page=99"):
            items = list(range(50))
            page_items, pager = paginate(items, per_page=10)
            assert pager["page"] == 5  # última
            assert page_items == list(range(40, 50))

    def test_page_invalido_lanza_value_error(self):
        """Un page no entero (e.g. 'abc') lanza ValueError."""
        with app.test_request_context("/__test?page=abc"):
            with pytest.raises(ValueError, match="page.*inv"):
                paginate(list(range(10)))

    def test_per_page_custom(self):
        with app.test_request_context("/__test"):
            items = list(range(100))
            page_items, pager = paginate(items, per_page=25)
            assert pager["pages"] == 4
            assert page_items == list(range(0, 25))
