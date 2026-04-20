"""
SM-2 间隔重复算法
管理复习调度，优化记忆效率
"""
from datetime import datetime, timedelta
from models.database import get_connection


# SM-2 参数
MIN_EF = 1.3           # 最低难度系数
DEFAULT_EF = 2.5       # 默认难度系数
QUALITY_FAIL = 3       # 质量评分阈值（>=3 表示成功回忆）


def sm2_update(easiness_factor, repetitions, interval_days, quality):
    """
    SM-2 算法核心更新逻辑

    参数:
        easiness_factor: 当前难度系数
        repetitions: 连续正确回忆次数
        interval_days: 当前复习间隔（天）
        quality: 用户回忆质量评分（0-5）
            0 - 完全不记得
            1 - 不记得，但看到答案后想起来了
            2 - 不记得，但答案似乎很熟悉
            3 - 记得很吃力，犯了严重错误
            4 - 犹豫后回忆成功
            5 - 完美回忆

    返回: (new_ef, new_repetitions, new_interval)
    """
    # 更新难度系数
    new_ef = easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ef = max(MIN_EF, new_ef)

    if quality < QUALITY_FAIL:
        # 回忆失败：重置
        new_repetitions = 0
        new_interval = 1
    else:
        # 回忆成功
        new_repetitions = repetitions + 1
        if new_repetitions == 1:
            new_interval = 1
        elif new_repetitions == 2:
            new_interval = 6
        else:
            new_interval = round(interval_days * new_ef)
        # 间隔上限：365天
        new_interval = min(new_interval, 365)

    return new_ef, new_repetitions, new_interval


def schedule_review(user_id, knowledge_point_id, quality):
    """
    根据答题质量调度下次复习

    quality: 0-5 的评分
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM user_mastery WHERE user_id = ? AND knowledge_point_id = ?",
            (user_id, knowledge_point_id)
        ).fetchone()

        if not row:
            # 首次学习
            conn.execute(
                """INSERT INTO user_mastery
                   (user_id, knowledge_point_id, easiness_factor, interval_days, repetitions,
                    last_practiced, next_review, mastery_level)
                   VALUES (?, ?, ?, 0, 0, ?, ?, ?)""",
                (user_id, knowledge_point_id, DEFAULT_EF,
                 datetime.now().isoformat(),
                 (datetime.now() + timedelta(days=1)).isoformat(),
                 0.3 if quality >= 3 else 0.0)
            )
            conn.commit()
            return

        ef = row['easiness_factor'] or DEFAULT_EF
        reps = row['repetitions'] or 0
        interval = row['interval_days'] or 0

        new_ef, new_reps, new_interval = sm2_update(ef, reps, interval, quality)

        now = datetime.now()
        next_review = now + timedelta(days=new_interval)

        conn.execute(
            """UPDATE user_mastery
               SET easiness_factor = ?, repetitions = ?, interval_days = ?,
                   last_practiced = ?, next_review = ?
               WHERE user_id = ? AND knowledge_point_id = ?""",
            (new_ef, new_reps, new_interval,
             now.isoformat(), next_review.isoformat(),
             user_id, knowledge_point_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_due_reviews(user_id, category=None):
    """获取今日需要复习的知识点"""
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        if category:
            rows = conn.execute(
                """SELECT um.*, kp.name, kp.category
                   FROM user_mastery um
                   JOIN knowledge_points kp ON um.knowledge_point_id = kp.id
                   WHERE um.user_id = ? AND kp.category = ?
                   AND (um.next_review IS NULL OR um.next_review <= ?)
                   ORDER BY um.mastery_level ASC""",
                (user_id, category, now)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT um.*, kp.name, kp.category
                   FROM user_mastery um
                   JOIN knowledge_points kp ON um.knowledge_point_id = kp.id
                   WHERE um.user_id = ?
                   AND (um.next_review IS NULL OR um.next_review <= ?)
                   ORDER BY um.mastery_level ASC""",
                (user_id, now)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_new_items_for_today(user_id, category, daily_minutes=30, items_per_minute=2):
    """
    获取今天应该新学的知识点
    根据每日可用时间和学习速度计算
    """
    conn = get_connection()
    try:
        # 获取尚未开始学习的知识点
        rows = conn.execute(
            """SELECT kp.* FROM knowledge_points kp
               WHERE kp.category = ?
               AND kp.id NOT IN (
                   SELECT knowledge_point_id FROM user_mastery
                   WHERE user_id = ? AND repetitions > 0
               )
               ORDER BY kp.difficulty ASC""",
            (category, user_id)
        ).fetchall()

        # 根据时间限制返回适当数量
        max_new = max(1, int(daily_minutes * items_per_minute * 0.3))
        return [dict(r) for r in rows[:max_new]]
    finally:
        conn.close()
