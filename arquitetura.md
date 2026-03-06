# Arquitetura do Bot de Vendas de Contas Guest

Este documento descreve a estrutura técnica e o fluxo de funcionamento do bot para Telegram.

## Tecnologias Utilizadas
- **Linguagem:** Python 3.11
- **Biblioteca do Telegram:** `python-telegram-bot` (assíncrona)
- **Banco de Dados:** SQLite (para persistência de estoque e transações)
- **Pagamento:** Integração simulada via PIX (extensível para gateways reais como Mercado Pago)

## Estrutura de Pastas
```
telegram_bot_vendas/
├── bot.py                # Ponto de entrada do bot
├── database/
│   ├── db_manager.py     # Gerenciamento do SQLite
│   └── schema.sql        # Definição das tabelas
├── modules/
│   ├── inventory.py      # Lógica de estoque (arquivos .zip)
│   ├── payments.py       # Lógica de processamento de pagamentos
│   └── handlers.py       # Manipuladores de comandos do Telegram
├── storage/
│   └── accounts/         # Pasta onde os arquivos .zip serão armazenados
├── config.py             # Configurações (Tokens, Preços)
└── requirements.txt      # Dependências do projeto
```

## Fluxo de Venda
1. **Usuário** inicia o bot e vê o catálogo.
2. **Usuário** seleciona "Comprar Conta Guest Lvl 15".
3. **Bot** verifica se há estoque disponível no banco de dados.
4. **Bot** gera uma solicitação de pagamento (PIX).
5. **Sistema** confirma o pagamento (simulado ou via webhook).
6. **Bot** seleciona o próximo arquivo `.zip` disponível no estoque.
7. **Bot** envia o arquivo ao usuário e marca a conta como vendida no banco de dados.
