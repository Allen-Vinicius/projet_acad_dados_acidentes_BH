import numpy as np
import pandas as pd

ARQ_ENTRADA = "acidentes_bh_consolidado.csv"
ARQ_SAIDA = "acidentes_bh_dashboard.csv"


def limpar_texto(df: pd.DataFrame) -> pd.DataFrame:
    obj_cols = df.select_dtypes(include=["object"]).columns
    for c in obj_cols:
        df[c] = df[c].astype(str).str.strip()
        df[c] = df[c].replace({"nan": np.nan, "None": np.nan, "": np.nan})
    return df


def validar_coordenadas(df: pd.DataFrame) -> pd.DataFrame:
    for c in ["latitude", "longitude"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "latitude" in df.columns:
        df.loc[~df["latitude"].between(-21.0, -18.0), "latitude"] = np.nan
    if "longitude" in df.columns:
        df.loc[~df["longitude"].between(-46.0, -42.0), "longitude"] = np.nan
    return df


def normalize_flags(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {"NÃO": "N", "SIM": "S", "NÃO INFORMADO": "0"}
    obj_cols = df.select_dtypes(include=["object"]).columns
    for c in obj_cols:
        s = df[c]
        mask = s.isna()
        s = s.astype(str).str.strip()
        s = s.replace(mapping)
        s = s.mask(mask)
        df[c] = s
    return df


df = pd.read_csv(ARQ_ENTRADA, encoding="utf-8-sig", low_memory=False)
df = limpar_texto(df)
df = validar_coordenadas(df)
df = normalize_flags(df)

# Tipos numéricos usados no dashboard
num_cols = [
    "velocidade_permitida",
    "valor_ups",
    "faixa_hora_num",
    "mes",
    "ano",
    "dia",
    "total_envolvidos",
    "total_fatais",
    "idade_media_envolvidos",
    "total_condutores",
    "total_pedestres",
    "total_passageiros",
    "total_embriaguez",
    "total_veiculos",
]
for c in num_cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

# Data/hora e colunas derivadas para análises temporais
if "data" in df.columns:
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
if "hora" in df.columns:
    df["hora"] = pd.to_datetime(df["hora"], format="%H:%M:%S", errors="coerce").dt.time

if "data" in df.columns:
    hora_str = df["hora"].astype(str) if "hora" in df.columns else "00:00:00"
    df["data_hora"] = pd.to_datetime(
        df["data"].dt.strftime("%Y-%m-%d") + " " + hora_str, errors="coerce"
    )
    df["ano_mes"] = df["data"].dt.to_period("M").astype(str)
    dias = {
        0: "Segunda",
        1: "Terca",
        2: "Quarta",
        3: "Quinta",
        4: "Sexta",
        5: "Sabado",
        6: "Domingo",
    }
    meses = {
        1: "Janeiro",
        2: "Fevereiro",
        3: "Marco",
        4: "Abril",
        5: "Maio",
        6: "Junho",
        7: "Julho",
        8: "Agosto",
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }
    df["dia_semana"] = df["data"].dt.dayofweek.map(dias)
    df["mes_nome"] = df["data"].dt.month.map(meses)

# Indicadores de qualidade para mapa
df["tem_coordenada"] = (~df["latitude"].isna() & ~df["longitude"].isna()).astype(int)
df["tem_bairro"] = df["bairro"].notna().astype(int) if "bairro" in df.columns else 0

# Mantém apenas registros de BH quando o campo existir preenchido
if "nome_municipio" in df.columns:
    filtro_bh = df["nome_municipio"].isna() | (df["nome_municipio"].str.upper() == "BELO HORIZONTE")
    df = df.loc[filtro_bh].copy()

df.to_csv(ARQ_SAIDA, index=False, encoding="utf-8-sig")

print(f"Arquivo gerado: {ARQ_SAIDA}")
print(f"Dimensoes: {df.shape[0]} linhas x {df.shape[1]} colunas")
