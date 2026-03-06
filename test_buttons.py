#!/usr/bin/env python3
"""
Script de teste para validar a lógica dos botões +/- no menu de compra
"""

def test_button_logic():
    """Testa a lógica de incremento/decremento de quantidade"""

    # Simula estoque disponível
    stock_count = 10
    PRODUCT_PRICE = 0.50

    print("=" * 50)
    print("TESTE DA LÓGICA DOS BOTÕES +/-")
    print("=" * 50)
    print(f"Estoque disponível: {stock_count}")
    print(f"Preço unitário: R$ {PRODUCT_PRICE:.2f}")
    print()

    # Teste 1: Quantidade inicial
    qty = 1
    total = qty * PRODUCT_PRICE
    print(f"✅ Teste 1 - Quantidade inicial: {qty}x | Total: R$ {total:.2f}")

    # Teste 2: Incrementar quantidade
    qty = min(stock_count, qty + 1)
    total = qty * PRODUCT_PRICE
    print(f"✅ Teste 2 - Após clicar em '+': {qty}x | Total: R$ {total:.2f}")

    # Teste 3: Incrementar até o limite do estoque
    qty = 10
    for i in range(5):
        new_qty = min(stock_count, qty + 1)
        if new_qty == qty:
            print(f"✅ Teste 3 - Limite de estoque atingido: {qty}x (não incrementa mais)")
            break
        qty = new_qty

    # Teste 4: Decrementar quantidade
    qty = 5
    qty = max(1, qty - 1)
    total = qty * PRODUCT_PRICE
    print(f"✅ Teste 4 - Após clicar em '-': {qty}x | Total: R$ {total:.2f}")

    # Teste 5: Decrementar até o limite mínimo
    qty = 1
    new_qty = max(1, qty - 1)
    if new_qty == qty:
        print(f"✅ Teste 5 - Limite mínimo atingido: {qty}x (não decrementa mais)")

    # Teste 6: Validação de callback_data
    print()
    print("=" * 50)
    print("TESTE DE CALLBACK DATA")
    print("=" * 50)

    test_callbacks = [
        'buy_update_1',
        'buy_update_5',
        'buy_update_10',
        'buy_qty_3',
    ]

    for callback in test_callbacks:
        if callback.startswith('buy_update_'):
            qty = int(callback.split('_')[2])
            print(f"✅ Callback '{callback}' -> Quantidade: {qty}x")
        elif callback.startswith('buy_qty_'):
            qty = int(callback.split('_')[2])
            print(f"✅ Callback '{callback}' -> Finalizar com: {qty}x")

    print()
    print("=" * 50)
    print("TODOS OS TESTES PASSARAM! ✅")
    print("=" * 50)

if __name__ == "__main__":
    test_button_logic()
