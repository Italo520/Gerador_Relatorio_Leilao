# Formatação Automática de Moeda no Campo de Avaliação

## Como Usar

Ao preencher o campo de **Avaliação** na tabela de lotes, você pode digitar apenas números, e o sistema aplicará automaticamente a formatação de moeda brasileira.

### Exemplos de Uso:

| Você digita | Sistema formata para |
|-------------|---------------------|
| `1234567` | `12.345,67` |
| `100000` | `1.000,00` |
| `50` | `0,50` |
| `12345` | `123,45` |
| `1000000` | `10.000,00` |

## Comportamento do Sistema

✅ **Aceita apenas números**: O sistema remove automaticamente qualquer caractere que não seja número

✅ **Duas casas decimais**: Sempre mantém 2 casas após a vírgula (centavos)

✅ **Separação de milhares**: Usa ponto (.) para separar milhares

✅ **Formatação em tempo real**: A formatação é aplicada automaticamente enquanto você digita

## Exemplos Práticos

### Exemplo 1: Avaliação de R$ 1.500,00
- Digite: `150000`
- Resultado: `1.500,00`

### Exemplo 2: Avaliação de R$ 25.000,00
- Digite: `2500000`
- Resultado: `25.000,00`

### Exemplo 3: Avaliação de R$ 350,50
- Digite: `35050`
- Resultado: `350,50`

## Notas Importantes

- Os últimos 2 dígitos sempre representam os centavos
- Não é necessário digitar vírgulas, pontos ou o símbolo R$
- A formatação ocorre automaticamente ao sair do campo (evento `on_change`)
- O valor formatado é salvo e será usado no relatório gerado
