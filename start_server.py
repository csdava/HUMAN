import os
import sys
os.chdir('D:/User/Documents/PycharmProjects/human')
sys.path.insert(0, 'D:/User/Documents/PycharmProjects/human')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_management.settings')
import django
django.setup()
from django.core.management import execute_from_command_line
execute_from_command_line(['manage.py', 'runserver', '--noreload'])