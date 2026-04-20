"""
知识追踪器
为每个知识点维护掌握概率，根据答题表现和时间衰减动态更新
"""
import math
from datetime import datetime, timedelta
from models.database import get_connection


# 掌握度更新参数
GAIN_RATE_BASE = 0.3       # 答对时的基础增益率
PENALTY_RATE = 0.4         # 答错时的惩罚率
RETENTION_RATE = 0.98      # 每日记忆保持率（越高遗忘越慢）
MIN_MASTERY = 0.0
MAX_MASTERY = 1.0


def get_user_mastery(user_id, knowledge_point_id):
    """获取用户对某个知识点的掌握度"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM user_mastery WHERE user_id = ? AND knowledge_point_id = ?",
            (user_id, knowledge_point_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_user_mastery(user_id, category=None):
    """获取用户所有知识点的掌握度"""
    conn = get_connection()
    try:
        if category:
            rows = conn.execute(
                """SELECT um.*, kp.name, kp.category, kp.difficulty
                   FROM user_mastery um
                   JOIN knowledge_points kp ON um.knowledge_point_id = kp.id
                   WHERE um.user_id = ? AND kp.category = ?""",
                (user_id, category)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT um.*, kp.name, kp.category, kp.difficulty
                   FROM user_mastery um
                   JOIN knowledge_points kp ON um.knowledge_point_id = kp.id
                   WHERE um.user_id = ?""",
                (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def init_mastery(user_id, knowledge_point_id, initial_level=0.0):
    """初始化用户对某知识点的掌握度"""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM user_mastery WHERE user_id = ? AND knowledge_point_id = ?",
            (user_id, knowledge_point_id)
        ).fetchone()
        if existing:
            return
        conn.execute(
            """INSERT INTO user_mastery (user_id, knowledge_point_id, mastery_level, easiness_factor)
               VALUES (?, ?, ?, 2.5)""",
            (user_id, knowledge_point_id, initial_level)
        )
        conn.commit()
    finally:
        conn.close()


def init_all_mastery(user_id, category=None):
    """为用户初始化所有知识点的掌握度"""
    conn = get_connection()
    try:
        if category:
            kps = conn.execute(
                "SELECT id FROM knowledge_points WHERE category = ?", (category,)
            ).fetchall()
        else:
            kps = conn.execute("SELECT id FROM knowledge_points").fetchall()

        for kp in kps:
            init_mastery(user_id, kp['id'], 0.0)
    finally:
        conn.close()


def apply_time_decay(user_id):
    """对用户所有知识点应用时间衰减"""
    conn = get_connection()
    try:
        now = datetime.now()
        rows = conn.execute(
            "SELECT * FROM user_mastery WHERE user_id = ?", (user_id,)
        ).fetchall()

        for row in rows:
            if row['last_practiced']:
                last = datetime.fromisoformat(row['last_practiced'])
                days_since = (now - last).days
                if days_since > 0:
                    new_level = row['mastery_level'] * (RETENTION_RATE ** days_since)
                    new_level = max(MIN_MASTERY, min(MAX_MASTERY, new_level))
                    conn.execute(
                        "UPDATE user_mastery SET mastery_level = ? WHERE id = ?",
                        (new_level, row['id'])
                    )

        conn.commit()
    finally:
        conn.close()


def update_mastery_after_answer(user_id, knowledge_point_id, is_correct):
    """
    答题后更新掌握度
    is_correct: True/False
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM user_mastery WHERE user_id = ? AND knowledge_point_id = ?",
            (user_id, knowledge_point_id)
        ).fetchone()

        if not row:
            init_mastery(user_id, knowledge_point_id, 0.3 if is_correct else 0.0)
            return

        current = row['mastery_level']

        if is_correct:
            # 答对：增益随掌握度递减
            gain = GAIN_RATE_BASE * (1 - current)
            new_level = current + gain
        else:
            # 答错：惩罚
            new_level = current - current * PENALTY_RATE

        new_level = max(MIN_MASTERY, min(MAX_MASTERY, new_level))

        conn.execute(
            """UPDATE user_mastery
               SET mastery_level = ?, last_practiced = ?
               WHERE user_id = ? AND knowledge_point_id = ?""",
            (new_level, datetime.now().isoformat(), user_id, knowledge_point_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_category_mastery(user_id, category):
    """获取用户在某个大类（词汇/语法等）的整体掌握度"""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT um.mastery_level
               FROM user_mastery um
               JOIN knowledge_points kp ON um.knowledge_point_id = kp.id
               WHERE um.user_id = ? AND kp.category = ?""",
            (user_id, category)
        ).fetchall()

        if not rows:
            return 0.0

        levels = [r['mastery_level'] for r in rows]
        return sum(levels) / len(levels)
    finally:
        conn.close()


def get_weak_points(user_id, category=None, limit=10):
    """获取薄弱知识点（掌握度最低的）"""
    conn = get_connection()
    try:
        if category:
            rows = conn.execute(
                """SELECT um.mastery_level, kp.name, kp.category, kp.id as kp_id
                   FROM user_mastery um
                   JOIN knowledge_points kp ON um.knowledge_point_id = kp.id
                   WHERE um.user_id = ? AND kp.category = ?
                   ORDER BY um.mastery_level ASC
                   LIMIT ?""",
                (user_id, category, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT um.mastery_level, kp.name, kp.category, kp.id as kp_id
                   FROM user_mastery um
                   JOIN knowledge_points kp ON um.knowledge_point_id = kp.id
                   WHERE um.user_id = ?
                   ORDER BY um.mastery_level ASC
                   LIMIT ?""",
                (user_id, limit)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
