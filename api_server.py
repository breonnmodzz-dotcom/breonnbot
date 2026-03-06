"""
api_server.py — Servidor de API para o Site da Breonn Store
Roda junto com o bot.py, compartilhando o MESMO banco SQLite e pasta de contas.

Como usar: adicione ao final do bot.py (dentro do main()) ou rode em thread separada.
Veja as instruções no final deste arquivo.
"""

import asyncio
import os
import json
import zipfile
import io
import threading
import logging
import hmac
import hashlib
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Importa os mesmos módulos do bot
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    ACCOUNTS_DIR, SOLD_DIR, DB_PATH, MERCADOPAGO_TOKEN,
    ADMIN_ID, STORE_NAME, PRODUCT_NAME
)
from database.db_manager import DatabaseManager
from modules.inventory import InventoryModule

import mercadopago

logger = logging.getLogger(__name__)

# ── CONFIG DA API ────────────────────────────────────────────────────────────
API_PORT = int(os.getenv("API_PORT", 8080))
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "breonn-site-admin-2025")  # ← TROQUE ISSO
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
BASE_URL = os.getenv("BASE_URL", f"http://localhost:{API_PORT}")  # URL pública do servidor

# Instâncias compartilhadas (mesmas do bot)
db = DatabaseManager(DB_PATH)
inventory = InventoryModule()

# ── ARMAZENAMENTO DE PEDIDOS DO SITE ─────────────────────────────────────────
# Salvo em arquivo JSON para não perder entre reinicializações
ORDERS_FILE = os.path.join(os.path.dirname(DB_PATH), "site_orders.json")

def load_orders():
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_orders(orders):
    with open(ORDERS_FILE, "w") as f:
        json.dump(orders, f, indent=2)

# ── HELPERS ──────────────────────────────────────────────────────────────────
def get_product_price():
    from config import PRODUCT_PRICE as DEFAULT_PRICE
    return float(db.get_setting('product_price', DEFAULT_PRICE))

def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, x-admin-token",
        "Content-Type": "application/json",
    }

def send_telegram_message(chat_id, text, parse_mode="Markdown"):
    """Envia mensagem via Telegram Bot API (síncrono)"""
    import urllib.request
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": parse_mode}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem Telegram: {e}")

def send_telegram_document(chat_id, file_bytes, filename, caption=""):
    """Envia arquivo via Telegram Bot API (síncrono)"""
    import urllib.request
    import uuid
    boundary = uuid.uuid4().hex
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
        f"{chat_id}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="caption"\r\n\r\n'
        f"{caption}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    try:
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        logger.error(f"Erro ao enviar arquivo Telegram: {e}")

def deliver_account_to_telegram(chat_id, account_filename):
    """Entrega o arquivo de conta via Telegram"""
    file_path = os.path.join(ACCOUNTS_DIR, account_filename)
    if not os.path.exists(file_path):
        # Pode já ter sido movido para sold
        file_path = os.path.join(SOLD_DIR, account_filename)

    if not os.path.exists(file_path):
        send_telegram_message(chat_id, f"⚠️ Arquivo `{account_filename}` não encontrado. Contate @breonnmodz")
        return

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    send_telegram_document(
        chat_id, file_bytes, account_filename,
        caption=f"🎮 *Sua conta Guest — Breonn Store*\n📁 Arquivo: `{account_filename}`\n\n🦆 Obrigado pela compra!"
    )

