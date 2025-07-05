# app/models/__init__.py
from .user import User
from .customer import Customer
from .setting import Setting
from .send_code import  SendCode
from .translateLog import TranslateLog
__all__ = ['User', 'Customer', 'Setting','SendCode','TranslateLog']

