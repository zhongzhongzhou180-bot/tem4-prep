"""
数据报告服务
生成学习数据统计和可视化数据
"""
from datetime import datetime, date, timedelta
from models.database import get_connection
from engine.knowledge_tracker import get_category_mastery, get_weak_points
from engine.path_planner import get_milestones, determine_phase, get_phase_config
from engine.dynamic_adjuster import get_study_stats


def get_dashboard_data(user_id):
    """获取仪表盘所需的所有数据"""
    conn = get_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return None

        from services.auth_service import get_user_profile
        profile = get_user_profile(user_id) or {}

        # 考试倒计时
        from datetime import datetime
        try:
            exam_date = datetime.strptime(user['exam_date'], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            exam_date = date(2026, 6, 14)
        days_left = (exam_date - datetime.now().date()).days

        # 当前阶段
        phase = determine_phase(user['exam_date'])
        phase_config = get_phase_config(phase)

        # 各维度掌握度
        vocab_mastery = get_category_mastery(user_id, 'vocabulary')
        grammar_mastery = get_category_mastery(user_id, 'grammar')
        listening_mastery = profile.get('listening_level', 0.0)
        reading_mastery = profile.get('reading_level', 0.0)
        writing_mastery = profile.get('writing_level', 0.0)

        # 学习统计
        stats = get_study_stats(user_id)

        # 薄弱点
        weak_points = get_weak_points(user_id, limit=5)

        # 里程碑
        milestones = get_milestones(user_id)

        # 今日计划
        from engine.path_planner import generate_daily_plan
        today_plan = generate_daily_plan(user_id)

        # 近7天学习趋势
        trend = _get_7day_trend(user_id)

        return {
            'user': dict(user),
            'profile': profile,
            'days_left': days_left,
            'phase': phase,
            'phase_config': phase_config,
            'mastery': {
                'vocabulary': round(vocab_mastery, 3),
                'grammar': round(grammar_mastery, 3),
                'listening': round(listening_mastery, 3),
                'reading': round(reading_mastery, 3),
                'writing': round(writing_mastery, 3),
            },
            'stats': stats,
            'weak_points': weak_points,
            'milestones': milestones,
            'today_plan': today_plan,
            'trend': trend,
        }
    finally:
        conn.close()


def _get_7day_trend(user_id):
    """获取近7天的学习趋势数据"""
    conn = get_connection()
    try:
        today = datetime.now().date()
        trend = []
        for i in range(6, -1, -1):
            d = (today - timedelta(days=i)).isoformat()
            next_d = (today - timedelta(days=i - 1)).isoformat() if i > 0 else None

            if next_d:
                row = conn.execute(
                    """SELECT
                         COUNT(*) as total,
                         SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct
                       FROM learning_records
                       WHERE user_id = ? AND created_at >= ? AND created_at < ?""",
                    (user_id, d, next_d)
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT
                         COUNT(*) as total,
                         SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct
                       FROM learning_records
                       WHERE user_id = ? AND created_at >= ?""",
                    (user_id, d)
                ).fetchone()

            total = row['total'] or 0
            correct = row['correct'] or 0
            accuracy = round(correct / total, 2) if total > 0 else 0

            weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][
                (today - timedelta(days=i)).weekday()
            ]

            trend.append({
                'date': d,
                'weekday': weekday,
                'total': total,
                'correct': correct,
                'accuracy': accuracy,
            })

        return trend
    finally:
        conn.close()
