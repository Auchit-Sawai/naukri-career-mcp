"""
Database Models and Manager for Naukri Career Management
========================================================
SQLite database for storing jobs, applications, profile history, and resume data.
"""

import asyncio
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from contextlib import asynccontextmanager
import aiosqlite


class DatabaseManager:
    """Manages SQLite database for Naukri career data."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize database connection and create tables."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()
        await self._create_indexes()

    async def _create_tables(self) -> None:
        """Create all necessary tables."""
        schema = """
        -- Profile snapshots for history tracking
        CREATE TABLE IF NOT EXISTS profile_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            profile_url TEXT,
            headline TEXT,
            summary TEXT,
            skills TEXT, -- JSON array
            experience TEXT, -- JSON array
            education TEXT, -- JSON array
            certifications TEXT, -- JSON array
            projects TEXT, -- JSON array
            preferences TEXT, -- JSON object
            completeness_score REAL,
            raw_data TEXT -- Full raw profile JSON
        );

        -- Job search results
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE NOT NULL, -- Naukri job ID
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            experience_min INTEGER,
            experience_max INTEGER,
            salary_min REAL,
            salary_max REAL,
            job_type TEXT,
            description TEXT,
            requirements TEXT,
            skills TEXT, -- JSON array
            posted_date TEXT,
            job_url TEXT UNIQUE NOT NULL,
            source TEXT DEFAULT 'naukri',
            search_keywords TEXT, -- JSON array
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Job applications tracking
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER REFERENCES jobs(id),
            job_url TEXT NOT NULL,
            job_title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            applied_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'applied', -- applied, screening, interview, offer, rejected, withdrawn
            match_score REAL,
            resume_version TEXT, -- Path or hash of resume used
            cover_letter_path TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Interview rounds and recruiter communications
        CREATE TABLE IF NOT EXISTS interview_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL REFERENCES applications(id),
            round_number INTEGER NOT NULL,
            interview_date TEXT,
            interview_type TEXT, -- phone, video, onsite, technical, hr
            interviewer_name TEXT,
            interviewer_role TEXT,
            feedback TEXT,
            status TEXT, -- scheduled, completed, cancelled, rescheduled
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Recruiter contacts
        CREATE TABLE IF NOT EXISTS recruiter_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER REFERENCES applications(id),
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            linkedin_url TEXT,
            company TEXT,
            role TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Resume versions and parsing results
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_hash TEXT NOT NULL,
            parsed_data TEXT, -- JSON of parsed resume
            parsed_at TEXT NOT NULL DEFAULT (datetime('now')),
            is_base_resume BOOLEAN DEFAULT FALSE
        );

        -- Tailored resumes generated for specific jobs
        CREATE TABLE IF NOT EXISTS tailored_resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            base_resume_id INTEGER REFERENCES resumes(id),
            job_id INTEGER REFERENCES jobs(id),
            output_path TEXT NOT NULL,
            modifications TEXT, -- JSON of changes made
            match_score REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Cover letters generated
        CREATE TABLE IF NOT EXISTS cover_letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            base_resume_id INTEGER REFERENCES resumes(id),
            job_id INTEGER REFERENCES jobs(id),
            output_path TEXT NOT NULL,
            tone TEXT,
            content TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Profile change proposals (for approval workflow)
        CREATE TABLE IF NOT EXISTS profile_change_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_url TEXT,
            proposed_changes TEXT NOT NULL, -- JSON of all proposed changes
            resume_path TEXT,
            target_roles TEXT, -- JSON array
            target_industries TEXT, -- JSON array
            status TEXT DEFAULT 'pending', -- pending, approved, rejected, applied
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            reviewed_at TEXT,
            applied_at TEXT
        );

        -- Profile change history (applied changes)
        CREATE TABLE IF NOT EXISTS profile_change_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id INTEGER REFERENCES profile_change_proposals(id),
            field_name TEXT NOT NULL, -- headline, summary, skills, experience, etc.
            old_value TEXT,
            new_value TEXT,
            applied_at TEXT NOT NULL DEFAULT (datetime('now')),
            success BOOLEAN DEFAULT TRUE,
            error_message TEXT
        );

        -- Search history for analytics
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_params TEXT NOT NULL, -- JSON of search parameters
            results_count INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- User preferences and settings
        CREATE TABLE IF NOT EXISTS user_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
        await self._connection.executescript(schema)
        await self._connection.commit()

    async def _create_indexes(self) -> None:
        """Create database indexes for performance."""
        indexes = """
        CREATE INDEX IF NOT EXISTS idx_jobs_job_id ON jobs(job_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
        CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs(location);
        CREATE INDEX IF NOT EXISTS idx_jobs_posted_date ON jobs(posted_date);
        CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);
        CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
        CREATE INDEX IF NOT EXISTS idx_applications_applied_date ON applications(applied_date);
        CREATE INDEX IF NOT EXISTS idx_applications_company ON applications(company);
        CREATE INDEX IF NOT EXISTS idx_interview_rounds_application_id ON interview_rounds(application_id);
        CREATE INDEX IF NOT EXISTS idx_recruiter_contacts_application_id ON recruiter_contacts(application_id);
        CREATE INDEX IF NOT EXISTS idx_profile_snapshots_timestamp ON profile_snapshots(timestamp);
        CREATE INDEX IF NOT EXISTS idx_profile_change_proposals_status ON profile_change_proposals(status);
        """
        await self._connection.executescript(indexes)
        await self._connection.commit()

    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions."""
        await self._connection.execute("BEGIN")
        try:
            yield self._connection
            await self._connection.commit()
        except Exception:
            await self._connection.rollback()
            raise

    # ==================== Profile Snapshot Methods ====================

    async def save_profile_snapshot(self, data: Dict[str, Any]) -> int:
        """Save a profile snapshot."""
        cursor = await self._connection.execute(
            """INSERT INTO profile_snapshots
               (timestamp, profile_url, headline, summary, skills, experience,
                education, certifications, projects, preferences, completeness_score, raw_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().isoformat(),
                data.get("profile_url"),
                data.get("headline"),
                data.get("summary"),
                json.dumps(data.get("skills", [])),
                json.dumps(data.get("experience", [])),
                json.dumps(data.get("education", [])),
                json.dumps(data.get("certifications", [])),
                json.dumps(data.get("projects", [])),
                json.dumps(data.get("preferences", {})),
                data.get("completeness_score"),
                json.dumps(data.get("raw_data", {}))
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_latest_profile_snapshot(self) -> Optional[Dict[str, Any]]:
        """Get the most recent profile snapshot."""
        cursor = await self._connection.execute(
            "SELECT * FROM profile_snapshots ORDER BY timestamp DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if row:
            return self._row_to_profile_snapshot(row)
        return None

    async def get_profile_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get profile change history."""
        cursor = await self._connection.execute(
            "SELECT * FROM profile_snapshots ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [self._row_to_profile_snapshot(row) for row in rows]

    def _row_to_profile_snapshot(self, row: aiosqlite.Row) -> Dict[str, Any]:
        """Convert database row to profile snapshot dict."""
        return {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "profile_url": row["profile_url"],
            "headline": row["headline"],
            "summary": row["summary"],
            "skills": json.loads(row["skills"] or "[]"),
            "experience": json.loads(row["experience"] or "[]"),
            "education": json.loads(row["education"] or "[]"),
            "certifications": json.loads(row["certifications"] or "[]"),
            "projects": json.loads(row["projects"] or "[]"),
            "preferences": json.loads(row["preferences"] or "{}"),
            "completeness_score": row["completeness_score"],
            "raw_data": json.loads(row["raw_data"] or "{}")
        }

    # ==================== Job Methods ====================

    async def save_job(self, job_data: Dict[str, Any]) -> int:
        """Save or update a job listing."""
        # Check if job exists
        cursor = await self._connection.execute(
            "SELECT id FROM jobs WHERE job_url = ?", (job_data["job_url"],)
        )
        existing = await cursor.fetchone()

        if existing:
            # Update existing
            await self._connection.execute(
                """UPDATE jobs SET
                   title=?, company=?, location=?, experience_min=?, experience_max=?,
                   salary_min=?, salary_max=?, job_type=?, description=?, requirements=?,
                   skills=?, posted_date=?, search_keywords=?, updated_at=?
                   WHERE job_url=?""",
                (
                    job_data.get("title"),
                    job_data.get("company"),
                    job_data.get("location"),
                    job_data.get("experience_min"),
                    job_data.get("experience_max"),
                    job_data.get("salary_min"),
                    job_data.get("salary_max"),
                    job_data.get("job_type"),
                    job_data.get("description"),
                    job_data.get("requirements"),
                    json.dumps(job_data.get("skills", [])),
                    job_data.get("posted_date"),
                    json.dumps(job_data.get("search_keywords", [])),
                    datetime.now().isoformat(),
                    job_data["job_url"]
                )
            )
            await self._connection.commit()
            return existing["id"]
        else:
            # Insert new
            cursor = await self._connection.execute(
                """INSERT INTO jobs
                   (job_id, title, company, location, experience_min, experience_max,
                    salary_min, salary_max, job_type, description, requirements,
                    skills, posted_date, job_url, search_keywords)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_data.get("job_id"),
                    job_data.get("title"),
                    job_data.get("company"),
                    job_data.get("location"),
                    job_data.get("experience_min"),
                    job_data.get("experience_max"),
                    job_data.get("salary_min"),
                    job_data.get("salary_max"),
                    job_data.get("job_type"),
                    job_data.get("description"),
                    job_data.get("requirements"),
                    json.dumps(job_data.get("skills", [])),
                    job_data.get("posted_date"),
                    job_data["job_url"],
                    json.dumps(job_data.get("search_keywords", []))
                )
            )
            await self._connection.commit()
            return cursor.lastrowid

    async def get_job(self, job_url: str) -> Optional[Dict[str, Any]]:
        """Get job by URL."""
        cursor = await self._connection.execute(
            "SELECT * FROM jobs WHERE job_url = ?", (job_url,)
        )
        row = await cursor.fetchone()
        if row:
            return self._row_to_job(row)
        return None

    async def search_jobs(self, filters: Dict[str, Any], limit: int = 50) -> List[Dict[str, Any]]:
        """Search jobs with filters."""
        query = "SELECT * FROM jobs WHERE 1=1"
        params = []

        if filters.get("company"):
            query += " AND company LIKE ?"
            params.append(f"%{filters['company']}%")
        if filters.get("location"):
            query += " AND location LIKE ?"
            params.append(f"%{filters['location']}%")
        if filters.get("title"):
            query += " AND title LIKE ?"
            params.append(f"%{filters['title']}%")
        if filters.get("date_from"):
            query += " AND posted_date >= ?"
            params.append(filters["date_from"])
        if filters.get("date_to"):
            query += " AND posted_date <= ?"
            params.append(filters["date_to"])

        query += " ORDER BY posted_date DESC LIMIT ?"
        params.append(limit)

        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_job(row) for row in rows]

    def _row_to_job(self, row: aiosqlite.Row) -> Dict[str, Any]:
        """Convert database row to job dict."""
        return {
            "id": row["id"],
            "job_id": row["job_id"],
            "title": row["title"],
            "company": row["company"],
            "location": row["location"],
            "experience_min": row["experience_min"],
            "experience_max": row["experience_max"],
            "salary_min": row["salary_min"],
            "salary_max": row["salary_max"],
            "job_type": row["job_type"],
            "description": row["description"],
            "requirements": row["requirements"],
            "skills": json.loads(row["skills"] or "[]"),
            "posted_date": row["posted_date"],
            "job_url": row["job_url"],
            "source": row["source"],
            "search_keywords": json.loads(row["search_keywords"] or "[]"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    # ==================== Application Methods ====================

    async def create_application(self, app_data: Dict[str, Any]) -> int:
        """Create a new application record."""
        cursor = await self._connection.execute(
            """INSERT INTO applications
               (job_id, job_url, job_title, company, location, applied_date,
                status, match_score, resume_version, cover_letter_path, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                app_data.get("job_id"),
                app_data["job_url"],
                app_data["job_title"],
                app_data["company"],
                app_data.get("location"),
                app_data.get("applied_date", datetime.now().isoformat()),
                app_data.get("status", "applied"),
                app_data.get("match_score"),
                app_data.get("resume_version"),
                app_data.get("cover_letter_path"),
                app_data.get("notes")
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def update_application(self, app_id: int, updates: Dict[str, Any]) -> bool:
        """Update application record."""
        set_clauses = []
        params = []

        for key, value in updates.items():
            if key in ["status", "match_score", "resume_version", "cover_letter_path", "notes"]:
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            return False

        set_clauses.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(app_id)

        query = f"UPDATE applications SET {', '.join(set_clauses)} WHERE id = ?"
        cursor = await self._connection.execute(query, params)
        await self._connection.commit()
        return cursor.rowcount > 0

    async def get_applications(self, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Get applications with filters."""
        query = "SELECT * FROM applications WHERE 1=1"
        params = []

        if filters.get("status"):
            query += " AND status = ?"
            params.append(filters["status"])
        if filters.get("company"):
            query += " AND company LIKE ?"
            params.append(f"%{filters['company']}%")
        if filters.get("date_from"):
            query += " AND applied_date >= ?"
            params.append(filters["date_from"])
        if filters.get("date_to"):
            query += " AND applied_date <= ?"
            params.append(filters["date_to"])

        query += " ORDER BY applied_date DESC LIMIT ?"
        params.append(limit)

        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_application(row) for row in rows]

    async def get_application_stats(self, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
        """Get application statistics."""
        where_clause = "WHERE 1=1"
        params = []

        if date_from:
            where_clause += " AND applied_date >= ?"
            params.append(date_from)
        if date_to:
            where_clause += " AND applied_date <= ?"
            params.append(date_to)

        # Total applications
        cursor = await self._connection.execute(
            f"SELECT COUNT(*) as total FROM applications {where_clause}", params
        )
        total = (await cursor.fetchone())["total"]

        # By status
        cursor = await self._connection.execute(
            f"SELECT status, COUNT(*) as count FROM applications {where_clause} GROUP BY status", params
        )
        by_status = {row["status"]: row["count"] for row in await cursor.fetchall()}

        # By company (top 10)
        cursor = await self._connection.execute(
            f"SELECT company, COUNT(*) as count FROM applications {where_clause} GROUP BY company ORDER BY count DESC LIMIT 10", params
        )
        by_company = {row["company"]: row["count"] for row in await cursor.fetchall()}

        # Average match score
        cursor = await self._connection.execute(
            f"SELECT AVG(match_score) as avg_score FROM applications {where_clause} AND match_score IS NOT NULL", params
        )
        avg_score = (await cursor.fetchone())["avg_score"] or 0

        return {
            "total_applications": total,
            "by_status": by_status,
            "top_companies": by_company,
            "average_match_score": round(avg_score, 1)
        }

    def _row_to_application(self, row: aiosqlite.Row) -> Dict[str, Any]:
        """Convert database row to application dict."""
        return {
            "id": row["id"],
            "job_id": row["job_id"],
            "job_url": row["job_url"],
            "job_title": row["job_title"],
            "company": row["company"],
            "location": row["location"],
            "applied_date": row["applied_date"],
            "status": row["status"],
            "match_score": row["match_score"],
            "resume_version": row["resume_version"],
            "cover_letter_path": row["cover_letter_path"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    # ==================== Interview Round Methods ====================

    async def add_interview_round(self, round_data: Dict[str, Any]) -> int:
        """Add an interview round."""
        cursor = await self._connection.execute(
            """INSERT INTO interview_rounds
               (application_id, round_number, interview_date, interview_type,
                interviewer_name, interviewer_role, feedback, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                round_data["application_id"],
                round_data["round_number"],
                round_data.get("interview_date"),
                round_data.get("interview_type"),
                round_data.get("interviewer_name"),
                round_data.get("interviewer_role"),
                round_data.get("feedback"),
                round_data.get("status", "scheduled"),
                round_data.get("notes")
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_interview_rounds(self, application_id: int) -> List[Dict[str, Any]]:
        """Get interview rounds for an application."""
        cursor = await self._connection.execute(
            "SELECT * FROM interview_rounds WHERE application_id = ? ORDER BY round_number",
            (application_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # ==================== Recruiter Contact Methods ====================

    async def add_recruiter_contact(self, contact_data: Dict[str, Any]) -> int:
        """Add a recruiter contact."""
        cursor = await self._connection.execute(
            """INSERT INTO recruiter_contacts
               (application_id, name, email, phone, linkedin_url, company, role, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                contact_data.get("application_id"),
                contact_data["name"],
                contact_data.get("email"),
                contact_data.get("phone"),
                contact_data.get("linkedin_url"),
                contact_data.get("company"),
                contact_data.get("role"),
                contact_data.get("notes")
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    # ==================== Resume Methods ====================

    async def save_resume(self, file_path: str, file_hash: str, parsed_data: Dict[str, Any], is_base: bool = False) -> int:
        """Save resume parsing result."""
        cursor = await self._connection.execute(
            """INSERT OR REPLACE INTO resumes (file_path, file_hash, parsed_data, is_base_resume)
               VALUES (?, ?, ?, ?)""",
            (file_path, file_hash, json.dumps(parsed_data), is_base)
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_resume(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get resume by file path."""
        cursor = await self._connection.execute(
            "SELECT * FROM resumes WHERE file_path = ?", (file_path,)
        )
        row = await cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "file_path": row["file_path"],
                "file_hash": row["file_hash"],
                "parsed_data": json.loads(row["parsed_data"] or "{}"),
                "parsed_at": row["parsed_at"],
                "is_base_resume": bool(row["is_base_resume"])
            }
        return None

    async def save_tailored_resume(self, data: Dict[str, Any]) -> int:
        """Save tailored resume record."""
        cursor = await self._connection.execute(
            """INSERT INTO tailored_resumes
               (base_resume_id, job_id, output_path, modifications, match_score)
               VALUES (?, ?, ?, ?, ?)""",
            (
                data["base_resume_id"],
                data.get("job_id"),
                data["output_path"],
                json.dumps(data.get("modifications", {})),
                data.get("match_score")
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def save_cover_letter(self, data: Dict[str, Any]) -> int:
        """Save cover letter record."""
        cursor = await self._connection.execute(
            """INSERT INTO cover_letters
               (base_resume_id, job_id, output_path, tone, content)
               VALUES (?, ?, ?, ?, ?)""",
            (
                data["base_resume_id"],
                data.get("job_id"),
                data["output_path"],
                data.get("tone", "professional"),
                data.get("content")
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    # ==================== Profile Change Proposal Methods ====================

    async def save_profile_change_proposal(self, proposal_data: Dict[str, Any]) -> int:
        """Save a profile change proposal for approval."""
        cursor = await self._connection.execute(
            """INSERT INTO profile_change_proposals
               (profile_url, proposed_changes, resume_path, target_roles, target_industries, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                proposal_data.get("profile_url"),
                json.dumps(proposal_data["proposed_changes"]),
                proposal_data.get("resume_path"),
                json.dumps(proposal_data.get("target_roles", [])),
                json.dumps(proposal_data.get("target_industries", [])),
                proposal_data.get("status", "pending")
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_profile_change_proposal(self, proposal_id: int) -> Optional[Dict[str, Any]]:
        """Get a profile change proposal."""
        cursor = await self._connection.execute(
            "SELECT * FROM profile_change_proposals WHERE id = ?", (proposal_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "profile_url": row["profile_url"],
                "proposed_changes": json.loads(row["proposed_changes"]),
                "resume_path": row["resume_path"],
                "target_roles": json.loads(row["target_roles"] or "[]"),
                "target_industries": json.loads(row["target_industries"] or "[]"),
                "status": row["status"],
                "created_at": row["created_at"],
                "reviewed_at": row["reviewed_at"],
                "applied_at": row["applied_at"]
            }
        return None

    async def update_proposal_status(self, proposal_id: int, status: str) -> bool:
        """Update proposal status."""
        now = datetime.now().isoformat()
        field = "reviewed_at" if status in ["approved", "rejected"] else "applied_at"
        cursor = await self._connection.execute(
            f"UPDATE profile_change_proposals SET status = ?, {field} = ? WHERE id = ?",
            (status, now, proposal_id)
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def save_profile_change_history(self, history_data: Dict[str, Any]) -> int:
        """Record applied profile change."""
        cursor = await self._connection.execute(
            """INSERT INTO profile_change_history
               (proposal_id, field_name, old_value, new_value, success, error_message)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                history_data.get("proposal_id"),
                history_data["field_name"],
                history_data.get("old_value"),
                history_data.get("new_value"),
                history_data.get("success", True),
                history_data.get("error_message")
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    # ==================== Search History ====================

    async def save_search_history(self, search_params: Dict[str, Any], results_count: int) -> int:
        """Save search parameters for analytics."""
        cursor = await self._connection.execute(
            "INSERT INTO search_history (search_params, results_count) VALUES (?, ?)",
            (json.dumps(search_params), results_count)
        )
        await self._connection.commit()
        return cursor.lastrowid

    # ==================== Settings ====================

    async def set_setting(self, key: str, value: str) -> None:
        """Set a user setting."""
        await self._connection.execute(
            "INSERT OR REPLACE INTO user_settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat())
        )
        await self._connection.commit()

    async def get_setting(self, key: str, default: str = "") -> str:
        """Get a user setting."""
        cursor = await self._connection.execute(
            "SELECT value FROM user_settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else default

    # ==================== Export ====================

    async def export_table(self, table: str, format: str = "csv") -> str:
        """Export a table to CSV or JSON."""
        cursor = await self._connection.execute(f"SELECT * FROM {table}")
        rows = await cursor.fetchall()
        data = [dict(row) for row in rows]

        if format == "json":
            return json.dumps(data, indent=2, default=str)
        else:
            # CSV
            if not data:
                return ""
            import csv
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            return output.getvalue()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
