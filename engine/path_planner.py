"""
学习路径规划器
基于知识图谱、考试倒计时和用户能力，生成并管理学习计划
"""
from datetime import datetime, timedelta, date
from models.database import get_connection
from engine.knowledge_tracker import get_category_mastery, get_all_user_mastery


def determine_phase(exam_date_str):
    """
    根据考试日期确定当前备考阶段
    返回: 'foundation' / 'reinforcement' / 'sprint'
    """
    try:
        exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        exam_date = date(2026, 6, 14)

    days_left = (exam_date - datetime.now().date()).days

    if days_left > 90:
        return 'foundation'       # 基础阶段：> 3个月
    elif days_left > 30:
        return 'reinforcement'    # 强化阶段：1-3个月
    else:
        return 'sprint'           # 冲刺阶段：< 1个月


def get_phase_config(phase):
    """获取各阶段配置"""
    configs = {
        'foundation': {
            'name': '基础阶段',
            'description': '系统学习所有知识点，建立知识框架',
            'vocab_ratio': 0.5,       # 词汇占比
            'grammar_ratio': 0.5,     # 语法占比
            'new_ratio': 0.6,         # 新学内容占比
            'review_ratio': 0.4,      # 复习占比
            'color': '#7CB342',
        },
        'reinforcement': {
            'name': '强化阶段',
            'description': '针对薄弱点专项突破，大量练习',
            'vocab_ratio': 0.4,
            'grammar_ratio': 0.6,
            'new_ratio': 0.2,
            'review_ratio': 0.8,
            'color': '#FFB74D',
        },
        'sprint': {
            'name': '冲刺阶段',
            'description': '模拟考试、限时训练、查漏补缺',
            'vocab_ratio': 0.3,
            'grammar_ratio': 0.7,
            'new_ratio': 0.1,
            'review_ratio': 0.9,
            'color': '#EF5350',
        }
    }
    return configs.get(phase, configs['foundation'])


def generate_daily_plan(user_id, plan_date=None):
    """
    为用户生成每日学习计划

    返回: dict 包含今日任务列表
    """
    conn = get_connection()
    try:
        # 获取用户信息
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return None

        if not plan_date:
            plan_date = datetime.now().date().isoformat()

        daily_minutes = user['daily_study_minutes'] or 30
        exam_date = user['exam_date']
        phase = determine_phase(exam_date)
        phase_config = get_phase_config(phase)

        # 更新用户当前阶段
        conn.execute("UPDATE users SET current_phase = ? WHERE id = ?", (phase, user_id))
        conn.commit()

        # 获取各维度掌握度
        vocab_mastery = get_category_mastery(user_id, 'vocabulary')
        grammar_mastery = get_category_mastery(user_id, 'grammar')

        # 计算各模块时间分配
        vocab_time = int(daily_minutes * phase_config['vocab_ratio'])
        grammar_time = daily_minutes - vocab_time

        # 构建任务列表
        tasks = []

        # 词汇任务
        if vocab_time > 0:
            vocab_task = build_category_task(
                user_id, 'vocabulary', vocab_time, vocab_mastery, phase_config
            )
            tasks.extend(vocab_task)

        # 语法任务
        if grammar_time > 0:
            grammar_task = build_category_task(
                user_id, 'grammar', grammar_time, grammar_mastery, phase_config
            )
            tasks.extend(grammar_task)

        # 保存计划
        import json
        existing = conn.execute(
            "SELECT id FROM study_plans WHERE user_id = ? AND plan_date = ?",
            (user_id, plan_date)
        ).fetchone()

        tasks_json = json.dumps(tasks, ensure_ascii=False)

        if existing:
            conn.execute(
                "UPDATE study_plans SET planned_tasks = ?, phase = ? WHERE id = ?",
                (tasks_json, phase, existing['id'])
            )
        else:
            conn.execute(
                """INSERT INTO study_plans (user_id, plan_date, phase, planned_tasks)
                   VALUES (?, ?, ?, ?)""",
                (user_id, plan_date, phase, tasks_json)
            )

        conn.commit()

        return {
            'date': plan_date,
            'phase': phase,
            'phase_name': phase_config['name'],
            'phase_description': phase_config['description'],
            'daily_minutes': daily_minutes,
            'vocab_mastery': round(vocab_mastery, 2),
            'grammar_mastery': round(grammar_mastery, 2),
            'tasks': tasks,
        }
    finally:
        conn.close()


