# Rodar SENAI Courses Advisor 24/7 no Raspberry Pi 4

Este guia descreve como implantar o **SENAI Courses Advisor** em um Raspberry Pi 4 com **Raspberry Pi OS** para execução contínua (24/7).

---

## Visão geral

O projeto é um serviço em Python que:

- Faz scraping dos cursos gratuitos de TI do SENAI SP
- Verifica alterações (novos cursos, turmas, vagas)
- Envia notificações via Telegram
- Roda como agendador: checagem diária (08:00), relatório semanal e verificação de turmas assistidas a cada N minutos

**Requisitos de rede:** acesso à internet (HTTPS para SENAI e Telegram). Nenhuma porta local é exposta.

---

## 1. Pré-requisitos no Raspberry Pi

### 1.1 Atualizar o sistema

```bash
sudo apt update && sudo apt upgrade -y
```

### 1.2 Instalar Python 3, pip e venv

O Raspberry Pi OS já inclui Python 3. Confirme a versão (recomendado 3.9+):

```bash
python3 --version
```

Instale pip e venv se necessário:

```bash
sudo apt install -y python3-pip python3-venv git
```

---

## 2. Clonar ou copiar o projeto

### Opção A: Clonar do GitHub

```bash
cd ~
git clone https://github.com/SEU_USUARIO/courses-advisor.git
cd courses-advisor
```

### Opção B: Copiar do PC (SCP, USB, etc.)

Copie a pasta do projeto (sem o `venv` e sem o `.env` com dados sensíveis) para o Pi, por exemplo em `~/courses-advisor`.

---

## 3. Ambiente virtual e dependências

### 3.1 Criar e ativar o venv

```bash
cd ~/courses-advisor
python3 -m venv venv
source venv/bin/activate
```

### 3.2 Instalar dependências

Para evitar o **Playwright** (opcional e pesado no Pi), use um `requirements` sem ele:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Se quiser omitir o Playwright no Pi, crie `requirements-pi.txt` removendo a linha do `playwright` e use:

```bash
pip install -r requirements-pi.txt
```

O scraping principal usa `requests` e `beautifulsoup4`; o Playwright só é necessário para cenários com conteúdo dinâmico.

---

## 4. Configuração (.env)

Crie o arquivo `.env` na raiz do projeto (por exemplo `~/courses-advisor/.env`):

```bash
nano .env
```

Conteúdo mínimo:

```env
# Obrigatório para notificações
TELEGRAM_BOT_TOKEN=seu_token_do_botfather
TELEGRAM_CHAT_ID=seu_chat_id

# Opcionais (valores padrão)
WEEKLY_REPORT_WEEKDAY=0
WEEKLY_REPORT_HOUR=9
WATCHED_CLASS_CHECK_INTERVAL=60
```

Salve (Ctrl+O, Enter) e saia (Ctrl+X). **Nunca faça commit do `.env`** (ele deve estar no `.gitignore`).

---

## 5. Serviço systemd (rodar 24/7 e reiniciar em falhas)

Para que o app inicie no boot e seja reiniciado em caso de falha, use um serviço systemd.

### 5.1 Instalar os arquivos de serviço

O repositório inclui os arquivos em `systemd/`. No Pi, copie-os para o systemd (ajuste o caminho se o projeto não estiver em `~/senai-pull`):

```bash
sudo cp ~/senai-pull/systemd/courses-advisor.service /etc/systemd/system/
sudo cp ~/senai-pull/systemd/courses-advisor-bot.service /etc/systemd/system/
```

Se o seu usuário ou pasta forem diferentes, edite os arquivos em `systemd/` antes de copiar, ou edite depois em `/etc/systemd/system/` (campos `User`, `WorkingDirectory`, `ExecStart`).

**Alternativa:** criar manualmente com `sudo nano /etc/systemd/system/courses-advisor.service` e colar o conteúdo abaixo (ajustando User e caminhos):

```ini
[Unit]
Description=SENAI Courses Advisor - Scraper e notificações Telegram
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/courses-advisor
ExecStart=/home/pi/courses-advisor/venv/bin/python main.py
Restart=always
RestartSec=60
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Salve e feche o editor.

### 5.2 Ativar e iniciar o serviço

```bash
sudo systemctl daemon-reload
sudo systemctl enable courses-advisor
sudo systemctl start courses-advisor
sudo systemctl status courses-advisor
```

O status deve mostrar `active (running)`. Para acompanhar os logs em tempo real:

```bash
journalctl -u courses-advisor -f
```

### 5.3 Comandos úteis

| Ação              | Comando                              |
|-------------------|--------------------------------------|
| Parar             | `sudo systemctl stop courses-advisor` |
| Reiniciar         | `sudo systemctl restart courses-advisor` |
| Desativar no boot | `sudo systemctl disable courses-advisor` |
| Ver últimas 100 linhas de log | `journalctl -u courses-advisor -n 100` |

---

## 6. Bot interativo (opcional)

Se quiser usar o **bot do Telegram** (`bot.py`) além do agendador, crie um segundo serviço:

```bash
sudo nano /etc/systemd/system/courses-advisor-bot.service
```

```ini
[Unit]
Description=SENAI Courses Advisor - Bot Telegram
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/courses-advisor
ExecStart=/home/pi/courses-advisor/venv/bin/python bot.py
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Depois:

```bash
sudo systemctl daemon-reload
sudo systemctl enable courses-advisor-bot
sudo systemctl start courses-advisor-bot
sudo systemctl status courses-advisor-bot
```

---

## 7. Rede e energia

- **Internet:** Wi-Fi ou Ethernet estável.
- **Energia:** Use a fonte oficial do Pi 4 (5V 3A). Para maior confiabilidade em quedas de energia, considere um UPS ou nobreak.

---

## 8. Resumo rápido

1. Atualizar o Pi e instalar `python3`, `python3-pip`, `python3-venv`, `git`.
2. Colocar o projeto em `~/courses-advisor` (clone ou cópia).
3. Criar venv, ativar e instalar dependências (`requirements.txt` ou `requirements-pi.txt`).
4. Criar `.env` com `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.
5. Criar e habilitar o serviço `courses-advisor.service` e iniciar com `systemctl`.
6. (Opcional) Criar e habilitar `courses-advisor-bot.service` para o bot.
7. Garantir internet e alimentação estáveis.

---

## 9. Solução de problemas

- **Serviço não inicia:** confira caminhos em `WorkingDirectory` e `ExecStart` e permissões do usuário (`User`).
- **Sem notificações:** verifique `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no `.env` e se o bot foi iniciado no Telegram.
- **Erro de rede:** teste `ping 8.8.8.8` e acesso a `https://www.sp.senai.br`.
- **Logs:** use `journalctl -u courses-advisor -f` para ver saída e erros em tempo real.
