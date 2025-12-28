# Автоматический деплой

Этот проект использует GitHub Actions для автоматического деплоя на сервер при создании нового тега.

## Настройка

### 1. Настройка SSH ключей

На вашем локальном компьютере:

```bash
# Создайте SSH ключ специально для деплоя (без пароля)
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy_key -N ""
```

На сервере (158.160.93.142):

```bash
# Добавьте публичный ключ в authorized_keys
cat ~/.ssh/github_deploy_key.pub | ssh brief_admin@158.160.93.142 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

# Или вручную скопируйте содержимое github_deploy_key.pub в ~/.ssh/authorized_keys на сервере
```

### 2. Настройка GitHub Secrets

Перейдите в настройки вашего репозитория на GitHub:
`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

Добавьте следующие секреты:

- **SSH_HOST**: `158.160.93.142`
- **SSH_USERNAME**: `brief_admin`
- **SSH_PRIVATE_KEY**: содержимое файла `~/.ssh/github_deploy_key` (приватный ключ)
- **SSH_PORT**: `22` (опционально, по умолчанию 22)

Чтобы получить приватный ключ:
```bash
cat ~/.ssh/github_deploy_key
```

Скопируйте весь вывод, включая `-----BEGIN OPENSSH PRIVATE KEY-----` и `-----END OPENSSH PRIVATE KEY-----`.

### 3. Настройка сервера

На сервере убедитесь, что:

1. Установлен tmux:
```bash
tmux -V  # Должно показать версию tmux
# Если нет: sudo apt install tmux
```

2. Репозиторий находится в `~/summary_bot`:
```bash
cd ~/summary_bot
git remote -v  # Должен показать ваш GitHub репозиторий
```

3. Бот запущен в tmux сессии `br`:
```bash
# Если ещё не запущен, создайте сессию:
tmux new -s br
cd ~/summary_bot
./run.sh

# Отключитесь от сессии (бот продолжит работать):
# Нажмите Ctrl+B, затем D
```

### 4. Создание деплоя

Теперь для деплоя просто создайте тег и запушьте его:

```bash
# Создайте тег с версией
git tag v1.0.0

# Запушьте тег на GitHub
git push origin v1.0.0
```

GitHub Actions автоматически:
1. Подключится к серверу по SSH
2. Перейдёт в директорию `~/summary_bot`
3. Выполнит `git checkout` на нужный тег
4. Запустит `deploy.sh`, который:
   - Обновит зависимости
   - Проверит конфигурацию
   - Перезапустит бота в tmux сессии `br`
   - Покажет последние строки вывода

### 5. Проверка статуса деплоя

Перейдите в `Actions` вкладку вашего репозитория на GitHub, чтобы увидеть статус деплоя.

На сервере можете проверить:
```bash
# Посмотреть список tmux сессий
tmux ls

# Подключиться к сессии с ботом
tmux attach -t br

# Посмотреть вывод без подключения
tmux capture-pane -t br -p | tail -30
```

## Ручной деплой

Если нужно выполнить деплой вручную (например, для тестирования):

```bash
ssh brief_admin@158.160.93.142
cd ~/summary_bot
git pull
./deploy.sh
```

Или старым способом через tmux:
```bash
ssh brief_admin@158.160.93.142
tmux attach -t br
# Внутри tmux:
cd ~/summary_bot
git pull
# Остановить бота: Ctrl+C
./run.sh
# Отключиться от сессии: Ctrl+B, затем D
```

## Откат к предыдущей версии

Если что-то пошло не так:

```bash
ssh brief_admin@158.160.93.142
cd ~/summary_bot
git tag  # Посмотреть доступные версии
git checkout v1.0.0  # Откатиться на предыдущий тег
./deploy.sh
```

## Управление tmux сессией

Полезные команды для работы с tmux:

```bash
# Список всех сессий
tmux ls

# Подключиться к сессии
tmux attach -t br

# Отключиться от сессии (не останавливая бота)
Ctrl+B, затем D

# Остановить бота в сессии
tmux send-keys -t br C-c

# Запустить бота в существующей сессии
tmux send-keys -t br "cd ~/summary_bot && ./run.sh" Enter

# Посмотреть вывод сессии
tmux capture-pane -t br -p | tail -50

# Убить сессию (останавливает бота)
tmux kill-session -t br
```

## Troubleshooting

### Деплой не запускается

- Проверьте, что тег имеет формат `v*.*.*` (например, v1.0.0)
- Убедитесь, что все секреты настроены в GitHub

### Ошибка подключения по SSH

- Проверьте, что публичный ключ добавлен в `~/.ssh/authorized_keys` на сервере
- Проверьте, что приватный ключ правильно скопирован в GitHub Secrets

### Бот не запускается после деплоя

- Подключитесь к tmux: `tmux attach -t br`
- Посмотрите ошибки в выводе
- Проверьте конфигурацию: `python check_config.py`
- Проверьте виртуальное окружение: `which python` (должно быть в venv)

### Сессия tmux не найдена

- Создайте новую сессию: `tmux new -s br`
- Запустите бота: `cd ~/summary_bot && ./run.sh`
- Отключитесь: `Ctrl+B, затем D`