def build_category_task(user_id, category, minutes, mastery, phase_config):
    """构建某个类别的学习任务"""
    from engine.spaced_repetition import get_due_reviews, get_new_items_for_today

    tasks = []
    items_per_minute = 2  # 每分钟约2题

    # 复习任务
    due_reviews = get_due_reviews(user_id, category)
    review_count = min(len(due_reviews), int(minutes * items_per_minute * phase_config['review_ratio']))

    if review_count > 0:
        tasks.append({
            'type': 'review',
            'category': category,
            'category_name': '词汇复习' if category == 'vocabulary' else '语法复习',
            'count': review_count,
            'estimated_minutes': max(1, review_count // items_per_minute),
            'priority': 1,
        })

    # 新学任务
    new_items = get_new_items_for_today(user_id, category, minutes, items_per_minute)
    new_count = min(len(new_items), int(minutes * items_per_minute * phase_config['new_ratio']))

    if new_count > 0:
        tasks.append({
            'type': 'new',
            'category': category,
            'category_name': '词汇新学' if category == 'vocabulary' else '语法新学',
            'count': new_count,
            'estimated_minutes': max(1, new_count // items_per_minute),
            'priority': 2,
        })

    # 如果掌握度较低，增加专项练习
    if mastery < 0.4:
        tasks.append({
            'type': 'practice',
            'category': category,
            'category_name': f"{'词汇' if category == 'vocabulary' else '语法'}专项练习",
            'count': 10,
            'estimated_minutes': 5,
            'priority': 0,  # 最高优先级
        })

    # 确保至少有一个任务
    if not tasks:
        # 对于新用户或没有任务的情况，添加基础学习任务
        tasks.append({
            'type': 'new',
            'category': category,
            'category_name': '词汇基础学习' if category == 'vocabulary' else '语法基础学习',
            'count': min(10, int(minutes * items_per_minute)),
            'estimated_minutes': min(5, minutes),
            'priority': 2,
        })

    return tasks


def get_weekly_plan(user_id):
    """获取本周学习计划概览"""
    conn = get_connection()
    try:
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())  # 本周一

        plans = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            plan = conn.execute(
                "SELECT * FROM study_plans WHERE user_id = ? AND plan_date = ?",
                (user_id, d.isoformat())
            ).fetchone()
            if plan:
                import json
                tasks = json.loads(plan['planned_tasks']) if plan['planned_tasks'] else []
                actual = json.loads(plan['actual_tasks']) if plan['actual_tasks'] else []
                plans.append({
                    'date': d.isoformat(),
                    'weekday': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][d.weekday()],
                    'phase': plan['phase'],
                    'tasks': tasks,
                    'actual': actual,
                    'is_today': d == today,
                    'is_past': d < today,
                })
            else:
                # 如果是今天，生成新计划
                if d == today:
                    daily_plan = generate_daily_plan(user_id, d.isoformat())
                    if daily_plan:
                        plans.append({
                            'date': d.isoformat(),
                            'weekday': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][d.weekday()],
                            'phase': daily_plan['phase'],
                            'tasks': daily_plan['tasks'],
                            'actual': [],
                            'is_today': True,
                            'is_past': False,
                        })
                    else:
                        plans.append({
                            'date': d.isoformat(),
                            'weekday': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][d.weekday()],
                            'phase': None,
                            'tasks': [],
                            'actual': [],
                            'is_today': True,
                            'is_past': False,
                        })
                else:
                    plans.append({
                        'date': d.isoformat(),
                        'weekday': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][d.weekday()],
                        'phase': None,
                        'tasks': [],
                        'actual': [],
                        'is_today': d == today,
                        'is_past': d < today,
                    })

        return plans
    finally:
        conn.close()


def get_milestones(user_id):
    """获取学习里程碑"""
    conn = get_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return []

        exam_date = datetime.strptime(user['exam_date'], '%Y-%m-%d').date()
        today = datetime.now().date()
        days_left = (exam_date - today).days

        milestones = []

        # 基于日期的里程碑
        if days_left > 90:
            milestones.append({
                'name': '完成基础阶段学习',
                'target_date': (exam_date - timedelta(days=90)).isoformat(),
                'status': 'upcoming',
            })
        if days_left > 30:
            milestones.append({
                'name': '进入强化阶段',
                'target_date': (exam_date - timedelta(days=30)).isoformat(),
                'status': 'upcoming',
            })
        milestones.append({
            'name': '冲刺阶段开始',
            'target_date': (exam_date - timedelta(days=30)).isoformat(),
            'status': 'upcoming' if days_left > 30 else 'current',
        })
        milestones.append({
            'name': 'TEM-4 考试日',
            'target_date': exam_date.isoformat(),
            'status': 'upcoming',
        })

        # 基于掌握度的里程碑
        vocab_m = get_category_mastery(user_id, 'vocabulary')
        grammar_m = get_category_mastery(user_id, 'grammar')

        if vocab_m >= 0.8:
            milestones.append({'name': '词汇掌握度达到80%', 'status': 'completed'})
        elif vocab_m >= 0.6:
            milestones.append({'name': '词汇掌握度达到60%', 'status': 'completed'})
        else:
            milestones.append({'name': '词汇掌握度达到60%', 'status': 'upcoming', 'progress': round(vocab_m / 0.6 * 100)})

        if grammar_m >= 0.8:
            milestones.append({'name': '语法掌握度达到80%', 'status': 'completed'})
        elif grammar_m >= 0.6:
            milestones.append({'name': '语法掌握度达到60%', 'status': 'completed'})
        else:
            milestones.append({'name': '语法掌握度达到60%', 'status': 'upcoming', 'progress': round(grammar_m / 0.6 * 100)})

        return milestones
    finally:
        conn.close()
