import re
import unicodedata
import pandas as pd

ARQ_ENTRADA = 'Dados_de_Acidentes_de_Transito_em_BH.xlsx'
ARQ_SAIDA = 'acidentes_bh_consolidado.csv'


def norm_col(name: str) -> str:
    name = str(name).strip().lower()
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^a-z0-9]+', '_', name).strip('_')
    return name


def to_bool_num(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.lower()
    mapa = {
        '1': 1, '0': 0,
        's': 1, 'n': 0,
        'sim': 1, 'nao': 0, 'não': 0,
        'true': 1, 'false': 0,
        'y': 1, 'yes': 1, 'no': 0,
    }
    out = s.map(mapa)
    return out.fillna(0)


def normalize_flags(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {'NÃO': 'N', 'SIM': 'S', 'NÃO INFORMADO': '0'}
    obj_cols = df.select_dtypes(include=['object']).columns
    for c in obj_cols:
        s = df[c]
        mask = s.isna()
        s = s.astype(str).str.strip()
        s = s.replace(mapping)
        s = s.mask(mask)
        df[c] = s
    return df

def ensure_boletim_col(df: pd.DataFrame) -> pd.DataFrame:
    candidates = ['boletim', 'numero_boletim', 'num_boletim', 'numero_bol', 'n_boletim', 'no_boletim']
    for c in candidates:
        if c in df.columns:
            return df.rename(columns={c: 'boletim'})
    for c in df.columns:
        if 'boletim' in c:
            return df.rename(columns={c: 'boletim'})
    return df.rename(columns={df.columns[0]: 'boletim'})


boletins = pd.read_excel(ARQ_ENTRADA, sheet_name='boletins')
envolvidos = pd.read_excel(ARQ_ENTRADA, sheet_name='envolvidos')
veiculos = pd.read_excel(ARQ_ENTRADA, sheet_name='veiculos')
logradouros = pd.read_excel(ARQ_ENTRADA, sheet_name='logradouros')
coordenadas = pd.read_excel(ARQ_ENTRADA, sheet_name='coordenadas')

for df in [boletins, envolvidos, veiculos, logradouros, coordenadas]:
    df.columns = [norm_col(c) for c in df.columns]

boletins = ensure_boletim_col(boletins)
envolvidos = ensure_boletim_col(envolvidos)
veiculos = ensure_boletim_col(veiculos)
logradouros = ensure_boletim_col(logradouros)
coordenadas = ensure_boletim_col(coordenadas)

# Base por acidente (1 linha por boletim)
base = boletins.copy()

# Agregacoes de envolvidos por boletim
if 'desc_severidade' in envolvidos.columns:
    severidade = envolvidos['desc_severidade'].astype(str).str.strip().str.upper()
    envolvidos['flag_fatal'] = severidade.eq('FATAL').astype(int)
else:
    envolvidos['flag_fatal'] = 0

if 'numero_envolvido' in envolvidos.columns:
    envolvidos['numero_envolvido'] = pd.to_numeric(envolvidos['numero_envolvido'], errors='coerce')
    envolvidos['fatal_numero_envolvido'] = envolvidos['numero_envolvido'].where(envolvidos['flag_fatal'].eq(1), 0).fillna(0)
else:
    envolvidos['fatal_numero_envolvido'] = envolvidos['flag_fatal']

if 'idade' in envolvidos.columns:
    envolvidos['idade'] = pd.to_numeric(envolvidos['idade'], errors='coerce')

agg_map = {
    'total_envolvidos': ('boletim', 'size'),
    'total_fatais': ('fatal_numero_envolvido', 'sum'),
}
if 'idade' in envolvidos.columns:
    agg_map['idade_media_envolvidos'] = ('idade', 'mean')

agg_env = envolvidos.groupby('boletim', as_index=False).agg(**agg_map)

for col, new_col in [
    ('condutor', 'total_condutores'),
    ('pedestre', 'total_pedestres'),
    ('passageiro', 'total_passageiros'),
    ('embreagues', 'total_embriaguez')
]:
    if col in envolvidos.columns:
        env_flag = envolvidos[['boletim', col]].copy()
        env_flag[col] = to_bool_num(env_flag[col])
        agg_col = env_flag.groupby('boletim', as_index=False)[col].sum().rename(columns={col: new_col})
        agg_env = agg_env.merge(agg_col, on='boletim', how='left')

# Agregacoes de veiculos por boletim
agg_vei = veiculos.groupby('boletim', as_index=False).agg(total_veiculos=('boletim', 'size'))

# Logradouro principal por boletim (primeira ocorrencia)
if 'seq_logradouros' in logradouros.columns:
    logradouros['seq_logradouros'] = pd.to_numeric(logradouros['seq_logradouros'], errors='coerce')
    logradouros = logradouros.sort_values(['boletim', 'seq_logradouros'])
else:
    logradouros = logradouros.sort_values(['boletim'])

cols_log = [c for c in ['nome_municipio', 'tipo_logradouro', 'nome_logradouro', 'bairro'] if c in logradouros.columns]
log_principal = logradouros.groupby('boletim', as_index=False)[cols_log].first() if cols_log else logradouros[['boletim']].drop_duplicates()

# Coordenada principal por boletim
cols_coord = [c for c in ['longitude', 'latitude'] if c in coordenadas.columns]
coord = coordenadas.groupby('boletim', as_index=False)[cols_coord].first() if cols_coord else coordenadas[['boletim']].drop_duplicates()

# Merge final
final = (
    base
    .merge(agg_env, on='boletim', how='left')
    .merge(agg_vei, on='boletim', how='left')
    .merge(log_principal, on='boletim', how='left')
    .merge(coord, on='boletim', how='left')
)

# Ajustes finais
for c in ['total_envolvidos', 'total_fatais', 'total_condutores', 'total_pedestres', 'total_passageiros', 'total_embriaguez', 'total_veiculos']:
    if c in final.columns:
        final[c] = final[c].fillna(0)

if 'idade_media_envolvidos' in final.columns:
    final['idade_media_envolvidos'] = final['idade_media_envolvidos'].round(1)

final = normalize_flags(final)
final.to_csv(ARQ_SAIDA, index=False, encoding='utf-8-sig')

print(f'Arquivo gerado: {ARQ_SAIDA}')
print(f'Dimensoes: {final.shape[0]} linhas x {final.shape[1]} colunas')
print('Colunas:')
print(', '.join(final.columns))
