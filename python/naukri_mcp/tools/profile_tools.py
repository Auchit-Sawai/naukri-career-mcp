"""
Profile Management Tools
========================
Tools for auditing, optimizing, and updating Naukri profile.
"""

import logging
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from naukri_mcp.db.database import DatabaseManager
from naukri_mcp.browser.manager import BrowserManager
from naukri_mcp.tools.resume_tools import ResumeTools

logger = logging.getLogger(__name__)


class ProfileTools:
    """Tools for Naukri profile management."""

    def __init__(self, db: DatabaseManager, browser: BrowserManager):
        self.db = db
        self.browser = browser
        self.resume_tools = ResumeTools(db)

    async def audit_profile(self, profile_url: Optional[str] = None, resume_path: Optional[str] = None) -> str:
        """Audit Naukri profile for completeness and optimization opportunities."""
        logger.info("Starting profile audit...")

        # Get current profile
        profile = await self.browser.get_profile(profile_url)
        completeness = await self.browser.get_profile_completeness()

        audit_result = {
            "profile_data": profile,
            "completeness_score": completeness.get("score", 0),
            "missing_sections": completeness.get("missing", []),
            "issues": [],
            "recommendations": [],
            "resume_comparison": None
        }

        # Check each section
        if not profile.get("headline"):
            audit_result["issues"].append("Missing professional headline")
            audit_result["recommendations"].append("Add a keyword-rich professional headline")

        if not profile.get("summary") or len(profile.get("summary", "")) < 100:
            audit_result["issues"].append("Profile summary missing or too short")
            audit_result["recommendations"].append("Write a comprehensive 3-4 paragraph summary with industry keywords")

        skills = profile.get("skills", [])
        if len(skills) < 10:
            audit_result["issues"].append(f"Only {len(skills)} skills listed (recommend 15-25)")
            audit_result["recommendations"].append("Add more technical, functional, and domain-specific skills")

        experience = profile.get("experience", [])
        if len(experience) == 0:
            audit_result["issues"].append("No employment history found")
            audit_result["recommendations"].append("Add all relevant work experience with achievements")

        education = profile.get("education", [])
        if len(education) == 0:
            audit_result["issues"].append("No education details found")

        certifications = profile.get("certifications", [])
        if len(certifications) == 0:
            audit_result["recommendations"].append("Add relevant certifications (CFA, FRM, PMP, cloud certs, etc.)")

        projects = profile.get("projects", [])
        if len(projects) == 0:
            audit_result["recommendations"].append("Add key projects demonstrating impact")

        preferences = profile.get("preferences", {})
        if not preferences.get("preferredRoles"):
            audit_result["recommendations"].append("Set preferred job titles for better job matching")
        if not preferences.get("preferredLocations"):
            audit_result["recommendations"].append("Set preferred locations")

        # Compare with resume if provided
        if resume_path:
            resume_data = await self.resume_tools.parse_resume(resume_path)
            audit_result["resume_comparison"] = self._compare_profile_to_resume(profile, resume_data)

        # Save audit snapshot
        await self.db.save_profile_snapshot({
            "profile_url": profile_url,
            **profile,
            "completeness_score": completeness.get("score", 0),
            "raw_data": profile
        })

        return self._format_audit_report(audit_result)

    def _compare_profile_to_resume(self, profile: Dict, resume: Dict) -> Dict[str, Any]:
        """Compare profile data with resume data."""
        comparison = {
            "skills_match": [],
            "skills_missing_in_profile": [],
            "experience_gaps": [],
            "education_gaps": []
        }

        # Skills comparison
        profile_skills = set(s.lower() for s in profile.get("skills", []))
        resume_skills = set(s.lower() for s in resume.get("skills", []))

        comparison["skills_match"] = list(profile_skills & resume_skills)
        comparison["skills_missing_in_profile"] = list(resume_skills - profile_skills)

        # Experience comparison (simplified)
        profile_companies = set(exp.get("company", "").lower() for exp in profile.get("experience", []))
        resume_companies = set(exp.get("company", "").lower() for exp in resume.get("experience", []))

        comparison["experience_gaps"] = list(resume_companies - profile_companies)

        return comparison

    def _format_audit_report(self, audit: Dict) -> str:
        """Format audit result as readable report."""
        lines = [
            "=" * 60,
            "NAUKRI PROFILE AUDIT REPORT",
            "=" * 60,
            f"\nCompleteness Score: {audit['completeness_score']}/100",
            f"\nMissing Sections: {', '.join(audit['missing_sections']) if audit['missing_sections'] else 'None detected'}",
            "\n--- ISSUES FOUND ---"
        ]

        if audit["issues"]:
            for i, issue in enumerate(audit["issues"], 1):
                lines.append(f"{i}. {issue}")
        else:
            lines.append("No major issues found!")

        lines.append("\n--- RECOMMENDATIONS ---")
        for i, rec in enumerate(audit["recommendations"], 1):
            lines.append(f"{i}. {rec}")

        if audit["resume_comparison"]:
            comp = audit["resume_comparison"]
            lines.append("\n--- RESUME COMPARISON ---")
            lines.append(f"Matching Skills: {len(comp['skills_match'])}")
            lines.append(f"Skills Missing from Profile: {len(comp['skills_missing_in_profile'])}")
            if comp["skills_missing_in_profile"]:
                lines.append(f"  Missing: {', '.join(comp['skills_missing_in_profile'][:15])}")
                if len(comp["skills_missing_in_profile"]) > 15:
                    lines.append(f"  ... and {len(comp['skills_missing_in_profile']) - 15} more")
            lines.append(f"Experience Gaps (companies in resume but not profile): {len(comp['experience_gaps'])}")
            if comp["experience_gaps"]:
                lines.append(f"  Missing: {', '.join(comp['experience_gaps'])}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    async def get_profile(self, profile_url: Optional[str] = None) -> str:
        """Get current profile data."""
        profile = await self.browser.get_profile(profile_url)
        return json.dumps(profile, indent=2, default=str)

    async def propose_profile_changes(self, resume_path: str, target_roles: List[str] = None, target_industries: List[str] = None) -> str:
        """Propose optimized profile changes based on resume and target roles."""
        logger.info("Generating profile optimization proposals...")

        # Parse resume
        resume_data = await self.resume_tools.parse_resume(resume_path)

        # Get current profile
        current_profile = await self.browser.get_profile()

        # Generate optimized versions
        proposals = {
            "headline": self._generate_optimized_headline(resume_data, target_roles, target_industries),
            "summary": self._generate_optimized_summary(resume_data, target_roles, target_industries),
            "skills": self._generate_optimized_skills(resume_data, current_profile.get("skills", []), target_roles, target_industries),
            "experience": self._generate_optimized_experience(resume_data, current_profile.get("experience", [])),
            "education": resume_data.get("education", []),
            "certifications": resume_data.get("certifications", []),
            "projects": resume_data.get("projects", []),
            "preferences": self._generate_preferences(target_roles, target_industries)
        }

        # Save proposal for approval workflow
        proposal_id = await self.db.save_profile_change_proposal({
            "profile_url": "https://www.naukri.com/mnjuser/profile",
            "proposed_changes": proposals,
            "resume_path": resume_path,
            "target_roles": target_roles or [],
            "target_industries": target_industries or []
        })

        return self._format_proposal_report(proposals, proposal_id)

    def _generate_optimized_headline(self, resume: Dict, target_roles: List[str], target_industries: List[str]) -> str:
        """Generate optimized professional headline."""
        current_role = resume.get("current_role", "")
        years_exp = resume.get("total_experience_years", 0)
        key_skills = resume.get("top_skills", [])[:5]

        # Build headline components
        parts = []
        if current_role:
            parts.append(current_role)
        elif target_roles:
            parts.append(target_roles[0])

        if years_exp:
            parts.append(f"{years_exp}+ Years Experience")

        if key_skills:
            parts.append(" | ".join(key_skills))

        if target_industries:
            parts.append(f" | {target_industries[0]} Domain Expert")

        headline = " | ".join(parts)
        # Naukri headline limit ~250 chars
        return headline[:250]

    def _generate_optimized_summary(self, resume: Dict, target_roles: List[str], target_industries: List[str]) -> str:
        """Generate optimized profile summary."""
        years = resume.get("total_experience_years", 0)
        current_role = resume.get("current_role", "Experienced Professional")
        key_achievements = resume.get("key_achievements", [])
        top_skills = resume.get("top_skills", [])[:10]
        domain_expertise = resume.get("domain_expertise", [])

        summary_parts = [
            f"Results-driven {current_role} with {years}+ years of experience "
            f"in {', '.join(target_industries[:2]) if target_industries else 'financial services and technology'}.",
            ""
        ]

        if key_achievements:
            summary_parts.append("Key Achievements:")
            for ach in key_achievements[:3]:
                summary_parts.append(f"â€¢ {ach}")
            summary_parts.append("")

        summary_parts.append("Core Competencies:")
        summary_parts.append("â€¢ " + ", ".join(top_skills))
        summary_parts.append("")

        if domain_expertise:
            summary_parts.append("Domain Expertise:")
            summary_parts.append("â€¢ " + ", ".join(domain_expertise))
            summary_parts.append("")

        summary_parts.append(
            f"Seeking challenging {target_roles[0] if target_roles else 'senior'} opportunities "
            f"to leverage expertise in data-driven decision making, process automation, "
            f"and strategic business analysis."
        )

        return "\n".join(summary_parts)

    def _generate_optimized_skills(self, resume: Dict, current_skills: List[str], target_roles: List[str], target_industries: List[str]) -> List[str]:
        """Generate optimized skills list."""
        # Start with resume skills
        resume_skills = resume.get("skills", [])
        all_skills = set(s.lower() for s in resume_skills)
        all_skills.update(s.lower() for s in current_skills)

        # Add domain-specific keywords based on target roles/industries
        domain_keywords = {
            "business analyst": ["requirements gathering", "process modeling", "sql", "tableau", "power bi", "jira", "confluence", "agile", "scrum", "user stories", "gap analysis", "stakeholder management"],
            "capital markets": ["fixed income", "equities", "derivatives", "trade lifecycle", "settlement", "custody", "corporate actions", "bloomberg", "reuters", "risk management"],
            "financial data": ["data analysis", "python", "pandas", "numpy", "sql", "etl", "data quality", "factset", "refinitiv", "bloomberg", "time series", "quantitative analysis"],
            "investment research": ["equity research", "financial modeling", "valuation", "dcf", "comparable analysis", "earnings models", "industry analysis", "report writing", "bloomberg", "factset"],
            "ai automation": ["machine learning", "python", "langchain", "llm", "prompt engineering", "rag", "vector databases", "automation", "n8n", "zapier", "api integration", "workflow automation"]
        }

        for role in (target_roles or []):
            role_lower = role.lower()
            for key, keywords in domain_keywords.items():
                if key in role_lower:
                    all_skills.update(keywords)

        for industry in (target_industries or []):
            ind_lower = industry.lower()
            if "financial" in ind_lower or "capital" in ind_lower or "investment" in ind_lower:
                all_skills.update(domain_keywords.get("capital markets", []))

        # Convert back to title case and sort
        optimized = sorted([s.title() for s in all_skills])
        return optimized[:30]  # Limit to top 30

    def _generate_optimized_experience(self, resume: Dict, current_experience: List[Dict]) -> List[Dict]:
        """Generate optimized experience entries from resume."""
        return resume.get("experience", [])

    def _generate_preferences(self, target_roles: List[str], target_industries: List[str]) -> Dict[str, Any]:
        """Generate job preferences."""
        return {
            "preferredRoles": target_roles or ["Business Analyst", "Senior Business Analyst", "Product Analyst", "Data Analyst"],
            "preferredIndustries": target_industries or ["Financial Services", "Capital Markets", "Investment Management", "FinTech", "Information Technology"],
            "preferredLocations": ["Mumbai", "Pune", "Bangalore", "Hyderabad", "Remote"],
            "expectedSalary": "As per industry standards",
            "noticePeriod": "30 days",
            "jobType": ["Full-time", "Contract"]
        }

    def _format_proposal_report(self, proposals: Dict, proposal_id: int) -> str:
        """Format proposal for review."""
        lines = [
            "=" * 60,
            f"PROFILE OPTIMIZATION PROPOSAL (ID: {proposal_id})",
            "=" * 60,
            "\nâš ï¸  REVIEW REQUIRED: Changes will NOT be applied without your explicit approval.",
            "\n--- PROPOSED CHANGES ---\n"
        ]

        for section, content in proposals.items():
            lines.append(f"\n### {section.upper().replace('_', ' ')}")
            lines.append("-" * 40)

            if isinstance(content, str):
                lines.append(content[:500] + ("..." if len(content) > 500 else ""))
            elif isinstance(content, list):
                for item in content[:10]:
                    if isinstance(item, dict):
                        lines.append(f"  â€¢ {item.get('title', item.get('name', str(item)))}")
                    else:
                        lines.append(f"  â€¢ {item}")
                if len(content) > 10:
                    lines.append(f"  ... and {len(content) - 10} more")
            elif isinstance(content, dict):
                for k, v in content.items():
                    lines.append(f"  {k}: {v}")

        lines.append("\n" + "=" * 60)
        lines.append(f"\nTo approve and apply: Use 'naukri_apply_profile_changes' with proposal_id={proposal_id} and confirm=true")
        lines.append("To reject: Use 'naukri_apply_profile_changes' with confirm=false")
        lines.append("=" * 60)

        return "\n".join(lines)

    async def apply_profile_changes(self, changes: Dict, confirm: bool) -> str:
        """Apply approved profile changes to Naukri."""
        if not confirm:
            # Reject proposal
            proposal_id = changes.get("proposal_id")
            if proposal_id:
                await self.db.update_proposal_status(proposal_id, "rejected")
            return "Profile changes rejected. No changes were made to your Naukri profile."

        proposal_id = changes.get("proposal_id")
        if not proposal_id:
            return "Error: No proposal ID provided. Cannot apply changes."

        # Get the proposal
        proposal = await self.db.get_profile_change_proposal(proposal_id)
        if not proposal:
            return f"Error: Proposal {proposal_id} not found."

        if proposal["status"] != "approved":
            await self.db.update_proposal_status(proposal_id, "approved")

        proposed = proposal["proposed_changes"]
        results = []

        # Apply each change
        if "headline" in proposed:
            result = await self.browser.update_profile_headline(proposed["headline"])
            results.append(f"Headline: {'âœ“' if result['success'] else 'âœ—'} {result.get('message', result.get('error'))}")
            await self.db.save_profile_change_history({
                "proposal_id": proposal_id,
                "field_name": "headline",
                "old_value": "",  # Would need to capture before
                "new_value": proposed["headline"],
                "success": result["success"],
                "error_message": result.get("error")
            })

        if "summary" in proposed:
            result = await self.browser.update_profile_summary(proposed["summary"])
            results.append(f"Summary: {'âœ“' if result['success'] else 'âœ—'} {result.get('message', result.get('error'))}")
            await self.db.save_profile_change_history({
                "proposal_id": proposal_id,
                "field_name": "summary",
                "new_value": proposed["summary"],
                "success": result["success"],
                "error_message": result.get("error")
            })

        if "skills" in proposed:
            result = await self.browser.update_profile_skills(proposed["skills"])
            results.append(f"Skills: {'âœ“' if result['success'] else 'âœ—'} {result.get('message', result.get('error'))}")
            await self.db.save_profile_change_history({
                "proposal_id": proposal_id,
                "field_name": "skills",
                "new_value": json.dumps(proposed["skills"]),
                "success": result["success"],
                "error_message": result.get("error")
            })

        await self.db.update_proposal_status(proposal_id, "applied")

        return "PROFILE CHANGES APPLIED\n" + "\n".join(results)

    async def update_headline(self, new_headline: str, confirm: bool) -> str:
        """Update professional headline directly."""
        if not confirm:
            return "Headline update cancelled. No changes made."

        result = await self.browser.update_profile_headline(new_headline)
        return f"Headline Update: {'Success' if result['success'] else 'Failed'} - {result.get('message', result.get('error'))}"

    async def update_summary(self, new_summary: str, confirm: bool) -> str:
        """Update profile summary directly."""
        if not confirm:
            return "Summary update cancelled. No changes made."

        result = await self.browser.update_profile_summary(new_summary)
        return f"Summary Update: {'Success' if result['success'] else 'Failed'} - {result.get('message', result.get('error'))}"

    async def update_skills(self, skills: List[str], confirm: bool) -> str:
        """Update skills directly."""
        if not confirm:
            return "Skills update cancelled. No changes made."

        result = await self.browser.update_profile_skills(skills)
        return f"Skills Update: {'Success' if result['success'] else 'Failed'} - {result.get('message', result.get('error'))}"

    async def update_experience(self, experience: List[Dict], confirm: bool) -> str:
        """Update employment history (placeholder - complex UI interaction)."""
        if not confirm:
            return "Experience update cancelled. No changes made."

        return "Experience update requires manual browser interaction. Please use Naukri UI directly for complex experience edits."

    async def update_preferences(self, preferences: Dict, confirm: bool) -> str:
        """Update job preferences (placeholder)."""
        if not confirm:
            return "Preferences update cancelled. No changes made."

        return "Preferences update requires manual browser interaction. Please use Naukri UI directly."

    async def login(self, email: str, password: str) -> str:
        """Login to Naukri."""
        result = await self.browser.login(email, password)
        if result["success"]:
            return "âœ… Successfully logged in to Naukri.com"
        else:
            return f"âŒ Login failed: {result.get('error')}"

    async def get_profile_completeness(self, profile_url: Optional[str] = None) -> str:
        """Get profile completeness score."""
        completeness = await self.browser.get_profile_completeness()
        return f"Profile Completeness: {completeness.get('score', 0)}/100\nMissing: {', '.join(completeness.get('missing', [])) or 'None'}"

    async def check_session_status(self) -> str:
        """Check Naukri session status and detect expiry."""
        status = await self.browser.check_session_status()
        lines = [
            "=== NAUKRI SESSION STATUS ===",
            f"Valid: {status.get('valid', False)}",
            f"Reason: {status.get('reason', 'Unknown')}",
            f"Action: {status.get('action', 'none')}",
            f"Current URL: {status.get('current_url', 'N/A')}"
        ]
        if "error" in status:
            lines.append(f"Error: {status['error']}")
        return "\n".join(lines)

    async def ensure_valid_session(self, email: Optional[str] = None, password: Optional[str] = None) -> str:
        """Ensure valid Naukri session. If expired, attempt re-login with provided credentials."""
        result = await self.browser.ensure_valid_session(email, password)
        lines = [
            "=== SESSION VALIDATION RESULT ===",
            f"Success: {result.get('success', False)}",
        ]
        if "status" in result:
            status = result["status"]
            lines.append(f"Valid: {status.get('valid', False)}")
            lines.append(f"Reason: {status.get('reason', 'Unknown')}")
            lines.append(f"Action: {status.get('action', 'none')}")
        if "relogged" in result:
            lines.append(f"Re-logged in: {result['relogged']}")
        if "message" in result:
            lines.append(f"Message: {result['message']}")
        if "error" in result:
            lines.append(f"Error: {result['error']}")
        return "\n".join(lines)
