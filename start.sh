#!/bin/bash

# Script de inicialização para o Bot de Vendas no Termux

echo "--------------------------------------------------"
echo "💎 BREONN STORE  - Iniciando..."
echo "--------------------------------------------------"

# Verifica se as dependências estão instaladas
if ! python3 -c "import mercadopago" &> /dev/null; then
    echo "⚠️ Dependências faltando. Rodando instalador..."
    bash install_termux.sh
fi

# Loop para manter o bot rodando mesmo se cair
while true; do
    echo "🚀 Iniciando o bot..."
    python3 bot.py
    echo "⚠️ Bot caiu ou foi parado. Reiniciando em 3 segundos..."
    sleep 3
done
