# Инструкции по деплою на PythonAnywhere

## 1. Создание аккаунта
1. Зарегистрируйтесь на [PythonAnywhere](https://www.pythonanywhere.com/)
2. Выберите бесплатный план (Beginner)

## 2. Настройка веб-приложения
1. В панели управления перейдите в раздел "Web"
2. Нажмите "Add a new web app"
3. Выберите домен (ваш_логин.pythonanywhere.com)
4. Выберите "Django" и последнюю версию Python
5. В настройках укажите:
   - Source code: /home/YOUR_USERNAME/app
   - Working directory: /home/YOUR_USERNAME/app
   - WSGI configuration file: /var/www/YOUR_USERNAME_pythonanywhere_com_wsgi.py

## 3. Настройка виртуального окружения
1. В консоли PythonAnywhere выполните:
```bash
cd ~/app
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 4. Настройка базы данных
1. В консоли выполните:
```bash
python manage.py migrate
python manage.py createsuperuser
```

## 5. Настройка статических файлов
1. В настройках веб-приложения укажите:
   - Static files: /home/YOUR_USERNAME/app/static
   - Media files: /home/YOUR_USERNAME/app/media

## 6. Настройка переменных окружения
1. В настройках веб-приложения добавьте:
   - DJANGO_SETTINGS_MODULE=certification_system.settings
   - DEBUG=False
   - ALLOWED_HOSTS=ваш_домен.pythonanywhere.com

## 7. Перезапуск приложения
1. В панели управления нажмите "Reload" для вашего веб-приложения

## Примечания
- Замените YOUR_USERNAME на ваше имя пользователя на PythonAnywhere
- Замените ваш_домен на ваш домен на PythonAnywhere
- В production настройках обязательно установите DEBUG=False
- Настройте SECRET_KEY в production настройках 