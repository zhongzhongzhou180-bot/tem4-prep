"""
TEM-4 自适应备考系统 - Flask 主应用
"""
import json
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY


# ===== 自定义 Jinja2 过滤器 =====
@app.template_filter('from_json')
def from_json_filter(value):
    """JSON 字符串转 Python 对象"""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    return value or []


# ===== 数据库初始化 =====
def init_app():
    """应用启动时初始化数据库"""
    from models.database import init_db, seed_knowledge_points, seed_questions
    init_db()
    seed_knowledge_points()
    seed_questions()


# ===== 认证装饰器 =====
def login_required(f):
    """登录验证装饰器"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ===== 认证路由 =====
@app.route('/register', methods=['GET', 'POST'])
def register():
    """注册"""
    if request.method == 'GET':
        return render_template('auth/register.html')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    exam_date = request.form.get('exam_date', Config.DEFAULT_EXAM_DATE)
    daily_minutes = int(request.form.get('daily_minutes', 30))
    target_score = int(request.form.get('target_score', 60))

    if not username or not password:
        return render_template('auth/register.html', error='请填写用户名和密码')

    if len(password) < 4:
        return render_template('auth/register.html', error='密码至少4位')

    from services.auth_service import register_user
    user_id, msg = register_user(username, password, exam_date=exam_date,
                                  daily_minutes=daily_minutes, target_score=target_score)

    if user_id is None:
        return render_template('auth/register.html', error=msg)

    # 注册成功，初始化掌握度
    from engine.knowledge_tracker import init_all_mastery
    init_all_mastery(user_id)

    session['user_id'] = user_id
    session['username'] = username
    return redirect(url_for('assessment'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录"""
    if request.method == 'GET':
        return render_template('auth/login.html')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    from services.auth_service import authenticate_user
    user, msg = authenticate_user(username, password)

    if user is None:
        return render_template('auth/login.html', error=msg)

    session['user_id'] = user['id']
    session['username'] = user['username']
    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    return redirect(url_for('login'))


# ===== 仪表盘 =====
@app.route('/')
@login_required
def dashboard():
    """主仪表盘"""
    from services.report_service import get_dashboard_data
    data = get_dashboard_data(session['user_id'])

    if not data:
        return redirect(url_for('login'))

    return render_template('dashboard.html',
                           current_user={'username': session['username'],
                                         'target_score': data['user']['target_score']},
                           days_left=data['days_left'],
                           phase=data['phase'],
                           phase_config=data['phase_config'],
                           mastery=data['mastery'],
                           stats=data['stats'],
                           weak_points=data['weak_points'],
                           milestones=data['milestones'],
                           today_plan=data['today_plan'],
                           trend=data['trend'],
                           profile=data['profile'])


# ===== 水平诊断 =====
@app.route('/assessment')
@login_required
def assessment():
    """水平诊断页面"""
    # 检查是否已有掌握度数据
    from engine.knowledge_tracker import get_all_user_mastery
    mastery = get_all_user_mastery(session['user_id'])
    has_data = any(m['mastery_level'] > 0 for m in mastery)

    return render_template('assessment/assessment.html',
                           started=False, finished=False)


@app.route('/assessment/start', methods=['POST'])
@login_required
def start_assessment():
    """开始诊断测试"""
    from services.assessment_service import generate_assessment

    # 生成词汇和语法测试题
    vocab_questions = generate_assessment('vocabulary', count=10)
    grammar_questions = generate_assessment('grammar', count=10)
    all_questions = vocab_questions + grammar_questions

    # 存储到 session
    session['assessment_questions'] = [q['id'] for q in all_questions]
    session['assessment_answers'] = []
    session['assessment_index'] = 0

    return redirect(url_for('show_assessment_question'))


@app.route('/assessment/question')
@login_required
def show_assessment_question():
    """显示诊断测试题目"""
    index = session.get('assessment_index', 0)
    question_ids = session.get('assessment_questions', [])

    if index >= len(question_ids):
        return redirect(url_for('finish_assessment'))

    from services.practice_service import get_question_by_id
    question = get_question_by_id(question_ids[index])

    if not question:
        return redirect(url_for('finish_assessment'))

    category_name = '📝 词汇测试' if question['category'] == 'vocabulary' else '📐 语法测试'

    return render_template('assessment/assessment.html',
                           started=True, finished=False,
                           current_question=question,
                           current_index=index,
                           total_questions=len(question_ids),
                           current_category_name=category_name)