# ── HTTP HANDLER ──────────────────────────────────────────────────────────────
class APIHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # silencia logs do HTTPServer

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def get_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def is_admin(self):
        token = self.headers.get("x-admin-token") or parse_qs(urlparse(self.path).query).get("token", [None])[0]
        return token == ADMIN_API_TOKEN

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # ── GET /api/stock ──
        if path == "/api/stock":
            inventory.sync_physical_files()
            count = db.get_available_count()
            price = get_product_price()
            return self.send_json({
                "total": count,
                "price": price,
                "available": count > 0,
                "product": PRODUCT_NAME,
                "store": STORE_NAME,
            })

        # ── GET /api/order/:id ──
        elif path.startswith("/api/order/"):
            order_id = path.split("/api/order/")[1]
            orders = load_orders()
            order = orders.get(order_id)
            if not order:
                return self.send_json({"error": "Pedido não encontrado"}, 404)
            safe = {k: v for k, v in order.items() if k not in ("reserved_ids",)}
            if order.get("status") == "paid":
                safe["accounts_delivered"] = order.get("accounts_delivered", [])
            return self.send_json(safe)

        # ── GET /api/admin/stock ──
        elif path == "/api/admin/stock":
            if not self.is_admin():
                return self.send_json({"error": "Unauthorized"}, 401)
            inventory.sync_physical_files()
            import sqlite3
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, filename, status, added_at FROM inventory ORDER BY id DESC")
                accounts = [{"id": r[0], "filename": r[1], "status": r[2], "added_at": r[3]} for r in cursor.fetchall()]
            return self.send_json({
                "accounts": accounts,
                "summary": {
                    "available": db.get_available_count(),
                    "sold": db.get_sold_count(),
                    "reserved": sum(1 for a in accounts if a["status"] == "reserved"),
                    "total": len(accounts),
                }
            })

        # ── GET /api/admin/orders ──
        elif path == "/api/admin/orders":
            if not self.is_admin():
                return self.send_json({"error": "Unauthorized"}, 401)
            orders = load_orders()
            sorted_orders = sorted(orders.values(), key=lambda o: o.get("created_at", ""), reverse=True)
            safe = [{k: v for k, v in o.items() if k != "reserved_ids"} for o in sorted_orders[:50]]
            return self.send_json(safe)

        else:
            return self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # ── POST /api/payment/create ──
        if path == "/api/payment/create":
            body = self.get_body()
            inventory.sync_physical_files()
            quantity = int(body.get("quantity", 1))
            available = db.get_available_count()

            if available < quantity:
                return self.send_json({"error": "Estoque insuficiente", "stock": available}, 400)

            price = get_product_price()
            total = price * quantity
            order_id = f"SITE_{int(time.time())}_{os.urandom(3).hex().upper()}"

            # Reservar contas no banco (mudar status para 'reserved')
            import sqlite3
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, filename FROM inventory WHERE status = 'available' LIMIT ?",
                    (quantity,)
                )
                accounts_to_reserve = cursor.fetchall()
                if len(accounts_to_reserve) < quantity:
                    return self.send_json({"error": "Estoque insuficiente"}, 400)

                reserved_ids = []
                for acc_id, filename in accounts_to_reserve:
                    cursor.execute("UPDATE inventory SET status = 'reserved' WHERE id = ?", (acc_id,))
                    reserved_ids.append({"id": acc_id, "filename": filename})
                conn.commit()

            # Criar pagamento no Mercado Pago (PIX)
            try:
                sdk = mercadopago.SDK(MERCADOPAGO_TOKEN)
                payment_data = {
                    "transaction_amount": float(total),
                    "description": f"{quantity}x Conta Guest - {STORE_NAME}",
                    "payment_method_id": "pix",
                    "payer": {
                        "email": body.get("buyer_email") or f"site_{order_id}@breonn.store",
                        "first_name": body.get("buyer_name", "Comprador"),
                    },
                    "external_reference": order_id,
                    "notification_url": f"{BASE_URL}/api/webhook/mp",
                }
                response = sdk.payment().create(payment_data)
                payment = response["response"]

                if response["status"] not in (200, 201) or payment.get("status") != "pending":
                    # Reverter reserva
                    with db._get_connection() as conn:
                        for r in reserved_ids:
                            conn.execute("UPDATE inventory SET status = 'available' WHERE id = ?", (r["id"],))
                        conn.commit()
                    return self.send_json({"error": "Erro ao criar pagamento MP", "details": payment}, 500)

                pix_data = payment.get("point_of_interaction", {}).get("transaction_data", {})
                mp_payment_id = str(payment["id"])

                # Salvar pedido
                orders = load_orders()
                orders[order_id] = {
                    "id": order_id,
                    "mp_payment_id": mp_payment_id,
                    "status": "pending",
                    "source": body.get("source", "site"),
                    "buyer_email": body.get("buyer_email", ""),
                    "buyer_name": body.get("buyer_name", ""),
                    "quantity": quantity,
                    "amount": total,
                    "reserved_ids": reserved_ids,
                    "accounts_delivered": [],
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "delivered_at": None,
                    "telegram_chat_id": body.get("telegram_chat_id"),
                }
                save_orders(orders)

                # Salvar no banco de pagamentos do bot
                db.add_payment(mp_payment_id, 0, total)

                return self.send_json({
                    "order_id": order_id,
                    "mp_payment_id": mp_payment_id,
                    "pix_qr_code": pix_data.get("qr_code"),
                    "pix_copy_paste": pix_data.get("qr_code_base64"),
                    "amount": total,
                    "status": "pending",
                })

            except Exception as e:
                logger.error(f"Erro criar pagamento: {e}")
                # Reverter reserva
                with db._get_connection() as conn:
                    for r in reserved_ids:
                        conn.execute("UPDATE inventory SET status = 'available' WHERE id = ?", (r["id"],))
                    conn.commit()
                return self.send_json({"error": str(e)}, 500)

        # ── POST /api/webhook/mp ──
        elif path == "/api/webhook/mp":
            body = self.get_body()
            self.send_json({"ok": True})  # responder rápido

            if body.get("type") != "payment":
                return

            payment_id = str(body.get("data", {}).get("id", ""))
            if not payment_id:
                return

            # Processar em thread para não bloquear
            threading.Thread(target=self._process_mp_webhook, args=(payment_id,), daemon=True).start()

        # ── POST /api/admin/account ──
        elif path == "/api/admin/account":
            if not self.is_admin():
                return self.send_json({"error": "Unauthorized"}, 401)
            # Só registra no banco — o arquivo precisa ser copiado manualmente para ACCOUNTS_DIR
            body = self.get_body()
            filename = body.get("filename")
            if not filename:
                return self.send_json({"error": "filename obrigatório"}, 400)
            db.add_to_inventory(filename)
            return self.send_json({"success": True, "filename": filename})

        else:
            return self.send_json({"error": "Not found"}, 404)

    def _process_mp_webhook(self, payment_id):
        """Processa webhook do MP em background"""
        try:
            sdk = mercadopago.SDK(MERCADOPAGO_TOKEN)
            response = sdk.payment().get(payment_id)
            payment = response["response"]

            if payment.get("status") != "approved":
                return

            order_id = payment.get("external_reference", "")
            orders = load_orders()

            if order_id not in orders:
                # Pode ser um pagamento do bot — verificar se o bot já processou
                existing = db.get_payment(payment_id)
                if existing and existing[3] != "approved":
                    db.update_payment_status(payment_id, "approved")
                return

            order = orders[order_id]
            if order.get("status") == "paid":
                return  # já processado

            # Marcar como pago
            orders[order_id]["status"] = "paid"
            orders[order_id]["delivered_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

            # Marcar contas como vendidas no banco
            delivered = []
            with db._get_connection() as conn:
                for r in order.get("reserved_ids", []):
                    acc_id = r["id"]
                    filename = r["filename"]
                    conn.execute("UPDATE inventory SET status = 'sold' WHERE id = ?", (acc_id,))
                    conn.execute(
                        "INSERT INTO sales (user_id, inventory_id, amount, payment_status) VALUES (?, ?, ?, ?)",
                        (0, acc_id, order["amount"] / max(order["quantity"], 1), "completed")
                    )
                    # Mover arquivo físico para sold
                    src = os.path.join(ACCOUNTS_DIR, filename)
                    dst = os.path.join(SOLD_DIR, filename)
                    if os.path.exists(src):
                        import shutil
                        shutil.move(src, dst)
                    delivered.append(filename)
                conn.commit()

            orders[order_id]["accounts_delivered"] = delivered
            save_orders(orders)

            db.update_payment_status(payment_id, "approved")

            # Entregar via Telegram se veio do bot/site com chat_id
            chat_id = order.get("telegram_chat_id")
            if chat_id and delivered:
                send_telegram_message(
                    chat_id,
                    f"✅ *Pagamento aprovado!*\n\nPedido: `{order_id}`\nSegue(m) sua(s) conta(s):"
                )
                for filename in delivered:
                    deliver_account_to_telegram(chat_id, filename)
                send_telegram_message(
                    chat_id,
                    "🦆 Obrigado pela compra na *Breonn Store*!\nQualquer dúvida: @breonnmodz"
                )

            logger.info(f"✅ Pedido {order_id} processado. Contas entregues: {delivered}")

        except Exception as e:
            logger.error(f"Erro processar webhook MP: {e}")

    def do_DELETE(self):
        path = urlparse(self.path).path

        if path.startswith("/api/admin/account/"):
            if not self.is_admin():
                return self.send_json({"error": "Unauthorized"}, 401)
            acc_id = path.split("/api/admin/account/")[1]
            try:
                with db._get_connection() as conn:
                    conn.execute("DELETE FROM inventory WHERE id = ? AND status = 'available'", (int(acc_id),))
                    conn.commit()
                return self.send_json({"success": True})
            except Exception as e:
                return self.send_json({"error": str(e)}, 500)

        return self.send_json({"error": "Not found"}, 404)


# ── INICIAR SERVIDOR ──────────────────────────────────────────────────────────
def start_api_server():
    server = HTTPServer(("0.0.0.0", API_PORT), APIHandler)
    logger.info(f"🌐 API do site rodando na porta {API_PORT}")
    print(f"🌐 API do site rodando em http://0.0.0.0:{API_PORT}")
    server.serve_forever()

def start_api_in_thread():
    """Chame isso no main() do bot.py para rodar a API em paralelo"""
    t = threading.Thread(target=start_api_server, daemon=True)
    t.start()
    return t


# ────────────────────────────────────────────────────────────────────────────
# COMO INTEGRAR AO SEU bot.py:
#
# 1. Coloque este arquivo (api_server.py) na raiz do projeto (junto com bot.py)
#
# 2. No bot.py, adicione no topo:
#    from api_server import start_api_in_thread
#
# 3. No main(), ANTES de application.run_polling(), adicione:
#    start_api_in_thread()
#    print("🌐 API do site iniciada!")
#
# 4. Configure as variáveis de ambiente:
#    API_PORT=8080
#    ADMIN_API_TOKEN=sua-senha-forte-aqui
#    BASE_URL=https://seu-dominio.com
#    (TELEGRAM_TOKEN já está no seu config.py)
#
# 5. No site (index.html), troque:
#    const API_URL = 'https://seu-servidor:8080';
#
# 6. Se usar ngrok para testes:
#    ngrok http 8080
#    → use a URL gerada como BASE_URL e API_URL no site
#
# ROTAS DISPONÍVEIS:
#   GET  /api/stock                    → estoque público
#   POST /api/payment/create           → gerar PIX
#   POST /api/webhook/mp               → webhook do Mercado Pago
#   GET  /api/order/:id                → status do pedido
#   GET  /api/admin/stock              → estoque admin (requer x-admin-token)
#   GET  /api/admin/orders             → pedidos admin (requer x-admin-token)
#   DELETE /api/admin/account/:id      → remover conta (requer x-admin-token)
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Teste standalone
    logging.basicConfig(level=logging.INFO)
    start_api_server()
