"""
动态调整器
根据用户学习表现动态调整学习计划
"""
from datetime import datetime, date, timedelta
from models.database import get_connection
from engine.knowledge_tracker import get_category_mastery, get_weak_points, apply_time_decay
from engine.path_planner import generate_daily_plan


# 掌握度更新参数（与 knowledge_tracker 保持一致）
GAIN_RATE_BASE = 0.3
PENALTY_RATE = 0.4
MIN_MASTERY = 0.0
MAX_MASTERY = 1.0

# SM-2 参数
MIN_EF = 1.3
DEFAULT_EF = 2.5
QUALITY_FAIL = 3


def record_learning_result(user_id, question_id, user_answer, is_correct, time_spent=0):
    """
    记录学习结果并触发动态调整
    所有数据库操作在同一个连接内完成，避免 SQLite 锁竞争

    返回: dict 包含更新后的掌握度信息
    """
    conn = get_connection()
    try:
        # 获取题目信息
        question = conn.execute(
            "SELECT * FROM questions WHERE id = ?", (question_id,)
        ).fetchone()

        if not question:
            return {'error': '题目不存在'}

        kp_id = question['knowledge_point_id']

        # 1. 记录学习记录
        conn.execute(
            """INSERT INTO learning_records
               (user_id, question_id, user_answer, is_correct, time_spent)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, question_id, user_answer, 1 if is_correct else 0, time_spent)
        )

        # 2. 更新知识掌握度（内联，不调用外部函数）
        row = conn.execute(
            "SELECT * FROM user_mastery WHERE user_id = ? AND knowledge_point_id = ?",
            (user_id, kp_id)
        ).fetchone()

        if row:
            current = row['mastery_level']
            if is_correct:
                gain = GAIN_RATE_BASE * (1 - current)
                new_level = current + gain
            else:
                new_level = current - current * PENALTY_RATE
            new_level = max(MIN_MASTERY, min(MAX_MASTERY, new_level))
            conn.execute(
                "UPDATE user_mastery SET mastery_level = ?, last_practiced = ? WHERE user_id = ? AND knowledge_point_id = ?",
                (new_level, datetime.now().isoformat(), user_id, kp_id)
            )
        else:
            # 首次接触此知识点
            conn.execute(
                """INSERT INTO user_mastery (user_id, knowledge_point_id, mastery_level, easiness_factor)
                   VALUES (?, ?, ?, ?)""",
                (user_id, kp_id, 0.3 if is_correct else 0.0, DEFAULT_EF)
            )

        # 3. 更新间隔重复调度（内联 SM-2）
        mastery_row = conn.execute(
            "SELECT * FROM user_mastery WHERE user_id = ? AND knowledge_point_id = ?",
            (user_id, kp_id)
        ).fetchone()

        if mastery_row:
            ef = mastery_row['easiness_factor'] or DEFAULT_EF
            reps = mastery_row['repetitions'] or 0
            interval = mastery_row['interval_days'] or 0
            quality = 4 if is_correct else 2  # 答错=2（不是完全不记得），避免EF急剧下降

            # SM-2 更新
            new_ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            new_ef = max(MIN_EF, new_ef)

            if quality < QUALITY_FAIL:
                new_reps = 0
                new_interval = 1
            else:
                new_reps = reps + 1
                if new_reps == 1:
                    new_interval = 1
                elif new_reps == 2:
                    new_interval = 6
                else:
                    new_interval = round(interval * new_ef)
                # 间隔上限：365天（超过一年没必要再复习了）
                new_interval = min(new_interval, 365)

            now = datetime.now()
            next_review = now + timedelta(days=new_interval)

            conn.execute(
                """UPDATE user_mastery
                   SET easiness_factor = ?, repetitions = ?, interval_days = ?,
                       last_practiced = ?, next_review = ?
                   WHERE user_id = ? AND knowledge_point_id = ?""",
                (new_ef, new_reps, new_interval,
                 now.isoformat(), next_review.isoformat(),
                 user_id, kp_id)
            )

        # 4. 更新用户画像（内联）
        _update_profile_inline(conn, user_id)

        conn.commit()

        # 5. 获取更新后的掌握度
        kp_row = conn.execute("SELECT category FROM knowledge_points WHERE id = ?", (kp_id,)).fetchone()
        category = kp_row['category'] if kp_row else 'vocabulary'

        new_mastery = get_category_mastery(user_id, category)

        return {
            'is_correct': is_correct,
            'knowledge_point_id': kp_id,
            'new_category_mastery': round(new_mastery, 3),
        }
    finally:
        conn.close()


def _update_profile_inline(conn, user_id):
    """在已有连接内更新用户画像"""
    # 计算各维度掌握度
    vocab_rows = conn.execute(
        """SELECT um.mastery_level FROM user_mastery um
           JOIN knowledge_points kp ON um.knowledge_point_id = kp.id
           WHERE um.user_id = ? AND kp.category = 'vocabulary'""",
        (user_id,)
    ).fetchall()
    vocab_m = sum(r['mastery_level'] for r in vocab_rows) / len(vocab_rows) if vocab_rows else 0.0

    grammar_rows = conn.execute(
        """SELECT um.mastery_level FROM user_mastery um
           JOIN knowledge_points kp ON um.knowledge_point_id = kp.id
           WHERE um.user_id = ? AND kp.category = 'grammar'""",
        (user_id,)
    ).fetchall()
    grammar_m = sum(r['mastery_level'] for r in grammar_rows) / len(grammar_rows) if grammar_rows else 0.0

    # 估算分数
    estimated_score = min(100, int(vocab_m * 10 + grammar_m * 10 + 40))

    # 更新连续学习天数
    profile = conn.execute(
        "SELECT * FROM user_profile WHERE user_id = ?", (user_id,)
    ).fetchone()

    streak = 0
    if profile and profile['last_study_date']:
        last = datetime.fromisoformat(profile['last_study_date']).date()
        today = datetime.now().date()
        if last == today - timedelta(days=1):
            streak = (profile['streak_days'] or 0) + 1
        elif last == today:
            streak = profile['streak_days'] or 0
        else:
            streak = 1
    else:
        streak = 1

    total_questions = (profile['total_questions'] or 0) + 1

    conn.execute(
        """UPDATE user_profile
           SET vocabulary_level = ?, grammar_level = ?, estimated_score = ?,
               total_questions = ?, streak_days = ?, last_study_date = ?,
               updated_at = ?
           WHERE user_id = ?""",
        (round(vocab_m, 3), round(grammar_m, 3), estimated_score,
         total_questions, streak, datetime.now().date().isoformat(),
         datetime.now().isoformat(), user_id)
    )


def check_and_adjust(user_id):
    """
    检查是否需要动态调整学习计划
    在每次学习会话结束时调用
    """
    conn = get_connection()
    try:
        three_days_ago = (datetime.now() - timedelta(days=3)).isoformat()
        recent_records = conn.execute(
            """SELECT lr.is_correct, kp.category
               FROM learning_records lr
               JOIN questions q ON lr.question_id = q.id
               JOIN knowledge_points kp ON q.knowledge_point_id = kp.id
               WHERE lr.user_id = ? AND lr.created_at >= ?""",
            (user_id, three_days_ago)
        ).fetchall()

        if len(recent_records) < 5:
            return {'needs_adjustment': False, 'reason': '数据不足，暂不调整'}

        adjustments = []
        category_stats = {}

        for r in recent_records:
            cat = r['category']
            if cat not in category_stats:
                category_stats[cat] = {'correct': 0, 'total': 0}
            category_stats[cat]['total'] += 1
            if r['is_correct']:
                category_stats[cat]['correct'] += 1

        for cat, stats in category_stats.items():
            accuracy = stats['correct'] / stats['total']
            if accuracy < 0.5 and stats['total'] >= 5:
                adjustments.append({
                    'category': cat,
                    'action': 'increase',
                    'reason': f"近3天{cat}正确率仅{accuracy:.0%}，建议增加练习",
                })
            elif accuracy > 0.85 and stats['total'] >= 10:
                adjustments.append({
                    'category': cat,
                    'action': 'decrease',
                    'reason': f"近3天{cat}正确率达{accuracy:.0%}，可适当减少时间",
                })

        needs_adjustment = len(adjustments) > 0

        if needs_adjustment:
            new_plan = generate_daily_plan(user_id)
            conn.execute(
                """UPDATE study_plans SET is_adjusted = 1
                   WHERE user_id = ? AND plan_date = ?""",
                (user_id, datetime.now().date().isoformat())
            )
            conn.commit()

        return {
            'needs_adjustment': needs_adjustment,
            'adjustments': adjustments,
            'category_stats': {k: {'accuracy': round(v['correct']/v['total'], 2), 'total': v['total']}
                              for k, v in category_stats.items()},
        }
    finally:
        conn.close()


def get_study_stats(user_id):
    """获取用户学习统计"""
    conn = get_connection()
    try:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM learning_records WHERE user_id = ?", (user_id,)
        ).fetchone()['cnt']

        correct = conn.execute(
            "SELECT COUNT(*) as cnt FROM learning_records WHERE user_id = ? AND is_correct = 1",
            (user_id,)
        ).fetchone()['cnt']

        today = datetime.now().isoformat()  # 与 created_at 格式一致（本地时间）
        today_total = conn.execute(
            "SELECT COUNT(*) as cnt FROM learning_records WHERE user_id = ? AND DATE(created_at) = DATE(?)",
            (user_id, today)
        ).fetchone()['cnt']

        today_correct = conn.execute(
            "SELECT COUNT(*) as cnt FROM learning_records WHERE user_id = ? AND is_correct = 1 AND DATE(created_at) = DATE(?)",
            (user_id, today)
        ).fetchone()['cnt']

        study_days = conn.execute(
            "SELECT COUNT(DISTINCT DATE(created_at)) as cnt FROM learning_records WHERE user_id = ?",
            (user_id,)
        ).fetchone()['cnt']

        accuracy = correct / total if total > 0 else 0
        today_accuracy = today_correct / today_total if today_total > 0 else 0

        return {
            'total_questions': total,
            'correct_questions': correct,
            'accuracy': round(accuracy, 3),
            'today_questions': today_total,
            'today_correct': today_correct,
            'today_accuracy': round(today_accuracy, 3),
            'study_days': study_days,
        }
    finally:
        conn.close()
