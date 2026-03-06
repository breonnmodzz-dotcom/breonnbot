# 💎 BREONN STORE ELITE - Bot de Vendas Automáticas 💎

Este projeto é um bot avançado para Telegram focado na venda automática de produtos digitais (contas, arquivos, etc.), com entrega instantânea e sistema de pagamento automatizado via Mercado Pago.

## 🚀 Novas Funcionalidades (v2.2 FIX)

- **Pagamento Automatizado (PIX)**: Integração real com Mercado Pago para geração de PIX Copia e Cola.
- **Confirmação em Tempo Real**: Botão para verificar o status do pagamento e creditar saldo automaticamente.
- **Sistema de Saldo**: Usuários podem adicionar saldo à conta e usar para compras futuras.
- **Painel Administrativo**: Comandos para gerenciar usuários, banir, adicionar saldo manual e configurar o bot.
- **Configuração Dinâmica**: Configure seu Access Token do Mercado Pago diretamente pelo bot com `/settoken`.
- **Entrega Instantânea**: Envio automático do arquivo após a confirmação do pagamento ou uso do saldo.

## 🛠️ Como Configurar e Executar

### Pré-requisitos

- Python 3.9+ ou Termux (Android)
- Token do Bot no Telegram ([@BotFather](https://t.me/BotFather))
- Access Token do Mercado Pago (obtido no painel de desenvolvedor do MP)

### Passos para Instalação (PC/Linux)

1. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure o Token do Telegram:**
   Edite o arquivo `config.py` ou crie um arquivo `.env` com seu `TELEGRAM_TOKEN`.

3. **Execute o bot:**
   ```bash
   python bot.py
   ```

### Passos para Instalação (Termux - Android)

1. **Execute o script de instalação:**
   ```bash
   bash install_termux.sh
   ```

2. **Inicie o bot:**
   ```bash
   python bot.py
   ```

## 🔑 Configurando o Mercado Pago

Após iniciar o bot, você deve configurar seu token para que os pagamentos funcionem:

1. Vá ao chat do seu bot.
2. Use o comando: `/settoken SEU_ACCESS_TOKEN_DO_MERCADO_PAGO`
3. O bot confirmará a atualização e o sistema de saldo estará ativo!

## 📂 Estrutura do Projeto

- `bot.py`: Ponto de entrada principal.
- `config.py`: Configurações globais e variáveis.
- `modules/handlers.py`: Lógica de comandos, botões e pagamentos.
- `database/db_manager.py`: Gerenciamento do banco de dados SQLite.
- `storage/accounts/`: Pasta onde você deve colocar os arquivos `.zip` para venda.

## 🛡️ Comandos Administrativos

- `/settoken <token>`: Configura o Mercado Pago.
- `/addsaldo <@user> <valor>`: Adiciona saldo manualmente a um usuário.
- `/confirmar <@user> <valor>`: Confirma um pagamento manual com bônus de evento.
- `/banir <@user>`: Bane um usuário da loja.
- `/evento <multiplicador>`: Ativa bônus de recarga (ex: 1.5 para 50% de bônus).
- `/stats`: Mostra estatísticas de vendas e lucro.