@app.route('/assessment/answer', methods=['POST'])
@login_required
def answer_assessment():
    """提交诊断测试答案"""
    question_id = int(request.form.get('question_id'))
    user_answer = request.form.get('answer', '')
    current_index = int(request.form.get('current_index'))

    # 判断正误
    from services.practice_service import get_question_by_id
    question = get_question_by_id(question_id)
    is_correct = (user_answer == question['correct_answer'])

    # 记录答案
    answers = session.get('assessment_answers', [])
    answers.append({
        'question_id': question_id,
        'user_answer': user_answer,
        'is_correct': is_correct,
    })
    session['assessment_answers'] = answers
    session['assessment_index'] = current_index + 1

    # 检查是否完成
    if current_index + 1 >= len(session.get('assessment_questions', [])):
        return redirect(url_for('finish_assessment'))

    return redirect(url_for('show_assessment_question'))


@app.route('/assessment/finish')
@login_required
def finish_assessment():
    """完成诊断测试"""
    answers = session.get('assessment_answers', [])

    if not answers:
        return redirect(url_for('assessment'))

    from services.assessment_service import submit_assessment
    results = submit_assessment(session['user_id'], answers)

    # 清除 session 中的测试数据
    session.pop('assessment_questions', None)
    session.pop('assessment_answers', None)
    session.pop('assessment_index', None)

    return render_template('assessment/assessment.html',
                           started=True, finished=True,
                           results=results)


# ===== 练习路由 =====
@app.route('/practice/<category>')
@login_required
def practice(category):
    """练习页面"""
    if category not in ['vocabulary', 'grammar']:
        return redirect(url_for('dashboard'))

    mode = request.args.get('mode', 'mixed')
    count = 10

    from services.practice_service import get_questions_for_practice
    questions = get_questions_for_practice(session['user_id'], category, count, mode)

    from engine.knowledge_tracker import get_category_mastery
    mastery = get_category_mastery(session['user_id'], category)

    return render_template('practice/practice.html',
                           current_user={'username': session['username']},
                           category=category,
                           mode=mode,
                           questions=questions,
                           mastery=mastery,
                           correct_count=0)


@app.route('/api/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    """提交练习答案（AJAX）"""
    data = request.get_json()
    question_id = data.get('question_id')
    user_answer = data.get('user_answer')
    is_correct = data.get('is_correct', False)
    time_spent = data.get('time_spent', 0)

    from engine.dynamic_adjuster import record_learning_result
    result = record_learning_result(session['user_id'], question_id, user_answer, is_correct, time_spent)

    return jsonify(result)


# ===== 学习计划 =====
@app.route('/plan')
@login_required
def plan():
    """学习计划页面"""
    from engine.path_planner import (
        get_weekly_plan, get_milestones, determine_phase,
        get_phase_config, generate_daily_plan
    )
    from engine.knowledge_tracker import get_category_mastery

    weekly_plan = get_weekly_plan(session['user_id'])
    milestones = get_milestones(session['user_id'])

    from services.auth_service import get_user_by_id
    user = get_user_by_id(session['user_id'])
    current_phase = determine_phase(user['exam_date'])

    phases = {}
    for p in ['foundation', 'reinforcement', 'sprint']:
        phases[p] = get_phase_config(p)

    vocab_mastery = get_category_mastery(session['user_id'], 'vocabulary')
    grammar_mastery = get_category_mastery(session['user_id'], 'grammar')
    today_plan = generate_daily_plan(session['user_id'])

    return render_template('plan.html',
                           current_user={'username': session['username']},
                           weekly_plan=weekly_plan,
                           milestones=milestones,
                           phases=phases,
                           current_phase=current_phase,
                           vocab_mastery=vocab_mastery,
                           grammar_mastery=grammar_mastery,
                           today_plan=today_plan)


# ===== 上下文处理器 =====
@app.context_processor
def inject_current_user():
    """注入当前用户信息到所有模板"""
    if 'user_id' in session:
        return {'current_user': {'id': session['user_id'], 'username': session.get('username', '')}}
    return {}


# ===== 错误处理 =====
@app.errorhandler(404)
def page_not_found(e):
    return render_template('base.html', content='<div class="text-center py-20"><div class="text-6xl mb-4">🌿</div><h1 class="text-2xl font-bold" style="color:#5D4037;">页面不存在</h1><p style="color:#8D6E63;">迷路了？回仪表盘看看吧</p><a href="/" class="ac-btn inline-block mt-4">🏠 返回</a></div>'), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template('base.html', content='<div class="text-center py-20"><div class="text-6xl mb-4">🐛</div><h1 class="text-2xl font-bold" style="color:#5D4037;">出了点小问题</h1><p style="color:#8D6E63;">别担心，刷新试试看</p></div>'), 500


# ===== 启动 =====
if __name__ == '__main__':
    print("=" * 50)
    print("  🌳 TEM-4 自适应备考系统 启动中...")
    print("=" * 50)
    init_app()
    print("  ✅ 数据库初始化完成")
    print("  🌿 访问 http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
