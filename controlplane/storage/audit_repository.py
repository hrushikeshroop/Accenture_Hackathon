from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from controlplane.security.redaction import redact_text


class AuditRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with closing(self.connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS evaluations (
                    evaluation_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    use_case TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    risk_tier TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    is_replay INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    evaluation_id TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(evaluations)"
                ).fetchall()
            }
            if "is_replay" not in columns:
                connection.execute(
                    "ALTER TABLE evaluations ADD COLUMN "
                    "is_replay INTEGER NOT NULL DEFAULT 0"
                )
            connection.commit()

    def save(
        self,
        *,
        evaluation_id: str,
        event_id: str,
        fingerprint: str,
        use_case: str,
        policy_id: str,
        policy_version: str,
        decision: str,
        risk_tier: str,
        event: dict[str, Any],
        result: dict[str, Any],
        counts_toward_history: bool = True,
    ) -> None:
        with closing(self.connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO evaluations (
                    evaluation_id, event_id, fingerprint, use_case, policy_id,
                    policy_version, decision, risk_tier, event_json, result_json,
                    is_replay
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evaluation_id,
                    event_id,
                    fingerprint,
                    use_case,
                    policy_id,
                    policy_version,
                    decision,
                    risk_tier,
                    json.dumps(event, default=str),
                    json.dumps(result, default=str),
                    0 if counts_toward_history else 1,
                ),
            )
            connection.commit()

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM evaluations ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row(row) for row in rows]

    def get(self, evaluation_id: str) -> dict[str, Any] | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM evaluations WHERE evaluation_id = ?", (evaluation_id,)
            ).fetchone()
        return self._row(row) if row else None

    def history_stats(self, fingerprint: str) -> tuple[int, float]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                WITH latest_feedback AS (
                    SELECT f.evaluation_id, f.label
                    FROM feedback f
                    INNER JOIN (
                        SELECT evaluation_id, MAX(id) AS latest_id
                        FROM feedback
                        GROUP BY evaluation_id
                    ) latest ON f.id = latest.latest_id
                )
                SELECT COUNT(*) AS total,
                       SUM(
                           CASE
                                WHEN latest_feedback.label IN (
                                    'FALSE_POSITIVE', 'REVIEW_APPROVE'
                                ) THEN 0
                                WHEN latest_feedback.label IN (
                                    'UNSAFE_ESCAPE', 'INCORRECT',
                                    'REVIEW_REGENERATE', 'REVIEW_BLOCK'
                                ) THEN 1
                               WHEN evaluations.decision IN (
                                   'BLOCK', 'REGENERATE', 'ESCALATE'
                               ) THEN 1
                               ELSE 0
                           END
                       ) AS failures
                FROM evaluations
                LEFT JOIN latest_feedback
                    ON latest_feedback.evaluation_id = evaluations.evaluation_id
                WHERE fingerprint = ? AND is_replay = 0
                """,
                (fingerprint,),
            ).fetchone()
        total = int(row["total"] or 0)
        failures = int(row["failures"] or 0)
        return total, (failures / total if total else 0.0)

    def add_feedback(
        self, evaluation_id: str, reviewer_id: str, label: str, reason: str
    ) -> None:
        with closing(self.connect()) as connection:
            connection.execute(
                """
                INSERT INTO feedback (evaluation_id, reviewer_id, label, reason)
                VALUES (?, ?, ?, ?)
                """,
                (
                    evaluation_id,
                    redact_text(reviewer_id),
                    label,
                    redact_text(reason),
                ),
            )
            connection.commit()

    def list_feedback(self, limit: int = 10000) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM feedback ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["is_replay"] = bool(result.get("is_replay", 0))
        result["event"] = json.loads(result.pop("event_json"))
        result["result"] = json.loads(result.pop("result_json"))
        return result
