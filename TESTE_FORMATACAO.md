# Teste da Formatação Automática de Moeda

## Como Testar

1. Execute o sistema: `iniciar_sistema.bat`
2. Selecione um leilão da lista lateral
3. Localize a coluna "Avaliação" na tabela de lotes
4. Clique em um campo de avaliação e teste os exemplos abaixo

## Casos de Teste

### ✅ Teste 1: Valor simples (R$ 1.500,00)
**Digite:** `150000`
**Resultado esperado:** `1.500,00`

### ✅ Teste 2: Valor com milhares (R$ 25.000,00)
**Digite:** `2500000`
**Resultado esperado:** `25.000,00`

### ✅ Teste 3: Valor pequeno (R$ 0,50)
**Digite:** `50`
**Resultado esperado:** `0,50`

### ✅ Teste 4: Valor com centavos (R$ 350,75)
**Digite:** `35075`
**Resultado esperado:** `350,75`

### ✅ Teste 5: Valor grande (R$ 1.234.567,89)
**Digite:** `123456789`
**Resultado esperado:** `1.234.567,89`

### ✅ Teste 6: Apenas caracteres não numéricos
**Digite:** `abc123def`
**Resultado esperado:** `1,23` (remove letras, mantém apenas números)

### ✅ Teste 7: Mistura de números e símbolos
**Digite:** `R$ 1.500,00`
**Resultado esperado:** `150000,00` (remove tudo exceto números)

## Comportamento Esperado

1. **Ao digitar:** O campo aceita qualquer caractere
2. **Ao sair do campo (blur):** A formatação é aplicada automaticamente
3. **Formato final:** Sempre `X.XXX.XXX,XX` com duas casas decimais

## Verificação no Relatório

Depois de preencher as avaliações:
1. Clique em "Gerar Relatório HTML"
2. Verifique se os valores aparecem corretamente formatados no relatório
3. Os valores devem estar na coluna "Avaliação" de cada lote

## Observações

- A formatação acontece em tempo real ao alterar o valor
- Os valores são salvos já formatados
- Não é necessário digitar vírgulas ou pontos
- Os últimos 2 dígitos sempre representam os centavos
