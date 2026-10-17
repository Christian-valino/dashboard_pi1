"""
Dashboard - Levantamento de Sinais e CDVs (Vias 1 e 2)
Projeto Integrador 1 - Ciência de Dados

Como rodar:
    pip install -r requirements.txt
    python limpeza.py          # só na primeira vez (gera os CSVs tratados)
    streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PASTA = Path(__file__).parent / "dados"

# Cores fixas para o dashboard inteiro (quem vê o gráfico aprende a "ler" as cores)
COR_SINAL = "#E4572E"
COR_CDV = "#2E86AB"
COR_STATUS = {"Conectado": "#2A9D8F", "Sem conexão": "#BDBDBD", "Não preenchido": "#E9C46A"}
ORDEM_STATUS = ["Conectado", "Sem conexão", "Não preenchido"]

st.set_page_config(page_title="Sinais e CDVs - Vias 1 e 2", page_icon="🚦", layout="wide")


# ----------------------------------------------------------------------------
# Dados
# ----------------------------------------------------------------------------
@st.cache_data
def carregar():
    # Se os CSVs tratados ainda não existem, roda a limpeza automaticamente
    if not (PASTA / "sinais_tratado.csv").exists():
        import limpeza
        limpeza.main()
    sinais = pd.read_csv(PASTA / "sinais_tratado.csv")
    cdvs = pd.read_csv(PASTA / "cdvs_tratado.csv")
    # Nome original do CDV, sem o sufixo (A), (B)... usado para blocos com nome repetido na planilha
    cdvs["cdv_base"] = cdvs["cdv"].str.replace(r" \(.\)$", "", regex=True)
    log = pd.read_csv(PASTA / "log_qualidade.csv")
    return sinais, cdvs, log


def mostrar(fig, altura=380):
    """Mostra um gráfico Plotly com layout limpo e consistente."""
    fig.update_layout(height=altura, margin=dict(l=10, r=10, t=40, b=10),
                      font=dict(size=14), legend_title_text="")
    try:
        st.plotly_chart(fig, width="stretch")
    except TypeError:  # versões antigas do Streamlit
        st.plotly_chart(fig, use_container_width=True)


def ficha(df, id_col, escolhido):
    """Tabela 'local x função' com os terminais de um equipamento."""
    d = df[df[id_col] == escolhido].copy()
    d["terminal"] = d["terminal"].fillna(d["status"].map({"Sem conexão": "—", "Não preenchido": "(vazio)"}))
    ordem_local = list(dict.fromkeys(d["local"]))          # mantém a ordem original
    ordem_func = list(dict.fromkeys(d["funcao"]))
    tab = (d.groupby(["local", "funcao"])["terminal"].agg(" | ".join).unstack("funcao")
           .reindex(index=ordem_local, columns=ordem_func))
    return tab


sinais, cdvs, log = carregar()

# ----------------------------------------------------------------------------
# Cabeçalho
# ----------------------------------------------------------------------------
st.title("🚦 Levantamento de Sinais e CDVs - Vias 1 e 2")
st.markdown(
    "Este painel mostra **onde estão ligados** os fios de cada **Sinal** (semáforo de luzes) e de cada "
    "**CDV** (circuito de via) da linha, nas Vias 1 e 2. Cada ligação é registrada em um **local**: "
    "uma *Locação*, um *Armário TB* ou uma *Interface*."
)

# Filtro simples na barra lateral (vale para a aba de CDVs)
st.sidebar.header("Filtros")
via_sel = st.sidebar.radio("Via (aba CDVs)", ["Todas", "Via 1", "Via 2"])
st.sidebar.caption("A planilha de Sinais não informa a via, por isso o filtro vale só para os CDVs.")
st.sidebar.divider()
st.sidebar.markdown("**Legenda das cores**")
st.sidebar.markdown(
    f"<span style='color:{COR_SINAL}'>■</span> Sinais &nbsp; <span style='color:{COR_CDV}'>■</span> CDVs<br>"
    f"<span style='color:{COR_STATUS['Conectado']}'>■</span> Conectado<br>"
    f"<span style='color:{COR_STATUS['Sem conexão']}'>■</span> Sem conexão (marcado com '-')<br>"
    f"<span style='color:{COR_STATUS['Não preenchido']}'>■</span> Não preenchido (célula vazia)",
    unsafe_allow_html=True)

cdvs_f = cdvs if via_sel == "Todas" else cdvs[cdvs["via"] == via_sel]

aba1, aba2, aba3, aba4 = st.tabs(["📌 Visão geral", "🚦 Sinais", "🛤️ CDVs", "🧹 Qualidade dos dados"])

# ----------------------------------------------------------------------------
# ABA 1 - Visão geral
# ----------------------------------------------------------------------------
with aba1:
    locs_sinais = set(sinais.loc[sinais.tipo_local == "Locação", "local"])
    locs_cdvs = set(cdvs.loc[cdvs.tipo_local == "Locação", "local"])
    pontos = int((sinais.status == "Conectado").sum() + (cdvs.status == "Conectado").sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sinais levantados", sinais["sinal"].nunique())
    c2.metric("CDVs levantados", cdvs["cdv_base"].nunique())
    c3.metric("Locações diferentes", len(locs_sinais | locs_cdvs))
    c4.metric("Pontos de ligação registrados", pontos)

    col_a, col_b = st.columns(2)

    with col_a:
        # Locações mais usadas: quantos equipamentos diferentes passam em cada uma
        ls = (sinais[(sinais.tipo_local == "Locação")].groupby("local")["sinal"].nunique()
              .rename("Sinais"))
        lc = (cdvs[(cdvs.tipo_local == "Locação") & (cdvs.status == "Conectado")]
              .groupby("local")["cdv_base"].nunique().rename("CDVs"))
        loc = pd.concat([ls, lc], axis=1).fillna(0).astype(int)
        loc["Total"] = loc.sum(axis=1)
        loc = loc.sort_values("Total", ascending=False).head(10).drop(columns="Total")
        loc = loc.reset_index().melt(id_vars="local", var_name="Equipamento", value_name="Quantidade")
        fig = px.bar(loc, y="local", x="Quantidade", color="Equipamento", orientation="h",
                     color_discrete_map={"Sinais": COR_SINAL, "CDVs": COR_CDV},
                     title="As 10 Locações mais usadas", labels={"local": ""})
        fig.update_yaxes(categoryorder="total ascending")
        mostrar(fig)
        topo = loc.groupby("local")["Quantidade"].sum().sort_values(ascending=False)
        st.caption(f"Como ler: cada barra mostra quantos Sinais e CDVs têm ligação naquela Locação. "
                   f"**{topo.index[0]}** é a mais usada ({topo.iloc[0]} equipamentos).")

    with col_b:
        # Qualidade/preenchimento do levantamento
        st_s = sinais["status"].value_counts().rename("Sinais")
        st_c = cdvs["status"].value_counts().rename("CDVs")
        stt = pd.concat([st_s, st_c], axis=1).fillna(0).reindex(ORDEM_STATUS).fillna(0)
        stt = stt.div(stt.sum()).mul(100).round(1).reset_index().rename(columns={"index": "Status", "status": "Status"})
        stt = stt.melt(id_vars="Status", var_name="Base", value_name="%")
        fig = px.bar(stt, x="Base", y="%", color="Status", color_discrete_map=COR_STATUS,
                     category_orders={"Status": ORDEM_STATUS}, text="%",
                     title="Situação de cada ponto do levantamento (%)")
        fig.update_traces(texttemplate="%{text:.0f}%", textposition="inside")
        fig.update_yaxes(range=[0, 100], title="")
        fig.update_xaxes(title="")
        mostrar(fig)
        st.caption("Como ler: 'Conectado' = tem um terminal registrado; 'Sem conexão' = a planilha marca '-' "
                   "(a função não é ligada naquele local); 'Não preenchido' = célula vazia.")

# ----------------------------------------------------------------------------
# ABA 2 - Sinais
# ----------------------------------------------------------------------------
with aba2:
    st.subheader("Sinais")
    st.markdown("Cada sinal tem **4 funções** (2 do aspecto *Vermelho*: RGE e RGENX; 2 do *Amarelo*: YGE e YGENX). "
                "Cada função é ligada em alguns locais, do campo (Locação) até a Interface.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Sinais", sinais["sinal"].nunique())
    c2.metric("Locais por sinal (média)", f"{sinais.groupby('sinal')['local'].nunique().mean():.1f}")
    c3.metric("Pontos conectados", int((sinais.status == "Conectado").sum()))

    col_a, col_b = st.columns(2)
    with col_a:
        por_sinal = (sinais.groupby(["sinal", "sinal_nome"])["local"].nunique().reset_index(name="Locais")
                     .sort_values("sinal"))
        fig = px.bar(por_sinal, x="sinal_nome", y="Locais", text="Locais",
                     title="Quantos locais cada sinal atravessa", labels={"sinal_nome": ""},
                     color_discrete_sequence=[COR_SINAL])
        fig.update_xaxes(categoryorder="array", categoryarray=por_sinal["sinal_nome"].tolist(), tickangle=-45)
        fig.update_yaxes(dtick=1)
        mostrar(fig)
        st.caption("Como ler: quanto maior a barra, mais 'paradas' o fio daquele sinal faz entre o campo e a interface.")

    with col_b:
        s_loc = (sinais[sinais.tipo_local == "Locação"].groupby("local")["sinal"].nunique()
                 .reset_index(name="Sinais").sort_values("Sinais", ascending=False))
        fig = px.bar(s_loc, x="local", y="Sinais", text="Sinais", title="Quantos sinais passam em cada Locação",
                     labels={"local": ""}, color_discrete_sequence=[COR_SINAL])
        fig.update_xaxes(categoryorder="total descending", tickangle=-45, tickmode="linear")
        fig.update_yaxes(dtick=1)
        mostrar(fig)
        st.caption("Como ler: Locações com barras altas concentram ligações de vários sinais.")

    col_c, col_d = st.columns(2)
    with col_c:
        pref = (sinais[sinais.status == "Conectado"].groupby("prefixo_terminal").size()
                .reset_index(name="Pontos"))
        fig = px.pie(pref, names="prefixo_terminal", values="Pontos", hole=0.45,
                     title="Tipos de terminal usados nos sinais",
                     color_discrete_sequence=["#E4572E", "#F18F01", "#C73E1D", "#F4A261", "#8D6E63"])
        fig.update_traces(textinfo="percent", textposition="inside")
        mostrar(fig)
        st.caption("Como ler: o prefixo do código do terminal (LB, LC, TB...) indica o tipo de ponto de ligação.")

    with col_d:
        st.markdown("**Ficha de um sinal**")
        escolhido = st.selectbox("Escolha um sinal", sorted(sinais["sinal_nome"].unique(),
                                                             key=lambda x: int(x.split()[1])))
        st.dataframe(ficha(sinais, "sinal_nome", escolhido), width="stretch")
        st.caption("Cada linha é um local; cada coluna é uma função do sinal; a célula é o terminal onde o fio liga.")

# ----------------------------------------------------------------------------
# ABA 3 - CDVs
# ----------------------------------------------------------------------------
with aba3:
    st.subheader(f"CDVs ({via_sel})")
    st.markdown("Cada CDV tem **5 funções**: 3 de *Codificação* (NCTP, SCTP, N12-CTP) e 2 de *Indicação* "
                "(TPR, TPRN). O nome do CDV indica a via e o sentido, por exemplo **1N08T** = Via 1, Norte, nº 08.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CDVs", cdvs_f["cdv_base"].nunique())
    c2.metric("Locações diferentes", cdvs_f.loc[cdvs_f.tipo_local == "Locação", "local"].nunique())
    c3.metric("Pontos conectados", int((cdvs_f.status == "Conectado").sum()))
    c4.metric("Funções 'sem conexão'", f"{(cdvs_f.status == 'Sem conexão').mean() * 100:.0f}%")

    col_a, col_b = st.columns(2)
    with col_a:
        base = cdvs_f[(cdvs_f.tipo_local == "Locação") & (cdvs_f.status == "Conectado")]
        n_loc = (base.groupby(["cdv", "via"])["local"].nunique().reset_index(name="Locações")
                 .sort_values("Locações", ascending=False))
        fig = px.bar(n_loc, x="cdv", y="Locações", color="via", text="Locações",
                     color_discrete_map={"Via 1": "#2E86AB", "Via 2": "#F18F01"},
                     title="Em quantas Locações cada CDV está ligado", labels={"cdv": ""})
        ordem = n_loc["cdv"].tolist()
        fig.update_xaxes(categoryorder="array", categoryarray=ordem, tickmode="array",
                         tickvals=ordem, ticktext=ordem, tickangle=-45)   # mostra todos os nomes
        fig.update_yaxes(dtick=1)
        mostrar(fig)
        if len(n_loc):
            maximo = n_loc["Locações"].max()
            lideres = ", ".join(n_loc.loc[n_loc["Locações"] == maximo, "cdv"])
            st.caption(f"Como ler: CDVs com barras altas são mais 'espalhados' pela linha. "
                       f"Os mais espalhados ({maximo} Locações): **{lideres}**.")

    with col_b:
        fun = (cdvs_f.groupby(["funcao", "status"]).size().reset_index(name="n"))
        fun["%"] = fun["n"] / fun.groupby("funcao")["n"].transform("sum") * 100
        fig = px.bar(fun, x="funcao", y="%", color="status", color_discrete_map=COR_STATUS,
                     category_orders={"status": ORDEM_STATUS, "funcao": ["NCTP", "SCTP", "N12-CTP", "TPR", "TPRN"]},
                     title="Cada função está ligada em quanto % dos locais?",
                     labels={"funcao": "", "status": ""})
        fig.update_yaxes(range=[0, 100], title="%")
        mostrar(fig)
        pct = (fun[fun.status == "Conectado"].set_index("funcao")["%"]).round(0)
        if len(pct):
            st.caption(f"Como ler: verde = função ligada no local. A função mais presente é **{pct.idxmax()}** "
                       f"({pct.max():.0f}%) e a menos presente é **{pct.idxmin()}** ({pct.min():.0f}%).")

    # Mapa de calor CDV x Locação
    mapa = (cdvs_f[(cdvs_f.tipo_local == "Locação") & (cdvs_f.status == "Conectado")]
            .groupby(["cdv", "local"]).size().unstack("local").fillna(0))
    if not mapa.empty:
        mapa = mapa.reindex(sorted(mapa.columns, key=lambda x: int(x.split()[1])), axis=1)
        mapa = mapa.where(mapa > 0)   # zero vira vazio: o gráfico fica mais limpo
        fig = px.imshow(mapa, aspect="auto", color_continuous_scale="Blues", text_auto=".0f",
                        labels=dict(x="Locação", y="CDV", color="Pontos"),
                        title="Mapa de calor: quantos pontos cada CDV tem em cada Locação")
        mostrar(fig, altura=max(380, 26 * len(mapa) + 120))
        st.caption("Como ler: quanto mais escura a célula, mais funções daquele CDV estão ligadas naquela Locação "
                   "(cada terminal conectado conta 1 ponto). Célula vazia = o CDV não tem ligação ali.")

    st.markdown("**Ficha de um CDV**")
    escolhido = st.selectbox("Escolha um CDV", sorted(cdvs_f["cdv"].unique()))
    st.dataframe(ficha(cdvs_f, "cdv", escolhido), width="stretch")
    st.caption("'—' significa 'sem conexão' (a planilha marca '-'); '(vazio)' significa célula não preenchida.")

# ----------------------------------------------------------------------------
# ABA 4 - Qualidade dos dados
# ----------------------------------------------------------------------------
with aba4:
    st.subheader("Como os dados foram tratados")
    st.markdown(
        "As planilhas originais são organizadas para **leitura visual** (blocos lado a lado, células mescladas). "
        "Para fazer gráficos, foram transformadas em tabelas em que **cada linha é um ponto de ligação** "
        "(equipamento + função + local + terminal)."
    )
    precisa = log[log["motivo"].str.contains("CONFERIR")]
    c1, c2, c3 = st.columns(3)
    c1.metric("Linhas na base de Sinais", len(sinais))
    c2.metric("Linhas na base de CDVs", len(cdvs))
    c3.metric("Itens para conferir na fonte", len(precisa))

    st.markdown("**O que foi feito**")
    st.markdown(
        "- Blocos lado a lado reorganizados em uma única tabela por planilha.\n"
        "- Nomes de local padronizados (*Armario TB* e *Armários TB* → **Armário TB**; *interface 2* → **Interface 2**).\n"
        "- Espaços extras removidos e códigos de interface padronizados (ex.: `B0923` → `B09 23`; `BL B-11` → `LB B-11`).\n"
        "- Células com dois terminais (`LB A-23 / LB B-22`) separadas em duas linhas.\n"
        "- Cada ponto recebeu um **status**: *Conectado*, *Sem conexão* ('-') ou *Não preenchido* (vazio).\n"
        "- Variáveis novas: via e sentido (a partir do nome do CDV), aspecto do sinal (vermelho/amarelo), "
        "tipo de local e prefixo do terminal."
    )
    st.markdown("**Registro de alterações e itens para conferir**")
    st.dataframe(log, width="stretch", hide_index=True)

    st.markdown("**Baixar as bases tratadas**")
    d1, d2, d3 = st.columns(3)
    d1.download_button("sinais_tratado.csv", sinais.to_csv(index=False).encode("utf-8-sig"),
                       "sinais_tratado.csv", "text/csv")
    d2.download_button("cdvs_tratado.csv", cdvs.to_csv(index=False).encode("utf-8-sig"),
                       "cdvs_tratado.csv", "text/csv")
    d3.download_button("log_qualidade.csv", log.to_csv(index=False).encode("utf-8-sig"),
                       "log_qualidade.csv", "text/csv")
