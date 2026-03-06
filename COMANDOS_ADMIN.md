# 🛡️ Comandos de Administrador

## 👑 Dono: @breonnmodz (ID: 7981212751)

O bot reconhece você como dono tanto pelo **ID** quanto pelo **username @breonnmodz**.

---

## 📋 Comandos Disponíveis

### 1️⃣ `/confirmar` - Confirmar Pagamento
Usado para confirmar um pagamento e adicionar saldo à conta do usuário.

**Formato:**
```
/confirmar <@usuario ou ID> <valor>
```

**Exemplos:**
```
/confirmar @joao 50
/confirmar 123456789 100.50
```

**O que faz:**
- ✅ Adiciona o valor ao saldo do usuário
- 📨 Envia notificação automática para o usuário
- 💰 Mostra o saldo atualizado

---

### 2️⃣ `/addsaldo` - Adicionar/Remover Saldo
Usado para adicionar ou remover saldo manualmente (sem confirmação de pagamento).

**Formato:**
```
/addsaldo <@usuario ou ID> <valor>
```

**Exemplos:**
```
/addsaldo @joao 50          (adiciona R$ 50)
/addsaldo 123456789 100.50  (adiciona R$ 100.50)
/addsaldo @joao -20         (remove R$ 20)
```

**O que faz:**
- ➕ Adiciona saldo (valores positivos)
- ➖ Remove saldo (valores negativos)
- 📨 Envia notificação automática para o usuário
- 💰 Mostra o saldo atualizado

---

### 3️⃣ `/promover` - Promover Admin
Usado para promover um usuário a administrador.

**Formato:**
```
/promover <@usuario ou ID>
```

**Exemplos:**
```
/promover @maria
/promover 987654321
```

**O que faz:**
- 👑 Concede permissões de admin ao usuário
- ✅ Usuário promovido pode usar `/confirmar` e `/addsaldo`
- ⚠️ **Apenas o dono pode promover admins**

---

### 4️⃣ `/sync` - Sincronizar Estoque
Usado para sincronizar arquivos da pasta `storage/accounts` com o banco de dados.

**Formato:**
```
/sync
```

**O que faz:**
- 🔄 Detecta novos arquivos na pasta de estoque
- 📦 Adiciona ao banco de dados automaticamente
- 📊 Mostra quantos arquivos foram adicionados

---

### 5️⃣ `/organizar` - Organizar Estoque (ZIP/DAT)
Converte arquivos `.dat` para `.zip` e renomeia tudo para o padrão `guest1.zip`, `guest2.zip`, etc.

**Formato:**
```
/organizar
```

**O que faz:**
- 📦 Converte automaticamente arquivos `.dat` em arquivos `.zip` compactados
- 🏷️ Renomeia todos os arquivos de estoque para uma ordem numérica (`guest1`, `guest2`, ...)
- 🔄 Sincroniza automaticamente o banco de dados com os novos nomes
- ✨ Deixa o estoque limpo e padronizado

---

### 5️⃣ `/meuid` - Ver Informações
Mostra suas informações e status no bot.

**Formato:**
```
/meuid
```

**O que mostra:**
- 🆔 Seu ID do Telegram
- 👤 Seu username
- 👑 Seu status (Dono/Admin/Usuário)

---

## 🔐 Sistema de Segurança

### Verificação de Dono
O bot reconhece você como dono de **duas formas**:
1. **Por ID**: `7981212751`
2. **Por Username**: `@breonnmodz`

Isso significa que mesmo se seu ID mudar (criar nova conta), o bot ainda te reconhece pelo username.

### Verificação de Admin
- ✅ Dono tem acesso total automaticamente
- ✅ Admins promovidos podem usar `/confirmar` e `/addsaldo`
- ❌ Apenas o dono pode usar `/promover` e `/sync`

---

## 🐛 Solução de Problemas

### "Usuário não encontrado"
O usuário precisa ter dado `/start` no bot pelo menos uma vez.

### "Acesso Negado"
Verifique se você está usando o username correto (@breonnmodz) ou se seu ID está correto.

### "Valor inválido"
Use apenas números. Exemplos válidos: `50`, `100.50`, `25,00`

---

## 📝 Notas Importantes

1. **Valores decimais**: Use ponto (`.`) ou vírgula (`,`) como separador decimal
2. **Username**: Pode usar com ou sem `@` (ex: `@joao` ou `joao`)
3. **Notificações**: O bot tenta notificar o usuário automaticamente, mas se ele bloqueou o bot, a notificação não será enviada
4. **Saldo negativo**: É possível ter saldo negativo usando `/addsaldo` com valor negativo

---

### 6️⃣ `/cupom` - Criar Cupom de Saldo
Cria um código que os usuários podem resgatar para ganhar saldo.

**Formato:**
```
/cupom <CODIGO> <valor> <usos>
```

**Exemplo:**
```
/cupom NATAL10 10 50
```
(Cria o cupom NATAL10 que dá R$ 10 para as primeiras 50 pessoas)

---

## 🆘 Suporte

Para dúvidas ou problemas, entre em contato com @breonnmodz
