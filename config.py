import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'tem4-prep-dev-key-2026')
    # 云平台兼容：优先使用环境变量，否则使用本地 data 目录
    DATABASE = os.environ.get('DATABASE_URL', os.path.join(BASE_DIR, 'data', 'tem4.db'))
    # 默认考试日期：2026年6月14日
    DEFAULT_EXAM_DATE = '2026-06-14'
