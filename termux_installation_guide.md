# Guia de Instalação do Bot de Vendas no Termux

Este guia detalha como configurar e executar o bot de vendas do Telegram em um dispositivo Android usando o aplicativo Termux.

## Pré-requisitos

1.  **Dispositivo Android**: Um smartphone ou tablet com Android.
2.  **Termux**: Baixe e instale o aplicativo Termux da [F-Droid](https://f-droid.org/packages/com.termux/) ou [Google Play Store](https://play.google.com/store/apps/details?id=com.termux).
3.  **Conexão com a Internet**: Necessária para baixar pacotes e o código do bot.
4.  **Bot de Vendas**: O arquivo `.zip` do projeto do bot que você recebeu anteriormente.

## Passos para Instalação

### 1. Configurar o Termux

Abra o Termux e atualize os pacotes:

```bash
pkg update && pkg upgrade -y
```

Instale o Python e o `git` (se ainda não estiverem instalados):

```bash
pkg install python git -y
```

### 2. Acessar o Armazenamento Interno

Para que o Termux possa acessar os arquivos do seu dispositivo (onde você colocará o `.zip` do bot e os arquivos das contas), conceda permissão de armazenamento:

```bash
termux-setup-storage
```

Isso criará uma pasta `storage` no seu diretório home do Termux, com links para suas pastas de armazenamento interno (como `shared` para o armazenamento principal).

### 3. Transferir o Projeto do Bot

Transfira o arquivo `telegram_bot_vendas.zip` (que você recebeu) para uma pasta de fácil acesso no armazenamento interno do seu Android, por exemplo, na pasta `Download`.

### 4. Extrair o Projeto no Termux

No Termux, navegue até a pasta onde você salvou o `.zip` e extraia-o:

```bash
cd storage/downloads
unzip telegram_bot_vendas.zip
```

Agora, mova a pasta extraída para o seu diretório home do Termux:

```bash
mv telegram_bot_vendas ~/
cd ~/telegram_bot_vendas
```

### 5. Instalar Dependências do Python

Dentro da pasta `telegram_bot_vendas` no Termux, instale as dependências do Python:

```bash
pip install -r requirements.txt
```

### 6. Configurar o Bot

Edite o arquivo `.env` (ou `config.py` se preferir) para inserir seu `TELEGRAM_TOKEN` e `ADMIN_ID`.

```bash
nano .env
```

Substitua `SEU_TOKEN_AQUI` e `SEU_ID_DE_ADMIN_DO_TELEGRAM` pelos valores corretos. Pressione `Ctrl+X`, depois `Y` e `Enter` para salvar e sair do `nano`.

### 7. Adicionar Arquivos de Contas

Coloque os arquivos `.zip` das contas guest que você deseja vender na pasta `~/telegram_bot_vendas/storage/accounts/`.

Você pode fazer isso copiando-os do armazenamento interno do seu Android para esta pasta usando um gerenciador de arquivos ou diretamente pelo Termux (se você já tiver os arquivos em `storage/shared/`):

```bash
cp storage/shared/caminho/para/sua_conta.zip storage/accounts/
```

### 8. Sincronizar Estoque (Opcional, mas recomendado)

Para garantir que o bot reconheça os novos arquivos `.zip` adicionados, você pode executar um script de sincronização (se disponível no futuro) ou simplesmente iniciar o bot, que fará uma verificação inicial.

### 9. Executar o Bot

Finalmente, inicie o bot:

```bash
python bot.py
```

O bot deverá iniciar e você verá a mensagem "Bot iniciado...". Ele agora estará online e pronto para receber comandos no Telegram.

## Mantendo o Bot Online

Para manter o bot funcionando em segundo plano mesmo quando você fechar o Termux, você pode usar ferramentas como `tmux` ou `nohup`.

### Usando `tmux` (Recomendado)

1.  Instale `tmux`:
    ```bash
    pkg install tmux -y
    ```
2.  Inicie uma nova sessão `tmux`:
    ```bash
    tmux new -s bot_session
    ```
3.  Navegue até a pasta do bot e execute-o:
    ```bash
    cd ~/telegram_bot_vendas
    python bot.py
    ```
4.  Para sair da sessão `tmux` sem parar o bot, pressione `Ctrl+B` e depois `D`.
5.  Para reentrar na sessão `tmux`:
    ```bash
    tmux attach -t bot_session
    ```

Com `tmux`, seu bot continuará rodando mesmo que você feche o aplicativo Termux.

---

**Autor**: Manus AI
**Data**: 03 de Fevereiro de 2026
