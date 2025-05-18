import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

class DBManager:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self._create_table()

    def _create_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS English_Learnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grammar_mistakes TEXT,
            better_vocabulary TEXT,
            better_phrases TEXT,
            new_vocabulary TEXT,
            new_phrases TEXT,
            learned_date TEXT,
            recalled_count INTEGER DEFAULT 0,
            note TEXT
        );
        """
        self.conn.execute(query)
        self.conn.commit()

    def add_learning_entry(
        self,
        feedback_json: Dict[str, Any],
        new_vocab: List[str],
        new_phrases: List[str],
        note: Optional[str] = None
    ) -> bool:
        if not (feedback_json or new_vocab or new_phrases):
            return False  # Don't insert empty learnings

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO English_Learnings (
                grammar_mistakes,
                better_vocabulary,
                better_phrases,
                new_vocabulary,
                new_phrases,
                learned_date,
                recalled_count,
                note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            json.dumps(feedback_json.get("grammar_mistakes", {})),
            json.dumps(feedback_json.get("better_vocabulary", {})),
            json.dumps(feedback_json.get("better_phrases", {})),
            json.dumps(new_vocab),
            json.dumps(new_phrases),
            datetime.today().strftime('%Y-%m-%d'),
            0,
            note
        ))
        self.conn.commit()
        return True

    def get_random_learnings(self, learning_type: str = "", limit: int = 5) -> List[Dict[str, Any]]:
        query = """
        SELECT * FROM English_Learnings
        WHERE recalled_count < 2
        """
        
        params = []
        
        if learning_type:
            if learning_type == "grammar":
                query += " AND grammar_mistakes != '{}'"
            elif learning_type == "vocabulary":
                query += " AND (better_vocabulary != '{}' OR new_vocabulary != '[]')"
            elif learning_type == "phrases":
                query += " AND (better_phrases != '{}' OR new_phrases != '[]')"
        
        query += " ORDER BY RANDOM() LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()
        return [self._format_entry(row) for row in rows]

    def _format_entry(self, row) -> Dict[str, Any]:
        return {
            "id": row[0],
            "grammar_mistakes": json.loads(row[1] or '{}'),
            "better_vocabulary": json.loads(row[2] or '{}'),
            "better_phrases": json.loads(row[3] or '{}'),
            "new_vocabulary": json.loads(row[4] or '[]'),
            "new_phrases": json.loads(row[5] or '[]'),
            "learned_date": row[6],
            "recalled_count": row[7],
            "note": row[8]
        }

    def mark_as_recalled(self, id: int):
        self.conn.execute("""
            UPDATE English_Learnings
            SET recalled_count = recalled_count + 1
            WHERE id = ?
        """, (id,))
        self.conn.commit()

    def close(self):
        self.conn.close()


if __name__ == "__main__":
        # Initialize the database manager
    db = DBManager()

    # Example input data
    feedback_json = {
        "grammar_mistakes": {
            "He don't know the answer.": "He doesn't know the answer."
        },
        "better_vocabulary": {
            "very big": "enormous"
        },
        "better_phrases": {
            "I am going to sleep now.": "I'm heading to bed now."
        }
    }

    new_vocab = ["nitty-gritty"]
    new_phrases = ["looked down upon"]

    # 1. Adding a learning entry
    success = db.add_learning_entry(
        feedback_json=feedback_json,
        new_vocab=[],
        new_phrases=[],
        note="First example entry"
    )

    if success:
        print("Successfully added learning entry!")
    else:
        print("Failed to add entry (possibly duplicate)")

    success = db.add_learning_entry(
        feedback_json={},
        new_vocab=[],
        new_phrases=new_phrases,
        note="2 example entry"
    )

    success = db.add_learning_entry(
        feedback_json={},
        new_vocab=new_vocab,
        new_phrases=[],
        note="3 example entry"
    )

    # 2. Retrieving random learnings by type
    print("\nGetting grammar learnings:")
    grammar_learnings = db.get_random_learnings(learning_type="grammar", limit=2)
    for learning in grammar_learnings:
        print(f"- {learning['grammar_mistakes']}")

    print("\nGetting vocabulary learnings:")
    vocab_learnings = db.get_random_learnings(learning_type="vocabulary", limit=2)
    for learning in vocab_learnings:
        print(f"- {learning['better_vocabulary']} or {learning['new_vocabulary']}")

    print("\nGetting phrase learnings:")
    phrase_learnings = db.get_random_learnings(learning_type="phrases", limit=2)
    for learning in phrase_learnings:
        print(f"- {learning['better_phrases']} or {learning['new_phrases']}")

    # 3. Marking an entry as recalled
    if grammar_learnings:
        first_id = grammar_learnings[0]['id']
        db.mark_as_recalled(first_id)
        print(f"\nMarked entry {first_id} as recalled")

    # 4. Getting all learnings (no type filter)
    print("\nGetting all learnings:")
    all_learnings = db.get_random_learnings(limit=2)
    for learning in all_learnings:
        print(learning)

    # Close the database connection when done
    db.close()