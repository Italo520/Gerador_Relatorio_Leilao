# Guia de Compartilhamento do Sistema

Este documento explica as duas principais formas de compartilhar o **Gerador de Relatórios de Leilão**: enviando o código-fonte ou criando um arquivo executável (.exe).

## Opção 1: Compartilhar o Código Fonte (Recomendado)

Esta é a forma mais segura e garantida de que o sistema funcionará em outro computador, pois instala todas as dependências do zero.

### Passo 1: Preparar os arquivos
Antes de enviar, certifique-se de que você tem os seguintes arquivos na pasta:
- `sistema_leiloes.py`
- `scraper.py`
- `requirements.txt`
- `Relatório Leilões.html`
- `logo_leiloespb` (arquivo de imagem)
- `instalar_dependencias.bat`
- `iniciar_sistema.bat`

**O que NÃO enviar:**
- Pastas `__pycache__`, `build`, `dist`.
- Arquivo `leiloes_completo.json` (a menos que queira enviar os dados já baixados).
- Pasta `.git` (se houver).

### Passo 2: Enviar para a outra pessoa
1. Compacte (Zip) a pasta do projeto com os arquivos listados acima.
2. Envie o arquivo `.zip` para a pessoa.

### Passo 3: Instruções para quem recebe
A pessoa que receber o sistema precisará seguir estes passos:

1. **Instalar o Python**: Baixar e instalar o Python (versão 3.8 ou superior) do site oficial [python.org](https://www.python.org/). **Importante:** Marcar a opção "Add Python to PATH" durante a instalação.
2. **Abrir o terminal**: Abrir o CMD ou PowerShell na pasta do projeto descompactado.
3. **Instalar as dependências**:
   - Basta clicar duas vezes no arquivo `instalar_dependencias.bat`.
   - Ou rodar manualmente:
     ```bash
     pip install -r requirements.txt
     playwright install chromium
     ```

4. **Rodar o sistema**:
   - Clique duas vezes em `iniciar_sistema.bat`.
   - Ou rode manualmente:
     ```bash
     python sistema_leiloes.py
     ```

---

## Opção 2: Gerar um Executável (.exe)

Esta opção cria um arquivo único que pode ser clicado para abrir, sem precisar instalar Python explicitamente. **Porém**, como o sistema usa o **Playwright** (robô de navegação), há um detalhe importante sobre os navegadores.

### Passo 1: Gerar o Executável
Você já possui o arquivo de configuração `GeradorRelatorioLeilao.spec`. Para gerar o executável atualizado:

1. Abra o terminal na pasta do projeto.
2. Execute o comando:
   ```bash
   pyinstaller GeradorRelatorioLeilao.spec
   ```
3. Aguarde o processo terminar.

### Passo 2: Localizar o Arquivo
O arquivo executável será criado na pasta `dist`:
- `dist/GeradorRelatorioLeilao.exe`

### Passo 3: Compartilhar
Você pode enviar apenas esse arquivo `.exe` para a pessoa.

### ⚠️ Atenção Importante sobre o Playwright
O executável contém o código do sistema, mas **NÃO contém os navegadores** (Chromium) que o robô usa.

Se a pessoa que receber o arquivo **nunca tiver usado Playwright** no computador dela, o sistema pode dar erro ao tentar "Atualizar Dados".

**Solução para o usuário final:**
Se o robô não funcionar, a pessoa precisará instalar os navegadores separadamente. Como ela não tem Python instalado (no cenário de usar apenas o .exe), isso pode ser complicado.

**Recomendação:**
Para uso profissional ou distribuição para leigos, a **Opção 1** é mais robusta pois garante que todo o ambiente (Python + Dependências + Navegadores) seja configurado corretamente.

Se precisar distribuir o .exe, certifique-se de que a máquina de destino já tenha os navegadores do Playwright instalados ou instrua o usuário a instalar.
