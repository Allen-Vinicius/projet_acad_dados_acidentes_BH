# Projeto Acadêmico - Acidentes de BH

Dashboard em Streamlit para análise de acidentes de trânsito em Belo Horizonte, com filtros interativos, visualizações em Plotly e previsão com Prophet.

## Estrutura principal

- `dashboard_app.py`: aplicação Streamlit.
- `acidentes_bh_dashboard.csv`: base consolidada para o painel.
- `Dados_de_Acidentes_de_Transito_em_BH.xlsx`: abas complementares de envolvidos e veículos.
- `requirements.txt`: dependências para deploy.

## Executar localmente

```powershell
pip install -r requirements.txt
streamlit run dashboard_app.py
```

## Deploy no Streamlit Community Cloud

1. Suba este projeto para um repositório no GitHub.
2. Acesse `https://share.streamlit.io/`.
3. Clique em `Create app`.
4. Selecione o repositório, branch e o arquivo de entrada `dashboard_app.py`.
5. Em `Advanced settings`, mantenha Python `3.12` ou escolha outra versão suportada, se necessário.
6. Conclua o deploy e aguarde a instalação das dependências listadas em `requirements.txt`.

## Observações

- O app lê os arquivos de dados com caminho relativo ao próprio projeto, o que ajuda no deploy em nuvem.
- A aba de previsão depende da biblioteca `prophet`. Se essa dependência falhar na instalação, o restante do dashboard continua funcionando, mas a previsão ficará indisponível.
