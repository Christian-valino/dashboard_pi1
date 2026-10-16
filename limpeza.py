"""
limpeza.py - Transforma as duas planilhas "visuais" (blocos lado a lado, células
mescladas) em tabelas organizadas (1 linha = 1 ponto de conexão).

Entradas : dados/levantamento_BD_Sinais_via_1_e_2.xlsx
           dados/levantamento_BD_CDVs_via_1_e_2.xlsx
Saídas   : dados/sinais_tratado.csv
           dados/cdvs_tratado.csv
           dados/log_qualidade.csv   (o que foi corrigido / o que merece conferência)

Uso: python limpeza.py
"""
import re
from pathlib import Path

import openpyxl
import pandas as pd

PASTA = Path(__file__).parent / "dados"
ARQ_SINAIS = PASTA / "levantamento_BD_Sinais_via_1_e_2.xlsx"
ARQ_CDVS = PASTA / "levantamento_BD_CDVs_via_1_e_2.xlsx"

log = []  # registro de tudo que foi mexido


def registrar(base, equipamento, local, funcao, original, tratado, motivo):
    log.append(dict(base=base, equipamento=equipamento, local=local, funcao=funcao,
                    valor_original=original, valor_tratado=tratado, motivo=motivo))


# ----------------------------------------------------------------------------
# Funções de limpeza de texto
# ----------------------------------------------------------------------------
def limpar_local(txt):
    """Padroniza o nome do local: 'Armario TB'/'Armários TB' -> 'Armário TB' etc."""
    t = re.sub(r"\s+", " ", str(txt)).strip()
    baixo = t.lower()
    if baixo.startswith("armario") or baixo.startswith("armário"):
        return "Armário TB"
    if baixo.startswith("interface"):
        return "Interface 2"
    if baixo.startswith("bastidor"):
        return "Bastidor DCC1"
    m = re.match(r"(?i)loca[çc][ãa]o\s*(\d+)", t)
    if m:
        return f"Locação {int(m.group(1))}"
    return t


def tipo_do_local(local):
    return "Locação" if local.startswith("Locação") else local


def limpar_terminal(valor, base, equip, local, funcao):
    """Devolve (lista_de_terminais, status).
    status: Conectado | Sem conexão ('-') | Não preenchido (vazio)."""
    if valor is None:
        return [None], "Não preenchido"
    original = str(valor)
    t = re.sub(r"\s+", " ", original).strip().upper()
    if t == "":
        return [None], "Não preenchido"
    if t == "-":
        return [None], "Sem conexão"
    if t.startswith("="):  # fórmula que aponta para uma célula com '-'
        registrar(base, equip, local, funcao, original, "-", "fórmula apontava para célula '-'")
        return [None], "Sem conexão"

    partes = [p.strip() for p in t.split("/")]
    saida = []
    for p in partes:
        novo = p
        novo = re.sub(r"^BL ", "LB ", novo)                      # 'BL B-11' -> 'LB B-11'
        m = re.fullmatch(r"B\s?(\d{2})\s?(\d{2})", novo)          # interfaces: 'B0923' -> 'B09 23'
        if m:
            novo = f"B{m.group(1)} {m.group(2)}"
        if novo != p:  # só registra quando o texto realmente foi reescrito
            registrar(base, equip, local, funcao, p, novo, "padronização de formato")
        saida.append(novo)
    if len(saida) > 1:
        registrar(base, equip, local, funcao, original, " | ".join(saida),
                  "célula com 2 terminais: separada em 2 linhas")
    return saida, "Conectado"


PADROES_OK = [
    r"(LB|LC) [A-Z]{1,2}-\d+",       # LB B-12, LC D-1, LB AA-16
    r"(LB|LC) TB{1,2}-[A-Z]{2}\d+",  # LB TB-AA22, LB TBB-BB13
    r"TB\d-[A-Z]\d+",                # TB2-E5, TB3-C37
    r"B\d{2} \d{2}",                 # interfaces: B02 21
    r"BAC\d+",                       # bastidor DCC1: BAC21
]


def prefixo_do_terminal(t):
    if pd.isna(t):
        return None
    if t.startswith("LB"):
        return "LB"
    if t.startswith("LC"):
        return "LC"
    if t.startswith("TB"):
        return "TB"
    if re.match(r"BAC", t):
        return "Bastidor (BAC)"
    if re.match(r"B\d", t):
        return "Interface (B)"
    return "Outro"


def terminal_suspeito(t):
    if pd.isna(t):
        return False
    return not any(re.fullmatch(p, t) for p in PADROES_OK)


