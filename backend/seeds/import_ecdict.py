#!/usr/bin/env python3
"""
ECDICT 词库导入脚本
将 ECDICT SQLite 数据导入到 MegaWords 的 dictionary_word 表

用法:
    python -m backend.seeds.import_ecdict [--limit N] [--mysql]

默认导入到 SQLite（开发环境），--mysql 导入到 MySQL
"""

import argparse
import os
import sqlite3
import sys

# ECDICT 字段映射:
# word → word
# phonetic → phonetic
# audio → audio_url
# pos → part_of_speech (取第一个词性)
# translation → chinese_meaning
# tag → level (考试等级: zk=中考, gk=高考, cet4, cet6, ielts, toefl, gre)
# collins → 用于排序（柯林斯星级）

ECDICT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ecdict.db")

TAG_LEVEL_MAP = {
    "zk": "中考",
    "gk": "高考",
    "cet4": "CET4",
    "cet6": "CET6",
    "ielts": "IELTS",
    "toefl": "TOEFL",
    "gre": "GRE",
}


def extract_pos(translation: str) -> str:
    """从翻译中提取词性"""
    if not translation:
        return ""
    parts = translation.split(".", 1)
    pos_map = {
        "adj": "adj.",
        "adv": "adv.",
        "n": "n.",
        "v": "v.",
        "vt": "vt.",
        "vi": "vi.",
        "prep": "prep.",
        "conj": "conj.",
        "pron": "pron.",
        "interj": "interj.",
        "det": "det.",
        "num": "num.",
        "art": "art.",
        "aux": "aux.",
    }
    first = parts[0].strip().lower()
    for key, val in pos_map.items():
        if first.startswith(key):
            return val
    return ""


def extract_level(tag: str) -> str:
    """从标签提取考试等级"""
    if not tag:
        return ""
    tags = tag.strip().split()
    levels = []
    for t in tags:
        if t in TAG_LEVEL_MAP:
            levels.append(TAG_LEVEL_MAP[t])
    return ",".join(levels) if levels else ""


def import_to_sqlite(limit: int = None):
    """导入到数据库（自动检测SQLite/MySQL）"""
    from sqlalchemy import text

    from backend.database import _get_engine

    src = sqlite3.connect(ECDICT_PATH)
    src.row_factory = sqlite3.Row

    engine = _get_engine()
    is_mysql = "mysql" in str(engine.url).lower()
    insert_sql = (
        """
        INSERT IGNORE INTO dictionary_word
        (word, phonetic, audio_url, part_of_speech, chinese_meaning, level)
        VALUES (:word, :phonetic, :audio_url, :pos, :meaning, :level)
    """
        if is_mysql
        else """
        INSERT OR IGNORE INTO dictionary_word
        (word, phonetic, audio_url, part_of_speech, chinese_meaning, level)
        VALUES (:word, :phonetic, :audio_url, :pos, :meaning, :level)
    """
    )
    count = 0

    query = "SELECT * FROM stardict WHERE translation IS NOT NULL AND translation != ''"
    if limit:
        query += f" LIMIT {limit}"

    with engine.connect() as conn:
        rows = src.execute(query).fetchall()
        for row in rows:
            word = row["word"].strip().lower()
            if not word or len(word) > 100:
                continue

            phonetic = row["phonetic"] or ""
            audio_url = row["audio"] or ""
            pos = extract_pos(row["translation"])
            chinese_meaning = row["translation"][:255] if row["translation"] else ""
            level = extract_level(row["tag"])

            try:
                conn.execute(
                    text(insert_sql),
                    {
                        "word": word,
                        "phonetic": phonetic,
                        "audio_url": audio_url,
                        "pos": pos,
                        "meaning": chinese_meaning,
                        "level": level,
                    },
                )
                count += 1
                if count % 10000 == 0:
                    conn.commit()
                    print(f"  Imported {count} words...")
            except Exception:
                pass  # skip duplicates

        conn.commit()

    src.close()
    print(f"Done! Imported {count} words into dictionary_word")


def import_to_mysql(limit: int = None):
    """导入到 MySQL（生产环境）"""
    import pymysql

    src = sqlite3.connect(ECDICT_PATH)
    src.row_factory = sqlite3.Row

    conn = pymysql.connect(
        host="localhost",
        user="root",
        password="",
        database="megawords",
        charset="utf8mb4",
    )
    cursor = conn.cursor()
    count = 0

    query = "SELECT * FROM stardict WHERE translation IS NOT NULL AND translation != ''"
    if limit:
        query += f" LIMIT {limit}"

    rows = src.execute(query).fetchall()
    for row in rows:
        word = row["word"].strip().lower()
        if not word or len(word) > 100:
            continue

        phonetic = row["phonetic"] or ""
        audio_url = row["audio"] or ""
        pos = extract_pos(row["translation"])
        chinese_meaning = row["translation"][:255] if row["translation"] else ""
        level = extract_level(row["tag"])

        try:
            cursor.execute(
                """
                INSERT IGNORE INTO dictionary_word
                (word, phonetic, audio_url, part_of_speech, chinese_meaning, level)
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
                (word, phonetic, audio_url, pos, chinese_meaning, level),
            )
            count += 1
            if count % 10000 == 0:
                conn.commit()
                print(f"  Imported {count} words...")
        except Exception:
            pass

    conn.commit()
    cursor.close()
    conn.close()
    src.close()
    print(f"Done! Imported {count} words into MySQL dictionary_word")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import ECDICT into MegaWords")
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of words to import"
    )
    parser.add_argument(
        "--mysql", action="store_true", help="Import to MySQL instead of SQLite"
    )
    args = parser.parse_args()

    if not os.path.exists(ECDICT_PATH):
        print(f"ECDICT database not found at {ECDICT_PATH}")
        print("Please download from: https://github.com/skywind3000/ECDICT/releases")
        sys.exit(1)

    print(f"Starting ECDICT import (limit={args.limit}, mysql={args.mysql})...")
    if args.mysql:
        import_to_mysql(args.limit)
    else:
        import_to_sqlite(args.limit)
