# Sistema Gerador de Relatórios de Leilão

Este sistema permite visualizar os dados extraídos do site de leilões e gerar relatórios em HTML formatados.

## Instalação

1. Certifique-se de ter o **Python** instalado no seu computador.
2. Execute o arquivo de instalação (clique duplo):
   ```
   instalar_dependencias.bat
   ```
   *Isso irá instalar todas as bibliotecas necessárias e os navegadores do Playwright.*

## Como Usar

1. Para abrir o programa, execute o arquivo (clique duplo):
   ```
   iniciar_sistema.bat
   ```

2. **Na interface:**
   - Clique em **"Atualizar Dados"** para rodar o scraper e buscar os leilões mais recentes.
   - Selecione um leilão na lista lateral.
   - Visualize os lotes na tabela central.
   - Clique em **"Gerar Relatório HTML"** para criar o arquivo do relatório.
   - O arquivo HTML será salvo na mesma pasta e aberto automaticamente.

## Arquivos do Projeto

- `iniciar_sistema.bat`: Atalho para iniciar o programa facilmente.
- `instalar_dependencias.bat`: Script para instalar tudo o que é necessário.
- `sistema_leiloes.py`: O aplicativo desktop (interface gráfica).
- `scraper.py`: O script que baixa os dados do site.
- `Relatório Leilões.html`: O modelo (template) usado para gerar os relatórios.
- `leiloes_completo.json`: O banco de dados local (gerado pelo scraper).
