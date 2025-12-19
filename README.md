# Sistema Gerador de Relatórios de Leilão

Este sistema permite visualizar os dados extraídos do site de leilões e gerar relatórios em HTML formatados.

## Pré-requisitos

1. Python instalado.
2. Dependências instaladas:
   ```bash
   pip install -r requirements.txt
   ```
3. Navegadores do Playwright instalados (para o scraper):
   ```bash
   playwright install chromium
   ```

## Como Usar

1. Execute o sistema:
   ```bash
   python sistema_leiloes.py
   ```

2. **Na interface:**
   - Clique em **"Atualizar Dados"** para rodar o scraper e buscar os leilões mais recentes.
   - Selecione um leilão na lista lateral.
   - Visualize os lotes na tabela central.
   - Clique em **"Gerar Relatório HTML"** para criar o arquivo do relatório.
   - O arquivo HTML será salvo na mesma pasta e aberto automaticamente.

## Arquivos do Projeto

- `sistema_leiloes.py`: O aplicativo desktop (interface gráfica).
- `scraper.py`: O script que baixa os dados do site.
- `Relatório Leilões.html`: O modelo (template) usado para gerar os relatórios.
- `leiloes_completo.json`: O banco de dados local (gerado pelo scraper).
