#!/bin/bash

# Script de instalação automatizada para o Bot de Vendas no Termux

echo "Iniciando a instalação do Bot de Vendas no Termux..."

# 1. Atualizar pacotes
echo "Atualizando pacotes..."
pkg update && pkg upgrade -y

# 2. Instalar Python e outras ferramentas necessárias
echo "Instalando Python e dependências do sistema..."
pkg install python git nano unzip -y

# 3. Instalar dependências do Python
echo "Instalando dependências do bot..."
# Instalando individualmente para garantir que o erro do Mercado Pago seja resolvido
pip install python-telegram-bot==21.10
pip install mercadopago
pip install python-dotenv

# 4. Configurar diretórios
echo "Garantindo que os diretórios necessários existam..."
mkdir -p storage/accounts
mkdir -p storage/sold
mkdir -p database

echo "Instalação concluída com sucesso!"
echo "--------------------------------------------------"
echo "Próximos passos:"
echo "1. Configure seu token no arquivo .env (use: nano .env)"
echo "2. Coloque seus arquivos .zip em storage/accounts/"
echo "3. Execute o bot com: python bot.py"
echo "4. No bot, use /settoken <seu_token_mp> para ativar o Mercado Pago"
echo "--------------------------------------------------"
