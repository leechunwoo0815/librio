# backend/seeds/seed_questions.py
"""题库种子数据 — 为测试环境创建示例题目"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.database import get_session, Base, _get_engine
from backend.domain.advancement.models import QuestionBank
from backend.domain.book.models import Book


# 每本书 5 道示例题目（英文阅读理解）
SAMPLE_QUESTIONS = [
    {
        "questions": [
            {
                "question_text": "What is the main character's name?",
                "option_a": "Tom",
                "option_b": "Jerry",
                "option_c": "Bob",
                "option_d": "Alice",
                "correct_answer": "A",
                "explanation": "The main character is introduced as Tom in chapter 1.",
                "difficulty": 1,
            },
            {
                "question_text": "Where does the story take place?",
                "option_a": "In a school",
                "option_b": "In a forest",
                "option_c": "In a city",
                "option_d": "On a farm",
                "correct_answer": "B",
                "explanation": "The story is set in a magical forest.",
                "difficulty": 1,
            },
            {
                "question_text": "What does the word 'brave' mean in the story?",
                "option_a": "Scared",
                "option_b": "Courageous",
                "option_c": "Lazy",
                "option_d": "Angry",
                "correct_answer": "B",
                "explanation": "Brave means having courage, not being afraid.",
                "difficulty": 2,
            },
            {
                "question_text": "What happened at the end of the story?",
                "option_a": "The character went home",
                "option_b": "The character made a new friend",
                "option_c": "The character lost something",
                "option_d": "The character moved away",
                "correct_answer": "B",
                "explanation": "The story ends with the character making a new friend.",
                "difficulty": 2,
            },
            {
                "question_text": "Which sentence uses the past tense correctly?",
                "option_a": "He go to school yesterday",
                "option_b": "He goes to school yesterday",
                "option_c": "He went to school yesterday",
                "option_d": "He going to school yesterday",
                "correct_answer": "C",
                "explanation": "Went is the past tense of go.",
                "difficulty": 3,
            },
        ]
    }
]


def seed():
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
    db = get_session()()

    # 检查是否已有题目
    existing = db.query(QuestionBank).count()
    if existing > 0:
        print(f"题库已有 {existing} 道题目，跳过种子数据")
        db.close()
        return

    # 获取所有图书
    books = db.query(Book).filter(Book.is_deleted == 0).all()
    if not books:
        print("没有图书数据，请先运行 seed_test_data")
        db.close()
        return

    count = 0
    for book in books:
        template = SAMPLE_QUESTIONS[0]  # 使用同一套模板
        for q_data in template["questions"]:
            question = QuestionBank(
                book_id=book.id,
                question_text=q_data["question_text"],
                option_a=q_data["option_a"],
                option_b=q_data["option_b"],
                option_c=q_data.get("option_c"),
                option_d=q_data.get("option_d"),
                correct_answer=q_data["correct_answer"],
                explanation=q_data.get("explanation"),
                difficulty=q_data.get("difficulty", 1),
            )
            db.add(question)
            count += 1

    db.commit()
    print(f"题库种子数据创建成功: {count} 道题目（{len(books)} 本书）")
    db.close()


if __name__ == "__main__":
    seed()
