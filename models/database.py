"""
数据库初始化模块
创建所有必要的表并插入初始数据
"""
import sqlite3
import os
import json
from datetime import datetime, timedelta


def get_db_path():
    """获取数据库文件路径"""
    from config import Config
    db_path = Config.DATABASE
    # 确保目录存在
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    return db_path


def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库，创建所有表"""
    conn = get_connection()
    cursor = conn.cursor()

    # 用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            exam_date TEXT NOT NULL,
            daily_study_minutes INTEGER DEFAULT 30,
            target_score INTEGER DEFAULT 60,
            current_phase TEXT DEFAULT 'foundation',
            created_at TEXT DEFAULT (datetime('now')),
            last_login TEXT
        )
    ''')

    # 知识点表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            difficulty REAL DEFAULT 0.5,
            prerequisites TEXT DEFAULT '[]',
            description TEXT
        )
    ''')

    # 题目表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_point_id INTEGER,
            question_type TEXT NOT NULL,
            content TEXT NOT NULL,
            options TEXT DEFAULT '[]',
            correct_answer TEXT NOT NULL,
            explanation TEXT,
            difficulty REAL DEFAULT 0.5,
            FOREIGN KEY (knowledge_point_id) REFERENCES knowledge_points(id)
        )
    ''')

    # 用户知识掌握表（核心）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_mastery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            knowledge_point_id INTEGER NOT NULL,
            mastery_level REAL DEFAULT 0.0,
            last_practiced TEXT,
            next_review TEXT,
            easiness_factor REAL DEFAULT 2.5,
            interval_days INTEGER DEFAULT 0,
            repetitions INTEGER DEFAULT 0,
            UNIQUE(user_id, knowledge_point_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (knowledge_point_id) REFERENCES knowledge_points(id)
        )
    ''')

    # 学习记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            user_answer TEXT,
            is_correct INTEGER DEFAULT 0,
            time_spent REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )
    ''')

    # 学习计划表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_date TEXT NOT NULL,
            phase TEXT DEFAULT 'foundation',
            planned_tasks TEXT DEFAULT '[]',
            actual_tasks TEXT DEFAULT '[]',
            is_adjusted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # 用户能力画像表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            vocabulary_level REAL DEFAULT 0.0,
            grammar_level REAL DEFAULT 0.0,
            listening_level REAL DEFAULT 0.0,
            reading_level REAL DEFAULT 0.0,
            writing_level REAL DEFAULT 0.0,
            estimated_score REAL DEFAULT 0.0,
            total_study_minutes INTEGER DEFAULT 0,
            total_questions INTEGER DEFAULT 0,
            streak_days INTEGER DEFAULT 0,
            last_study_date TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ 数据库初始化完成")


def seed_knowledge_points():
    """插入初始知识点数据"""
    conn = get_connection()
    cursor = conn.cursor()

    # 检查是否已有数据
    count = cursor.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0]
    if count > 0:
        conn.close()
        print("ℹ️ 知识点数据已存在，跳过")
        return

    # 词汇知识点（按TEM-4大纲分类）
    vocab_categories = [
        ("核心动词 (Core Verbs)", "vocabulary", 0.3, "TEM-4高频动词"),
        ("核心名词 (Core Nouns)", "vocabulary", 0.3, "TEM-4高频名词"),
        ("核心形容词 (Core Adjectives)", "vocabulary", 0.4, "TEM-4高频形容词"),
        ("核心副词 (Core Adverbs)", "vocabulary", 0.4, "TEM-4高频副词"),
        ("核心介词 (Core Prepositions)", "vocabulary", 0.3, "TEM-4高频介词"),
        ("核心连词 (Core Conjunctions)", "vocabulary", 0.3, "TEM-4高频连词"),
        ("学术词汇 (Academic Words)", "vocabulary", 0.6, "TEM-4学术类词汇"),
        ("近义词辨析 (Synonym Discrimination)", "vocabulary", 0.7, "常见近义词辨析"),
        ("固定搭配 (Collocations)", "vocabulary", 0.6, "动词短语、名词搭配等"),
        ("词根词缀 (Roots & Affixes)", "vocabulary", 0.5, "常见词根词缀"),
    ]

    # 语法知识点
    grammar_categories = [
        ("时态 (Tenses)", "grammar", 0.3, "一般现在/过去/将来、进行时、完成时等"),
        ("被动语态 (Passive Voice)", "grammar", 0.4, "各时态的被动语态"),
        ("虚拟语气 (Subjunctive Mood)", "grammar", 0.7, "虚拟条件句、wish/as if等"),
        ("非谓语动词 (Non-finite Verbs)", "grammar", 0.7, "不定式、动名词、分词"),
        ("定语从句 (Attributive Clauses)", "grammar", 0.6, "限制性/非限制性定语从句"),
        ("名词性从句 (Noun Clauses)", "grammar", 0.6, "主语/宾语/表语/同位语从句"),
        ("状语从句 (Adverbial Clauses)", "grammar", 0.5, "时间/条件/原因/结果/让步等"),
        ("倒装句 (Inversion)", "grammar", 0.7, "完全倒装与部分倒装"),
        ("强调句 (Emphatic Sentences)", "grammar", 0.6, "It is...that/who...结构"),
        ("主谓一致 (Subject-Verb Agreement)", "grammar", 0.5, "主谓一致的规则与例外"),
        ("比较级与最高级 (Comparison)", "grammar", 0.4, "形容词/副词的比较等级"),
        ("代词 (Pronouns)", "grammar", 0.4, "人称/物主/指示/不定代词等"),
    ]

    all_points = vocab_categories + grammar_categories
    for name, category, difficulty, desc in all_points:
        cursor.execute(
            "INSERT INTO knowledge_points (name, category, difficulty, description) VALUES (?, ?, ?, ?)",
            (name, category, difficulty, desc)
        )

    conn.commit()
    conn.close()
    print(f"✅ 已插入 {len(all_points)} 个知识点")


def seed_questions():
    """插入示例题目数据"""
    conn = get_connection()
    cursor = conn.cursor()

    count = cursor.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    if count > 0:
        conn.close()
        print("ℹ️ 题目数据已存在，跳过")
        return

    # 获取知识点ID映射
    kp_map = {}
    for row in cursor.execute("SELECT id, name, category FROM knowledge_points"):
        kp_map[row['name']] = row['id']

    questions = []

    # ===== 词汇题 =====
    vocab_qp_id = kp_map.get("核心动词 (Core Verbs)", 1)

    # 核心动词
    questions.extend([
        (vocab_qp_id, "choice", "The government has _____ measures to combat pollution.",
         '["A. adapted", "B. adopted", "C. addicted", "D. addressed"]', "B",
         "adopt 意为'采纳、采取（措施）'；adapt 意为'适应'；addict 意为'上瘾'；address 意为'处理/解决'", 0.4),
        (vocab_qp_id, "choice", "She couldn't _____ her tears when she heard the news.",
         '["A. hold back", "B. hold on", "C. hold up", "D. hold out"]', "A",
         "hold back 意为'抑制、忍住'；hold on 意为'坚持/等一下'；hold up 意为'耽搁/举起'；hold out 意为'伸出/维持'", 0.4),
        (vocab_qp_id, "choice", "The company decided to _____ the project due to lack of funds.",
         '["A. abandon", "B. accomplish", "C. accumulate", "D. accelerate"]', "A",
         "abandon 意为'放弃'；accomplish 意为'完成'；accumulate 意为'积累'；accelerate 意为'加速'", 0.3),
        (vocab_qp_id, "choice", "The new policy will _____ next month.",
         '["A. take effect", "B. take place", "C. take part", "D. take over"]', "A",
         "take effect 意为'生效'；take place 意为'发生'；take part 意为'参加'；take over 意为'接管'", 0.4),
        (vocab_qp_id, "choice", "He _____ to finish the report by Friday.",
         '["A. managed", "B. attempted", "C. intended", "D. pretended"]', "A",
         "manage to do 意为'成功做到'；attempt to do 意为'试图做'；intend to do 意为'打算做'；pretend to do 意为'假装做'", 0.4),
    ])

    # 核心名词
    noun_kp_id = kp_map.get("核心名词 (Core Nouns)", 2)
    questions.extend([
        (noun_kp_id, "choice", "The _____ between the two countries has improved significantly.",
         '["A. relation", "B. relative", "C. relevance", "D. relief"]', "A",
         "relation 意为'关系'；relative 意为'亲戚/相对的'；relevance 意为'相关性'；relief 意为'缓解/救济'", 0.3),
        (noun_kp_id, "choice", "We need to find a _____ to this problem.",
         '["A. solution", "B. resolution", "C. conclusion", "D. decision"]', "A",
         "solution to a problem 意为'问题的解决方案'；resolution 意为'决议/决心'；conclusion 意为'结论'；decision 意为'决定'", 0.3),
        (noun_kp_id, "choice", "The professor made a great _____ to the field of science.",
         '["A. contribution", "B. distribution", "C. attribution", "D. substitution"]', "A",
         "make a contribution to 意为'对...做出贡献'；distribution 意为'分配'；attribution 意为'归因'；substitution 意为'替代'", 0.4),
    ])

    # 核心形容词
    adj_kp_id = kp_map.get("核心形容词 (Core Adjectives)", 3)
    questions.extend([
        (adj_kp_id, "choice", "The results were quite _____ from what we expected.",
         '["A. different", "B. indifferent", "C. differential", "D. differentiated"]', "A",
         "different from 意为'与...不同'；indifferent 意为'冷漠的'；differential 意为'差别的'；differentiated 意为'区分的'", 0.3),
        (adj_kp_id, "choice", "She is _____ about her chances of winning the competition.",
         '["A. optimistic", "B. pessimistic", "C. realistic", "D. fantastic"]', "A",
         "optimistic about 意为'对...乐观'；pessimistic 意为'悲观的'；realistic 意为'现实的'；fantastic 意为'极好的'", 0.4),
        (adj_kp_id, "choice", "The book provides a _____ analysis of the economic situation.",
         '["A. comprehensive", "B. comprehensible", "C. compulsory", "D. complicated"]', "A",
         "comprehensive 意为'全面的'；comprehensible 意为'可理解的'；compulsory 意为'强制的'；complicated 意为'复杂的'", 0.5),
    ])

    # 固定搭配
    collocation_kp_id = kp_map.get("固定搭配 (Collocations)", 9)
    questions.extend([
        (collocation_kp_id, "choice", "She has a good _____ of English grammar.",
         '["A. command", "B. commandment", "C. commentary", "D. commitment"]', "A",
         "have a good command of 意为'精通...'；commandment 意为'戒律'；commentary 意为'评论'；commitment 意为'承诺'", 0.5),
        (collocation_kp_id, "choice", "The teacher asked the students to _____ the new words.",
         '["A. look up", "B. look after", "C. look into", "D. look forward to"]', "A",
         "look up 意为'查阅'；look after 意为'照顾'；look into 意为'调查'；look forward to 意为'期待'", 0.3),
        (collocation_kp_id, "choice", "We should _____ the environment from pollution.",
         '["A. protect", "B. protest", "C. project", "D. promote"]', "A",
         "protect...from... 意为'保护...免受...'；protest 意为'抗议'；project 意为'项目/投射'；promote 意为'促进'", 0.3),
        (collocation_kp_id, "choice", "He is always making _____ about how tired he is.",
         '["A. complaints", "B. complements", "C. commitments", "D. complications"]', "A",
         "make complaints about 意为'抱怨...'；complement 意为'补充'；commitment 意为'承诺'；complication 意为'并发症/复杂化'", 0.4),
        (collocation_kp_id, "choice", "The meeting has been _____ until next week.",
         '["A. postponed", "B. proposed", "C. imposed", "D. exposed"]', "A",
         "postpone 意为'推迟'；propose 意为'提议'；impose 意为'强加'；expose 意为'暴露'", 0.4),
    ])

    # 近义词辨析
    synonym_kp_id = kp_map.get("近义词辨析 (Synonym Discrimination)", 8)
    questions.extend([
        (synonym_kp_id, "choice", "The two words 'affect' and 'effect' are often _____.",
         '["A. confused", "B. confessed", "C. confined", "D. confirmed"]', "A",
         "confused 意为'混淆'；confessed 意为'坦白'；confined 意为'限制'；confirmed 意为'确认'", 0.6),
        (synonym_kp_id, "choice", "The price of oil has _____ dramatically in recent years.",
         '["A. fluctuated", "B. formulated", "C. facilitated", "D. fluctuated"]', "A",
         "fluctuate 意为'波动'；formulate 意为'制定'；facilitate 意为'促进'", 0.6),
        (synonym_kp_id, "choice", "The government needs to _____ effective policies.",
         '["A. implement", "B. imply", "C. import", "D. impose"]', "A",
         "implement policies 意为'实施政策'；imply 意为'暗示'；import 意为'进口'；impose 意为'强加'", 0.5),
    ])

    # 学术词汇
    academic_kp_id = kp_map.get("学术词汇 (Academic Words)", 7)
    questions.extend([
        (academic_kp_id, "choice", "The research _____ a strong correlation between the two variables.",
         '["A. demonstrates", "B. demands", "C. declines", "D. defends"]', "A",
         "demonstrate 意为'证明/展示'；demand 意为'要求'；decline 意为'下降/拒绝'；defend 意为'辩护'", 0.6),
        (academic_kp_id, "choice", "The hypothesis was _____ by the experimental results.",
         '["A. verified", "B. varied", "C. vanished", "D. ventured"]', "A",
         "verify 意为'验证'；vary 意为'变化'；vanish 意为'消失'；venture 意为'冒险'", 0.6),
        (academic_kp_id, "choice", "The study _____ that regular exercise can improve mental health.",
         '["A. concludes", "B. excludes", "C. includes", "D. secludes"]', "A",
         "conclude 意为'得出结论'；exclude 意为'排除'；include 意为'包含'；seclude 意为'隔离'", 0.5),
    ])

    # ===== 语法题 =====
    # 时态
    tense_kp_id = kp_map.get("时态 (Tenses)", 11)
    questions.extend([
        (tense_kp_id, "choice", "By the time we arrived, the movie _____.",
         '["A. had already started", "B. has already started", "C. already started", "D. was already starting"]', "A",
         "'by the time + 过去时' 主句用过去完成时 had done", 0.3),
        (tense_kp_id, "choice", "She _____ English for five years before she went to England.",
         '["A. had studied", "B. has studied", "C. studied", "D. was studying"]', "A",
         "before 引导的时间状语从句，主句用过去完成时表示'过去的过去'", 0.3),
        (tense_kp_id, "choice", "I _____ my homework when you called me last night.",
         '["A. was doing", "B. did", "C. have done", "D. had done"]', "A",
         "when 引导的时间状语从句，表示过去某个时刻正在做某事，用过去进行时", 0.3),
        (tense_kp_id, "choice", "He _____ in this city since he was born.",
         '["A. has lived", "B. lived", "C. is living", "D. had lived"]', "A",
         "since 引导的时间状语，主句用现在完成时", 0.3),
        (tense_kp_id, "choice", "Look at the clouds. It _____ rain soon.",
         '["A. is going to", "B. will", "C. shall", "D. would"]', "A",
         "有迹象表明即将发生的事，用 be going to", 0.3),
    ])

    # 虚拟语气
    subjunctive_kp_id = kp_map.get("虚拟语气 (Subjunctive Mood)", 13)
    questions.extend([
        (subjunctive_kp_id, "choice", "If I _____ you, I would accept the offer.",
         '["A. were", "B. am", "C. was", "D. be"]', "A",
         "与现在事实相反的虚拟条件句，从句用过去时（be动词一律用were）", 0.5),
        (subjunctive_kp_id, "choice", "I wish I _____ harder when I was in college.",
         '["A. had studied", "B. studied", "C. have studied", "D. would study"]', "A",
         "wish 后接与过去事实相反的虚拟语气，用过去完成时", 0.6),
        (subjunctive_kp_id, "choice", "The teacher insisted that every student _____ the exam on time.",
         '["A. take", "B. takes", "C. took", "D. would take"]', "A",
         "insist/suggest/demand 等词后的宾语从句用 (should) + 动词原形", 0.6),
        (subjunctive_kp_id, "choice", "Without your help, we _____ the task.",
         '["A. couldn\'t have completed", "B. can\'t complete", "C. didn\'t complete", "D. won\'t complete"]', "A",
         "without 引导的含蓄条件句，表示与过去事实相反，用 couldn't have done", 0.7),
        (subjunctive_kp_id, "choice", "It is high time that we _____ measures to protect the environment.",
         '["A. took", "B. take", "C. have taken", "D. will take"]', "A",
         "It is high time that... 从句用过去时或 should + 动词原形", 0.6),
    ])

    # 非谓语动词
    nonfinite_kp_id = kp_map.get("非谓语动词 (Non-finite Verbs)", 14)
    questions.extend([
        (nonfinite_kp_id, "choice", "_____ from the top of the hill, the city looks beautiful.",
         '["A. Seen", "B. Seeing", "C. To see", "D. Having seen"]', "A",
         "城市是被看的，所以用过去分词 seen 作状语", 0.6),
        (nonfinite_kp_id, "choice", "The teacher asked the students _____ quietly.",
         '["A. to read", "B. reading", "C. read", "D. readed"]', "A",
         "ask sb. to do sth. 结构，用不定式作宾补", 0.4),
        (nonfinite_kp_id, "choice", "_____ is believing.",
         '["A. To see", "B. Seeing", "C. Seen", "D. Having seen"]', "A",
         "动名词作主语，表示一般性动作", 0.5),
        (nonfinite_kp_id, "choice", "He rushed to the station, only _____ the train had left.",
         '["A. to find", "B. finding", "C. found", "D. find"]', "A",
         "only to do 表示出乎意料的结果", 0.7),
        (nonfinite_kp_id, "choice", "The meeting _____ tomorrow is very important.",
         '["A. to be held", "B. held", "C. being held", "D. having been held"]', "A",
         "会议将在明天举行，用不定式作后置定语表示将来", 0.6),
    ])

    # 定语从句
    relative_kp_id = kp_map.get("定语从句 (Attributive Clauses)", 15)
    questions.extend([
        (relative_kp_id, "choice", "The book _____ I bought yesterday is very interesting.",
         '["A. which", "B. who", "C. whom", "D. whose"]', "A",
         "先行词是物，在从句中作宾语，用 which/that", 0.4),
        (relative_kp_id, "choice", "This is the reason _____ he was late for school.",
         '["A. why", "B. which", "C. what", "D. where"]', "A",
         "先行词是 reason，在从句中作原因状语，用 why", 0.5),
        (relative_kp_id, "choice", "I will never forget the day _____ I first came to this city.",
         '["A. when", "B. which", "C. that", "D. where"]', "A",
         "先行词是 day，在从句中作时间状语，用 when", 0.4),
        (relative_kp_id, "choice", "The student _____ mother is a teacher studies very hard.",
         '["A. whose", "B. who", "C. whom", "D. which"]', "A",
         "先行词是 student，与 mother 是所属关系，用 whose", 0.4),
    ])

    # 名词性从句
    noun_clause_kp_id = kp_map.get("名词性从句 (Noun Clauses)", 16)
    questions.extend([
        (noun_clause_kp_id, "choice", "_____ he said at the meeting surprised everyone.",
         '["A. What", "B. That", "C. Which", "D. How"]', "A",
         "主语从句中缺少 said 的宾语，用 what", 0.5),
        (noun_clause_kp_id, "choice", "I don't know _____ he will come or not.",
         '["A. whether", "B. if", "C. that", "D. what"]', "A",
         "与 or not 连用时只能用 whether，不能用 if", 0.5),
        (noun_clause_kp_id, "choice", "The question is _____ we should do next.",
         '["A. what", "B. that", "C. which", "D. how"]', "A",
         "表语从句中缺少 do 的宾语，用 what", 0.5),
    ])

    # 倒装句
    inversion_kp_id = kp_map.get("倒装句 (Inversion)", 18)
    questions.extend([
        (inversion_kp_id, "choice", "Not until he came back _____ the truth.",
         '["A. did I know", "B. I knew", "C. I did know", "D. knew I"]', "A",
         "Not until... 置于句首时，主句部分倒装", 0.7),
        (inversion_kp_id, "choice", "Only in this way _____ solve the problem.",
         '["A. can we", "B. we can", "C. do we", "D. we do"]', "A",
         "Only + 状语置于句首时，主句部分倒装", 0.7),
        (inversion_kp_id, "choice", "So loudly _____ that everyone could hear him.",
         '["A. did he speak", "B. he spoke", "C. he did speak", "D. spoke he"]', "A",
         "So...that... 结构中 So 置于句首时，主句部分倒装", 0.7),
    ])

    # 主谓一致
    agreement_kp_id = kp_map.get("主谓一致 (Subject-Verb Agreement)", 20)
    questions.extend([
        (agreement_kp_id, "choice", "The teacher together with his students _____ going to the museum.",
         '["A. is", "B. are", "C. were", "D. have been"]', "A",
         "together with 连接的并列主语，谓语与前面的主语一致", 0.5),
        (agreement_kp_id, "choice", "Each of the students _____ a dictionary.",
         '["A. has", "B. have", "C. having", "D. to have"]', "A",
         "each/every/either/neither + 单数名词，谓语用单数", 0.4),
        (agreement_kp_id, "choice", "The number of students in our school _____ increasing.",
         '["A. is", "B. are", "C. were", "D. have been"]', "A",
         "the number of... 意为'...的数量'，谓语用单数；a number of... 意为'许多'，谓语用复数", 0.5),
    ])

    # ===== 补充缺失知识点的题目 =====

    # 核心副词
    adv_kp_id = kp_map.get("核心副词 (Core Adverbs)", 4)
    questions.extend([
        (adv_kp_id, "choice", "She performed _____ in the final exam.",
         '["A. extremely well", "B. extreme well", "C. extremely good", "D. extreme good"]', "A",
         "副词 extremely 修饰形容词 well（副词作表语），extremely 不能修饰形容词 good 在此处", 0.3),
        (adv_kp_id, "choice", "The movie was _____ boring that I fell asleep.",
         '["A. so", "B. such", "C. very", "D. too"]', "A",
         "so + 形容词 + that... 结构；such + 名词 + that...", 0.4),
        (adv_kp_id, "choice", "He ran _____ to catch the last bus.",
         '["A. fast", "B. fastly", "C. fastness", "D. faster"]', "A",
         "fast 既可作形容词也可作副词，没有 fastly 这个词", 0.3),
        (adv_kp_id, "choice", "She hardly had time to finish the work, _____?",
         '["A. had she", "B. hadn\'t she", "C. did she", "D. didn\'t she"]', "A",
         "hardly 是否定副词，反意疑问句用肯定形式", 0.6),
        (adv_kp_id, "choice", "The meeting has been postponed _____.",
         '["A. temporarily", "B. temporary", "C. temporariness", "D. temporal"]', "A",
         "需要副词修饰动词 postponed，temporary 是形容词", 0.4),
    ])

    # 核心介词
    prep_kp_id = kp_map.get("核心介词 (Core Prepositions)", 5)
    questions.extend([
        (prep_kp_id, "choice", "She has been living here _____ 2010.",
         '["A. since", "B. for", "C. from", "D. in"]', "A",
         "since + 具体时间点；for + 时间段", 0.3),
        (prep_kp_id, "choice", "The book is _____ the table.",
         '["A. on", "B. in", "C. at", "D. by"]', "A",
         "on the table 表示在桌面上（接触表面）", 0.2),
        (prep_kp_id, "choice", "He is good _____ playing basketball.",
         '["A. at", "B. in", "C. on", "D. with"]', "A",
         "be good at 意为'擅长做某事'", 0.3),
        (prep_kp_id, "choice", "She arrived _____ the airport late.",
         '["A. at", "B. in", "C. on", "D. to"]', "A",
         "arrive at + 小地点（机场、车站等）；arrive in + 大地点（城市、国家）", 0.4),
        (prep_kp_id, "choice", "The professor is popular _____ his students.",
         '["A. with", "B. to", "C. at", "D. for"]', "A",
         "be popular with 意为'受...欢迎'", 0.4),
    ])

    # 核心连词
    conj_kp_id = kp_map.get("核心连词 (Core Conjunctions)", 6)
    questions.extend([
        (conj_kp_id, "choice", "_____ it rained heavily, they still went out.",
         '["A. Although", "B. Because", "C. So", "D. And"]', "A",
         "although 引导让步状语从句，'尽管...仍然...'", 0.4),
        (conj_kp_id, "choice", "Hurry up, _____ you will miss the train.",
         '["A. otherwise", "B. but", "C. or", "D. and"]', "A",
         "otherwise 意为'否则'，表示否定的条件", 0.5),
        (conj_kp_id, "choice", "_____ he was tired, he kept working.",
         '["A. Even though", "B. Because", "C. So that", "D. Unless"]', "A",
         "even though 意为'即使'，引导让步状语从句", 0.4),
        (conj_kp_id, "choice", "I will go to the party _____ I have time.",
         '["A. if", "B. unless", "C. because", "D. although"]', "A",
         "if 引导条件状语从句；unless = if not", 0.3),
        (conj_kp_id, "choice", "_____ you study hard, you won\'t pass the exam.",
         '["A. Unless", "B. If", "C. Because", "D. Although"]', "A",
         "unless = if not，'除非你努力学习，否则不会通过考试'", 0.5),
    ])

    # 被动语态
    passive_kp_id = kp_map.get("被动语态 (Passive Voice)", 12)
    questions.extend([
        (passive_kp_id, "choice", "The bridge _____ last year.",
         '["A. was built", "B. built", "C. is built", "D. has been built"]', "A",
         "last year 表过去时间，用一般过去时的被动语态 was/were + done", 0.3),
        (passive_kp_id, "choice", "A new hospital _____ in our city now.",
         '["A. is being built", "B. was built", "C. is building", "D. has built"]', "A",
         "now 表正在进行，用现在进行时的被动语态 is being + done", 0.5),
        (passive_kp_id, "choice", "The problem _____ by the time we arrived.",
         '["A. had been solved", "B. has been solved", "C. was solved", "D. is solved"]', "A",
         "by the time + 过去时，主句用过去完成时的被动语态 had been + done", 0.6),
        (passive_kp_id, "choice", "English _____ in many countries.",
         '["A. is spoken", "B. speaks", "C. spoke", "D. is speaking"]', "A",
         "English 是被说的，用一般现在时的被动语态 is/are + done", 0.3),
        (passive_kp_id, "choice", "The thief _____ by the police yesterday.",
         '["A. was arrested", "B. arrested", "C. is arrested", "D. has arrested"]', "A",
         "yesterday 表过去时间，thief 是被逮捕的，用 was + done", 0.3),
    ])

    # 词根词缀
    roots_kp_id = kp_map.get("词根词缀 (Roots & Affixes)", 10)
    questions.extend([
        (roots_kp_id, "choice", "The prefix 'un-' in 'unhappy' means _____.",
         '["A. not", "B. very", "C. again", "D. before"]', "A",
         "un- 是常见否定前缀，意为'不、非'", 0.3),
        (roots_kp_id, "choice", "The suffix '-able' in 'comfortable' means _____.",
         '["A. capable of", "B. full of", "C. without", "D. relating to"]', "A",
         "-able 是形容词后缀，意为'能够...的'", 0.4),
        (roots_kp_id, "choice", "The word 'rewrite' consists of the prefix 're-' meaning _____.",
         '["A. again", "B. not", "C. before", "D. after"]', "A",
         "re- 是常见前缀，意为'再次、重新'", 0.3),
        (roots_kp_id, "choice", "The root 'spect' in 'inspect' means _____.",
         '["A. to look", "B. to hear", "C. to write", "D. to feel"]', "A",
         "spect/spec 意为'看'：inspect(检查), respect(尊重), spectator(观众)", 0.6),
        (roots_kp_id, "choice", "The suffix '-ness' in 'happiness' is used to form _____.",
         '["A. a noun from an adjective", "B. an adverb from an adjective", "C. a verb from a noun", "D. an adjective from a noun"]', "A",
         "-ness 是名词后缀，将形容词变为名词：happy → happiness", 0.4),
    ])

    # 状语从句
    adverbial_kp_id = kp_map.get("状语从句 (Adverbial Clauses)", 17)
    questions.extend([
        (adverbial_kp_id, "choice", "I will wait _____ you come back.",
         '["A. until", "B. since", "C. after", "D. when"]', "A",
         "until 意为'直到...为止'，引导时间状语从句", 0.4),
        (adverbial_kp_id, "choice", "_____ it was raining, we decided to stay at home.",
         '["A. Because", "B. Although", "C. Unless", "D. If"]', "A",
         "because 引导原因状语从句", 0.3),
        (adverbial_kp_id, "choice", "She spoke slowly _____ everyone could understand.",
         '["A. so that", "B. although", "C. unless", "D. because"]', "A",
         "so that 引导目的状语从句，'以便...'", 0.5),
        (adverbial_kp_id, "choice", "_____ you go, I will follow you.",
         '["A. Wherever", "B. Whatever", "C. Whenever", "D. However"]', "A",
         "wherever 引导让步地点状语从句，'无论你去哪里'", 0.5),
        (adverbial_kp_id, "choice", "He worked hard _____ he could pass the exam.",
         '["A. so that", "B. although", "C. unless", "D. until"]', "A",
         "so that 引导目的状语从句，'为了...'", 0.4),
    ])

    # 强调句
    emphasis_kp_id = kp_map.get("强调句 (Emphatic Sentences)", 19)
    questions.extend([
        (emphasis_kp_id, "choice", "It was in the park _____ I met her yesterday.",
         '["A. that", "B. which", "C. where", "D. when"]', "A",
         "It is/was...that/who... 强调句型，被强调部分是地点状语时仍用 that", 0.6),
        (emphasis_kp_id, "choice", "It was not until midnight _____ he finished the work.",
         '["A. that", "B. when", "C. which", "D. then"]', "A",
         "It was not until...that... 是强调句的特殊形式", 0.7),
        (emphasis_kp_id, "choice", "It is the teacher _____ is responsible for the class.",
         '["A. who", "B. which", "C. whom", "D. that"]', "A",
         "强调人时用 who/that，此处 teacher 是人", 0.5),
    ])

    # 比较级与最高级
    comparison_kp_id = kp_map.get("比较级与最高级 (Comparison)", 21)
    questions.extend([
        (comparison_kp_id, "choice", "This book is _____ than that one.",
         '["A. more interesting", "B. interestinger", "C. most interesting", "D. interesting more"]', "A",
         "多音节形容词的比较级用 more + 原级", 0.3),
        (comparison_kp_id, "choice", "She is the _____ student in the class.",
         '["A. most diligent", "B. more diligent", "C. diligentest", "D. very diligent"]', "A",
         "多音节形容词的最高级用 the most + 原级", 0.3),
        (comparison_kp_id, "choice", "The _____ you practice, the _____ you will be.",
         '["A. more...better", "B. more...best", "C. most...better", "D. much...better"]', "A",
         "the + 比较级..., the + 比较级... 意为'越...越...'", 0.5),
        (comparison_kp_id, "choice", "He is not so _____ as his brother.",
         '["A. tall", "B. taller", "C. tallest", "D. the tallest"]', "A",
         "not so/as...as 结构中用原级，不用比较级", 0.4),
    ])

    # 代词
    pronoun_kp_id = kp_map.get("代词 (Pronouns)", 22)
    questions.extend([
        (pronoun_kp_id, "choice", "_____ is important to keep a promise.",
         '["A. It", "B. That", "C. This", "D. What"]', "A",
         "it 作形式主语，代替后面的不定式短语", 0.4),
        (pronoun_kp_id, "choice", "The book on the desk is _____. She put _____ there yesterday.",
         '["A. hers; it", "B. her; it", "C. she; it", "D. hers; its"]', "A",
         "hers 是名词性物主代词（= her book）；it 指代前文提到的 the book", 0.5),
        (pronoun_kp_id, "choice", "He has two sons. _____ are both doctors.",
         '["A. Both of them", "B. All of them", "C. Either of them", "D. Neither of them"]', "A",
         "两者都用 both；三者以上用 all；either 两者之一；neither 两者都不", 0.4),
        (pronoun_kp_id, "choice", "I don\'t like this shirt. Can you show me _____ one?",
         '["A. another", "B. other", "C. the other", "D. others"]', "A",
         "another 泛指另一个；the other 特指两者中的另一个", 0.4),
    ])

    # 插入所有题目
    for kp_id, q_type, content, options, answer, explanation, difficulty in questions:
        cursor.execute(
            """INSERT INTO questions
               (knowledge_point_id, question_type, content, options, correct_answer, explanation, difficulty)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (kp_id, q_type, content, options, answer, explanation, difficulty)
        )

    conn.commit()
    conn.close()
    print(f"✅ 已插入 {len(questions)} 道题目")


if __name__ == '__main__':
    init_db()
    seed_knowledge_points()
    seed_questions()
