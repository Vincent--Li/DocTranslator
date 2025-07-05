from datetime import datetime

from app import db


class TranslateLog(db.Model):
    """ 翻译日志表 """
    __tablename__ = 'translate_logs'

    id = db.Column(db.BigInteger, primary_key=True)
    md5_key = db.Column(db.String(100), nullable=False, unique=True)  # 原文MD5
    source = db.Column(db.Text, nullable=False)  # 原文内容
    content = db.Column(db.Text)  # 译文内容
    target_lang = db.Column(db.String(32), default='zh')
    model = db.Column(db.String(255), nullable=False)  # 使用的翻译模型
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 上下文参数
    prompt = db.Column(db.String(1024), default='')  # 实际使用的提示语
    api_url = db.Column(db.String(255), default='')  # 接口地址
    api_key = db.Column(db.String(255), default='')  # 接口密钥
    word_count = db.Column(db.Integer, default=0)  # 字数统计
    backup_model = db.Column(db.String(64), default='')  # 备用模型

    def to_dict(self):
        return {
            'id': self.id,
            'md5_key': self.md5_key,
            'source': self.source,
            'content': self.content,
            'target_lang': self.target_lang,
            'model': self.model,
            'created_at': self.created_at,
            'prompt': self.prompt,
            'api_url': self.api_url,
            'api_key': self.api_key,
            'word_count': self.word_count,
            'backup_model': self.backup_model
        }
