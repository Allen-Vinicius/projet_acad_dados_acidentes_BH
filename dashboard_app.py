from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from prophet import Prophet
except Exception:
    Prophet = None
st.set_page_config(
    page_title='Dashboard Acidentes BH',
    page_icon='car',
    layout='wide',
    initial_sidebar_state='expanded',
)

BASE_DIR = Path(__file__).resolve().parent


def normalize_col(name: str) -> str:
    name = str(name).strip().lower()
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', '_', name).strip('_')


def normalize_text(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().replace({'nan': np.nan, 'None': np.nan, '': np.nan, '0': np.nan})


def normalize_flag_series(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip().str.upper()
    s = s.replace({'SIM': 'S', 'NÃO': 'N', 'NAO': 'N', 'NÃO INFORMADO': '0', 'NAO INFORMADO': '0'})
    s = s.replace({'0': np.nan, 'NAN': np.nan, 'NONE': np.nan, '': np.nan})
    return s


def format_compact(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}b".replace('.', ',')
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}m".replace('.', ',')
    if n >= 1_000:
        return f"{n/1_000:.1f}k".replace('.', ',')
    return str(n)


def sexo_label(sigla: str) -> str:
    return {'M': 'Masculino', 'F': 'Feminino'}.get(sigla, sigla)




def ensure_boletim_col(df: pd.DataFrame) -> pd.DataFrame:
    candidates = ['boletim', 'numero_boletim', 'num_boletim', 'n_boletim', 'no_boletim', 'numero_bol']
    for c in candidates:
        if c in df.columns:
            return df.rename(columns={c: 'boletim'})
    return df


def safe_series(df: pd.DataFrame, col: str, default: str = '') -> pd.Series:
    if col in df.columns:
        s = df[col]
    else:
        s = pd.Series([default] * len(df), index=df.index, name=col)
    if s.name != col:
        s = s.rename(col)
    return s


def safe_upper(df: pd.DataFrame, col: str) -> pd.Series:
    return safe_series(df, col, '').astype(str).str.upper()


def sum_numeric(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns:
        return 0.0
    return pd.to_numeric(df[col], errors='coerce').fillna(0).sum()


def canonical_bairro_label(s: pd.Series) -> pd.Series:
    bairro = s.fillna('').astype(str).str.strip()
    bairro_upper = bairro.str.upper()
    return bairro.where(~bairro_upper.eq('CENTRO'), 'Centro')


def metric_card(label: str, value: str, help_text: str = '') -> None:
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-label'>{label}</div>
            <div class='metric-value'>{value}</div>
            <div class='metric-help'>{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    acc = pd.read_csv(BASE_DIR / 'acidentes_bh_dashboard.csv', encoding='utf-8-sig', low_memory=False)
    acc.columns = [normalize_col(c) for c in acc.columns]
    acc = ensure_boletim_col(acc)

    for c in ['data', 'data_hora']:
        if c in acc.columns:
            acc[c] = pd.to_datetime(acc[c], errors='coerce')

    for c in ['desc_regional', 'bairro', 'desc_tempo', 'desc_tipo_acidente', 'indicador_fatalidade', 'nome_municipio']:
        if c in acc.columns:
            acc[c] = normalize_text(acc[c])
    if 'indicador_fatalidade' in acc.columns:
        acc['indicador_fatalidade'] = normalize_flag_series(acc['indicador_fatalidade'])

    for c in ['total_fatais', 'total_envolvidos', 'total_veiculos', 'idade_media_envolvidos']:
        if c in acc.columns:
            acc[c] = pd.to_numeric(acc[c], errors='coerce')

    env = pd.read_excel(BASE_DIR / 'Dados_de_Acidentes_de_Transito_em_BH.xlsx', sheet_name='envolvidos')
    env.columns = [normalize_col(c) for c in env.columns]
    env = ensure_boletim_col(env)

    for c in ['sexo', 'cinto_seguranca', 'embreagues', 'condutor', 'desc_severidade', 'descricao_habilitacao', 'categoria_habilitacao', 'especie_veiculo']:
        if c in env.columns:
            env[c] = normalize_text(env[c]).str.upper()
    for c in ['cinto_seguranca', 'embreagues', 'condutor']:
        if c in env.columns:
            env[c] = normalize_flag_series(env[c])

    if 'idade' in env.columns:
        env['idade'] = pd.to_numeric(env['idade'], errors='coerce')

    veh = pd.read_excel(BASE_DIR / 'Dados_de_Acidentes_de_Transito_em_BH.xlsx', sheet_name='veiculos')
    veh.columns = [normalize_col(c) for c in veh.columns]
    veh = ensure_boletim_col(veh)

    for c in ['descricao_categoria', 'descricao_especie']:
        if c in veh.columns:
            veh[c] = normalize_text(veh[c]).str.upper()

    if 'boletim' not in acc.columns:
        raise KeyError('Coluna "boletim" nao encontrada em acidentes_bh_dashboard.csv')
    if 'boletim' not in env.columns:
        raise KeyError('Coluna "boletim" nao encontrada na planilha "envolvidos"')
    if 'boletim' not in veh.columns:
        raise KeyError('Coluna "boletim" nao encontrada na planilha "veiculos"')

    acc['boletim'] = acc['boletim'].astype(str)
    env['boletim'] = env['boletim'].astype(str)
    veh['boletim'] = veh['boletim'].astype(str)

    dim_cols = ['boletim', 'data', 'ano', 'mes', 'desc_regional', 'bairro', 'desc_tempo', 'desc_tipo_acidente']
    dim = acc[[c for c in dim_cols if c in acc.columns]].copy()

    env = env.merge(dim, on='boletim', how='left')
    veh = veh.merge(dim, on='boletim', how='left')

    return acc, env, veh


def apply_filters(
    acc: pd.DataFrame,
    env: pd.DataFrame,
    veh: pd.DataFrame,
    date_range: tuple[pd.Timestamp, pd.Timestamp],
    regionais: Iterable[str],
    bairros: Iterable[str],
    tipos: Iterable[str],
    climas: Iterable[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    d0, d1 = date_range
    mask = pd.Series(True, index=acc.index)

    if 'data' in acc.columns:
        mask &= acc['data'].between(d0, d1)
    if regionais:
        mask &= safe_series(acc, 'desc_regional').isin(regionais)
    if bairros:
        mask &= safe_series(acc, 'bairro').isin(bairros)
    if tipos:
        mask &= safe_series(acc, 'desc_tipo_acidente').isin(tipos)
    if climas:
        mask &= safe_series(acc, 'desc_tempo').isin(climas)

    acc_f = acc.loc[mask].copy()
    boletins = set(acc_f['boletim'].astype(str).unique())

    env_f = env[env['boletim'].isin(boletins)].copy()
    veh_f = veh[veh['boletim'].isin(boletins)].copy()

    return acc_f, env_f, veh_f


st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(circle at 8% 12%, #212225 0%, #101114 40%, #0a0a0c 85%);
        color: #f3f4f6;
    }
    .block-container { padding-top: 1.2rem; }
    h1, h2, h3 { color: #f8fafc !important; letter-spacing: .2px; }
    .subtitle { color: #cbd5e1; margin-top: -8px; margin-bottom: 14px; }
    .metric-card {
        background: linear-gradient(135deg, rgba(255,255,255,.06), rgba(255,255,255,.03));
        border: 1px solid rgba(255,255,255,.10);
        border-radius: 14px;
        padding: 14px 16px;
        height: clamp(110px, 12vw, 140px);
        box-shadow: 0 10px 24px rgba(0,0,0,.28);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        align-items: flex-start;
    }
    .metric-label { color: #f97316; font-size: 13px; text-transform: uppercase; letter-spacing: .8px; line-height: 1.1; }
    .metric-value { color: #f8fafc; font-size: 32px; font-weight: 700; line-height: 1; }
    .metric-help { color: #94a3b8; font-size: 12px; line-height: 1.2; }
    section[data-testid='stSidebar'] {
        background: linear-gradient(180deg, #131417 0%, #1c1f24 100%);
        border-right: 1px solid rgba(255,255,255,.08);
    }
    /* Period selector (radio -> pills) */
    .period-pill [role='radiogroup'] {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }
    .period-pill [role='radio'] {
        background: rgba(255,255,255,.08);
        border: 1px solid rgba(255,255,255,.15);
        border-radius: 999px;
        padding: 6px 12px;
        color: #e2e8f0;
        transition: all .18s ease;
    }
    .period-pill [role='radio'][aria-checked='true'] {
        background: #f97316;
        border-color: #f97316;
        color: #0b0b0e;
        font-weight: 700;
        box-shadow: 0 6px 18px rgba(249,115,22,.35);
    }
    .period-pill [role='radio'] > div {
        margin: 0;
    }
    .period-pill [role='radio'] > div > label {
        cursor: pointer;
        padding: 0;
    }
    .emb-card {
        background: linear-gradient(135deg, rgba(249,115,22,.18), rgba(255,255,255,.02));
        border: 1px solid rgba(249,115,22,.30);
        border-radius: 14px;
        padding: 12px 14px;
        box-shadow: 0 10px 22px rgba(0,0,0,.25);
        margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title('Dashboard de Acidentes de Transito - Belo Horizonte')
st.markdown("<div class='subtitle'>Analise interativa com foco em risco viario, severidade e perfil dos envolvidos.</div>", unsafe_allow_html=True)

acc, env, veh = load_data()

with st.sidebar:
    st.header('Filtros Globais')

    if 'data' not in acc.columns or acc['data'].isna().all():
        st.error('Coluna de data ausente ou sem valores validos.')
        st.stop()
    min_date = acc['data'].min().date()
    max_date = acc['data'].max().date()

    years = sorted([int(y) for y in acc['data'].dt.year.dropna().unique()])
    year_opts = ['Todo periodo'] + [str(y) for y in years]

    if 'quick_period' not in st.session_state:
        st.session_state['quick_period'] = 'Todo periodo'
    if 'date_range' not in st.session_state:
        st.session_state['date_range'] = (min_date, max_date)

    def set_period_from_quick() -> None:
        qp = st.session_state.get('quick_period', 'Todo periodo')
        if qp == 'Todo periodo':
            st.session_state['date_range'] = (min_date, max_date)
        else:
            y = int(qp)
            f0 = pd.Timestamp(f'{y}-01-01').date()
            f1 = pd.Timestamp(f'{y}-12-31').date()
            st.session_state['date_range'] = (f0, f1)

    def reset_period() -> None:
        st.session_state['quick_period'] = 'Todo periodo'
        st.session_state['date_range'] = (min_date, max_date)

    st.markdown("<div class='period-pill'>", unsafe_allow_html=True)
    quick = st.radio(
        'Periodo rapido',
        year_opts,
        index=0,
        horizontal=True,
        label_visibility='collapsed',
        key='quick_period',
        on_change=set_period_from_quick,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.button('Resetar periodo', on_click=reset_period)

    if quick == 'Todo periodo':
        date_range = st.date_input('Periodo', min_value=min_date, max_value=max_date, format='DD/MM/YYYY', key='date_range')
    else:
        y = int(quick)
        f0 = pd.Timestamp(f'{y}-01-01').date()
        f1 = pd.Timestamp(f'{y}-12-31').date()
        date_range = st.date_input('Periodo', min_value=min_date, max_value=max_date, format='DD/MM/YYYY', key='date_range')

    all_reg = sorted([x for x in safe_series(acc, 'desc_regional').dropna().unique() if str(x).strip()])
    reg_sel = st.multiselect('Regional', all_reg)

    acc_ref = acc if not reg_sel else acc[safe_series(acc, 'desc_regional').isin(reg_sel)]
    all_bairros = sorted([x for x in safe_series(acc_ref, 'bairro').dropna().unique() if str(x).strip()])
    bairro_sel = st.multiselect('Bairro', all_bairros)

    all_tipos = sorted([x for x in safe_series(acc, 'desc_tipo_acidente').dropna().unique() if str(x).strip()])
    tipo_sel = st.multiselect('Tipo de acidente', all_tipos)

    all_clima = sorted([x for x in safe_series(acc, 'desc_tempo').dropna().unique() if str(x).strip()])
    clima_sel = st.multiselect('Condicao climatica', all_clima)

if len(date_range) != 2:
    st.error('Selecione data inicial e final.')
    st.stop()

acc_f, env_f, veh_f = apply_filters(
    acc, env, veh,
    (pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])),
    reg_sel,
    bairro_sel,
    tipo_sel,
    clima_sel,
)

# KPIs
acc_total = int(acc_f['boletim'].nunique())
if 'numero_envolvido' in env_f.columns:
    env_total = int(sum_numeric(env_f, 'numero_envolvido'))
else:
    env_total = int(sum_numeric(acc_f, 'total_envolvidos'))
fatal_mask = safe_series(env_f, 'desc_severidade').astype(str).str.strip().str.upper().eq('FATAL')
if 'numero_envolvido' in env_f.columns:
    mortes_total = int(pd.to_numeric(env_f.loc[fatal_mask, 'numero_envolvido'], errors='coerce').fillna(0).sum())
else:
    mortes_total = int(sum_numeric(acc_f, 'total_fatais'))

condutores = env_f[safe_upper(env_f, 'condutor') == 'S'].copy()
idade_media = float(condutores['idade'].mean()) if not condutores.empty else np.nan

sem_hab = condutores[
    safe_upper(condutores, 'descricao_habilitacao').str.contains('INABILITADO', na=False)
    | safe_upper(condutores, 'categoria_habilitacao').eq('IN')
]
qtd_sem_hab = int(len(sem_hab))

cinto_norm = normalize_flag_series(safe_series(env_f, 'cinto_seguranca'))
sem_cinto_acc = int(cinto_norm.eq('N').sum())

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    metric_card('Total de acidentes', f'{acc_total:,}'.replace(',', '.'), '')
with c2:
    metric_card('Pessoas envolvidas', f'{env_total:,}'.replace(',', '.'), '')
with c3:
    metric_card('Mortes no periodo', f'{mortes_total:,}'.replace(',', '.'), '')
with c4:
    metric_card('Media idade condutores', '-' if np.isnan(idade_media) else f'{idade_media:.1f}', '')
with c5:
    metric_card('Condutores sem habilitacao', f'{qtd_sem_hab:,}'.replace(',', '.'), '')
with c6:
    metric_card('Acidentes sem cinto', f'{int(sem_cinto_acc):,}'.replace(',', '.'), '')

tab1, tab2, tab3, tab4, tab5 = st.tabs(['Tempo e Volume', 'Perfil e Severidade', 'Territorio BH', 'Veiculos', 'Previsao'])

with tab1:
    st.subheader('Evolucao de acidentes por mes e ano')
    col_a, col_b = st.columns(2)

    mes_map = {
        1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
        7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez',
    }
    monthly = (
        acc_f.assign(_mes_period=acc_f['data'].dt.to_period('M'))
        .groupby('_mes_period', as_index=False)['boletim']
        .nunique()
        .rename(columns={'boletim': 'acidentes'})
        .sort_values('_mes_period')
    )
    monthly['ACD_Mês'] = (
        monthly['_mes_period'].dt.to_timestamp().dt.month.map(mes_map)
        + '/'
        + monthly['_mes_period'].dt.to_timestamp().dt.year.astype(str)
    )
    yearly = (
        acc.assign(ACD_ANO=acc['data'].dt.year)
        .groupby('ACD_ANO', as_index=False)['boletim']
        .nunique()
        .rename(columns={'boletim': 'acidentes'})
    )

    fig_month = px.bar(
        monthly,
        x='ACD_Mês',
        y='acidentes',
        template='plotly_dark',
        color_discrete_sequence=['#22d3ee'],
        category_orders={'ACD_Mês': monthly['ACD_Mês'].tolist()},
    )
    fig_month.update_layout(bargap=0.45)
    fig_year = px.bar(yearly, x='ACD_ANO', y='acidentes', template='plotly_dark', color_discrete_sequence=['#f43f5e'])

    col_a.plotly_chart(fig_month, use_container_width=True)
    col_b.plotly_chart(fig_year, use_container_width=True)

    st.subheader('Tipos de acidente com maior ocorrencia')
    top_tipos = (
        acc_f.groupby('desc_tipo_acidente', as_index=False)['boletim']
        .nunique()
        .rename(columns={'boletim': 'acidentes'})
        .sort_values('acidentes', ascending=False)
        .head(10)
    )
    fig_tipos = px.bar(top_tipos, x='acidentes', y='desc_tipo_acidente', orientation='h', template='plotly_dark', color='acidentes', color_continuous_scale='Oranges')
    fig_tipos.update_layout(yaxis_title='Tipo', xaxis_title='Acidentes')
    st.plotly_chart(fig_tipos, use_container_width=True)

with tab2:
    st.subheader('Genero das pessoas envolvidas')
    sexo_full = safe_upper(env_f, 'sexo')
    genero = sexo_full.value_counts(dropna=False).rename_axis('sexo').reset_index(name='qtd')
    genero = genero[genero['sexo'].isin(['M', 'F'])]
    genero['qtd_label'] = genero['qtd'].apply(lambda x: format_compact(int(x)))
    sexo_colors = {'M': '#38bdf8', 'F': '#f472b6', 'NI': '#94a3b8'}
    fig_genero = px.pie(
        genero,
        names='sexo',
        values='qtd',
        hole=0.55,
        template='plotly_dark',
        color='sexo',
        color_discrete_map=sexo_colors,
    )
    fig_genero.update_traces(
        texttemplate='%{percent:.1%}<br>%{customdata[0]}',
        customdata=np.stack([genero['qtd_label']], axis=-1),
        textposition='inside',
    )
    fig_genero.update_layout(showlegend=True)

    left, right = st.columns([2, 1])
    left.plotly_chart(fig_genero, use_container_width=True)

    emb = env_f[normalize_flag_series(safe_series(env_f, 'embreagues')).eq('S')].copy()
    emb_sexo = safe_upper(emb, 'sexo')
    emb_sexo = emb_sexo[emb_sexo.isin(['M', 'F'])]
    emb_counts = emb_sexo.value_counts().reindex(['M', 'F']).fillna(0).astype(int)
    m_count = int(emb_counts.get('M', 0))
    f_count = int(emb_counts.get('F', 0))
    total_emb = m_count + f_count

    if total_emb == 0:
        winner = 'Sem dados'
        help_text = 'Nao ha registros com embriaguez no recorte'
    else:
        if m_count > f_count:
            winner = 'Masculino'
        elif f_count > m_count:
            winner = 'Feminino'
        else:
            winner = 'Empate'

        perc_m = (m_count / total_emb * 100) if total_emb else 0
        perc_f = (f_count / total_emb * 100) if total_emb else 0
        help_text = (
            f"M: {format_compact(m_count)} ({perc_m:.1f}%) | "
            f"F: {format_compact(f_count)} ({perc_f:.1f}%)"
        )

    right.markdown(
        f"""
        <div class='emb-card'>
            <div class='metric-label'>Embriaguez mais frequente</div>
            <div class='metric-value' style='font-size: 24px;'>{winner}</div>
            <div class='metric-help'>{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    emb_plot = pd.DataFrame({'sexo': ['F', 'M'], 'qtd': [f_count, m_count]}).sort_values('qtd', ascending=False)
    fig_emb = px.bar(
        emb_plot,
        x='qtd',
        y='sexo',
        orientation='h',
        template='plotly_dark',
        color='sexo',
        color_discrete_map={'M': '#38bdf8', 'F': '#fb7185'},
        category_orders={'sexo': emb_plot['sexo'].tolist()},
    )
    fig_emb.update_traces(
        text=None,
        marker=dict(
            line=dict(color='rgba(255,255,255,.35)', width=1),
            pattern=dict(shape='.', fgcolor='rgba(255,255,255,.35)', size=6, solidity=0.2),
        ),
        hovertemplate='Sexo: %{y}<br>Qtd: %{x}<extra></extra>',
    )
    fig_emb.update_layout(
        height=230,
        showlegend=False,
        xaxis_title='',
        yaxis_title='',
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,.08)', zeroline=False, tickformat=','),
        yaxis=dict(showgrid=False),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    right.plotly_chart(fig_emb, use_container_width=True)

    st.subheader('Condicoes climaticas e acidentes')
    clima = (
        acc_f.groupby('desc_tempo', as_index=False)['boletim']
        .nunique()
        .rename(columns={'boletim': 'acidentes'})
        .sort_values('acidentes', ascending=False)
    )
    fig_clima = px.bar(clima, x='desc_tempo', y='acidentes', template='plotly_dark', color='acidentes', color_continuous_scale='RdYlBu_r')
    st.plotly_chart(fig_clima, use_container_width=True)

    adverso = ['CHUVA', 'NUBLADO', 'NEBLINA']
    qtd_adverso = int(acc_f[acc_f['desc_tempo'].isin(adverso)]['boletim'].nunique())
    perc_adverso = (qtd_adverso / acc_total * 100) if acc_total else 0
    st.info(f"No recorte atual, {perc_adverso:.1f}% dos acidentes ocorreram em condicao climatica adversa.")

with tab3:
    st.subheader('Regionais com maior numero de acidentes')
    reg = (
        acc_f.groupby('desc_regional', as_index=False)['boletim']
        .nunique()
        .rename(columns={'boletim': 'acidentes'})
        .sort_values('acidentes', ascending=False)
    )
    fig_reg = px.bar(reg, x='desc_regional', y='acidentes', template='plotly_dark', color='acidentes', color_continuous_scale='Tealgrn')
    st.plotly_chart(fig_reg, use_container_width=True)

    st.subheader('Top 10 bairros com mais acidentes')
    bairro_rank = acc_f.copy()
    bairro_rank['bairro'] = canonical_bairro_label(safe_series(bairro_rank, 'bairro'))
    bairro_rank = bairro_rank[bairro_rank['bairro'] != '']
    top_bairro = (
        bairro_rank.groupby('bairro', as_index=False)['boletim']
        .nunique()
        .rename(columns={'boletim': 'acidentes'})
        .sort_values('acidentes', ascending=False)
        .head(10)
    )
    fig_bairro = px.bar(top_bairro, x='acidentes', y='bairro', orientation='h', template='plotly_dark', color='acidentes', color_continuous_scale='OrRd')
    st.plotly_chart(fig_bairro, use_container_width=True)

    st.subheader('Mapa de pontos dos acidentes')
    map_df = acc_f.copy()
    if 'latitude' in map_df.columns:
        map_df['latitude'] = pd.to_numeric(map_df['latitude'], errors='coerce')
    if 'longitude' in map_df.columns:
        map_df['longitude'] = pd.to_numeric(map_df['longitude'], errors='coerce')
    map_df = map_df.dropna(subset=['latitude', 'longitude'])
    map_df = map_df[['boletim', 'latitude', 'longitude', 'desc_tipo_acidente', 'desc_regional', 'bairro']].head(20000)

    if map_df.empty:
        st.warning('Sem coordenadas no recorte atual.')
    else:
        fig_map = px.scatter_mapbox(
            map_df,
            lat='latitude',
            lon='longitude',
            color='desc_regional',
            hover_data=['boletim', 'desc_tipo_acidente', 'bairro'],
            zoom=10.5,
            height=580,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_map.update_layout(
            template='plotly_dark',
            margin=dict(l=0, r=0, t=20, b=0),
            mapbox_style='open-street-map',
            legend_title_text='Regioes',
            legend=dict(font=dict(size=13)),
        )
        st.plotly_chart(fig_map, use_container_width=True)

with tab4:
    st.subheader('Tipos de veiculos envolvidos em acidentes')
    top_veic = (
        veh_f.groupby('descricao_especie', as_index=False)
        .size()
        .rename(columns={'size': 'qtd'})
        .sort_values('qtd', ascending=False)
        .head(12)
    )
    fig_veic = px.bar(top_veic, x='qtd', y='descricao_especie', orientation='h', template='plotly_dark', color='qtd', color_continuous_scale='Turbo')
    st.plotly_chart(fig_veic, use_container_width=True)

    st.subheader('Severidade dos Acidentes (Visão Qualitativa)')
    sev = env_f.groupby('desc_severidade', as_index=False).size().rename(columns={'size': 'qtd'})
    fig_sev = px.bar(sev, x='desc_severidade', y='qtd', template='plotly_dark', color='qtd', color_continuous_scale='Sunset')
    st.plotly_chart(fig_sev, use_container_width=True)

with tab5:
    st.subheader('Previsao de acidentes para os proximos meses')

    if Prophet is None:
        st.warning('Biblioteca Prophet nao disponivel. Instale com: pip install prophet')
    elif 'data' not in acc_f.columns or acc_f['data'].isna().all():
        st.warning('Sem dados de data para gerar previsao.')
    else:
        horizon = st.slider('Meses para prever', min_value=3, max_value=12, value=6, step=1)
        with st.expander('Como ler a previsao'):
            st.markdown(
                """
                - A previsao usa dados mensais do recorte atual e estima os proximos meses.
                - A linha azul mostra o historico observado (acidentes reais).
                - As barras laranjas representam o valor previsto.
                - As linhas claras indicam o intervalo de incerteza da previsao.
                - O Prophet ajusta tendência e sazonalidade anual a partir do histórico mensal para projetar os próximos meses.
                - Esse indicativo é exploratório; mudanças de política, clima ou frota podem alterar o padrão.
                """
            )

        monthly = (
            acc_f.assign(_mes=acc_f['data'].dt.to_period('M'))
            .groupby('_mes', as_index=False)['boletim']
            .nunique()
            .rename(columns={'boletim': 'acidentes'})
            .sort_values('_mes')
        )

        monthly['mes'] = monthly['_mes'].dt.to_timestamp()
        monthly = monthly[['mes', 'acidentes']].reset_index(drop=True)

        if len(monthly) < 6:
            st.warning('Base historica pequena para previsao. Recomenda-se pelo menos 6 meses.')
        else:
            prophet_df = monthly.rename(columns={'mes': 'ds', 'acidentes': 'y'})

            # Backtest simples: treina no historico e valida nos ultimos meses.
            test_periods = 6 if len(prophet_df) >= 18 else 3
            if len(prophet_df) > (test_periods + 6):
                train_df = prophet_df.iloc[:-test_periods].copy()
                test_df = prophet_df.iloc[-test_periods:].copy()

                bt_model = Prophet(
                    yearly_seasonality=True,
                    weekly_seasonality=False,
                    daily_seasonality=False,
                    interval_width=0.8,
                )
                bt_model.fit(train_df)
                bt_future = bt_model.make_future_dataframe(periods=test_periods, freq='MS')
                bt_forecast = bt_model.predict(bt_future)
                bt_pred = bt_forecast[['ds', 'yhat']].tail(test_periods)
                bt_eval = test_df.merge(bt_pred, on='ds', how='left')

                mae = (bt_eval['y'] - bt_eval['yhat']).abs().mean()
                denom = bt_eval['y'].replace(0, np.nan)
                mape = ((bt_eval['y'] - bt_eval['yhat']).abs() / denom).mean() * 100

                c1, c2 = st.columns(2)
                c1.metric('Backtest MAE', f'{mae:,.1f}'.replace(',', '.'))
                c2.metric('Backtest MAPE', '-' if np.isnan(mape) else f'{mape:.1f}%')
                st.caption(f'Backtest: treino ate {train_df["ds"].max():%m/%Y} e teste nos ultimos {test_periods} meses.')

                bt_plot = bt_eval.rename(columns={'ds': 'mes', 'y': 'Real', 'yhat': 'Previsto'})
                bt_long = bt_plot.melt(id_vars='mes', value_vars=['Real', 'Previsto'], var_name='Serie', value_name='Acidentes')
                fig_bt = px.line(
                    bt_long,
                    x='mes',
                    y='Acidentes',
                    color='Serie',
                    template='plotly_dark',
                    color_discrete_map={'Real': '#38bdf8', 'Previsto': '#f97316'},
                )
                fig_bt.update_layout(
                    xaxis_title='Mes',
                    yaxis_title='Acidentes (boletins unicos)',
                    hovermode='x unified',
                    legend_title_text='',
                    height=280,
                    margin=dict(l=10, r=10, t=10, b=10),
                )
                st.plotly_chart(fig_bt, use_container_width=True)

            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False,
                interval_width=0.8,
            )
            model.fit(prophet_df)

            future = model.make_future_dataframe(periods=horizon, freq='MS')
            forecast = model.predict(future)

            hist = prophet_df.copy()
            hist['tipo'] = 'Historico'
            pred = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
            pred = pred.rename(columns={'ds': 'mes', 'yhat': 'acidentes'})
            pred['tipo'] = 'Previsao'

            fig_fore = px.line(
                hist.rename(columns={'ds': 'mes', 'y': 'acidentes'}),
                x='mes',
                y='acidentes',
                template='plotly_dark',
                color_discrete_sequence=['#38bdf8'],
            )
            fig_fore.add_bar(
                x=pred['mes'],
                y=pred['acidentes'],
                name='Previsao',
                marker_color='#f97316',
                opacity=0.55,
            )
            fig_fore.add_scatter(
                x=pred['mes'],
                y=pred['yhat_upper'],
                mode='lines',
                name='Intervalo superior',
                line=dict(color='rgba(249,115,22,.35)', width=1),
            )
            fig_fore.add_scatter(
                x=pred['mes'],
                y=pred['yhat_lower'],
                mode='lines',
                name='Intervalo inferior',
                line=dict(color='rgba(249,115,22,.35)', width=1),
                fill='tonexty',
                fillcolor='rgba(249,115,22,.12)',
            )
            fig_fore.update_layout(
                xaxis_title='Mes',
                yaxis_title='Acidentes (boletins unicos)',
                hovermode='x unified',
                legend_title_text='',
            )
            st.plotly_chart(fig_fore, use_container_width=True)

            st.info('Previsão gerada com Prophet (tendência e sazonalidade anual). Esse indicativo é exploratório.')

st.caption('Projeto academico de visualizacao de dados - Acidentes de transito em Belo Horizonte.')