# ----------------------------------------------------------------------------
# SINAIS
# ----------------------------------------------------------------------------
def ler_sinais():
    ws = openpyxl.load_workbook(ARQ_SINAIS, data_only=True).active
    linhas = []
    for row in ws.iter_rows():
        for cel in row:
            if not (isinstance(cel.value, str) and re.match(r"(?i)SINAL\s+\d+\s+LUZ", cel.value)):
                continue
            r0, c0 = cel.row, cel.column
            n_sinal = int(re.search(r"\d+", cel.value).group())
            # cabeçalho: r0+3 = códigos (4RGE, 4RGENX, 4YGE, 4YGENX); dados começam em r0+5
            codigos = [ws.cell(r0 + 3, c0 + k).value for k in range(1, 5)]
            funcoes = []
            for cod in codigos:
                f = re.sub(r"^\d+", "", str(cod)).strip().upper()
                funcoes.append(f)
            if codigos[0] and not re.match(r"\d", str(codigos[0])):
                registrar("Sinais", f"Sinal {n_sinal}", "-", "cabeçalho", str(codigos[0]),
                          f"{n_sinal}{codigos[0]}", "código sem o número do sinal: número deduzido do título")
            r = r0 + 5
            while True:
                loc = ws.cell(r, c0).value
                tit = str(loc) if loc is not None else ""
                if loc is None or re.match(r"(?i)SINAL", tit) or tit.strip() == "":
                    break
                local = limpar_local(loc)
                for k, fn in enumerate(funcoes, start=1):
                    bruto = ws.cell(r, c0 + k).value
                    terminais, status = limpar_terminal(bruto, "Sinais", f"Sinal {n_sinal}", local, fn)
                    for t in terminais:
                        linhas.append(dict(
                            sinal=n_sinal, sinal_nome=f"Sinal {n_sinal}", funcao=fn,
                            aspecto="Vermelho" if fn.startswith("R") else "Amarelo",
                            local=local, tipo_local=tipo_do_local(local),
                            terminal=t, status=status))
                r += 1
    return pd.DataFrame(linhas)


# ----------------------------------------------------------------------------
# CDVs
# ----------------------------------------------------------------------------
GRUPO_FUNCAO = {"NCTP": "Codificação", "SCTP": "Codificação", "N12-CTP": "Codificação",
                "TPR": "Indicação", "TPRN": "Indicação"}


def nome_funcao(cod):
    c = str(cod).strip().upper()
    if c.endswith("N12-CTP"):
        return "N12-CTP"
    for f in ("TPRN", "TPR", "NCTP", "SCTP"):   # TPRN antes de TPR
        if c.endswith(f):
            return f
    return c


def ler_cdvs():
    ws = openpyxl.load_workbook(ARQ_CDVS, data_only=True).active
    # cache: quantas vezes cada nome de CDV já apareceu (há nomes repetidos na planilha)
    contagem_nome = {}
    blocos = []
    for row in ws.iter_rows():
        for cel in row:
            if isinstance(cel.value, str) and re.match(r"(?i)CDV\s+\w+\s+LUZ", cel.value):
                blocos.append(cel)
    # ordem de leitura: por posição (linha, coluna) para os duplicados ficarem estáveis
    blocos.sort(key=lambda c: (c.column, c.row))
    nomes = [re.match(r"(?i)CDV\s+(\w+)\s+LUZ", b.value).group(1).upper() for b in blocos]
    repetidos = {n for n in nomes if nomes.count(n) > 1}

    linhas = []
    for cel, nome in zip(blocos, nomes):
        r0, c0 = cel.row, cel.column
        contagem_nome[nome] = contagem_nome.get(nome, 0) + 1
        if nome in repetidos:
            cdv_id = f"{nome} ({chr(64 + contagem_nome[nome])})"
            registrar("CDVs", nome, "-", "título", cel.value, cdv_id,
                      "nome de CDV repetido na planilha: sufixo (A), (B)... adicionado - CONFERIR")
        else:
            cdv_id = nome
        m = re.match(r"(\d)([NS])(\d+)T?", nome)
        via, sentido, num = (int(m.group(1)), m.group(2), int(m.group(3))) if m else (None, None, None)
        funcoes = [nome_funcao(ws.cell(r0 + 3, c0 + k).value) for k in range(1, 6)]
        r = r0 + 4
        while True:
            loc = ws.cell(r, c0).value
            if loc is None or str(loc).strip() == "" or re.match(r"(?i)CDV", str(loc)):
                break
            local = limpar_local(loc)
            for k, fn in enumerate(funcoes, start=1):
                bruto = ws.cell(r, c0 + k).value
                terminais, status = limpar_terminal(bruto, "CDVs", cdv_id, local, fn)
                for t in terminais:
                    linhas.append(dict(
                        cdv=cdv_id, cdv_numero=num, via=f"Via {via}",
                        sentido={"N": "Norte", "S": "Sul"}.get(sentido),
                        funcao=fn, grupo_funcao=GRUPO_FUNCAO[fn],
                        local=local, tipo_local=tipo_do_local(local),
                        terminal=t, status=status))
            r += 1
    return pd.DataFrame(linhas)


# ----------------------------------------------------------------------------
def finalizar(df, base, id_col):
    df["prefixo_terminal"] = df["terminal"].map(prefixo_do_terminal)
    df["terminal_suspeito"] = df["terminal"].map(terminal_suspeito)
    for _, l in df[df["terminal_suspeito"]].iterrows():
        registrar(base, l[id_col], l["local"], l["funcao"], l["terminal"], l["terminal"],
                  "formato fora do padrão: manter, mas CONFERIR na fonte")
    return df


def main():
    sinais = finalizar(ler_sinais(), "Sinais", "sinal_nome")
    cdvs = finalizar(ler_cdvs(), "CDVs", "cdv")
    sinais.to_csv(PASTA / "sinais_tratado.csv", index=False, encoding="utf-8-sig")
    cdvs.to_csv(PASTA / "cdvs_tratado.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(log).drop_duplicates().to_csv(PASTA / "log_qualidade.csv", index=False,
                                               encoding="utf-8-sig")
    print(f"sinais_tratado.csv : {len(sinais)} linhas, {sinais['sinal'].nunique()} sinais")
    print(f"cdvs_tratado.csv   : {len(cdvs)} linhas, {cdvs['cdv'].nunique()} CDVs")
    print(f"log_qualidade.csv  : {len(set(map(str, log)))} registros")


if __name__ == "__main__":
    main()
