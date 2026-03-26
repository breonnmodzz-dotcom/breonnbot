import os
import io
import json
import zipfile
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import mercadopago
from flask import Flask, request
import uuid
import asyncio
import threading
import base64
from io import BytesIO
from datetime import datetime

from database import db, init_db

load_dotenv()

TOKEN        = os.getenv("TOKEN")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))
WEBHOOK_URL  = os.getenv("WEBHOOK_URL", "")
BOT_COMMISSION_RATE = float(os.getenv("BOT_COMMISSION_RATE", "0.05"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
init_db()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
_pending_file_products = {}

# PERMISSOES
def is_bot_owner(i): return i.user.id == BOT_OWNER_ID
def is_owner_or_bot_owner(i): return i.user.id == i.guild.owner_id or is_bot_owner(i)
def is_manager_or_bot_owner(i): return db.is_manager(i.guild.id, i.user.id) or is_bot_owner(i)

# UTILITARIOS
def get_bot_commission_rate(): return BOT_COMMISSION_RATE

def calc_split(amount):
    bot_share = round(amount * get_bot_commission_rate(), 2)
    owner_share = round(amount - bot_share, 2)
    return bot_share, owner_share

def is_valid_url(url):
    if not url or not isinstance(url, str): return False
    u = url.strip()
    return u.startswith("http://") or u.startswith("https://")

def color_from_config(server):
    try:
        color_val = server.get('color', '#5865F2')
        if not color_val: return discord.Color.blurple()
        color_map = {
            "verde": discord.Color.green(), "vermelho": discord.Color.red(),
            "azul": discord.Color.blue(), "amarelo": discord.Color.gold(),
            "roxo": discord.Color.purple(), "branco": discord.Color.from_rgb(255,255,255),
            "preto": discord.Color.from_rgb(0,0,0), "cinza": discord.Color.greyple()
        }
        if str(color_val).lower() in color_map: return color_map[str(color_val).lower()]
        if not str(color_val).startswith('#'): return discord.Color.blurple()
        return discord.Color.from_str(color_val)
    except: return discord.Color.blurple()

def format_price(val_str):
    try: return round(float(val_str.replace(',', '.')), 2)
    except: return 0.0

def store_embed(server, guild, category="Geral"):
    embed = discord.Embed(
        title=f"🛍️  {guild.name} — {category}",
        description=server.get('welcome_msg') or f"Bem-vindo ao painel de **{category}**! 👇",
        color=color_from_config(server),
    )
    if is_valid_url(server.get('logo_url')): embed.set_thumbnail(url=server['logo_url'].strip())
    if is_valid_url(server.get('banner_url')): embed.set_image(url=server['banner_url'].strip())
    embed.set_footer(text="Pagamento seguro via Pix • Entrega automática")
    return embed

def build_guest_zip(accounts):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, acc in enumerate(accounts, start=1):
            filename = f"conta_{i:03d}.dat"
            content = acc.get("raw") or json.dumps(acc, ensure_ascii=False) if isinstance(acc, dict) else str(acc)
            zf.writestr(filename, content)
    zip_buffer.seek(0)
    return zip_buffer

# LOGS MELHORADOS
async def send_log(guild_id, type_log, embed):
    server = db.get_server(guild_id)
    if not server: return
    channel_id = server.get('logs_vendas_id' if type_log == 'venda' else 'logs_entregas_id')
    if not channel_id: return
    channel = bot.get_channel(int(channel_id))
    if channel:
        try: await channel.send(embed=embed)
        except: pass

def log_pagamento_gerado(tx_id, buyer, produto_nome, quantidade, total, bot_share, owner_share):
    embed = discord.Embed(title="🔔  PIX GERADO — AGUARDANDO PAGAMENTO", color=discord.Color.from_rgb(255, 165, 0), timestamp=datetime.now())
    embed.add_field(name="👤 Cliente", value=f"{buyer.mention}\n`{buyer.name}` (ID: `{buyer.id}`)", inline=True)
    embed.add_field(name="📦 Produto", value=f"**{produto_nome}**", inline=True)
    embed.add_field(name="🔢 Quantidade", value=f"`{quantidade}` unid.", inline=True)
    embed.add_field(name="💵 Total a Pagar", value=f"**R$ {total:.2f}**", inline=True)
    embed.add_field(name="💸 Comissão Bot", value=f"R$ {bot_share:.2f}", inline=True)
    embed.add_field(name="💰 Repasse ao Dono", value=f"R$ {owner_share:.2f}", inline=True)
    embed.add_field(name="🆔 ID Transação", value=f"`{tx_id}`", inline=False)
    embed.set_footer(text="⏳ Aguardando confirmação do pagamento...")
    return embed

def log_pagamento_aprovado(tx_id, payment_id, buyer_id, buyer_name, produto_nome, quantidade, total, bot_share, owner_share):
    embed = discord.Embed(title="✅  PAGAMENTO APROVADO", color=discord.Color.green(), timestamp=datetime.now())
    embed.add_field(name="👤 Cliente", value=f"<@{buyer_id}>\n`{buyer_name}` (ID: `{buyer_id}`)", inline=True)
    embed.add_field(name="📦 Produto", value=f"**{produto_nome}**", inline=True)
    embed.add_field(name="🔢 Quantidade", value=f"`{quantidade}` unid.", inline=True)
    embed.add_field(name="💵 Valor Total", value=f"**R$ {total:.2f}**", inline=True)
    embed.add_field(name="💸 Comissão Bot", value=f"R$ {bot_share:.2f}", inline=True)
    embed.add_field(name="💰 Repasse ao Dono", value=f"R$ {owner_share:.2f}", inline=True)
    embed.add_field(name="🆔 ID Transação", value=f"`{tx_id}`", inline=True)
    embed.add_field(name="💳 ID Pagamento MP", value=f"`{payment_id}`", inline=True)
    embed.set_footer(text="✅ Confirmado pelo Mercado Pago • Entrega em processamento...")
    return embed

def log_entrega_realizada(tx_id, buyer, produto_nome, quantidade, total, itens_entregues):
    embed = discord.Embed(title="📦  ENTREGA REALIZADA COM SUCESSO", color=discord.Color.from_rgb(0, 200, 150), timestamp=datetime.now())
    embed.set_thumbnail(url=buyer.display_avatar.url)
    embed.add_field(name="👤 Cliente", value=f"{buyer.mention}\n`{buyer.name}` (ID: `{buyer.id}`)", inline=True)
    embed.add_field(name="📦 Produto", value=f"**{produto_nome}**", inline=True)
    embed.add_field(name="🔢 Solicitado", value=f"`{quantidade}` unid.", inline=True)
    embed.add_field(name="✅ Entregue", value=f"`{itens_entregues}` item(ns)", inline=True)
    embed.add_field(name="💵 Valor Pago", value=f"**R$ {total:.2f}**", inline=True)
    embed.add_field(name="📬 Método", value="DM (Mensagem Direta)", inline=True)
    embed.add_field(name="🆔 ID Transação", value=f"`{tx_id}`", inline=False)
    embed.set_footer(text="📦 Entrega automática concluída")
    return embed

def log_entrega_falha(tx_id, buyer_id, produto_nome, motivo):
    embed = discord.Embed(title="❌  FALHA NA ENTREGA — AÇÃO NECESSÁRIA", color=discord.Color.red(), timestamp=datetime.now())
    embed.add_field(name="👤 Cliente", value=f"<@{buyer_id}>", inline=True)
    embed.add_field(name="📦 Produto", value=f"**{produto_nome}**", inline=True)
    embed.add_field(name="⚠️ Motivo", value=motivo, inline=False)
    embed.add_field(name="🆔 ID Transação", value=f"`{tx_id}`", inline=False)
    embed.set_footer(text="❌ Verifique manualmente e realize a entrega!")
    return embed

# UI CLASSES
class QuantidadeModal(discord.ui.Modal, title="🔢 Digitar Quantidade"):
    quantidade = discord.ui.TextInput(label="Quantidade desejada", placeholder="Ex: 5, 10, 50...", required=True, min_length=1, max_length=5)
    def __init__(self, view):
        super().__init__()
        self.view = view
    async def on_submit(self, interaction):
        try:
            val = int(self.quantidade.value)
            if val <= 0: raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Quantidade inválida!", ephemeral=True)
        if self.view.product.get('delivery', 'auto') == 'auto':
            stock_count = db.get_stock_count(self.view.product['id'])
            if val > stock_count:
                return await interaction.response.send_message(f"❌ Estoque insuficiente! Apenas **{stock_count}** disponíveis.", ephemeral=True)
        self.view.quantity = val
        await interaction.response.edit_message(embed=self.view.get_embed(), view=self.view)

class CarrinhoView(discord.ui.View):
    def __init__(self, product, server):
        super().__init__(timeout=300)
        self.product, self.server, self.quantity = product, server, 1
    def get_embed(self):
        embed = discord.Embed(title=f"🛒  Carrinho — {self.product['name']}", description=self.product.get('description', 'Sem descrição.'), color=color_from_config(self.server))
        embed.add_field(name="💵 Preço Unitário", value=f"R$ {self.product['price']:.2f}", inline=True)
        embed.add_field(name="📦 Quantidade", value=str(self.quantity), inline=True)
        embed.add_field(name="💰 Total", value=f"**R$ {self.product['price'] * self.quantity:.2f}**", inline=True)
        if is_valid_url(self.product.get('image_url')): embed.set_thumbnail(url=self.product['image_url'])
        return embed
    @discord.ui.button(label="➕", style=discord.ButtonStyle.secondary)
    async def add(self, interaction, button):
        if self.product.get('delivery', 'auto') == 'auto' and self.quantity >= db.get_stock_count(self.product['id']):
            return await interaction.response.send_message("❌ Estoque insuficiente.", ephemeral=True)
        self.quantity += 1
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    @discord.ui.button(label="🔢", style=discord.ButtonStyle.secondary)
    async def set_qty(self, interaction, button):
        await interaction.response.send_modal(QuantidadeModal(self))
    @discord.ui.button(label="➖", style=discord.ButtonStyle.secondary)
    async def sub(self, interaction, button):
        if self.quantity > 1:
            self.quantity -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
    @discord.ui.button(label="✅  Finalizar Compra", style=discord.ButtonStyle.success, row=1)
    async def finish(self, interaction, button):
        try:
            await interaction.response.defer(ephemeral=True)
            if not self.server.get('mp_token'):
                return await interaction.followup.send("❌ O dono do servidor não configurou o token do Mercado Pago!", ephemeral=True)
            sdk = mercadopago.SDK(self.server['mp_token'])
            total = float(self.product['price'] * self.quantity)
            if total < 0.01:
                return await interaction.followup.send("❌ Valor inválido.", ephemeral=True)
            payment_data = {
                "transaction_amount": total,
                "description": f"Compra de {self.quantity}x {self.product['name']}",
                "payment_method_id": "pix",
                "payer": {"email": f"{interaction.user.id}@discord.com", "first_name": interaction.user.display_name}
            }
            result = sdk.payment().create(payment_data)
            payment = result.get("response")
            if not payment or "point_of_interaction" not in payment:
                error_msg = "Erro ao gerar o Pix."
                if payment and "message" in payment: error_msg += f" Detalhes: {payment['message']}"
                return await interaction.followup.send(f"❌ {error_msg}", ephemeral=True)
            pix_data = payment["point_of_interaction"]["transaction_data"]
            bot_share, owner_share = calc_split(total)
            tx_id = str(uuid.uuid4())
            db.save_transaction({
                "id": tx_id, "payment_id": str(payment["id"]),
                "server_id": str(interaction.guild.id), "product_id": self.product['id'],
                "buyer_id": str(interaction.user.id), "buyer_name": interaction.user.display_name,
                "amount": total, "bot_commission": bot_share, "server_share": owner_share,
                "quantity": self.quantity, "status": "pending", "delivery": self.product.get('delivery', 'auto')
            })
            qr_bytes = base64.b64decode(pix_data["qr_code_base64"])
            file = discord.File(BytesIO(qr_bytes), filename="qrcode.png")
            embed = discord.Embed(title="⚡  Pagamento via Pix", description=f"**Produto:** {self.product['name']}\n**Quantidade:** {self.quantity}\n**Total:** R$ {total:.2f}", color=discord.Color.green())
            embed.set_image(url="attachment://qrcode.png")
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            await interaction.followup.send(f"**Código Pix Copia e Cola:**\n```\n{pix_data['qr_code']}\n```", ephemeral=True)
            log_embed = log_pagamento_gerado(tx_id, interaction.user, self.product['name'], self.quantity, total, bot_share, owner_share)
            await send_log(interaction.guild.id, 'venda', log_embed)
            try: await interaction.delete_original_response()
            except: pass
        except Exception as e:
            print(f"Erro finalizar: {e}")
            try: await interaction.followup.send(f"❌ Erro interno: {e}", ephemeral=True)
            except: pass

class StoreView(discord.ui.View):
    def __init__(self, products, server_config):
        super().__init__(timeout=None)
        options = []
        for p in products:
            qty = db.get_stock_count(p['id'])
            if p.get('delivery') == 'manual' or qty > 0:
                options.append(discord.SelectOption(label=p['name'][:25], value=p['id'], description=f"R$ {p['price']:.2f} • {qty if p.get('delivery')=='auto' else 'Manual'}", emoji="📦"))
        if not options: options = [discord.SelectOption(label="Vazio", value="none")]
        select = discord.ui.Select(placeholder="📋 Escolha um produto...", options=options)
        async def callback(interaction):
            if select.values[0] == "none": return
            product = db.get_product(select.values[0])
            view = CarrinhoView(product, server_config)
            try: await interaction.message.delete()
            except: pass
            await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)
        select.callback = callback
        self.add_item(select)

# EVENTO: MEMBRO ENTRA -> CARGO MEMBRO + LOG
@bot.event
async def on_member_join(member: discord.Member):
    try:
        server_data = db.get_server(member.guild.id)
        if not server_data: return
        role = None
        role_membro_id = server_data.get("role_membro_id")
        if role_membro_id:
            role = member.guild.get_role(int(role_membro_id))
            if role:
                await member.add_roles(role, reason="Cargo automático ao entrar no servidor")
        log_channel_id = server_data.get("logs_entradas_id")
        if log_channel_id:
            channel = bot.get_channel(int(log_channel_id))
            if channel:
                embed = discord.Embed(title="🚪 Novo Membro Entrou", color=discord.Color.green(), timestamp=datetime.now())
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="👤 Usuário", value=f"{member.mention}\n`{member.name}` (ID: `{member.id}`)", inline=True)
                embed.add_field(name="📅 Conta Criada em", value=f"<t:{int(member.created_at.timestamp())}:D>", inline=True)
                embed.add_field(name="🎖️ Cargo Dado", value=role.mention if role else "Nenhum", inline=True)
                embed.set_footer(text=f"Membro #{member.guild.member_count} do servidor")
                await channel.send(embed=embed)
    except Exception as e:
        print(f"Erro on_member_join: {e}")

