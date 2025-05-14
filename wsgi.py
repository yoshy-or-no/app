import os
import sys

# Add your project directory to the sys.path
path = '/home/YOUR_USERNAME/app'
if path not in sys.path:
    sys.path.append(path)

# Set the Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'certification_system.settings'

# Activate your virtual environment
activate_this = '/home/YOUR_USERNAME/app/venv/bin/activate_this.py'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

# Import Django's WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application() 