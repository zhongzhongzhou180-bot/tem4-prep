"""
练习服务
处理题目获取、答题提交、练习会话管理
"""
import json
from models.database import get_connection
from engine.knowledge_tracker import get_all_user_mastery, get_category_mastery


def get_questions_for_practice(user_id, category, count=10, mode='mixed'):
    """
    获取练习题目

    mode:
        'mixed' - 新学+复习混合
        'review' - 仅复习
        'new' - 仅新学
        'weak' - 薄弱点专项
    """
    conn = get_connection()
    try:
        if mode == 'weak':
            # 薄弱点模式：优先选择掌握度低的知识点的题目
            from engine.knowledge_tracker import get_weak_points
            weak_points = get_weak_points(user_id, category, limit=5)
            if weak_points:
                kp_ids = [wp['kp_id'] for wp in weak_points]
                placeholders = ','.join('?' * len(kp_ids))
                questions = conn.execute(
                    f"""SELECT q.*, kp.name as kp_name, kp.category
                        FROM questions q
                        JOIN knowledge_points kp ON q.knowledge_point_id = kp.id
                        WHERE q.knowledge_point_id IN ({placeholders})
                        ORDER BY RANDOM()
                        LIMIT ?""",
                    (*kp_ids, count)
                ).fetchall()
            else:
                questions = _get_random_questions(conn, category, count)
        elif mode == 'review':
            from engine.spaced_repetition import get_due_reviews
            due = get_due_reviews(user_id, category)
            if due:
                kp_ids = [d['knowledge_point_id'] for d in due[:count]]
                placeholders = ','.join('?' * len(kp_ids))
                questions = conn.execute(
                    f"""SELECT q.*, kp.name as kp_name, kp.category
                        FROM questions q
                        JOIN knowledge_points kp ON q.knowledge_point_id = kp.id
                        WHERE q.knowledge_point_id IN ({placeholders})
                        ORDER BY RANDOM()
                        LIMIT ?""",
                    (*kp_ids, count)
                ).fetchall()
            else:
                questions = _get_random_questions(conn, category, count)
        else:
            # 混合模式
            questions = _get_smart_questions(conn, user_id, category, count)

        return [dict(q) for q in questions]
    finally:
        conn.close()


def _get_random_questions(conn, category, count):
    """获取随机题目"""
    rows = conn.execute(
        """SELECT q.*, kp.name as kp_name, kp.category
           FROM questions q
           JOIN knowledge_points kp ON q.knowledge_point_id = kp.id
           WHERE kp.category = ?
           ORDER BY RANDOM()
           LIMIT ?""",
        (category, count)
    ).fetchall()
    return rows


def _get_smart_questions(conn, user_id, category, count):
    """智能选题：平衡新题和复习题"""
    # 60% 复习题 + 40% 新题
    review_count = int(count * 0.6)
    new_count = count - review_count

    # 获取已掌握的知识点（用于复习）
    mastered = conn.execute(
        """SELECT um.knowledge_point_id
           FROM user_mastery um
           JOIN knowledge_points kp ON um.knowledge_point_id = kp.id
           WHERE um.user_id = ? AND kp.category = ? AND um.mastery_level > 0.1""",
        (user_id, category)
    ).fetchall()

    # 获取未掌握的知识点（用于新学）
    unmastered = conn.execute(
        """SELECT kp.id
           FROM knowledge_points kp
           WHERE kp.category = ?
           AND kp.id NOT IN (
               SELECT knowledge_point_id FROM user_mastery
               WHERE user_id = ? AND mastery_level > 0.1
           )""",
        (category, user_id)
    ).fetchall()

    questions = []

    if mastered:
        kp_ids = [m['knowledge_point_id'] for m in mastered]
        placeholders = ','.join('?' * len(kp_ids))
        review_qs = conn.execute(
            f"""SELECT q.*, kp.name as kp_name, kp.category
                FROM questions q
                JOIN knowledge_points kp ON q.knowledge_point_id = kp.id
                WHERE q.knowledge_point_id IN ({placeholders})
                ORDER BY RANDOM()
                LIMIT ?""",
            (*kp_ids, review_count)
        ).fetchall()
        questions.extend(review_qs)

    if unmastered:
        kp_ids = [u['id'] for u in unmastered]
        placeholders = ','.join('?' * len(kp_ids))
        new_qs = conn.execute(
            f"""SELECT q.*, kp.name as kp_name, kp.category
                FROM questions q
                JOIN knowledge_points kp ON q.knowledge_point_id = kp.id
                WHERE q.knowledge_point_id IN ({placeholders})
                ORDER BY RANDOM()
                LIMIT ?""",
            (*kp_ids, new_count)
        ).fetchall()
        questions.extend(new_qs)

    # 如果不够，补充随机题
    if len(questions) < count:
        remaining = count - len(questions)
        extra = _get_random_questions(conn, category, remaining)
        questions.extend(extra)

    return questions[:count]


def get_question_by_id(question_id):
    """获取单个题目详情"""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT q.*, kp.name as kp_name, kp.category
               FROM questions q
               JOIN knowledge_points kp ON q.knowledge_point_id = kp.id
               WHERE q.id = ?""",
            (question_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_practice_history(user_id, category=None, limit=20):
    """获取练习历史"""
    conn = get_connection()
    try:
        if category:
            rows = conn.execute(
                """SELECT lr.*, q.content, q.correct_answer, q.explanation, kp.name as kp_name
                   FROM learning_records lr
                   JOIN questions q ON lr.question_id = q.id
                   JOIN knowledge_points kp ON q.knowledge_point_id = kp.id
                   WHERE lr.user_id = ? AND kp.category = ?
                   ORDER BY lr.created_at DESC
                   LIMIT ?""",
                (user_id, category, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT lr.*, q.content, q.correct_answer, q.explanation, kp.name as kp_name, kp.category
                   FROM learning_records lr
                   JOIN questions q ON lr.question_id = q.id
                   JOIN knowledge_points kp ON q.knowledge_point_id = kp.id
                   WHERE lr.user_id = ?
                   ORDER BY lr.created_at DESC
                   LIMIT ?""",
                (user_id, limit)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
