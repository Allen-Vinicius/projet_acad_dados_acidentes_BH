# Dashboard Acidentes BH

## Executar no navegador (PowerShell)

```powershell
./start_dashboard_browser.ps1
```

- O script sobe o Streamlit em `127.0.0.1`.
- Se a porta `8501` estiver ocupada, ele usa a proxima livre (`8502`, `8503`, ...).
- O navegador abre automaticamente quando o servidor estiver pronto.
- Logs ficam em `streamlit_stdout.log` e `streamlit_stderr.log`.
- Mantenha o terminal aberto enquanto usa o dashboard.

## Erro `Connection timed out`

Esse erro normalmente ocorre quando o servidor nao ficou ativo. Use este fluxo:

1. Execute `./start_dashboard_browser.ps1`.
2. Copie a URL exibida no terminal (ex.: `http://127.0.0.1:8502`).
3. Abra com:

```powershell
Start-Process "http://127.0.0.1:8502"
```

4. Se ainda falhar, feche processos antigos de Streamlit/Python e execute de novo:

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process
```

## Streamlit nao encontrado

Se aparecer erro de Streamlit ausente, instale com:

```powershell
pip install streamlit
```

## Execucao manual (alternativa)

```powershell
python -m streamlit run dashboard_app.py --server.address 127.0.0.1 --server.port 8501
```
