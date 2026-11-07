"""
Job Search and Matching Tools
=============================
Tools for searching Naukri jobs and matching against resume.
"""

import logging
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from naukri_mcp.db.database import DatabaseManager
from naukri_mcp.browser.manager import BrowserManager
from naukri_mcp.tools.resume_tools import ResumeTools

logger = logging.getLogger(__name__)


class JobTools:
    """Tools for job search and resume-job matching."""

    def __init__(self, db: DatabaseManager, browser: BrowserManager):
        self.db = db
        self.browser = browser
        self.resume_tools = ResumeTools(db)

    async def search_jobs(self, keywords: List[str] = None, location: str = None,
                          experience_min: int = None, experience_max: int = None,
                          salary_min: float = None, job_types: List[str] = None,
                          companies: List[str] = None, posted_within_days: int = 30,
                          limit: int = 50) -> str:
        """Search Naukri for jobs matching criteria."""
        logger.info(f"Searching jobs with keywords: {keywords}")

        criteria = {
            "keywords": keywords or [],
            "location": location,
            "experience_min": experience_min,
            "experience_max": experience_max,
            "salary_min": salary_min,
            "job_types": job_types or [],
            "companies": companies or [],
            "posted_within_days": posted_within_days,
            "limit": limit
        }

        # Search via browser
        jobs = await self.browser.search_jobs(criteria)

        # Get details for each job and save to database
        saved_jobs = []
        for job in jobs:
            if job.get("url"):
                try:
                    details = await self.browser.get_job_details(job["url"])
                    job_data = {**job, **details}
                    job_data["search_keywords"] = keywords or []
                    job_id = await self.db.save_job(job_data)
                    job_data["db_id"] = job_id
                    saved_jobs.append(job_data)
                except Exception as e:
                    logger.warning(f"Failed to get details for {job.get('url')}: {e}")
                    saved_jobs.append(job)

        # Save search history
        await self.db.save_search_history(criteria, len(saved_jobs))

        return self._format_job_search_results(saved_jobs, criteria)

    async def get_job_details(self, job_url: str) -> str:
        """Get detailed job description from a job URL."""
        logger.info(f"Fetching job details: {job_url}")

        # Check database first
        existing = await self.db.get_job(job_url)
        if existing:
            return self._format_job_details(existing)

        # Fetch from browser
        job_data = await self.browser.get_job_details(job_url)
        job_data["job_url"] = job_url

        # Save to database
        job_id = await self.db.save_job(job_data)
        job_data["db_id"] = job_id

        return self._format_job_details(job_data)

    async def match_job_to_resume(self, job_url: str, resume_path: str, job_data: Dict = None) -> str:
        """Match a job description against resume and calculate compatibility."""
        logger.info(f"Matching job {job_url} to resume {resume_path}")

        # Get job data
        if job_data is None:
            job_data = await self.browser.get_job_details(job_url)
            job_data["job_url"] = job_url

        # Parse resume
        resume_data = await self.resume_tools.parse_resume(resume_path)

        # Calculate match
        match_result = self._calculate_match(resume_data, job_data)

        # Save job if not exists
        if "job_url" in job_data:
            await self.db.save_job({**job_data, "job_url": job_url})

        return self._format_match_result(match_result, job_data, resume_data)

    async def find_matching_jobs(self, resume_path: str, keywords: List[str] = None,
                                 location: str = None, min_match_score: float = 70,
                                 limit: int = 20) -> str:
        """Search jobs and automatically match against resume."""
        logger.info(f"Finding matching jobs for resume: {resume_path}")

        # Parse resume first
        resume_data = await self.resume_tools.parse_resume(resume_path)

        # Extract keywords from resume if not provided
        if not keywords:
            keywords = resume_data.get("top_skills", [])[:10]
            if resume_data.get("current_role"):
                keywords.append(resume_data["current_role"])

        # Search jobs
        criteria = {
            "keywords": keywords,
            "location": location,
            "posted_within_days": 30,
            "limit": limit * 3  # Search more to filter by match score
        }

        jobs = await self.browser.search_jobs(criteria)

        # Get details and match each job
        matches = []
        for job in jobs[:limit * 2]:  # Limit detail fetching
            if job.get("url"):
                try:
                    details = await self.browser.get_job_details(job["url"])
                    job_data = {**job, **details}
                    match_result = self._calculate_match(resume_data, job_data)

                    if match_result["score"] >= min_match_score:
                        match_result["job"] = job_data
                        matches.append(match_result)

                        # Save job
                        await self.db.save_job({**job_data, "job_url": job["url"], "search_keywords": keywords})
                except Exception as e:
                    logger.warning(f"Failed to process job {job.get('url')}: {e}")

        # Sort by match score
        matches.sort(key=lambda x: x["score"], reverse=True)
        matches = matches[:limit]

        return self._format_matching_jobs(matches, resume_data, min_match_score)

    def _calculate_match(self, resume: Dict, job: Dict) -> Dict[str, Any]:
        """Calculate resume-job compatibility score."""
        score = 0
        max_score = 100
        details = {
            "skills_match": [],
            "skills_missing": [],
            "experience_match": False,
            "location_match": False,
            "role_match": False,
            "keyword_matches": []
        }

        # Skills matching (40% weight)
        resume_skills = set(s.lower().strip() for s in resume.get("skills", []))
        job_skills = set(s.lower().strip() for s in job.get("skills", []))

        # Also extract skills from job description
        job_text = (job.get("description", "") + " " + job.get("requirements", "")).lower()
        for skill in resume_skills:
            if skill in job_text:
                job_skills.add(skill)

        matched_skills = resume_skills & job_skills
        missing_skills = job_skills - resume_skills

        details["skills_match"] = sorted(list(matched_skills))
        details["skills_missing"] = sorted(list(missing_skills))[:15]

        if job_skills:
            skills_score = (len(matched_skills) / len(job_skills)) * 40
        else:
            skills_score = 20  # Default if no skills listed
        score += skills_score

        # Experience matching (20% weight)
        resume_exp = resume.get("total_experience_years", 0)
        job_exp_min = self._extract_experience(job.get("experience", ""))
        job_exp_max = job_exp_min

        if job_exp_min and resume_exp >= job_exp_min * 0.8:
            details["experience_match"] = True
            score += 20
        elif job_exp_min and resume_exp >= job_exp_min * 0.5:
            score += 10

        # Role/Title matching (20% weight)
        resume_role = resume.get("current_role", "").lower()
        job_title = job.get("title", "").lower()

        role_keywords = ["analyst", "manager", "lead", "senior", "principal", "consultant", "specialist"]
        resume_role_words = set(resume_role.split())
        job_title_words = set(job_title.split())

        common_role_words = resume_role_words & job_title_words & set(role_keywords)
        if common_role_words:
            details["role_match"] = True
            score += 20
        elif resume_role_words & job_title_words:
            score += 10

        # Location matching (10% weight)
        resume_locations = [l.lower() for l in resume.get("preferred_locations", [])]
        job_location = job.get("location", "").lower()

        if any(loc in job_location for loc in resume_locations) or not resume_locations:
            details["location_match"] = True
            score += 10

        # Keyword density in description (10% weight)
        key_terms = resume.get("top_skills", []) + resume.get("domain_expertise", [])
        keyword_hits = sum(1 for term in key_terms if term.lower() in job_text)
        details["keyword_matches"] = [term for term in key_terms if term.lower() in job_text][:10]
        score += min(keyword_hits * 2, 10)

        return {
            "score": round(min(score, max_score), 1),
            "details": details
        }

    def _extract_experience(self, exp_text: str) -> Optional[int]:
        """Extract years of experience from text like '3-5 years' or '5+ years'."""
        if not exp_text:
            return None
        import re
        # Match patterns like "3-5", "5+", "3 to 5", etc.
        matches = re.findall(r'(\d+)\s*[-+to]\s*(\d+)?', exp_text.lower())
        if matches:
            return int(matches[0][0])
        # Single number
        matches = re.findall(r'(\d+)\s*years?', exp_text.lower())
        if matches:
            return int(matches[0])
        return None

    def _format_job_search_results(self, jobs: List[Dict], criteria: Dict) -> str:
        """Format job search results."""
        lines = [
            "=" * 60,
            f"JOB SEARCH RESULTS ({len(jobs)} jobs found)",
            "=" * 60,
            f"Search Criteria: {', '.join(criteria.get('keywords', [])) or 'None'} | "
            f"Location: {criteria.get('location', 'Any')} | "
            f"Experience: {criteria.get('experience_min', 'Any')}-{criteria.get('experience_max', 'Any')} yrs",
            ""
        ]

        for i, job in enumerate(jobs, 1):
            lines.append(f"{i}. {job.get('title', 'N/A')} at {job.get('company', 'N/A')}")
            lines.append(f"   ðŸ“ {job.get('location', 'N/A')} | ðŸ’¼ {job.get('experience', 'N/A')} | ðŸ’° {job.get('salary', 'Not disclosed')}")
            if job.get("url"):
                lines.append(f"   ðŸ”— {job['url']}")
            lines.append("")

        return "\n".join(lines)

    def _format_job_details(self, job: Dict) -> str:
        """Format detailed job information."""
        lines = [
            "=" * 60,
            f"JOB DETAILS: {job.get('title', 'N/A')}",
            "=" * 60,
            f"Company: {job.get('company', 'N/A')}",
            f"Location: {job.get('location', 'N/A')}",
            f"Experience: {job.get('experience', 'N/A')}",
            f"Salary: {job.get('salary', 'Not disclosed')}",
            f"Job Type: {job.get('job_type', 'N/A')}",
            f"Posted: {job.get('posted_date', 'N/A')}",
            f"URL: {job.get('job_url', 'N/A')}",
            ""
        ]

        if job.get("description"):
            lines.append("--- DESCRIPTION ---")
            desc = job["description"][:1000]
            lines.append(desc + ("..." if len(job["description"]) > 1000 else ""))
            lines.append("")

        if job.get("requirements"):
            lines.append("--- REQUIREMENTS ---")
            req = job["requirements"][:1000]
            lines.append(req + ("..." if len(job["requirements"]) > 1000 else ""))
            lines.append("")

        if job.get("skills"):
            lines.append(f"Skills: {', '.join(job['skills'][:20])}")
            if len(job["skills"]) > 20:
                lines.append(f"  ... and {len(job['skills']) - 20} more")

        return "\n".join(lines)

    def _format_match_result(self, match: Dict, job: Dict, resume: Dict) -> str:
        """Format resume-job match result."""
        score = match["score"]
        details = match["details"]

        lines = [
            "=" * 60,
            f"RESUME-JOB MATCH ANALYSIS",
            "=" * 60,
            f"Job: {job.get('title', 'N/A')} at {job.get('company', 'N/A')}",
            f"Match Score: {score}/100 {'ðŸŸ¢' if score >= 80 else 'ðŸŸ¡' if score >= 60 else 'ðŸ”´'}",
            ""
        ]

        lines.append("--- SKILLS ANALYSIS ---")
        lines.append(f"Matched Skills ({len(details['skills_match'])}): {', '.join(details['skills_match'][:15])}")
        if len(details['skills_match']) > 15:
            lines.append(f"  ... and {len(details['skills_match']) - 15} more")
        lines.append(f"Missing Skills ({len(details['skills_missing'])}): {', '.join(details['skills_missing'][:10])}")
        if len(details['skills_missing']) > 10:
            lines.append(f"  ... and {len(details['skills_missing']) - 10} more")
        lines.append("")

        lines.append("--- OTHER FACTORS ---")
        lines.append(f"Experience Match: {'âœ“' if details['experience_match'] else 'âœ—'}")
        lines.append(f"Role Match: {'âœ“' if details['role_match'] else 'âœ—'}")
        lines.append(f"Location Match: {'âœ“' if details['location_match'] else 'âœ—'}")
        lines.append(f"Keyword Matches: {', '.join(details['keyword_matches'][:8])}")
        lines.append("")

        if score >= 80:
            lines.append("ðŸŽ¯ EXCELLENT MATCH - Strongly recommended to apply")
        elif score >= 60:
            lines.append("ðŸ‘ GOOD MATCH - Worth applying with tailored resume")
        elif score >= 40:
            lines.append("âš ï¸  MODERATE MATCH - Consider if you meet key requirements")
        else:
            lines.append("âŒ LOW MATCH - Significant gaps in requirements")

        return "\n".join(lines)

    def _format_matching_jobs(self, matches: List[Dict], resume: Dict, min_score: float) -> str:
        """Format multiple matching jobs."""
        lines = [
            "=" * 60,
            f"MATCHING JOBS FOUND: {len(matches)} (min score: {min_score})",
            "=" * 60,
            f"Resume: {resume.get('current_role', 'N/A')} | {resume.get('total_experience_years', 0)} yrs exp",
            f"Top Skills: {', '.join(resume.get('top_skills', [])[:8])}",
            ""
        ]

        for i, match in enumerate(matches, 1):
            job = match["job"]
            score = match["score"]
            details = match["details"]

            lines.append(f"{i}. {job.get('title', 'N/A')} at {job.get('company', 'N/A')} â€” Score: {score}/100")
            lines.append(f"   ðŸ“ {job.get('location', 'N/A')} | ðŸ’¼ {job.get('experience', 'N/A')} | ðŸ’° {job.get('salary', 'Not disclosed')}")
            lines.append(f"   âœ“ Matched: {len(details['skills_match'])} skills | âœ— Missing: {len(details['skills_missing'])} skills")
            if job.get("url"):
                lines.append(f"   ðŸ”— {job['url']}")
            lines.append("")

        if not matches:
            lines.append("No jobs found matching the minimum score criteria.")
            lines.append("Try lowering min_match_score or broadening search keywords.")

        return "\n".join(lines)