# COMANDOS SLASH
@bot.tree.command(name="sync", description="🔄 [Dono Bot] Sincronizar comandos manualmente")
async def sync(interaction: discord.Interaction):
    if not is_bot_owner(interaction): return await interaction.response.send_message("❌ Apenas o dono do bot.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    try:
        synced = await bot.tree.sync()
        for g in bot.guilds:
            try: await bot.tree.sync(guild=g)
            except: pass
        await interaction.followup.send(f"✅ {len(synced)} comandos sincronizados!", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"❌ Erro: {e}", ephemeral=True)

@bot.tree.command(name="logs", description="📂 Configurar canais de logs de vendas e entregas")
@app_commands.describe(vendas="Canal para logs de vendas", entregas="Canal para logs de entrega")
async def logs(interaction: discord.Interaction, vendas: discord.TextChannel = None, entregas: discord.TextChannel = None):
    if not is_owner_or_bot_owner(interaction): return await interaction.response.send_message("❌ Apenas o dono.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    if not db.get_server(interaction.guild.id): db.save_server({"id": str(interaction.guild.id), "owner_id": str(interaction.guild.owner_id)})
    update_data = {"id": str(interaction.guild.id)}
    msg = "✅ Canais de log atualizados:\n"
    if vendas: update_data["logs_vendas_id"] = str(vendas.id); msg += f"- Vendas: {vendas.mention}\n"
    if entregas: update_data["logs_entregas_id"] = str(entregas.id); msg += f"- Entregas: {entregas.mention}\n"
    db.save_server(update_data)
    await interaction.followup.send(msg, ephemeral=True)

@bot.tree.command(name="confirmar", description="🛠️ Listar e aprovar pagamentos pendentes")
async def confirmar(interaction: discord.Interaction):
    if not is_manager_or_bot_owner(interaction): return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    txs = [t for t in db.get_transactions(interaction.guild.id) if t['status'] == 'pending']
    if not txs: return await interaction.followup.send("📭 Nada pendente.", ephemeral=True)
    view = discord.ui.View(timeout=60)
    options = []
    for t in txs[:25]:
        p = db.get_product(t['product_id']); p_name = p['name'] if p else "Removido"
        try: dt = datetime.fromisoformat(t['created_at']).strftime('%H:%M:%S')
        except: dt = "--:--:--"
        options.append(discord.SelectOption(label=f"[{dt}] {t['buyer_name']}"[:100], value=t['id'], description=f"R$ {t['amount']:.2f} - {p_name}"[:100]))
    sel = discord.ui.Select(placeholder="Selecione para aprovar...", options=options)
    async def call(inter):
        tx = next((x for x in txs if x['id'] == sel.values[0]), None)
        if not tx: return
        tx['status'] = 'approved'
        db.save_transaction(tx)
        s = db.get_server(tx['server_id'])
        if s:
            _, o_s = calc_split(tx['amount'])
            db.add_balance(tx['server_id'], o_s)
            db.add_bot_balance(tx['amount'] * get_bot_commission_rate())
            p = db.get_product(tx['product_id'])
            log_embed = log_pagamento_aprovado(
                tx['id'], tx['payment_id'], tx['buyer_id'], tx['buyer_name'],
                p['name'] if p else 'Removido', tx.get('quantity', 1),
                tx['amount'], tx.get('bot_commission', 0), tx.get('server_share', 0)
            )
            await send_log(tx['server_id'], 'venda', log_embed)
        asyncio.run_coroutine_threadsafe(deliver_items(tx), bot.loop)
        await inter.response.send_message("✅ Aprovado! Entrega sendo processada...", ephemeral=True)
    sel.callback = call
    view.add_item(sel)
    await interaction.followup.send("🛠️ Pendentes:", view=view, ephemeral=True)

@bot.tree.command(name="adicionar", description="📦 Adicionar produto e estoque")
async def adicionar(interaction: discord.Interaction):
    if not is_manager_or_bot_owner(interaction): return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
    class AddModal(discord.ui.Modal, title="📦 Adicionar Produto"):
        n = discord.ui.TextInput(label="Nome", required=True)
        p = discord.ui.TextInput(label="Preço (Ex: 0.65)", required=True)
        c = discord.ui.TextInput(label="Painel", default="Painel 1", required=True)
        async def on_submit(self, inter):
            pr = format_price(self.p.value)
            _pending_file_products[inter.user.id] = {"nome": self.n.value, "preco": pr, "guild_id": str(inter.guild.id), "categoria": self.c.value}
            await inter.response.send_message(f"✅ Adicionando **{self.n.value}** (R$ {pr:.2f}). Envie o estoque!", ephemeral=True)
    await interaction.response.send_modal(AddModal())

@bot.tree.command(name="gerente", description="👑 Gerenciar gerentes")
async def gerente(interaction: discord.Interaction):
    if not is_owner_or_bot_owner(interaction): return await interaction.response.send_message("❌ Apenas o dono.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    if not db.get_server(interaction.guild.id): db.save_server({"id": str(interaction.guild.id), "owner_id": str(interaction.guild.owner_id)})
    v = discord.ui.View(timeout=60)
    s = discord.ui.UserSelect(placeholder="Selecione o usuário para promover/remover...")
    async def call(inter):
        u = s.values[0]
        if db.is_manager(inter.guild.id, u.id):
            db.remove_manager(inter.guild.id, u.id)
            msg = f"❌ {u.mention} removido de gerente."
        else:
            db.add_manager(inter.guild.id, u.id)
            msg = f"✅ {u.mention} agora é gerente."
        await inter.response.edit_message(content=msg, view=None)
    s.callback = call
    v.add_item(s)
    await interaction.followup.send("👑 **Painel de Gerência**\nSelecione um usuário:", view=v, ephemeral=True)

@bot.tree.command(name="painel", description="🛍️ Ver painel")
async def painel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    s = db.get_server(interaction.guild.id)
    p = db.get_products(interaction.guild.id)
    if not s: db.save_server({"id": str(interaction.guild.id), "owner_id": str(interaction.guild.owner_id)}); s = db.get_server(interaction.guild.id)
    if not p: return await interaction.followup.send("❌ Nenhum produto.", ephemeral=True)
    v = discord.ui.View(timeout=60)
    cats = sorted(list(set(x.get('category', 'Geral') for x in p)))
    sel = discord.ui.Select(options=[discord.SelectOption(label=c, value=c) for c in cats])
    async def call(inter):
        c_n = sel.values[0]
        emb = store_embed(s, inter.guild, c_n)
        vi = StoreView([x for x in p if x.get('category') == c_n], s)
        await inter.response.send_message(embed=emb, view=vi, ephemeral=True)
    sel.callback = call
    v.add_item(sel)
    await interaction.followup.send("📂 Painel:", view=v, ephemeral=True)

@bot.tree.command(name="atualizar", description="🔄 Enviar painel ao canal")
async def atualizar(interaction: discord.Interaction):
    if not is_manager_or_bot_owner(interaction): return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    s = db.get_server(interaction.guild.id)
    p = db.get_products(interaction.guild.id)
    ch = discord.utils.get(interaction.guild.text_channels, name="🛒・loja")
    if not ch: return await interaction.followup.send("❌ Canal **🛒・loja** não existe.", ephemeral=True)
    if not p: return await interaction.followup.send("❌ Nenhum produto.", ephemeral=True)
    v = discord.ui.View(timeout=60)
    cats = sorted(list(set(x.get('category', 'Geral') for x in p)))
    sel = discord.ui.Select(options=[discord.SelectOption(label=c, value=c) for c in cats])
    async def call(inter):
        c_n = sel.values[0]
        emb = store_embed(s, inter.guild, c_n)
        vi = StoreView([x for x in p if x.get('category') == c_n], s)
        await ch.send(embed=emb, view=vi)
        await inter.response.edit_message(content="✅ Enviado!", view=None)
    sel.callback = call
    v.add_item(sel)
    await interaction.followup.send("🔄 Enviar:", view=v, ephemeral=True)

@bot.tree.command(name="saldo", description="💰 Ver saldo")
async def saldo(interaction: discord.Interaction):
    if not is_owner_or_bot_owner(interaction): return await interaction.response.send_message("❌ Apenas o dono.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    s = db.get_server(interaction.guild.id)
    if not s: db.save_server({"id": str(interaction.guild.id), "owner_id": str(interaction.guild.owner_id)}); b = 0.0
    else: b = s.get('balance', 0.0)
    await interaction.followup.send(f"💰 Saldo: R$ {b:.2f}", ephemeral=True)

@bot.tree.command(name="configurar", description="⚙️ Configurar token do Mercado Pago")
async def configurar(interaction: discord.Interaction, token_mp: str):
    if not is_owner_or_bot_owner(interaction): return await interaction.response.send_message("❌ Apenas o dono.", ephemeral=True)
    db.save_server({"id": str(interaction.guild.id), "owner_id": str(interaction.guild.owner_id), "mp_token": token_mp})
    await interaction.response.send_message("✅ Token do Mercado Pago configurado!", ephemeral=True)

@bot.tree.command(name="visual", description="🎨 Personalizar o visual do painel")
async def visual(interaction: discord.Interaction):
    if not is_owner_or_bot_owner(interaction): return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
    class VisualModal(discord.ui.Modal, title="🎨 Personalizar Painel"):
        logo = discord.ui.TextInput(label="Logo (Link da imagem pequena)", placeholder="https://i.imgur.com/xxx.png", required=False)
        banner = discord.ui.TextInput(label="Banner (Link da imagem grande)", placeholder="https://i.imgur.com/yyy.png", required=False)
        cor = discord.ui.TextInput(label="Cor Hexadecimal", placeholder="#FF0000 (Vermelho) | #00FF00 (Verde)", required=False, min_length=4, max_length=7)
        msg_boas_vindas = discord.ui.TextInput(label="Mensagem de Boas-vindas", placeholder="Texto no topo do painel...", style=discord.TextStyle.paragraph, required=False)
        async def on_submit(self, inter):
            await inter.response.defer(ephemeral=True)
            update_data = {"id": str(inter.guild.id)}
            res_msg = "🎨 **Alterações:**\n"
            if self.logo.value: update_data["logo_url"] = self.logo.value.strip(); res_msg += "- ✅ Logo\n"
            if self.banner.value: update_data["banner_url"] = self.banner.value.strip(); res_msg += "- ✅ Banner\n"
            if self.cor.value:
                c = self.cor.value.strip()
                if not c.startswith('#'): c = f"#{c}"
                update_data["color"] = c; res_msg += f"- ✅ Cor `{c}`\n"
            if self.msg_boas_vindas.value: update_data["welcome_msg"] = self.msg_boas_vindas.value.strip(); res_msg += "- ✅ Boas-vindas\n"
            if len(update_data) > 1: db.save_server(update_data); await inter.followup.send(res_msg, ephemeral=True)
            else: await inter.followup.send("⚠️ Nenhuma alteração.", ephemeral=True)
    embed_tutorial = discord.Embed(title="🎨 Tutorial de Personalização", description="**🖼️ Link da imagem?**\n1. Clique em **Hospedar Imagem**\n2. Envie a imagem\n3. Copie o Link Direto (.png/.jpg)\n\n**🎨 Cores:** `#FF0000` (Vermelho) | `#00FF00` (Verde) | `#0000FF` (Azul) | `#FFFF00` (Amarelo) | `#FFFFFF` (Branco)\n\nClique em **Abrir Formulário** para salvar!", color=discord.Color.blue())
    view = discord.ui.View()
    btn_host = discord.ui.Button(label="🌐 Hospedar Imagem", url="https://postimages.org/")
    btn_form = discord.ui.Button(label="📝 Abrir Formulário", style=discord.ButtonStyle.success)
    async def btn_callback(inter): await inter.response.send_modal(VisualModal())
    btn_form.callback = btn_callback
    view.add_item(btn_host)
    view.add_item(btn_form)
    await interaction.response.send_message(embed=embed_tutorial, view=view, ephemeral=True)

@bot.tree.command(name="estoque", description="📦 Ver estoque")
async def estoque(interaction: discord.Interaction):
    if not is_manager_or_bot_owner(interaction): return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    p = db.get_products(interaction.guild.id)
    emb = discord.Embed(title="📦 Estoque", color=discord.Color.blue())
    for x in p: emb.add_field(name=f"{x['name']} ({x.get('category','Geral')})", value=f"{db.get_stock_count(x['id'])} unid. | R$ {x['price']:.2f}", inline=False)
    await interaction.followup.send(embed=emb, ephemeral=True)

@bot.tree.command(name="apagar", description="🗑️ Apagar produto ou painel")
@app_commands.choices(tipo=[app_commands.Choice(name="Produto", value="produto"), app_commands.Choice(name="Painel", value="categoria")])
async def apagar(interaction: discord.Interaction, tipo: str, nome: str):
    if not is_manager_or_bot_owner(interaction): return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
    if tipo == "produto":
        pr = next((x for x in db.get_products(interaction.guild.id) if x['name'].lower() == nome.lower()), None)
        if pr: db.delete_product(pr['id']); await interaction.response.send_message("✅ Produto apagado!", ephemeral=True)
        else: await interaction.response.send_message("❌ Não encontrado.", ephemeral=True)
    else:
        db.delete_category(interaction.guild.id, nome)
        await interaction.response.send_message("✅ Painel apagado!", ephemeral=True)

@bot.tree.command(name="setup_loja", description="🛒 [Setup 1] Cria a categoria e canal da loja")
async def setup_loja(interaction: discord.Interaction):
    if not is_owner_or_bot_owner(interaction): return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    try:
        cat = await interaction.guild.create_category("🛒 LOJA AUTOMÁTICA")
        await interaction.guild.create_text_channel("🛒・loja", category=cat)
        await interaction.followup.send("🛒 **Setup Loja** concluído!", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"❌ Erro: {e}", ephemeral=True)

@bot.tree.command(name="setup_completo", description="🚀 Cria loja, comunidade, suporte, logs, cargos e permissões completas")
async def setup_completo(interaction: discord.Interaction):
    if not is_owner_or_bot_owner(interaction): return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    try:
        guild = interaction.guild
        everyone = guild.default_role

        # CARGOS
        roles_config = [
            {"name": "👑 Dono",    "color": discord.Color.from_rgb(255, 215, 0),  "hoist": True, "mentionable": False, "permissions": discord.Permissions.all()},
            {"name": "🛡️ Admin",   "color": discord.Color.red(),                  "hoist": True, "mentionable": True,  "permissions": discord.Permissions(administrator=True)},
            {"name": "🛠️ Suporte", "color": discord.Color.blue(),                 "hoist": True, "mentionable": True,  "permissions": discord.Permissions(manage_messages=True, kick_members=True, mute_members=True)},
            {"name": "💎 Cliente", "color": discord.Color.gold(),                 "hoist": True, "mentionable": False, "permissions": discord.Permissions(send_messages=True, read_messages=True, read_message_history=True)},
            {"name": "👤 Membro",  "color": discord.Color.light_grey(),           "hoist": True, "mentionable": False, "permissions": discord.Permissions(send_messages=True, read_messages=True, read_message_history=True)},
        ]
        created_roles = {}
        for r_data in roles_config:
            role = discord.utils.get(guild.roles, name=r_data["name"])
            if not role:
                role = await guild.create_role(name=r_data["name"], color=r_data["color"], hoist=r_data["hoist"], mentionable=r_data["mentionable"], permissions=r_data["permissions"])
            created_roles[r_data["name"]] = role

        role_dono    = created_roles["👑 Dono"]
        role_admin   = created_roles["🛡️ Admin"]
        role_suporte = created_roles["🛠️ Suporte"]
        role_cliente = created_roles["💎 Cliente"]
        role_membro  = created_roles["👤 Membro"]

        # Dar cargo Dono ao dono do servidor
        try:
            owner_member = await guild.fetch_member(guild.owner_id)
            if role_dono not in owner_member.roles:
                await owner_member.add_roles(role_dono, reason="Setup — Cargo Dono atribuído ao dono do servidor")
        except Exception as e:
            print(f"Aviso cargo Dono: {e}")

        # LOJA
        cat_loja = discord.utils.get(guild.categories, name="🛒 LOJA AUTOMÁTICA")
        if not cat_loja:
            ow_loja = {
                everyone:     discord.PermissionOverwrite(read_messages=True, send_messages=False),
                role_membro:  discord.PermissionOverwrite(read_messages=True, send_messages=False),
                role_cliente: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                role_admin:   discord.PermissionOverwrite(read_messages=True, send_messages=True),
                role_dono:    discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
                guild.me:     discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            cat_loja = await guild.create_category("🛒 LOJA AUTOMÁTICA", overwrites=ow_loja)
        if not discord.utils.get(cat_loja.text_channels, name="🛒・loja"):
            await guild.create_text_channel("🛒・loja", category=cat_loja, topic="🛒 Compre produtos com pagamento automático via Pix!")

        # COMUNIDADE
        cat_com = discord.utils.get(guild.categories, name="💬 COMUNIDADE")
        if not cat_com:
            cat_com = await guild.create_category("💬 COMUNIDADE")

        # AVISOS: apenas Dono manda
        if not discord.utils.get(cat_com.text_channels, name="📢・avisos"):
            ow_avisos = {
                everyone:     discord.PermissionOverwrite(read_messages=True,  send_messages=False, add_reactions=False),
                role_membro:  discord.PermissionOverwrite(read_messages=True,  send_messages=False, add_reactions=True),
                role_cliente: discord.PermissionOverwrite(read_messages=True,  send_messages=False, add_reactions=True),
                role_suporte: discord.PermissionOverwrite(read_messages=True,  send_messages=False),
                role_admin:   discord.PermissionOverwrite(read_messages=True,  send_messages=False),
                role_dono:    discord.PermissionOverwrite(read_messages=True,  send_messages=True,  manage_messages=True, mention_everyone=True),
                guild.me:     discord.PermissionOverwrite(read_messages=True,  send_messages=True),
            }
            await guild.create_text_channel("📢・avisos", category=cat_com, overwrites=ow_avisos, topic="📢 Apenas o Dono pode enviar mensagens aqui.")

        # CHAT GERAL: membros+ falam
        if not discord.utils.get(cat_com.text_channels, name="💬・chat-geral"):
            ow_chat = {
                everyone:     discord.PermissionOverwrite(read_messages=False),
                role_membro:  discord.PermissionOverwrite(read_messages=True, send_messages=True, add_reactions=True),
                role_cliente: discord.PermissionOverwrite(read_messages=True, send_messages=True, add_reactions=True),
                role_suporte: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
                role_admin:   discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
                role_dono:    discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True, manage_channels=True),
                guild.me:     discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            await guild.create_text_channel("💬・chat-geral", category=cat_com, overwrites=ow_chat, topic="💬 Converse com a comunidade!")

        # SUPORTE
        cat_sup = discord.utils.get(guild.categories, name="⚙️ SUPORTE")
        if not cat_sup:
            ow_sup = {
                everyone:     discord.PermissionOverwrite(read_messages=False),
                role_membro:  discord.PermissionOverwrite(read_messages=True, send_messages=True),
                role_cliente: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                role_suporte: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
                role_admin:   discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
                role_dono:    discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
                guild.me:     discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            cat_sup = await guild.create_category("⚙️ SUPORTE", overwrites=ow_sup)
        if not discord.utils.get(cat_sup.text_channels, name="🎫・abrir-ticket"):
            await guild.create_text_channel("🎫・abrir-ticket", category=cat_sup, topic="🎫 Precisa de ajuda? Fale com o suporte!")

        # LOGS (privado)
        cat_logs = discord.utils.get(guild.categories, name="📊 SISTEMA DE LOGS")
        if not cat_logs:
            ow_logs = {
                everyone:     discord.PermissionOverwrite(read_messages=False),
                role_suporte: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                role_admin:   discord.PermissionOverwrite(read_messages=True, send_messages=False),
                role_dono:    discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
                guild.me:     discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            cat_logs = await guild.create_category("📊 SISTEMA DE LOGS", overwrites=ow_logs)

        ch_vendas   = discord.utils.get(cat_logs.text_channels, name="💰・logs-vendas")
        if not ch_vendas:
            ch_vendas = await guild.create_text_channel("💰・logs-vendas", category=cat_logs, topic="💰 Registro automático de vendas e pagamentos.")

        ch_entregas = discord.utils.get(cat_logs.text_channels, name="📦・logs-entregas")
        if not ch_entregas:
            ch_entregas = await guild.create_text_channel("📦・logs-entregas", category=cat_logs, topic="📦 Registro automático de entregas.")

        ch_entradas = discord.utils.get(cat_logs.text_channels, name="🚪・logs-entradas")
        if not ch_entradas:
            ch_entradas = await guild.create_text_channel("🚪・logs-entradas", category=cat_logs, topic="🚪 Registro de membros que entram/saem.")

        # SALVAR
        db.save_server({
            "id": str(guild.id), "owner_id": str(guild.owner_id),
            "logs_vendas_id":   str(ch_vendas.id),
            "logs_entregas_id": str(ch_entregas.id),
            "logs_entradas_id": str(ch_entradas.id),
            "role_dono_id":     str(role_dono.id),
            "role_admin_id":    str(role_admin.id),
            "role_suporte_id":  str(role_suporte.id),
            "role_cliente_id":  str(role_cliente.id),
            "role_membro_id":   str(role_membro.id),
        })

        embed = discord.Embed(title="🚀 Setup Completo Finalizado!", description="Tudo criado e configurado com permissões corretas.", color=discord.Color.green(), timestamp=datetime.now())
        embed.add_field(name="👑 Cargos Criados", value=(
            f"{role_dono.mention} — Dono (atribuído ao dono do servidor ✅)\n"
            f"{role_admin.mention} — Administradores\n"
            f"{role_suporte.mention} — Equipe de Suporte\n"
            f"{role_cliente.mention} — Clientes (dado após compra automaticamente)\n"
            f"{role_membro.mention} — Membros (dado ao entrar automaticamente)"
        ), inline=False)
        embed.add_field(name="📂 Canais Criados", value=(
            "🛒 **LOJA** → `🛒・loja`\n"
            "💬 **COMUNIDADE** → `📢・avisos` | `💬・chat-geral`\n"
            "⚙️ **SUPORTE** → `🎫・abrir-ticket`\n"
            "📊 **LOGS** → `💰・logs-vendas` | `📦・logs-entregas` | `🚪・logs-entradas`"
        ), inline=False)
        embed.add_field(name="🔐 Permissões", value=(
            "📢 `avisos` → **Apenas o Dono** envia mensagens\n"
            "💬 `chat-geral` → Membros+ (sem cargo = sem acesso)\n"
            "📊 `Logs` → Privado (só Dono envia, Admin/Suporte veem)\n"
            "👤 `Membro` → Dado automaticamente ao entrar\n"
            "💎 `Cliente` → Dado automaticamente após compra aprovada"
        ), inline=False)
        embed.set_footer(text="Use /configurar para adicionar o token do Mercado Pago")
        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Erro no setup: {e}", ephemeral=True)
        print(f"Erro setup_completo: {e}")

@bot.tree.command(name="unsetup", description="🗑️ Remove todos os canais e categorias de setup")
async def unsetup(interaction: discord.Interaction):
    if not is_owner_or_bot_owner(interaction): return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    channel_names = ["🛒・loja", "📢・avisos", "💬・chat-geral", "🎫・abrir-ticket", "💰・logs-vendas", "📦・logs-entregas", "🚪・logs-entradas"]
    cat_names = ["🛒 LOJA AUTOMÁTICA", "💬 COMUNIDADE", "⚙️ SUPORTE", "📊 SISTEMA DE LOGS", "⚙️ SUPORTE & COMUNIDADE"]
    for ch in interaction.guild.channels:
        if ch.name in channel_names or (isinstance(ch, discord.CategoryChannel) and ch.name in cat_names):
            try: await ch.delete()
            except: pass
    await interaction.followup.send("🗑️ Todos os canais de setup removidos!", ephemeral=True)

@bot.tree.command(name="comissao", description="⚙️ [Dono Bot] Configurar taxa de comissão")
async def comissao(interaction: discord.Interaction, taxa: float):
    global BOT_COMMISSION_RATE
    if not is_bot_owner(interaction): return await interaction.response.send_message("❌ Apenas dono do bot.", ephemeral=True)
    BOT_COMMISSION_RATE = taxa / 100.0
    await interaction.response.send_message(f"✅ Taxa: {taxa}%", ephemeral=True)

@bot.tree.command(name="sacar", description="💸 [Dono Bot] Zerar saldo do servidor")
async def sacar(interaction: discord.Interaction):
    if not is_bot_owner(interaction): return await interaction.response.send_message("❌ Apenas dono do bot.", ephemeral=True)
    s = db.get_server(interaction.guild.id)
    b = s.get('balance', 0.0) if s else 0.0
    if b <= 0: return await interaction.response.send_message("⚠️ Sem saldo.", ephemeral=True)
    v = discord.ui.View(timeout=60)
    btn = discord.ui.Button(label="💸 Zerar Saldo", style=discord.ButtonStyle.danger)
    async def call(inter): db.reset_balance(str(inter.guild.id)); await inter.response.edit_message(content=f"✅ R$ {b:.2f} zerado.", view=None)
    btn.callback = call
    v.add_item(btn)
    await interaction.response.send_message(f"💸 Zerar R$ {b:.2f}?", view=v, ephemeral=True)

@bot.tree.command(name="saldo_bot", description="💰 [Dono Bot] Ver saldo total acumulado do bot")
async def saldo_bot(interaction: discord.Interaction):
    if not is_bot_owner(interaction): return await interaction.response.send_message("❌ Apenas dono do bot.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    b_bal = db.get_bot_balance()
    await interaction.followup.send(f"💰 Saldo Total do Bot: R$ {b_bal:.2f}", ephemeral=True)

# ENTREGA
async def deliver_items(tx):
    try:
        guild = bot.get_guild(int(tx["server_id"]))
        u = await bot.fetch_user(int(tx["buyer_id"]))
        p = db.get_product(tx["product_id"])
        accs = []
        if guild:
            try:
                member = await guild.fetch_member(u.id)
                server_data = db.get_server(guild.id)
                role_id = server_data.get("role_cliente_id")
                if role_id:
                    role = guild.get_role(int(role_id))
                    if role and role not in member.roles:
                        await member.add_roles(role, reason="Compra aprovada — cargo Cliente atribuído")
            except Exception as e:
                print(f"Erro cargo Cliente: {e}")
        for _ in range(tx.get('quantity', 1)):
            it = db.sell_stock_item(tx["product_id"])
            if not it: break
            try: accs.append(json.loads(it["item_data"]))
            except: accs.append({"raw": it["item_data"]})
        if accs:
            buf = build_guest_zip(accs)
            buf.seek(0)
            await u.send(f"✅ **{p['name'] if p else 'Produto'}** — Obrigado pela compra! Seus itens estão no arquivo abaixo.", file=discord.File(buf, filename="contas.zip"))
            log_embed = log_entrega_realizada(tx['id'], u, p['name'] if p else 'Removido', tx.get('quantity', 1), tx.get('amount', 0), len(accs))
            await send_log(tx['server_id'], 'entrega', log_embed)
        else:
            log_embed = log_entrega_falha(tx['id'], tx['buyer_id'], p['name'] if p else 'Removido', "Estoque esgotado durante a entrega. Entregue manualmente!")
            await send_log(tx['server_id'], 'entrega', log_embed)
    except Exception as e:
        print(f"Erro na entrega: {e}")

# WEBHOOK
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def mp_webhook():
    d = request.json or {}
    p_id = (d.get("data") or {}).get("id") or request.args.get("id")
    tx = db.get_transaction_by_payment_id(p_id)
    if tx and tx["status"] == "pending":
        s = db.get_server(tx["server_id"])
        sdk = mercadopago.SDK(s["mp_token"])
        pay = sdk.payment().get(p_id).get("response", {})
        if pay.get("status") == "approved":
            tx["status"] = "approved"
            db.save_transaction(tx)
            _, o_s = calc_split(tx['amount'])
            db.add_balance(tx["server_id"], o_s)
            db.add_bot_balance(tx['amount'] * get_bot_commission_rate())
            p = db.get_product(tx["product_id"])
            log_embed = log_pagamento_aprovado(tx['id'], tx['payment_id'], tx['buyer_id'], tx['buyer_name'], p['name'] if p else 'Removido', tx.get('quantity', 1), tx['amount'], tx.get('bot_commission', 0), tx.get('server_share', 0))
            asyncio.run_coroutine_threadsafe(send_log(tx['server_id'], 'venda', log_embed), bot.loop)
            asyncio.run_coroutine_threadsafe(deliver_items(tx), bot.loop)
    return "OK", 200

@bot.event
async def on_ready():
    print(f"✅ {bot.user} pronto!")
    await bot.tree.sync()
    for g in bot.guilds:
        try: await bot.tree.sync(guild=g)
        except: pass

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.author.id not in _pending_file_products: return
    pend = _pending_file_products.pop(message.author.id)
    accs = []
    try:
        async with message.channel.typing():
            if message.attachments:
                att = message.attachments[0]
                f_b = await att.read()
                if att.filename.lower().endswith('.zip'):
                    with zipfile.ZipFile(io.BytesIO(f_b)) as zf:
                        for n in zf.namelist():
                            if not n.endswith('/') and any(n.lower().endswith(e) for e in ['.dat', '.txt', '.json']):
                                accs.append({"raw": zf.read(n).decode('utf-8', errors='replace'), "filename": n})
                else:
                    lines = [l.strip() for l in f_b.decode('utf-8', errors='replace').splitlines() if l.strip()]
                    for l in lines:
                        try: o = json.loads(l); accs.append(o if "guest_account_info" in o else {"raw": l})
                        except: accs.append({"raw": l})
            elif message.content.strip():
                lines = [l.strip() for l in message.content.splitlines() if l.strip()]
                for l in lines:
                    try: o = json.loads(l); accs.append(o if "guest_account_info" in o else {"raw": l})
                    except: accs.append({"raw": l})
            if not accs: return await message.reply("❌ Arquivo vazio ou inválido.")
            p_id = str(uuid.uuid4())
            db.save_product({"id": p_id, "server_id": pend["guild_id"], "name": pend["nome"], "price": pend["preco"], "delivery": "auto", "category": pend["categoria"]})
            db.add_stock_items([{"id": str(uuid.uuid4()), "product_id": p_id, "item_data": json.dumps(a), "is_sold": False} for a in accs])
            await message.reply(f"✅ **{pend['nome']}** — {len(accs)} itens adicionados ao estoque!")
    except Exception as e:
        await message.reply(f"❌ Erro: {e}")

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000), daemon=True).start()
    bot.run(TOKEN)
