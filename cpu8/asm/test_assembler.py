"""Tests del ensamblador de cpu8 (``asm/assembler.py``).

Se ejecutan con ``pytest`` desde la raiz del proyecto o desde ``asm/``:

    python3 -m pytest asm/test_assembler.py -v

Cubre la codificacion segun ``docs/ISA.md``, la verificacion de los programas
demo (byte a byte contra los ``.hex`` comprometidos) y los casos limite que se
corrigieron: colision etiqueta/registro en LD/ST indirecto, BOM UTF-8, CRLF,
linea del error de desbordamiento, literales con signo, etc.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Permite ``import assembler`` aunque pytest no anada asm/ al sys.path.
_ASM_DIR = Path(__file__).resolve().parent
if str(_ASM_DIR) not in sys.path:
    sys.path.insert(0, str(_ASM_DIR))

import assembler

PROGRAMS_DIR = _ASM_DIR.parent / "programs"
DEMOS = sorted(p.stem for p in PROGRAMS_DIR.glob("*.asm"))


def asm(src: str) -> list[int]:
    """Ensambla y devuelve la lista de bytes (lanza AssemblerError si falla)."""
    salida, _etiquetas, _listado = assembler.ensamblar(src)
    return salida


def leer_hex(path: Path) -> list[int]:
    return [int(line, 16) for line in path.read_text().split()]


# ---------------------------------------------------------------------------
#  Verificacion de los programas demo (regresion byte a byte)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nombre", DEMOS)
def test_programa_demo_es_byte_identico_al_hex(nombre: str) -> None:
    fuente = (PROGRAMS_DIR / f"{nombre}.asm").read_text()
    esperado = leer_hex(PROGRAMS_DIR / f"{nombre}.hex")
    assert asm(fuente) == esperado


# ---------------------------------------------------------------------------
#  Codificacion basica (docs/ISA.md §3)
# ---------------------------------------------------------------------------

def test_nop_es_mov_a_a() -> None:
    assert asm("NOP") == [0x20]
    assert asm("MOV A, A") == [0x20]


def test_ldi_y_alu() -> None:
    assert asm("LDI A, 5") == [0x10, 0x05]
    assert asm("LDI B, 3") == [0x14, 0x03]
    assert asm("ADD A, B") == [0x51]
    assert asm("SUB A, B") == [0x61]
    assert asm("CMP A, D") == [0xA3]
    assert asm("AND C, D") == [0x7B]
    assert asm("OR  C, D") == [0x8B]
    assert asm("XOR C, D") == [0x9B]


def test_shift_inc_dec_push_pop_out() -> None:
    assert asm("SHL A") == [0xB0]
    assert asm("SHR D") == [0xBD]
    assert asm("INC A") == [0x00]
    assert asm("DEC A") == [0x04]
    assert asm("PUSH B") == [0x09]
    assert asm("POP  C") == [0x0E]
    assert asm("OUT A") == [0xE0]
    assert asm("OUT C") == [0xE8]


def test_sistema_hlt_ret_ei_di() -> None:
    assert asm("HLT") == [0xF0]
    assert asm("RET") == [0xF1]
    assert asm("EI") == [0xF2]
    assert asm("DI") == [0xF3]


def test_jmp_call_jcc() -> None:
    # JMP = 0xC0 + a; CALL = 0xC1 + a; Jcc = 0xD0|cc + a (rd reservado 00).
    assert asm("JMP 0x10") == [0xC0, 0x10]
    assert asm("CALL 0x10") == [0xC1, 0x10]
    assert asm("JZ  0x10") == [0xD0, 0x10]
    assert asm("JNZ 0x10") == [0xD1, 0x10]
    assert asm("JC  0x10") == [0xD2, 0x10]
    assert asm("JNC 0x10") == [0xD3, 0x10]


def test_aliases_jhs_jlo() -> None:
    # ISA §4: JHS = JC (cc=10), JLO = JNC (cc=11).
    assert asm("JHS 0x10") == asm("JC  0x10") == [0xD2, 0x10]
    assert asm("JLO 0x10") == asm("JNC 0x10") == [0xD3, 0x10]


# ---------------------------------------------------------------------------
#  LD/ST directos e indirectos
# ---------------------------------------------------------------------------

def test_ld_st_directos_con_y_sin_corchetes() -> None:
    assert asm("LD A, [0x20]") == [0x30, 0x20]
    assert asm("LD A, 0x20") == [0x30, 0x20]
    assert asm("ST A, [0x20]") == [0x40, 0x20]
    assert asm("ST A, 0x20") == [0x40, 0x20]


def test_ld_st_indirectos() -> None:
    assert asm("LD A, [B]") == [0xF4, 0x01]
    assert asm("ST A, [B]") == [0xF5, 0x01]
    assert asm("LD D, [C]") == [0xF4, (0b11 << 2) | 0b10]
    assert asm("ST D, [C]") == [0xF5, (0b11 << 2) | 0b10]


def test_indirecto_tiene_tamano_2_bytes() -> None:
    # Un indirecto desplaza a la etiqueta siguiente 2 bytes, no 1.
    assert asm("LD A, [B]\nfin:\nHLT") == [0xF4, 0x01, 0xF0]


def test_etiqueta_nombrada_como_registro_minuscula_es_directa() -> None:
    # Colision: 'b' es una etiqueta (sensible a mayusculas); 'B' seria el
    # registro. Con 'b:' definida, [b] es un acceso directo a su direccion.
    src = "b:\nLDI A, 1\nLD A, [b]"
    assert asm(src) == [0x10, 0x01, 0x30, 0x00]   # 0x00 = direccion de 'b'


def test_etiqueta_mayuscula_colisiona_y_gana_la_etiqueta() -> None:
    src = "B:\nLDI A, 1\nLD A, [B]"
    assert asm(src) == [0x10, 0x01, 0x30, 0x00]


def test_sin_colision_el_registro_manda() -> None:
    # Si no existe la etiqueta 'B', [D] sigue siendo indirecto por registro.
    assert asm("LDI A, 1\nLD A, [D]") == [0x10, 0x01, 0xF4, 0x03]


# ---------------------------------------------------------------------------
#  Extensiones del §6: inmediatos, indexado y saltos con signo
# ---------------------------------------------------------------------------

def test_inmediatos_aldi_subi_cmpi() -> None:
    # Pagina 0x1 con la suboperacion en el campo rs: 00 LDI, 01 ADDI, 10 SUBI,
    # 11 CMPI.  Byte1 = 0x10 | (rd<<2) | subop; byte2 = inmediato.
    assert asm("LDI  A, 5") == [0x10, 0x05]
    assert asm("ADDI A, 5") == [0x11, 0x05]
    assert asm("SUBI B, 6") == [0x16, 0x06]
    assert asm("CMPI C, 7") == [0x1B, 0x07]
    assert asm("CMPI D, 0") == [0x1F, 0x00]


def test_inmediato_es_2_bytes_y_desplaza_etiquetas() -> None:
    assert asm("ADDI A, 1\nfin:\nHLT") == [0x11, 0x01, 0xF0]


def test_indexado_ld_st() -> None:
    # LD/ST rd,[rs+off]: opcode 0x3/0x4, base en rs (B/C/D), off en el 2o byte.
    assert asm("LD A, [B+3]") == [0x31, 0x03]
    assert asm("ST A, [B+3]") == [0x41, 0x03]
    assert asm("LD D, [C+1]") == [0x3E, 0x01]
    assert asm("ST D, [D+0]") == [0x4F, 0x00]


def test_indexado_desplazamiento_negativo() -> None:
    assert asm("LD A, [B-1]") == [0x31, 0xFF]


def test_indexado_desplazamiento_etiqueta() -> None:
    # La base es un registro y el desplazamiento una etiqueta.
    src = "tabla:\nLD A, [B+tabla]"
    assert asm(src) == [0x31, 0x00]


def test_indexado_con_base_a_es_error() -> None:
    # rs=00 codifica el modo absoluto, asi que la base A no esta disponible.
    with pytest.raises(assembler.AssemblerError, match="base B, C o D"):
        asm("LD A, [A+1]")


def test_indexado_no_confunde_con_indirecto() -> None:
    # [B] sigue siendo indirecto (0xF4); [B+0] es indexado con off=0.
    assert asm("LD A, [B]") == [0xF4, 0x01]
    assert asm("LD A, [B+0]") == [0x31, 0x00]


def test_saltos_con_signo_y_estado() -> None:
    # Familia en el campo rd del Jcc: 00 sin signo, 01 con signo, 10 estado.
    assert asm("JLT fin\nfin:\nHLT") == [0xD4, 0x02, 0xF0]
    assert asm("JGE fin\nfin:\nHLT") == [0xD5, 0x02, 0xF0]
    assert asm("JLE fin\nfin:\nHLT") == [0xD6, 0x02, 0xF0]
    assert asm("JGT fin\nfin:\nHLT") == [0xD7, 0x02, 0xF0]
    assert asm("JVS fin\nfin:\nHLT") == [0xD8, 0x02, 0xF0]
    assert asm("JVC fin\nfin:\nHLT") == [0xD9, 0x02, 0xF0]
    assert asm("JMI fin\nfin:\nHLT") == [0xDA, 0x02, 0xF0]
    assert asm("JPL fin\nfin:\nHLT") == [0xDB, 0x02, 0xF0]


def test_saltos_sin_signo_siguen_igual() -> None:
    # Retrocompatibilidad: JZ/JNZ/JC/JNC/(JHS/JLO) no cambian de byte.
    assert asm("JZ fin\nfin:\nHLT") == [0xD0, 0x02, 0xF0]
    assert asm("JNZ fin\nfin:\nHLT") == [0xD1, 0x02, 0xF0]
    assert asm("JC fin\nfin:\nHLT") == [0xD2, 0x02, 0xF0]
    assert asm("JNC fin\nfin:\nHLT") == [0xD3, 0x02, 0xF0]
    assert asm("JHS fin\nfin:\nHLT") == [0xD2, 0x02, 0xF0]
    assert asm("JLO fin\nfin:\nHLT") == [0xD3, 0x02, 0xF0]


# ---------------------------------------------------------------------------
#  MUL / DIV (grupo 0xF, Fase 9)
# ---------------------------------------------------------------------------

def test_mul_div_encoding() -> None:
    # byte1 = 0xF6 (MUL) / 0xF7 (DIV); byte2 = (rd<<2)|rs.
    assert asm("MUL A, B") == [0xF6, 0x01]
    assert asm("MUL D, C") == [0xF6, 0x0E]
    assert asm("DIV A, B") == [0xF7, 0x01]
    assert asm("DIV B, D") == [0xF7, 0x07]
    assert asm("MUL A, A") == [0xF6, 0x00]


def test_mul_div_son_2_bytes_y_desplazan_etiquetas() -> None:
    assert asm("MUL A, A\nfin:\nHLT") == [0xF6, 0x00, 0xF0]
    assert asm("DIV A, A\nfin:\nHLT") == [0xF7, 0x00, 0xF0]


def test_mul_div_exigen_dos_operandos() -> None:
    with pytest.raises(assembler.AssemblerError, match="2 operando"):
        asm("MUL A")
    with pytest.raises(assembler.AssemblerError, match="2 operando"):
        asm("DIV A, B, C")


# ---------------------------------------------------------------------------
#  IN / OUT portados (grupo 0xF, Fase 9)
# ---------------------------------------------------------------------------

def test_out_registro_sigue_igual() -> None:
    # Retrocompatibilidad: OUT rd (1 byte) no cambia.
    assert asm("OUT A") == [0xE0]
    assert asm("OUT D") == [0xEC]


def test_in_registro_encoding() -> None:
    # IN rd = 0xE0|(rd<<2)|01 (puerto 0).
    assert asm("IN A") == [0xE1]
    assert asm("IN D") == [0xED]


def test_out_ported_encoding() -> None:
    # OUT n,rd -> 0xF8, (rd<<2)|n.
    assert asm("OUT 1, A") == [0xF8, 0x01]
    assert asm("OUT 2, B") == [0xF8, 0x06]
    assert asm("OUT 3, D") == [0xF8, 0x0F]
    assert asm("OUT 0, C") == [0xF8, 0x08]


def test_in_ported_encoding() -> None:
    assert asm("IN 3, D") == [0xF9, 0x0F]
    assert asm("IN 1, A") == [0xF9, 0x01]


def test_out_in_ported_son_2_bytes() -> None:
    assert asm("OUT 1, A\nfin:\nHLT") == [0xF8, 0x01, 0xF0]
    assert asm("IN 2, D\nfin:\nHLT") == [0xF9, 0x0E, 0xF0]


def test_puerto_fuera_de_rango_es_error() -> None:
    with pytest.raises(assembler.AssemblerError, match="fuera de rango"):
        asm("OUT 4, A")


def test_out_in_numero_de_operandos() -> None:
    with pytest.raises(assembler.AssemblerError, match="1 o 2 operando"):
        asm("IN A, B, C")


# ---------------------------------------------------------------------------
#  Literales numericos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("literal", "valor"),
    [
        ("0", 0x00), ("7", 0x07), ("255", 0xFF), ("007", 0x07),
        ("$20", 0x20), ("$FF", 0xFF), ("0x20", 0x20), ("0X2A", 0x2A),
        ("0b1010", 0x0A), ("0B1111", 0x0F),
        ("-1", 0xFF), ("-128", 0x80), ("+5", 0x05),
    ],
)
def test_literal_numerico(literal: str, valor: int) -> None:
    assert asm(f"LDI A, {literal}") == [0x10, valor]


@pytest.mark.parametrize("literal", ["256", "-129", "0x100", "$100", "0b111111111"])
def test_literal_fuera_de_rango(literal: str) -> None:
    with pytest.raises(assembler.AssemblerError, match="fuera de rango"):
        asm(f"LDI A, {literal}")


@pytest.mark.parametrize("literal", ["$", "0x", "0b2", "abc", "0xZZ"])
def test_literal_no_valido(literal: str) -> None:
    with pytest.raises(assembler.AssemblerError):
        asm(f"LDI A, {literal}")


# ---------------------------------------------------------------------------
#  Analisis de lineas
# ---------------------------------------------------------------------------

def test_linea_solo_etiqueta_y_comentarios() -> None:
    src = "\n; comentario\nfoo:      ; solo etiqueta\n    HLT\n"
    salida, etiquetas, _ = assembler.ensamblar(src)
    assert salida == [0xF0]
    assert etiquetas == {"foo": 0}


def test_comentario_tras_instruccion() -> None:
    assert asm("LDI A, 1 ; carga uno\nOUT A") == [0x10, 0x01, 0xE0]


def test_tabs_y_espacios_indiferentes() -> None:
    assert asm("\tLDI\tA,\t1\n") == [0x10, 0x01]


def test_mnemonicos_y_registros_insensibles_a_mayusculas() -> None:
    assert asm("ldi a, 5") == asm("LDI A, 5") == [0x10, 0x05]


def test_etiquetas_son_sensibles_a_mayusculas() -> None:
    src = "Loop: HLT\nJMP Loop"   # 'Loop' definida, 'Loop' referenciada
    assert asm(src) == [0xF0, 0xC0, 0x00]
    with pytest.raises(assembler.AssemblerError, match="no definida"):
        asm("Loop: HLT\nJMP loop")


# ---------------------------------------------------------------------------
#  Etiquetas: referencias hacia adelante y errores
# ---------------------------------------------------------------------------

def test_referencia_hacia_adelante() -> None:
    # JMP(2B)@0, NOP(1B)@2, fin@3.
    assert asm("JMP fin\nNOP\nfin: HLT") == [0xC0, 0x03, 0x20, 0xF0]


def test_etiqueta_duplicada() -> None:
    with pytest.raises(assembler.AssemblerError, match="duplicada"):
        asm("x: HLT\nx: HLT")


def test_etiqueta_no_definida_linea_correcta() -> None:
    with pytest.raises(assembler.AssemblerError, match=r"linea 3:.*no definida"):
        asm("\n\nJMP nope")


def test_registro_invalido_linea_correcta() -> None:
    with pytest.raises(assembler.AssemblerError,
                       match=r"linea 2: registro desconocido 'X'"):
        asm("\nMOV A, X")


def test_numero_de_operandos_incorrecto() -> None:
    with pytest.raises(assembler.AssemblerError, match="operando"):
        asm("MOV A")
    with pytest.raises(assembler.AssemblerError, match="operando"):
        asm("NOP A")
    with pytest.raises(assembler.AssemblerError, match="mnemonico desconocido"):
        asm("FOO A")


# ---------------------------------------------------------------------------
#  Directivas (.org, .db, .equ)
# ---------------------------------------------------------------------------

def test_equ_constante_reutilizable() -> None:
    assert asm(".equ SIZE, 5\nLDI A, SIZE\nHLT") == [0x10, 0x05, 0xF0]
    # La constante puede definirse despues de usarse (pase 0 previo).
    assert asm("LDI A, N\n.equ N, 7\nHLT") == [0x10, 0x07, 0xF0]


def test_equ_encadenada() -> None:
    assert asm(".equ BASE, 0x10\n.equ TOPE, BASE\nLDI A, TOPE") == [0x10, 0x10]


def test_equ_duplicada_es_error() -> None:
    with pytest.raises(assembler.AssemblerError, match="constante duplicada"):
        asm(".equ X, 1\n.equ X, 2\nHLT")


def test_org_rellena_con_ceros() -> None:
    assert asm("LDI A, 1\n.org 0x04\nHLT") == [0x10, 0x01, 0x00, 0x00, 0xF0]


def test_org_etiqueta_siguiente() -> None:
    # La etiqueta despues de .org toma la direccion fijada.
    assert asm(".org 0x08\nfin:\nHLT\nJMP fin") == (
        [0x00] * 8 + [0xF0, 0xC0, 0x08])


def test_org_retrocede_es_error() -> None:
    with pytest.raises(assembler.AssemblerError, match="retrocede"):
        asm("LDI A, 1\n.org 0x00\nHLT")


def test_db_numeros_y_bases() -> None:
    assert asm(".db 1, 2, 0xFF, 0b1010, $20, -1\nHLT") == (
        [0x01, 0x02, 0xFF, 0x0A, 0x20, 0xFF, 0xF0])


def test_db_cadena_ascii_con_escapes() -> None:
    assert asm('.db "Hi\\n", 0') == [0x48, 0x69, 0x0A, 0x00]


def test_db_cadena_con_comas_y_comillas() -> None:
    # Las comas dentro de la cadena no separan campos, y se admite \" dentro.
    assert asm('.db "a,b", "c"') == [0x61, 0x2C, 0x62, 0x63]
    assert asm('.db "x\\"y"') == [0x78, 0x22, 0x79]


def test_db_etiqueta_hacia_adelante() -> None:
    # .db (1 byte) en 0, HLT en 1, etiqueta 'tab' en 2.
    assert asm(".db tab\nHLT\ntab: .db 0x99") == [0x02, 0xF0, 0x99]


def test_db_con_etiqueta_en_la_misma_linea() -> None:
    assert asm("tab: .db 7, 8\nLD A, [tab]") == [0x07, 0x08, 0x30, 0x00]


def test_directiva_minuscula_y_mayuscula() -> None:
    assert asm(".equ x, 3\nldi a, x") == [0x10, 0x03]
    assert asm(".DB 9") == [0x09]


def test_escape_no_valido_es_error() -> None:
    with pytest.raises(assembler.AssemblerError, match="escape no valido"):
        asm('.db "\\q"')


def test_org_fuera_de_rango_es_error() -> None:
    with pytest.raises(assembler.AssemblerError, match="fuera de rango"):
        asm(".org 0x100\nHLT")


# ---------------------------------------------------------------------------
#  Casos limite de fichero
# ---------------------------------------------------------------------------

def test_bom_utf8_al_inicio() -> None:
    assert asm("\ufeffLDI A, 1\nOUT A") == [0x10, 0x01, 0xE0]


def test_crlf() -> None:
    assert asm("LDI A, 1\r\nHLT\r\n") == [0x10, 0x01, 0xF0]


def test_fuente_vacio() -> None:
    assert asm("") == []
    assert asm("\n; solo comentarios\n   \n") == []


def test_256_bytes_es_el_maximo() -> None:
    assert len(asm("\n".join("NOP" for _ in range(256)))) == 256


def test_extraer_linea_del_error_de_desbordamiento() -> None:
    # 256 NOP caben; el 257.o desborda en la linea 257 (no en len(lineas)).
    src = "\n".join("NOP" for _ in range(257))
    with pytest.raises(assembler.AssemblerError) as exc:
        asm(src)
    assert "linea 257" in str(exc.value)
    assert "maximo es 256" in str(exc.value)


def test_linea_de_desbordamiento_ignora_comentarios_previos() -> None:
    # 40 lineas de comentario + 257 NOP: el desbordamiento ocurre en la 297.
    src = "; c\n" * 40 + "\n".join("NOP" for _ in range(257))
    with pytest.raises(assembler.AssemblerError) as exc:
        asm(src)
    assert "linea 297" in str(exc.value)


# ---------------------------------------------------------------------------
#  Interfaz de linea de comandos
# ---------------------------------------------------------------------------

def test_salida_por_defecto() -> None:
    assert assembler._fichero_salida_por_defecto("a/b/prog.asm") == "a/b/prog.hex"
    assert assembler._fichero_salida_por_defecto("PROG.ASM") == "PROG.hex"
    assert assembler._fichero_salida_por_defecto("prog") == "prog.hex"


def test_main_escribe_hex_y_devuelve_cero(tmp_path: Path) -> None:
    fuente = tmp_path / "p.asm"
    fuente.write_text("LDI A, 5\nOUT A\nHLT\n")
    salida = tmp_path / "p.hex"
    rc = assembler.main([str(fuente), "-o", str(salida)])
    assert rc == 0
    assert leer_hex(salida) == [0x10, 0x05, 0xE0, 0xF0]


def test_main_devuelve_uno_con_error(tmp_path: Path) -> None:
    fuente = tmp_path / "p.asm"
    fuente.write_text("JMP nope\n")
    rc = assembler.main([str(fuente), "-o", str(tmp_path / "p.hex")])
    assert rc == 1
