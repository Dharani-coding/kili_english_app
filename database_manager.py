import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import random

RECALL_COUNT = 3


class DBManager:
    def __init__(self, db_path="english_learning.db"):
        self.conn = sqlite3.connect(db_path)
        self._create_tables()

    def _create_tables(self):
        tables = {
            "GrammarMistakes": "mistake TEXT UNIQUE, correction TEXT",
            "BetterPhrases": "original TEXT UNIQUE, better TEXT",
            "BetterVocabulary": "word TEXT UNIQUE, better_word TEXT",
            "NewWords": "word TEXT UNIQUE",
            "NewPhrases": "phrase TEXT UNIQUE",
        }

        for table, fields in tables.items():
            query = f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {fields},
                learned_date TEXT,
                recalled_count INTEGER DEFAULT 0,
                note TEXT
            );
            """
            self.conn.execute(query)
        self.conn.commit()

    def _add_entry(
        self, table: str, data: Dict[str, str], note: Optional[str] = None
    ) -> bool:
        keys = ", ".join(data.keys()) + ", learned_date, note"
        placeholders = ", ".join("?" for _ in data) + ", ?, ?"
        values = list(data.values()) + [datetime.today().strftime("%Y-%m-%d"), note]

        try:
            self.conn.execute(
                f"INSERT INTO {table} ({keys}) VALUES ({placeholders})", values
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_random_from_tables(
        self, tables: List[str], total_limit: int = 5
    ) -> List[Dict]:
        """
        Retrieves a combined list of random entries from multiple tables.
        It evenly distributes `total_limit` across the given tables and
        fetches entries where recalled_count < RECALL_COUNT.
        """
        if not tables:
            return []

        results = []
        per_table_limit = max(1, total_limit // len(tables))

        for table in tables:
            cursor = self.conn.execute(
                f"SELECT * FROM {table} WHERE recalled_count < {RECALL_COUNT} ORDER BY RANDOM() LIMIT ?",
                (per_table_limit,),
            )
            columns = [desc[0] for desc in cursor.description]
            entries = cursor.fetchall()

            for entry in entries:
                self._increment_recall_count(table, entry[0])
                record = dict(zip(columns, entry))
                record["table"] = table  # Optionally tag with table name
                results.append(record)

        # If we got fewer results than total_limit, pad with additional randoms
        if len(results) < total_limit:
            random.shuffle(results)
        return results[:total_limit]

    def add_grammar_mistake(
        self, mistake: str, correction: str, note: Optional[str] = None
    ) -> bool:
        return self._add_entry(
            "GrammarMistakes", {"mistake": mistake, "correction": correction}, note
        )

    def add_better_phrase(
        self, original: str, better: str, note: Optional[str] = None
    ) -> bool:
        return self._add_entry(
            "BetterPhrases", {"original": original, "better": better}, note
        )

    def add_better_vocabulary(
        self, word: str, better_word: str, note: Optional[str] = None
    ) -> bool:
        return self._add_entry(
            "BetterVocabulary", {"word": word, "better_word": better_word}, note
        )

    def add_new_word(self, word: str, note: Optional[str] = None) -> bool:
        return self._add_entry("NewWords", {"word": word}, note)

    def add_new_phrase(self, phrase: str, note: Optional[str] = None) -> bool:
        return self._add_entry("NewPhrases", {"phrase": phrase}, note)

    def _increment_recall_count(self, table: str, entry_id: int):
        self.conn.execute(
            f"UPDATE {table} SET recalled_count = recalled_count + 1 WHERE id = ?",
            (entry_id,),
        )
        self.conn.commit()

    def _get_random_entries(self, table: str, limit: int = 5) -> List[Dict[str, str]]:
        cursor = self.conn.execute(
            f"SELECT * FROM {table} WHERE recalled_count < {RECALL_COUNT} ORDER BY RANDOM() LIMIT ?",
            (limit,),
        )
        columns = [description[0] for description in cursor.description]
        results = []
        for row in cursor.fetchall():
            self._increment_recall_count(table, row[0])
            results.append(dict(zip(columns, row)))
        return results

    def get_random_grammar_mistakes(self, limit: int = 5) -> List[Dict]:
        return self._get_random_entries("GrammarMistakes", limit)

    def get_random_better_phrases(self, limit: int = 5) -> List[Dict]:
        return self._get_random_entries("BetterPhrases", limit)

    def get_random_better_vocabulary(self, limit: int = 5) -> List[Dict]:
        return self._get_random_entries("BetterVocabulary", limit)

    def get_random_new_words(self, limit: int = 5) -> List[Dict]:
        return self._get_random_entries("NewWords", limit)

    def get_random_new_phrases(self, limit: int = 5) -> List[Dict]:
        return self._get_random_entries("NewPhrases", limit)

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    db = DBManager()

    db.add_grammar_mistake("He don't like it", "He doesn't like it", "Common mistake")
    db.add_better_phrase(
        "I'm going to sleep now", "I'm heading to bed", "Natural phrasing"
    )
    db.add_better_vocabulary("very big", "enormous", "Advanced vocab")
    db.add_new_word("nitty-gritty", "Heard it in a podcast")
    db.add_new_phrase("looked down upon", "From an article")

    # print("\nGrammar Mistakes:")
    # for e in db.get_random_grammar_mistakes():
    #     print(e)

    # print("\nBetter Phrases:")
    # for e in db.get_random_better_phrases():
    #     print(e)

    # print("\nBetter Vocabulary:")
    # for e in db.get_random_better_vocabulary():
    #     print(e)

    # print("\nNew Words:")
    # for e in db.get_random_new_words():
    #     print(e)

    # print("\nNew Phrases:")
    # for e in db.get_random_new_phrases():
    #     print(e)

    print("\nRandom Mix from Multiple Tables:")
    mixed = db.get_random_from_tables(
        ["GrammarMistakes", "BetterPhrases", "NewWords"], total_limit=3
    )

    for item in mixed:
        print(f"[{item['table']}] {item}\n")

    db.close()
