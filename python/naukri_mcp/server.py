#!/usr/bin/env python3
"""
Naukri Career Management MCP Server
====================================
Main entry point for the MCP server that exposes Naukri automation tools.
Uses MCP 2.3.0+ API with MCPServer and @tool() decorator registration.
"""

import asyncio
import functools
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.mcpserver import MCPServer
from mcp.server.stdio import stdio_server
from mcp import types

from naukri_mcp.tools.profile_tools import ProfileTools
from naukri_mcp.tools.job_tools import JobTools
from naukri_mcp.tools.application_tools import ApplicationTools
from naukri_mcp.tools.resume_tools import ResumeTools
from naukri_mcp.db.database import DatabaseManager
from naukri_mcp.browser.manager import BrowserManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler("naukri_mcp.log")
    ]
)
logger = logging.getLogger(__name__)


class NaukriMCPServer:
    """Main MCP Server for Naukri Career Management using MCP 2.3.0+ API."""

    def __init__(self):
        # Use MCPServer which has built-in tool management
        self.server = MCPServer(
            name="naukri-career-management",
            version="0.1.0",
            description="Naukri.com career management: profile optimization, job search, application tracking, resume tailoring"
        )
        self.db: Optional[DatabaseManager] = None
        self.browser: Optional[BrowserManager] = None
        self.profile_tools: Optional[ProfileTools] = None
        self.job_tools: Optional[JobTools] = None
        self.application_tools: Optional[ApplicationTools] = None
        self.resume_tools: Optional[ResumeTools] = None
        self._initialized = False

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize all components."""
        if self._initialized:
            return

        logger.info("Initializing Naukri MCP Server...")

        # Initialize database
        db_path = os.path.expandvars(os.path.expanduser(config.get("database_path", os.environ.get("NAUKRI_DB_PATH", "naukri_career.db"))))
        self.db = DatabaseManager(db_path)
        await self.db.initialize()
        logger.info(f"Database initialized: {db_path}")

        # Initialize browser manager
        headless = config.get("headless", True)
        browser_profile_dir = os.path.expandvars(os.path.expanduser(config.get("browser_profile_dir", os.environ.get("NAUKRI_BROWSER_PROFILE_DIR", "")))) or None
        self.browser = BrowserManager(headless=headless, profile_dir=browser_profile_dir)
        await self.browser.initialize()
        logger.info(f"Browser initialized (headless={headless}, profile_dir={browser_profile_dir})")

        # Initialize tool modules
        self.profile_tools = ProfileTools(self.db, self.browser)
        self.job_tools = JobTools(self.db, self.browser)
        self.application_tools = ApplicationTools(self.db, self.browser)
        self.resume_tools = ResumeTools(self.db)

        # Register all tools using MCP 2.3.0 API
        self._register_tools()

        self._initialized = True
        logger.info("Naukri MCP Server initialized successfully")

    def _register_tools(self) -> None:
        """Register all MCP tools using @server.tool() decorator."""

        def tool_wrapper(func):
            """Wrap tool function to catch exceptions and return error strings."""
            @functools.wraps(func)
            async def wrapper(*args, **kwargs) -> str:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logger.exception(f"Error in tool {func.__name__}")
                    return f"Error: {str(e)}"
            return wrapper

        # --- Profile Management Tools ---

        @self.server.tool(
            name="naukri_audit_profile",
            description="Audit Naukri profile for completeness, missing sections, and optimization opportunities. Compares against resume if provided."
        )
        @tool_wrapper
        async def naukri_audit_profile(
            profile_url: Optional[str] = None,
            resume_path: Optional[str] = None
        ) -> str:
            return await self.profile_tools.audit_profile(profile_url, resume_path)

        @self.server.tool(
            name="naukri_get_profile",
            description="Fetch and parse current Naukri profile data including headline, summary, skills, experience, education, certifications, projects, and preferences."
        )
        @tool_wrapper
        async def naukri_get_profile(
            profile_url: Optional[str] = None
        ) -> str:
            return await self.profile_tools.get_profile(profile_url)

        @self.server.tool(
            name="naukri_propose_profile_changes",
            description="Propose optimized profile changes (headline, summary, skills, experience, preferences) based on resume and target roles. Returns proposal for review - does NOT apply changes."
        )
        @tool_wrapper
        async def naukri_propose_profile_changes(
            resume_path: str,
            target_roles: Optional[List[str]] = None,
            target_industries: Optional[List[str]] = None
        ) -> str:
            return await self.profile_tools.propose_profile_changes(resume_path, target_roles, target_industries)

        @self.server.tool(
            name="naukri_apply_profile_changes",
            description="Apply approved profile changes to Naukri.com. Requires explicit confirmation. Shows proposed changes before applying."
        )
        @tool_wrapper
        async def naukri_apply_profile_changes(
            proposal_id: int,
            confirm: bool
        ) -> str:
            return await self.profile_tools.apply_profile_changes({"proposal_id": proposal_id}, confirm)

        @self.server.tool(
            name="naukri_update_headline",
            description="Update professional headline with optimized version. Requires explicit confirmation."
        )
        @tool_wrapper
        async def naukri_update_headline(
            new_headline: str,
            confirm: bool
        ) -> str:
            return await self.profile_tools.update_headline(new_headline, confirm)

        @self.server.tool(
            name="naukri_update_summary",
            description="Update profile summary with optimized version. Requires explicit confirmation."
        )
        @tool_wrapper
        async def naukri_update_summary(
            new_summary: str,
            confirm: bool
        ) -> str:
            return await self.profile_tools.update_summary(new_summary, confirm)

        @self.server.tool(
            name="naukri_update_skills",
            description="Update technical/functional skills with optimized keywords. Requires explicit confirmation."
        )
        @tool_wrapper
        async def naukri_update_skills(
            skills: List[str],
            confirm: bool
        ) -> str:
            return await self.profile_tools.update_skills(skills, confirm)

        @self.server.tool(
            name="naukri_update_experience",
            description="Update employment history from resume data. Note: Complex experience edits may require manual Naukri UI interaction."
        )
        @tool_wrapper
        async def naukri_update_experience(
            experience: List[Dict[str, Any]],
            confirm: bool
        ) -> str:
            return await self.profile_tools.update_experience(experience, confirm)

        @self.server.tool(
            name="naukri_update_preferences",
            description="Update job preferences (titles, locations, industries, salary). Note: May require manual Naukri UI interaction."
        )
        @tool_wrapper
        async def naukri_update_preferences(
            preferences: Dict[str, Any],
            confirm: bool
        ) -> str:
            return await self.profile_tools.update_preferences(preferences, confirm)

        # --- Job Search Tools ---

        @self.server.tool(
            name="naukri_search_jobs",
            description="Search Naukri.com for jobs matching criteria. Returns job listings with basic info."
        )
        @tool_wrapper
        async def naukri_search_jobs(
            keywords: Optional[List[str]] = None,
            location: Optional[str] = None,
            experience_min: Optional[int] = None,
            experience_max: Optional[int] = None,
            salary_min: Optional[float] = None,
            job_types: Optional[List[str]] = None,
            companies: Optional[List[str]] = None,
            posted_within_days: int = 30,
            limit: int = 50
        ) -> str:
            return await self.job_tools.search_jobs(
                keywords=keywords,
                location=location,
                experience_min=experience_min,
                experience_max=experience_max,
                salary_min=salary_min,
                job_types=job_types,
                companies=companies,
                posted_within_days=posted_within_days,
                limit=limit
            )

        @self.server.tool(
            name="naukri_get_job_details",
            description="Get detailed job description from a Naukri job posting URL including requirements, skills, and company info."
        )
        @tool_wrapper
        async def naukri_get_job_details(
            job_url: str
        ) -> str:
            return await self.job_tools.get_job_details(job_url)

        @self.server.tool(
            name="naukri_match_job_to_resume",
            description="Match a job description against resume and calculate compatibility score with detailed skill gap analysis."
        )
        @tool_wrapper
        async def naukri_match_job_to_resume(
            job_url: str,
            resume_path: str,
            job_data: Optional[Dict[str, Any]] = None
        ) -> str:
            return await self.job_tools.match_job_to_resume(job_url, resume_path, job_data)

        @self.server.tool(
            name="naukri_find_matching_jobs",
            description="Search jobs and automatically match against resume, returning only jobs above minimum match score."
        )
        @tool_wrapper
        async def naukri_find_matching_jobs(
            resume_path: str,
            keywords: Optional[List[str]] = None,
            location: Optional[str] = None,
            min_match_score: float = 70.0,
            limit: int = 20
        ) -> str:
            return await self.job_tools.find_matching_jobs(
                resume_path=resume_path,
                keywords=keywords,
                location=location,
                min_match_score=min_match_score,
                limit=limit
            )

        # --- Application Tracking Tools ---

        @self.server.tool(
            name="naukri_track_application",
            description="Record a job application in local database with job details, match score, and notes."
        )
        @tool_wrapper
        async def naukri_track_application(
            job_url: str,
            job_title: str,
            company: str,
            location: Optional[str] = None,
            applied_date: Optional[str] = None,
            status: str = "applied",
            match_score: Optional[float] = None,
            notes: Optional[str] = None
        ) -> str:
            return await self.application_tools.track_application(
                job_url=job_url,
                job_title=job_title,
                company=company,
                location=location,
                applied_date=applied_date,
                status=status,
                match_score=match_score,
                notes=notes
            )

        @self.server.tool(
            name="naukri_update_application_status",
            description="Update application status and add interview rounds, recruiter communications, and notes."
        )
        @tool_wrapper
        async def naukri_update_application_status(
            application_id: int,
            status: str,
            interview_round: Optional[int] = None,
            interview_date: Optional[str] = None,
            interview_type: Optional[str] = None,
            recruiter_name: Optional[str] = None,
            recruiter_contact: Optional[str] = None,
            notes: Optional[str] = None
        ) -> str:
            return await self.application_tools.update_application_status(
                application_id=application_id,
                status=status,
                interview_round=interview_round,
                interview_date=interview_date,
                interview_type=interview_type,
                recruiter_name=recruiter_name,
                recruiter_contact=recruiter_contact,
                notes=notes
            )

        @self.server.tool(
            name="naukri_get_applications",
            description="Get tracked applications with optional filters for status, company, date range."
        )
        @tool_wrapper
        async def naukri_get_applications(
            status: Optional[str] = None,
            company: Optional[str] = None,
            date_from: Optional[str] = None,
            date_to: Optional[str] = None,
            limit: int = 100
        ) -> str:
            return await self.application_tools.get_applications(
                status=status,
                company=company,
                date_from=date_from,
                date_to=date_to,
                limit=limit
            )

        @self.server.tool(
            name="naukri_get_application_stats",
            description="Get application statistics and pipeline summary including conversion rates."
        )
        @tool_wrapper
        async def naukri_get_application_stats(
            date_from: Optional[str] = None,
            date_to: Optional[str] = None
        ) -> str:
            return await self.application_tools.get_application_stats(date_from, date_to)

        # --- Resume Tools ---

        @self.server.tool(
            name="naukri_parse_resume",
            description="Parse resume file (PDF/DOCX) and extract structured data including skills, experience, education, achievements."
        )
        @tool_wrapper
        async def naukri_parse_resume(
            resume_path: str
        ) -> str:
            result = await self.resume_tools.parse_resume(resume_path)
            return json.dumps(result, indent=2, default=str)

        @self.server.tool(
            name="naukri_generate_tailored_resume",
            description="Generate a tailored resume for a specific job, highlighting matching skills and experience."
        )
        @tool_wrapper
        async def naukri_generate_tailored_resume(
            resume_path: str,
            job_url: str,
            job_data: Optional[Dict[str, Any]] = None,
            output_path: str = ""
        ) -> str:
            return await self.resume_tools.generate_tailored_resume(
                resume_path=resume_path,
                job_url=job_url,
                job_data=job_data,
                output_path=output_path
            )

        @self.server.tool(
            name="naukri_generate_cover_letter",
            description="Generate a customized cover letter for a job application with selectable tone."
        )
        @tool_wrapper
        async def naukri_generate_cover_letter(
            resume_path: str,
            job_url: str,
            job_data: Optional[Dict[str, Any]] = None,
            output_path: str = "",
            tone: str = "professional"
        ) -> str:
            return await self.resume_tools.generate_cover_letter(
                resume_path=resume_path,
                job_url=job_url,
                job_data=job_data,
                output_path=output_path,
                tone=tone
            )

        # --- Utility Tools ---

        @self.server.tool(
            name="naukri_login",
            description="Open no login flow; use the visible browser and sign in yourself."
        )
        @tool_wrapper
        async def naukri_login(
            email: str,
            password: str
        ) -> str:
            # Do not accept credentials through model tool arguments. Use the
            # visible browser login flow so secrets are entered directly by
            # the user and the persistent browser profile stores the session.
            return (
                "Credential-based login through MCP is disabled. Open the visible Naukri login "
                "browser and sign in yourself; do not provide your password to an AI model."
            )

        @self.server.tool(
            name="naukri_check_session",
            description="Check Naukri session status and detect expiry. Returns session validity and recommended action."
        )
        @tool_wrapper
        async def naukri_check_session() -> str:
            return await self.profile_tools.check_session_status()

        @self.server.tool(
            name="naukri_ensure_session",
            description="Check the saved Naukri session without submitting credentials."
        )
        @tool_wrapper
        async def naukri_ensure_session(
            email: Optional[str] = None,
            password: Optional[str] = None
        ) -> str:
            # Session check only; never pass credentials into a model-facing tool.
            return await self.profile_tools.ensure_valid_session()

        @self.server.tool(
            name="naukri_get_profile_completeness",
            description="Get profile completeness score and missing section recommendations from Naukri."
        )
        @tool_wrapper
        async def naukri_get_profile_completeness(
            profile_url: Optional[str] = None
        ) -> str:
            return await self.profile_tools.get_profile_completeness(profile_url)

        @self.server.tool(
            name="naukri_export_data",
            description="Export tracked data (jobs, applications, profile history) to CSV or JSON."
        )
        @tool_wrapper
        async def naukri_export_data(
            format: str = "csv",
            output_dir: str = "./exports",
            data_types: Optional[List[str]] = None
        ) -> str:
            if data_types is None:
                data_types = ["applications", "jobs", "profile_history"]
            return await self.application_tools.export_data(format, output_dir, data_types)

    async def run(self) -> None:
        """Run the MCP server over stdio."""
        logger.info("Starting MCP server over stdio...")
        await self.server.run_stdio_async()

    async def shutdown(self) -> None:
        """Cleanup resources."""
        logger.info("Shutting down Naukri MCP Server...")
        if self.browser:
            await self.browser.close()
        if self.db:
            await self.db.close()
        logger.info("Shutdown complete")


async def main():
    """Main entry point."""
    # Load config from file or environment
    config_path = Path("naukri_mcp_config.json")
    config = {}
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)

    server = NaukriMCPServer()
    try:
        await server.initialize(config)
        await server.run()
    finally:
        await server.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

