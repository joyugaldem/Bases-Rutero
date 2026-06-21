"""Tests para el parser SQL compartido (scripts/sql_parser.py)."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sql_parser import split_sql, split_statements


class TestSplitSqlBasico:
    """Sentencias simples terminadas en `;`.

    El parser es line-based: cada `;` debe estar al final de una línea
    (o precedido por otra `;` que cierre la sentencia). En archivos SQL
    reales esto siempre se cumple.
    """

    def test_una_sentencia(self):
        assert split_sql("SELECT 1;") == ["SELECT 1"]

    def test_multiples_sentencias(self):
        s = split_sql("SELECT 1;\nSELECT 2;\nSELECT 3;")
        assert s == ["SELECT 1", "SELECT 2", "SELECT 3"]

    def test_sentencia_sin_punto_y_coma_final(self):
        """Si la última línea no tiene `;`, la igualamos como una sola sentencia."""
        s = split_sql("SELECT 1;\nSELECT 2")
        assert s == ["SELECT 1", "SELECT 2"]

    def test_ignora_lineas_vacias(self):
        s = split_sql("\n\nSELECT 1;\n\n\nSELECT 2;")
        assert s == ["SELECT 1", "SELECT 2"]

    def test_ignora_comentarios_de_linea(self):
        s = split_sql("-- comentario\nSELECT 1;\n-- otro\nSELECT 2;")
        assert s == ["SELECT 1", "SELECT 2"]

    def test_comentario_inline_no_rompe_sentencia(self):
        """Un comentario al final de la línea (después del ;) se ignora."""
        s = split_sql("SELECT 1; -- comentario al final\nSELECT 2;")
        assert s == ["SELECT 1", "SELECT 2"]


class TestSplitSqlDelimiters:
    """Manejo de la directiva DELIMITER (stored procedures)."""

    def test_delimiter_doble_slash_para_procedure(self):
        sql = """
DELIMITER //
CREATE PROCEDURE foo()
BEGIN
    DECLARE x INT;
    SET x = 1;
END //
DELIMITER ;
SELECT 2;
"""
        s = split_sql(sql)
        # Debe haber 2 sentencias: el CREATE PROCEDURE y el SELECT 2
        assert len(s) == 2
        assert "CREATE PROCEDURE foo()" in s[0]
        assert "DECLARE x INT" in s[0]
        assert "SET x = 1" in s[0]
        assert s[1] == "SELECT 2"

    def test_delimiter_dolar(self):
        sql = """
DELIMITER $
CREATE PROCEDURE bar() BEGIN SELECT 1; END $
DELIMITER ;
"""
        s = split_sql(sql)
        assert len(s) == 1
        assert "CREATE PROCEDURE bar()" in s[0]

    def test_multiples_procedures_con_delimiter(self):
        sql = """
DELIMITER //
CREATE PROCEDURE a() BEGIN END //
CREATE PROCEDURE b() BEGIN END //
DELIMITER ;
"""
        s = split_sql(sql)
        assert len(s) == 2
        assert "PROCEDURE a" in s[0]
        assert "PROCEDURE b" in s[1]


class TestSplitSqlFiltros:
    """Filtrado de USE, SET NAMES y comentarios de bloque."""

    def test_filtra_use(self):
        s = split_sql("USE lacteosdb;\nSELECT 1;")
        assert s == ["SELECT 1"]

    def test_filtra_set_names(self):
        s = split_sql("SET NAMES utf8mb4;\nSELECT 1;")
        assert s == ["SELECT 1"]

    def test_filtra_use_case_insensitive(self):
        s = split_sql("use lacteosdb;\nSELECT 1;")
        assert s == ["SELECT 1"]

    def test_no_filtra_create_database(self):
        """CREATE DATABASE empieza con CREATE, no con USE."""
        s = split_sql("CREATE DATABASE foo;\nSELECT 1;")
        assert s == ["CREATE DATABASE foo", "SELECT 1"]

    def test_ignora_comentarios_de_bloque(self):
        s = split_sql("/* hola */\nSELECT 1;\n/* otro */\nSELECT 2;")
        assert s == ["SELECT 1", "SELECT 2"]

    def test_use_dentro_de_string_no_se_filtra(self):
        """Si la palabra USE aparece dentro de un string, no se filtra."""
        s = split_sql("INSERT INTO t VALUES ('USE esto');")
        assert s == ["INSERT INTO t VALUES ('USE esto')"]


class TestSplitSqlEdgeCases:
    """Casos límite."""

    def test_archivo_vacio(self):
        assert split_sql("") == []

    def test_solo_comentarios(self):
        assert split_sql("-- solo comentarios\n-- más comentarios\n") == []

    def test_string_con_punto_y_coma_dentro(self):
        """El `;` dentro de un string no debe dividir la sentencia."""
        s = split_sql("INSERT INTO t VALUES ('a;b;c');")
        assert s == ["INSERT INTO t VALUES ('a;b;c')"]

    def test_split_statements_es_alias_de_split_sql(self):
        """split_statements(filename, content) debe comportarse idéntico."""
        content = "SELECT 1;\nUSE foo;\nSELECT 2;"
        assert split_statements("dummy.sql", content) == split_sql(content)


class TestSplitSqlIntegracionSqlFiles:
    """Test de integración: parsear archivos reales del proyecto."""

    def test_parsear_01_schema(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "sql", "01_schema.sql"
        )
        if not os.path.exists(path):
            pytest.skip(f"archivo no encontrado: {path}")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        stmts = split_sql(content)
        # Debe parsear todas las sentencias sin explotar
        assert len(stmts) > 30
        # CREATE DATABASE y CREATE TABLE deben estar presentes
        assert any("CREATE DATABASE" in s for s in stmts)
        assert any("CREATE TABLE persona" in s for s in stmts)
        # USE lacteosdb y SET NAMES NO deben estar (filtrados)
        assert not any(s.strip().upper().startswith("USE ") for s in stmts)
        assert not any(s.strip().upper().startswith("SET NAMES") for s in stmts)

    def test_parsear_03_transacciones(self):
        """Archivo con DELIMITER // — el caso más complejo."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "sql", "03_transacciones.sql"
        )
        if not os.path.exists(path):
            pytest.skip(f"archivo no encontrado: {path}")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        stmts = split_sql(content)
        # Debe haber 5 procedimientos transaccionales
        assert any("sp_trx_crear_factura_completa" in s for s in stmts)
        assert any("sp_trx_registrar_pago" in s for s in stmts)
        assert any("sp_trx_crear_recorrido" in s for s in stmts)
        assert any("sp_trx_registrar_producto_completo" in s for s in stmts)
        assert any("sp_trx_anular_factura" in s for s in stmts)
