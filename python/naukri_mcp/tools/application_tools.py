"""
Application Tracking Tools
==========================
Tools for tracking job applications, interviews, and recruiter communications.
"""

import logging
import json
import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from naukri_mcp.db.database import DatabaseManager

logger = logging.getLogger(__name__)


class ApplicationTools:
    """Tools for application tracking and management."""

    def __init__(self, db: DatabaseManager, browser=None):
        self.db = db
        self.browser = browser

    async def track_application(self, job_url: str, job_title: str, company: str,
                                location: str = None, applied_date: str = None,
                                status: str = "applied", match_score: float = None,
                                notes: str = None) -> str:
        """Record a job application in local database."""
        logger.info(f"Tracking application: {job_title} at {company}")

        app_data = {
            "job_url": job_url,
            "job_title": job_title,
            "company": company,
            "location": location,
            "applied_date": applied_date or datetime.now().isoformat(),
            "status": status,
            "match_score": match_score,
            "notes": notes
        }

        # Check if job exists in database, get job_id
        job = await self.db.get_job(job_url)
        if job:
            app_data["job_id"] = job["id"]

        app_id = await self.db.create_application(app_data)

        return f"✅ Application tracked (ID: {app_id})\n" \
               f"   {job_title} at {company}\n" \
               f"   Status: {status} | Match Score: {match_score or 'N/A'}"

    async def update_application_status(self, application_id: int, status: str,
                                        interview_round: int = None,
                                        interview_date: str = None,
                                        interview_type: str = None,
                                        recruiter_name: str = None,
                                        recruiter_contact: str = None,
                                        notes: str = None) -> str:
        """Update application status and add interview/recruiter notes."""
        logger.info(f"Updating application {application_id} to {status}")

        updates = {"status": status}

        if interview_round is not None:
            updates["interview_round"] = interview_round
        if notes:
            updates["notes"] = notes

        success = await self.db.update_application(application_id, updates)

        if not success:
            return f"❌ Failed to update application {application_id}"

        result_lines = [f"✅ Application {application_id} updated to: {status}"]

        # Add interview round if provided
        if interview_round is not None:
            round_data = {
                "application_id": application_id,
                "round_number": interview_round,
                "interview_date": interview_date,
                "interview_type": interview_type,
                "interviewer_name": recruiter_name,
                "status": "scheduled" if interview_date else "completed"
            }
            if notes:
                round_data["notes"] = notes

            round_id = await self.db.add_interview_round(round_data)
            result_lines.append(f"   Interview Round {interview_round} added (ID: {round_id})")
            if interview_date:
                result_lines.append(f"   Date: {interview_date} | Type: {interview_type or 'Not specified'}")

        # Add recruiter contact if provided
        if recruiter_name:
            contact_data = {
                "application_id": application_id,
                "name": recruiter_name,
                "email": recruiter_contact if "@" in (recruiter_contact or "") else None,
                "phone": recruiter_contact if "@" not in (recruiter_contact or "") else None,
                "notes": notes
            }
            contact_id = await self.db.add_recruiter_contact(contact_data)
            result_lines.append(f"   Recruiter contact added (ID: {contact_id})")

        return "\n".join(result_lines)

    async def get_applications(self, status: str = None, company: str = None,
                               date_from: str = None, date_to: str = None,
                               limit: int = 100) -> str:
        """Get tracked applications with filters."""
        filters = {}
        if status:
            filters["status"] = status
        if company:
            filters["company"] = company
        if date_from:
            filters["date_from"] = date_from
        if date_to:
            filters["date_to"] = date_to

        applications = await self.db.get_applications(filters, limit)

        if not applications:
            return "No applications found matching the criteria."

        lines = [
            "=" * 60,
            f"APPLICATIONS ({len(applications)} found)",
            "=" * 60,
            ""
        ]

        for app in applications:
            status_emoji = {
                "applied": "📝",
                "screening": "🔍",
                "interview": "🎤",
                "offer": "🎉",
                "rejected": "❌",
                "withdrawn": "↩️"
            }.get(app["status"], "📋")

            lines.append(f"{status_emoji} [{app['id']}] {app['job_title']} at {app['company']}")
            lines.append(f"   📍 {app['location'] or 'N/A'} | 📅 Applied: {app['applied_date'][:10]}")
            lines.append(f"   Status: {app['status'].upper()} | Match: {app['match_score'] or 'N/A'}%")
            if app["notes"]:
                lines.append(f"   📝 {app['notes'][:100]}{'...' if len(app['notes']) > 100 else ''}")
            lines.append("")

        return "\n".join(lines)

    async def get_application_stats(self, date_from: str = None, date_to: str = None) -> str:
        """Get application statistics and pipeline summary."""
        stats = await self.db.get_application_stats(date_from, date_to)

        lines = [
            "=" * 60,
            "APPLICATION STATISTICS",
            "=" * 60,
            f"Total Applications: {stats['total_applications']}",
            f"Average Match Score: {stats['average_match_score']}%",
            "",
            "--- BY STATUS ---"
        ]

        status_order = ["applied", "screening", "interview", "offer", "rejected", "withdrawn"]
        for status in status_order:
            count = stats["by_status"].get(status, 0)
            if count > 0:
                emoji = {
                    "applied": "📝", "screening": "🔍", "interview": "🎤",
                    "offer": "🎉", "rejected": "❌", "withdrawn": "↩️"
                }.get(status, "📋")
                lines.append(f"  {emoji} {status.capitalize()}: {count}")

        lines.append("")
        lines.append("--- TOP COMPANIES ---")
        for company, count in list(stats["top_companies"].items())[:10]:
            lines.append(f"  {company}: {count} applications")

        # Calculate conversion rates
        total = stats['total_applications']
        if total > 0:
            interview_count = stats['by_status'].get('interview', 0)
            offer_count = stats['by_status'].get('offer', 0)
            lines.append("")
            lines.append("--- CONVERSION RATES ---")
            lines.append(f"  Interview Rate: {interview_count/total*100:.1f}% ({interview_count}/{total})")
            lines.append(f"  Offer Rate: {offer_count/total*100:.1f}% ({offer_count}/{total})")

        return "\n".join(lines)

    async def export_data(self, format: str = "csv", output_dir: str = "./exports",
                          data_types: List[str] = None) -> str:
        """Export tracked data to CSV/JSON."""
        data_types = data_types or ["applications", "jobs", "profile_history"]
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exported_files = []

        for data_type in data_types:
            if data_type == "applications":
                apps = await self.db.get_applications({}, limit=10000)
                filename = f"applications_{timestamp}.{format}"
                filepath = output_path / filename

                if format == "json":
                    with open(filepath, 'w') as f:
                        json.dump(apps, f, indent=2, default=str)
                else:
                    if apps:
                        with open(filepath, 'w', newline='') as f:
                            writer = csv.DictWriter(f, fieldnames=apps[0].keys())
                            writer.writeheader()
                            writer.writerows(apps)
                exported_files.append(str(filepath))

            elif data_type == "jobs":
                jobs = await self.db.search_jobs({}, limit=10000)
                filename = f"jobs_{timestamp}.{format}"
                filepath = output_path / filename

                if format == "json":
                    with open(filepath, 'w') as f:
                        json.dump(jobs, f, indent=2, default=str)
                else:
                    if jobs:
                        with open(filepath, 'w', newline='') as f:
                            writer = csv.DictWriter(f, fieldnames=jobs[0].keys())
                            writer.writeheader()
                            writer.writerows(jobs)
                exported_files.append(str(filepath))

            elif data_type == "profile_history":
                history = await self.db.get_profile_history(limit=1000)
                filename = f"profile_history_{timestamp}.{format}"
                filepath = output_path / filename

                if format == "json":
                    with open(filepath, 'w') as f:
                        json.dump(history, f, indent=2, default=str)
                else:
                    if history:
                        with open(filepath, 'w', newline='') as f:
                            writer = csv.DictWriter(f, fieldnames=history[0].keys())
                            writer.writeheader()
                            writer.writerows(history)
                exported_files.append(str(filepath))

        return f"✅ Data exported to {output_dir}:\n" + "\n".join(f"  • {f}" for f in exported_files)