"""
用户认证服务
处理注册、登录、密码哈希
"""
import hashlib
import os
from models.database import get_connection


def hash_password(password):
    """简单密码哈希（生产环境应使用 bcrypt）"""
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password, password_hash):
    """验证密码"""
    salt, hashed = password_hash.split(':')
    check = hashlib.sha256((password + salt).encode()).hexdigest()
    return check == hashed


def register_user(username, password, email=None, exam_date=None, daily_minutes=30, target_score=60):
    """注册新用户"""
    conn = get_connection()
    try:
        # 检查用户名是否已存在
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            return None, "用户名已存在"

        pw_hash = hash_password(password)
        if not exam_date:
            from config import Config
            exam_date = Config.DEFAULT_EXAM_DATE

        cursor = conn.execute(
            """INSERT INTO users (username, password_hash, email, exam_date, daily_study_minutes, target_score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, pw_hash, email, exam_date, daily_minutes, target_score)
        )
        user_id = cursor.lastrowid

        # 创建用户能力画像
        conn.execute(
            """INSERT INTO user_profile (user_id) VALUES (?)""",
            (user_id,)
        )

        conn.commit()
        return user_id, "注册成功"
    finally:
        conn.close()


def authenticate_user(username, password):
    """验证用户登录"""
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if not user:
            return None, "用户名不存在"

        if not verify_password(password, user['password_hash']):
            return None, "密码错误"

        # 更新最后登录时间
        from datetime import datetime
        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now().isoformat(), user['id'])
        )
        conn.commit()

        return dict(user), "登录成功"
    finally:
        conn.close()


def get_user_by_id(user_id):
    """根据ID获取用户信息"""
    conn = get_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(user) if user else None
    finally:
        conn.close()


def get_user_profile(user_id):
    """获取用户能力画像"""
    conn = get_connection()
    try:
        profile = conn.execute(
            "SELECT * FROM user_profile WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(profile) if profile else None
    finally:
        conn.close()


def update_user_profile(user_id, **kwargs):
    """更新用户能力画像"""
    if not kwargs:
        return
    conn = get_connection()
    try:
        from datetime import datetime
        kwargs['updated_at'] = datetime.now().isoformat()
        sets = ', '.join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [user_id]
        conn.execute(f"UPDATE user_profile SET {sets} WHERE user_id = ?", values)
        conn.commit()
    finally:
        conn.close()
