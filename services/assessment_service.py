"""
水平诊断服务
通过测试评估用户初始能力水平
"""
import random
from models.database import get_connection
from engine.knowledge_tracker import init_mastery, init_all_mastery, update_mastery_after_answer
from engine.path_planner import generate_daily_plan


def generate_assessment(category='vocabulary', count=10):
    """
    生成水平诊断测试题目
    从各难度梯度均匀抽样
    """
    conn = get_connection()
    try:
        # 按难度分层抽样
        easy = conn.execute(
            """SELECT q.*, kp.name as kp_name
               FROM questions q
               JOIN knowledge_points kp ON q.knowledge_point_id = kp.id
               WHERE kp.category = ? AND q.difficulty < 0.4
               ORDER BY RANDOM() LIMIT ?""",
            (category, count // 3)
        ).fetchall()

        medium = conn.execute(
            """SELECT q.*, kp.name as kp_name
               FROM questions q
               JOIN knowledge_points kp ON q.knowledge_point_id = kp.id
               WHERE kp.category = ? AND q.difficulty >= 0.4 AND q.difficulty < 0.7
               ORDER BY RANDOM() LIMIT ?""",
            (category, count // 3)
        ).fetchall()

        hard = conn.execute(
            """SELECT q.*, kp.name as kp_name
               FROM questions q
               JOIN knowledge_points kp ON q.knowledge_point_id = kp.id
               WHERE kp.category = ? AND q.difficulty >= 0.7
               ORDER BY RANDOM() LIMIT ?""",
            (category, count - len(easy) - len(medium))
        ).fetchall()

        questions = [dict(q) for q in easy + medium + hard]
        random.shuffle(questions)
        return questions
    finally:
        conn.close()


def submit_assessment(user_id, answers):
    """
    提交诊断测试结果

    answers: list of dict [{question_id: int, user_answer: str, is_correct: bool}]

    返回: dict 包含各维度评估结果
    """
    conn = get_connection()
    try:
        # 初始化所有知识点掌握度
        init_all_mastery(user_id)

        # 按类别统计
        category_results = {}

        for ans in answers:
            q_id = ans['question_id']
            is_correct = ans['is_correct']

            # 获取题目信息
            question = conn.execute(
                """SELECT q.*, kp.category, kp.id as kp_id
                   FROM questions q
                   JOIN knowledge_points kp ON q.knowledge_point_id = kp.id
                   WHERE q.id = ?""",
                (q_id,)
            ).fetchone()

            if not question:
                continue

            category = question['category']
            kp_id = question['kp_id']

            if category not in category_results:
                category_results[category] = {'correct': 0, 'total': 0}

            category_results[category]['total'] += 1
            if is_correct:
                category_results[category]['correct'] += 1

            # 更新掌握度
            update_mastery_after_answer(user_id, kp_id, is_correct)

        # 计算各维度掌握度
        from engine.knowledge_tracker import get_category_mastery
        profile = {}
        for cat in ['vocabulary', 'grammar']:
            accuracy = category_results.get(cat, {})
            total = accuracy.get('total', 0)
            correct = accuracy.get('correct', 0)
            raw_score = correct / total if total > 0 else 0.3

            # 使用知识追踪的综合掌握度（更准确）
            tracked_mastery = get_category_mastery(user_id, cat)
            # 综合诊断测试结果和追踪结果
            final_mastery = (raw_score * 0.4 + tracked_mastery * 0.6)
            final_mastery = max(0.0, min(1.0, final_mastery))

            profile[cat] = round(final_mastery, 3)

        # 更新用户画像
        from services.auth_service import update_user_profile
        estimated_score = int(profile.get('vocabulary', 0) * 10 + profile.get('grammar', 0) * 10 + 40)
        update_user_profile(
            user_id,
            vocabulary_level=profile.get('vocabulary', 0),
            grammar_level=profile.get('grammar', 0),
            estimated_score=min(100, estimated_score),
        )

        # 生成初始学习计划
        plan = generate_daily_plan(user_id)

        return {
            'profile': profile,
            'category_results': category_results,
            'estimated_score': min(100, estimated_score),
            'plan_generated': plan is not None,
        }
    finally:
        conn.close()
