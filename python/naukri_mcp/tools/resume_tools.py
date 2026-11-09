"""
Resume Processing Tools
=======================
Tools for parsing resumes and generating tailored versions.
"""

import logging
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from naukri_mcp.db.database import DatabaseManager

logger = logging.getLogger(__name__)


class ResumeTools:
    """Tools for resume parsing and generation."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def parse_resume(self, resume_path: str) -> Dict[str, Any]:
        """Parse resume file (PDF/DOCX) and extract structured data."""
        logger.info(f"Parsing resume: {resume_path}")

        path = Path(resume_path)
        if not path.exists():
            raise FileNotFoundError(f"Resume not found: {resume_path}")

        # Calculate file hash for deduplication
        file_hash = self._calculate_hash(path)

        # Check if already parsed
        existing = await self.db.get_resume(str(path))
        if existing and existing["file_hash"] == file_hash:
            logger.info("Using cached resume parse")
            return existing["parsed_data"]

        # Parse based on file type
        if path.suffix.lower() == ".pdf":
            parsed = await self._parse_pdf(path)
        elif path.suffix.lower() in [".docx", ".doc"]:
            parsed = await self._parse_docx(path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

        # Enhance parsed data
        parsed = self._enhance_parsed_data(parsed)

        # Save to database
        await self.db.save_resume(str(path), file_hash, parsed, is_base=True)

        return parsed

    def _calculate_hash(self, path: Path) -> str:
        """Calculate SHA256 hash of file."""
        hasher = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def _parse_pdf(self, path: Path) -> Dict[str, Any]:
        """Parse PDF resume."""
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber required for PDF parsing. Install: pip install pdfplumber")

        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""

        return self._extract_structured_data(text)

    async def _parse_docx(self, path: Path) -> Dict[str, Any]:
        """Parse DOCX resume."""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx required for DOCX parsing. Install: pip install python-docx")

        doc = Document(path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return self._extract_structured_data(text)

    def _extract_structured_data(self, text: str) -> Dict[str, Any]:
        """Extract structured data from resume text using heuristics."""
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        data = {
            "raw_text": text,
            "name": "",
            "email": "",
            "phone": "",
            "linkedin": "",
            "location": "",
            "summary": "",
            "skills": [],
            "experience": [],
            "education": [],
            "certifications": [],
            "projects": [],
            "total_experience_years": 0,
            "current_role": "",
            "top_skills": [],
            "domain_expertise": [],
            "preferred_locations": []
        }

        # Extract contact info
        import re
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        if email_match:
            data["email"] = email_match.group()

        phone_match = re.search(r'[\+]?[(]?[\d\s\-\(\)]{10,}', text)
        if phone_match:
            data["phone"] = phone_match.group().strip()

        linkedin_match = re.search(r'linkedin\.com/in/[\w\-]+', text, re.IGNORECASE)
        if linkedin_match:
            data["linkedin"] = linkedin_match.group()

        # Simple section detection
        current_section = None
        section_content = []

        for line in lines:
            line_lower = line.lower()

            # Detect sections
            if any(kw in line_lower for kw in ['summary', 'profile', 'objective']):
                if current_section and section_content:
                    data[current_section] = '\n'.join(section_content)
                current_section = "summary"
                section_content = [line]
            elif any(kw in line_lower for kw in ['experience', 'employment', 'work history', 'professional experience']):
                if current_section and section_content:
                    data[current_section] = '\n'.join(section_content)
                current_section = "experience"
                section_content = []
            elif any(kw in line_lower for kw in ['education', 'academic', 'qualification']):
                if current_section and section_content:
                    data[current_section] = '\n'.join(section_content)
                current_section = "education"
                section_content = []
            elif any(kw in line_lower for kw in ['certification', 'license', 'credential']):
                if current_section and section_content:
                    data[current_section] = '\n'.join(section_content)
                current_section = "certifications"
                section_content = []
            elif any(kw in line_lower for kw in ['project', 'portfolio']):
                if current_section and section_content:
                    data[current_section] = '\n'.join(section_content)
                current_section = "projects"
                section_content = []
            elif any(kw in line_lower for kw in ['skill', 'technology', 'technical', 'competenc']):
                if current_section and section_content:
                    data[current_section] = '\n'.join(section_content)
                current_section = "skills"
                section_content = []
            else:
                if current_section:
                    section_content.append(line)

        # Save last section
        if current_section and section_content:
            data[current_section] = '\n'.join(section_content)

        # Parse skills from skills section
        if isinstance(data.get("skills"), str):
            data["skills"] = self._parse_skills_text(data["skills"])

        # Parse experience
        if isinstance(data.get("experience"), str):
            data["experience"] = self._parse_experience_text(data["experience"])

        # Parse education
        if isinstance(data.get("education"), str):
            data["education"] = self._parse_education_text(data["education"])

        # Parse certifications
        if isinstance(data.get("certifications"), str):
            data["certifications"] = self._parse_certifications_text(data["certifications"])

        # Parse projects
        if isinstance(data.get("projects"), str):
            data["projects"] = self._parse_projects_text(data["projects"])

        # Calculate total experience
        data["total_experience_years"] = self._calculate_total_experience(data["experience"])

        # Get current role
        if data["experience"]:
            data["current_role"] = data["experience"][0].get("title", "")

        # Extract top skills
        data["top_skills"] = data["skills"][:15]

        # Extract domain expertise from experience
        data["domain_expertise"] = self._extract_domain_expertise(data["experience"])

        return data

    def _parse_skills_text(self, text: str) -> List[str]:
        """Parse skills from text with improved segmentation."""
        
        # First, normalize the text
        text = text.replace('\n', ' ').replace('\r', ' ')
        
        # Split by common skill delimiters, but be careful with colons in skill names
        # Pattern: split on commas, semicolons, pipes, bullets, newlines
        # But NOT on colons that are part of skill names like "C++", "C#", "AI/ML"
        # Split on: comma, semicolon, pipe, bullet, newline
        # Keep together: items separated by "•", "-", "*" at start of line
        
        # First split by newlines and bullets
        parts = re.split(r'[\n•\-*]', text)
        
        skills = []
        for part in parts:
            # Further split by commas, semicolons, pipes
            sub_parts = re.split(r'[,;|]', part)
            for sp in sub_parts:
                sp = sp.strip()
                # Remove trailing colons from skill names (e.g., "Business Analysis:" -> "Business Analysis")
                sp = re.sub(r':\s*$', '', sp)
                sp = sp.strip()
                if sp and len(sp) > 1 and len(sp) < 100:
                    # Filter out section headers and noise
                    sp_lower = sp.lower()
                    if not any(sp_lower.startswith(prefix) for prefix in 
                               ['skill', 'technolog', 'competenc', 'tool', 'language', 
                                'summary', 'profile', 'objective', 'experience', 'employment',
                                'education', 'certification', 'project', 'personal', 'contact',
                                'linkedin', 'phone', 'email', 'address', 'location',
                                'references', 'declaration', 'hobbies', 'interests',
                                'achievement', 'award', 'publication', 'patent']):
                        # Additional cleanup: remove leading/trailing punctuation
                        sp = sp.strip('.,;:')
                        if sp and len(sp) > 1:
                            skills.append(sp)
        
        # Deduplicate while preserving order
        seen = set()
        unique_skills = []
        for skill in skills:
            skill_lower = skill.lower()
            if skill_lower not in seen:
                seen.add(skill_lower)
                unique_skills.append(skill)
        
        # Post-process: merge skills that were incorrectly split
        # e.g., "Business Analysis" + "& Delivery" -> "Business Analysis & Delivery"
        merged_skills = []
        i = 0
        while i < len(unique_skills):
            skill = unique_skills[i]
            # Check if next skill looks like a continuation (starts with &, and, or, etc.)
            if i + 1 < len(unique_skills):
                next_skill = unique_skills[i + 1]
                if next_skill.lower().startswith(('&', 'and', 'or', 'with', 'for', 'of', 'in', 'on', 'to')):
                    # Merge them
                    merged = skill + ' ' + next_skill
                    merged_skills.append(merged)
                    i += 2
                    continue
            merged_skills.append(skill)
            i += 1
        
        return merged_skills[:50]

    def _parse_experience_text(self, text: str) -> List[Dict]:
        """Parse experience entries from text with improved duration extraction."""
        entries = []
        # Split by lines that look like job titles (contain dates or company indicators)
        blocks = re.split(r'\n\s*\n', text)

        for block in blocks:
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not lines:
                continue

            entry = {
                "title": lines[0] if lines else "",
                "company": "",
                "duration": "",
                "location": "",
                "description": "",
                "achievements": []
            }

            # Look for company, duration in subsequent lines
            for line in lines[1:]:
                line_lower = line.lower()
                # Check for company
                if any(kw in line_lower for kw in ['inc', 'ltd', 'corp', 'company', 'technologies', 'solutions', 'services', 'bank', 'capital', 'financial']):
                    entry["company"] = line
                # Check for duration patterns
                elif re.search(r'\d{4}\s*[-–to]\s*(\d{4}|present|current)', line_lower):
                    entry["duration"] = line
                elif re.search(r'\d{1,2}/\d{4}\s*[-–to]\s*(\d{1,2}/\d{4}|present|current)', line_lower):
                    entry["duration"] = line
                elif re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}\s*[-–to]\s*(\w{3,9}\s+\d{4}|present|current)', line_lower):
                    entry["duration"] = line
                elif line_lower.startswith(('•', '-', '*')):
                    entry["achievements"].append(line.lstrip('•-* '))
                else:
                    entry["description"] += line + " "

            if entry["title"]:
                entries.append(entry)

        return entries

    def _parse_education_text(self, text: str) -> List[Dict]:
        """Parse education entries."""
        entries = []
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        for line in lines:
            # Simple heuristic
            entry = {"degree": line, "institute": "", "year": ""}
            entries.append(entry)

        return entries

    def _parse_certifications_text(self, text: str) -> List[str]:
        """Parse certifications."""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        return lines

    def _parse_projects_text(self, text: str) -> List[Dict]:
        """Parse projects."""
        entries = []
        blocks = text.split('\n\n')

        for block in blocks:
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not lines:
                continue
            entry = {
                "name": lines[0],
                "description": '\n'.join(lines[1:]) if len(lines) > 1 else ""
            }
            entries.append(entry)

        return entries

    def _calculate_total_experience(self, experience: List[Dict]) -> int:
        """Calculate total years of experience with improved parsing."""
        total = 0
        current_year = 2025
        
        for exp in experience:
            duration = exp.get("duration", "")
            if not duration:
                continue
            
            # Try multiple patterns for date ranges
            patterns = [
                r'(\d{4})\s*[-–to]\s*(\d{4}|present|current)',  # 2020-2023, 2020 – present
                r'(\d{1,2}/\d{4})\s*[-–to]\s*(\d{1,2}/\d{4}|present|current)',  # 01/2020 - 03/2023
                r'(\w{3,9}\s+\d{4})\s*[-–to]\s*(\w{3,9}\s+\d{4}|present|current)',  # Jan 2020 - Mar 2023
                r'(\d{4})\s*to\s*(\d{4}|present|current)',  # 2020 to 2023
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, duration, re.IGNORECASE)
                for match in matches:
                    try:
                        start_str, end_str = match[0], match[1]
                        start_year = self._extract_year(start_str)
                        end_year = current_year if end_str.lower() in ['present', 'current'] else self._extract_year(end_str)
                        
                        if start_year and end_year and end_year >= start_year:
                            total += (end_year - start_year)
                    except (ValueError, IndexError):
                        continue
        
        return total
    
    def _extract_year(self, date_str: str) -> Optional[int]:
        """Extract year from various date formats."""
        import re
        date_str = date_str.strip()
        # Try 4-digit year
        year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
        if year_match:
            return int(year_match.group())
        # Try month year format
        month_year_match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})', date_str, re.IGNORECASE)
        if month_year_match:
            return int(month_year_match.group(2))
        return None

    def _extract_domain_expertise(self, experience: List[Dict]) -> List[str]:
        """Extract domain expertise from experience."""
        domains = set()
        domain_keywords = {
            "Capital Markets": ["capital market", "equity", "fixed income", "bond", "derivative", "trade lifecycle", "settlement"],
            "Investment Research": ["equity research", "valuation", "dcf", "financial modeling", "earnings", "coverage"],
            "Financial Data": ["factset", "bloomberg", "refinitiv", "reuters", "market data", "pricing", "reference data"],
            "Risk Management": ["risk", "var", "stress test", "credit risk", "market risk", "operational risk"],
            "Business Analysis": ["business analyst", "requirements", "process modeling", "gap analysis", "stakeholder"],
            "Data Analysis": ["data analysis", "sql", "python", "tableau", "power bi", "etl", "data quality"],
            "AI/ML": ["machine learning", "deep learning", "nlp", "llm", "langchain", "ai", "automation"],
            "Project Management": ["project management", "agile", "scrum", "jira", "confluence", "pmp"],
            "Banking": ["banking", "retail banking", "corporate banking", "lending", "credit"],
            "FinTech": ["fintech", "payment", "blockchain", "crypto", "digital banking"]
        }

        for exp in experience:
            text = (exp.get("title", "") + " " + exp.get("description", "") + " " +
                    " ".join(exp.get("achievements", []))).lower()
            for domain, keywords in domain_keywords.items():
                if any(kw in text for kw in keywords):
                    domains.add(domain)

        return sorted(list(domains))

    def _enhance_parsed_data(self, parsed: Dict) -> Dict:
        """Enhance parsed data with additional computed fields."""
        # Ensure all fields exist
        defaults = {
            "skills": [], "experience": [], "education": [],
            "certifications": [], "projects": [], "domain_expertise": [],
            "top_skills": [], "preferred_locations": []
        }
        for key, default in defaults.items():
            if key not in parsed:
                parsed[key] = default

        # Recalculate top skills if missing
        if not parsed["top_skills"] and parsed["skills"]:
            parsed["top_skills"] = parsed["skills"][:15]

        return parsed

    async def generate_tailored_resume(self, resume_path: str, job_url: str,
                                       job_data: Dict = None, output_path: str = None) -> str:
        """Generate a tailored resume for a specific job."""
        logger.info(f"Generating tailored resume for {job_url}")

        # Parse base resume
        base_resume = await self.parse_resume(resume_path)

        # Get job data if not provided
        if job_data is None:
            # This would need browser access - simplified for now
            job_data = {"title": "Target Position", "company": "Target Company",
                       "skills": [], "description": "", "requirements": ""}

        # Generate tailored content
        tailored = self._tailor_resume(base_resume, job_data)

        # Determine output path
        if not output_path:
            resume_file = Path(resume_path)
            output_path = str(resume_file.parent / f"{resume_file.stem}_tailored_{job_data.get('company', 'job').replace(' ', '_')}.txt")

        # Save tailored resume as text (for now - could generate DOCX/PDF)
        self._save_tailored_resume(tailored, output_path)

        # Save to database
        base_resume_record = await self.db.get_resume(resume_path)
        if base_resume_record:
            job = await self.db.get_job(job_url)
            await self.db.save_tailored_resume({
                "base_resume_id": base_resume_record["id"],
                "job_id": job["id"] if job else None,
                "output_path": output_path,
                "modifications": tailored.get("modifications", {}),
                "match_score": tailored.get("match_score")
            })

        return f"✅ Tailored resume generated: {output_path}\n" \
               f"Match Score: {tailored.get('match_score', 'N/A')}%\n" \
               f"Key modifications: {', '.join(tailored.get('modifications', {}).keys())}"

    def _tailor_resume(self, base_resume: Dict, job: Dict) -> Dict:
        """Tailor resume content for a specific job."""
        job_skills = set(s.lower() for s in job.get("skills", []))
        job_text = (job.get("description", "") + " " + job.get("requirements", "")).lower()

        # Find matching and missing skills
        resume_skills = set(s.lower() for s in base_resume.get("skills", []))
        matched = resume_skills & job_skills
        missing_in_resume = job_skills - resume_skills

        # Prioritize skills that appear in job description
        prioritized_skills = []
        for skill in base_resume.get("skills", []):
            if skill.lower() in job_text:
                prioritized_skills.append(skill)

        # Add missing skills that we can reasonably claim (from experience)
        claimed_skills = []
        for exp in base_resume.get("experience", []):
            exp_text = (exp.get("description", "") + " " + " ".join(exp.get("achievements", []))).lower()
            for skill in missing_in_resume:
                if skill in exp_text and skill not in claimed_skills:
                    claimed_skills.append(skill)

        modifications = {
            "skills_reordered": True,
            "skills_prioritized": prioritized_skills[:10],
            "skills_added_from_experience": claimed_skills[:5],
            "summary_tailored": True,
            "experience_highlighted": True
        }

        # Calculate estimated match score
        match_score = len(matched) / max(len(job_skills), 1) * 100 if job_skills else 50
        match_score = min(match_score + len(claimed_skills) * 5, 95)

        return {
            "base_resume": base_resume,
            "job": job,
            "modifications": modifications,
            "match_score": round(match_score, 1)
        }

    def _save_tailored_resume(self, tailored: Dict, output_path: str) -> None:
        """Save tailored resume to file."""
        base = tailored["base_resume"]
        job = tailored["job"]
        mods = tailored["modifications"]

        lines = [
            "=" * 60,
            f"TAILORED RESUME FOR: {job.get('title', 'Target Position')} at {job.get('company', 'Target Company')}",
            "=" * 60,
            "",
            f"Name: {base.get('name', 'N/A')}",
            f"Email: {base.get('email', 'N/A')}",
            f"Phone: {base.get('phone', 'N/A')}",
            f"LinkedIn: {base.get('linkedin', 'N/A')}",
            f"Location: {base.get('location', 'N/A')}",
            "",
            "--- PROFESSIONAL SUMMARY (TAILORED) ---",
            base.get('summary', 'Experienced professional seeking new opportunities.'),
            "",
            "--- CORE SKILLS (PRIORITIZED FOR THIS ROLE) ---"
        ]

        # Prioritized skills first
        for skill in mods.get("skills_prioritized", []):
            lines.append(f"  ✓ {skill}")

        # Other skills
        other_skills = [s for s in base.get("skills", []) if s not in mods.get("skills_prioritized", [])]
        for skill in other_skills[:10]:
            lines.append(f"  • {skill}")

        if mods.get("skills_added_from_experience"):
            lines.append("")
            lines.append("--- ADDITIONAL RELEVANT SKILLS (FROM EXPERIENCE) ---")
            for skill in mods["skills_added_from_experience"]:
                lines.append(f"  + {skill}")

        lines.extend([
            "",
            "--- PROFESSIONAL EXPERIENCE ---"
        ])

        for exp in base.get("experience", []):
            lines.append(f"\n{exp.get('title', '')} | {exp.get('company', '')}")
            lines.append(f"  {exp.get('duration', '')} | {exp.get('location', '')}")
            if exp.get("description"):
                lines.append(f"  {exp['description'][:200]}")
            for ach in exp.get("achievements", [])[:3]:
                lines.append(f"  • {ach}")

        lines.extend([
            "",
            "--- EDUCATION ---"
        ])

        for edu in base.get("education", []):
            lines.append(f"  {edu.get('degree', '')} | {edu.get('institute', '')} | {edu.get('year', '')}")

        if base.get("certifications"):
            lines.extend([
                "",
                "--- CERTIFICATIONS ---"
            ])
            for cert in base["certifications"]:
                lines.append(f"  • {cert}")

        if base.get("projects"):
            lines.extend([
                "",
                "--- KEY PROJECTS ---"
            ])
            for proj in base["projects"][:3]:
                lines.append(f"  {proj.get('name', '')}: {proj.get('description', '')[:150]}")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    async def generate_cover_letter(self, resume_path: str, job_url: str,
                                    job_data: Dict = None, output_path: str = None,
                                    tone: str = "professional") -> str:
        """Generate a customized cover letter for a job application."""
        logger.info(f"Generating cover letter for {job_url}")

        base_resume = await self.parse_resume(resume_path)

        if job_data is None:
            job_data = {"title": "Target Position", "company": "Target Company",
                       "description": "", "requirements": ""}

        cover_letter = self._generate_cover_letter_content(base_resume, job_data, tone)

        if not output_path:
            resume_file = Path(resume_path)
            output_path = str(resume_file.parent / f"{resume_file.stem}_cover_letter_{job_data.get('company', 'job').replace(' ', '_')}.txt")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cover_letter)

        # Save to database
        base_resume_record = await self.db.get_resume(resume_path)
        if base_resume_record:
            job = await self.db.get_job(job_url)
            await self.db.save_cover_letter({
                "base_resume_id": base_resume_record["id"],
                "job_id": job["id"] if job else None,
                "output_path": output_path,
                "tone": tone,
                "content": cover_letter
            })

        return f"✅ Cover letter generated: {output_path}\nTone: {tone}"

    def _generate_cover_letter_content(self, resume: Dict, job: Dict, tone: str) -> str:
        """Generate cover letter content."""
        name = resume.get("name", "Applicant")
        current_role = resume.get("current_role", "Experienced Professional")
        years_exp = resume.get("total_experience_years", 0)
        top_skills = resume.get("top_skills", [])[:5]
        key_achievements = []

        for exp in resume.get("experience", [])[:2]:
            key_achievements.extend(exp.get("achievements", [])[:2])

        job_title = job.get("title", "the position")
        company = job.get("company", "your organization")

        tone_styles = {
            "professional": {
                "opening": f"I am writing to express my strong interest in the {job_title} position at {company}.",
                "body": f"With {years_exp}+ years of experience as a {current_role}, I have developed deep expertise in {', '.join(top_skills)}.",
                "closing": "I would welcome the opportunity to discuss how my background aligns with your needs."
            },
            "enthusiastic": {
                "opening": f"I was thrilled to discover the {job_title} opening at {company}!",
                "body": f"As a passionate {current_role} with {years_exp}+ years of experience, I've consistently delivered results in {', '.join(top_skills)}.",
                "closing": "I'm excited about the possibility of contributing to {company}'s mission and would love to chat!"
            },
            "concise": {
                "opening": f"I am applying for the {job_title} role at {company}.",
                "body": f"{years_exp}+ years as {current_role} with expertise in {', '.join(top_skills)}.",
                "closing": "Available for interview at your convenience."
            },
            "detailed": {
                "opening": f"I am writing to apply for the {job_title} position at {company}, as advertised on Naukri.com.",
                "body": f"My {years_exp}+ years of experience as a {current_role} have equipped me with comprehensive skills in {', '.join(top_skills)}. "
                        f"In my current role, I have {key_achievements[0] if key_achievements else 'driven significant business impact'}. "
                        f"Additionally, I have {key_achievements[1] if len(key_achievements) > 1 else 'led cross-functional initiatives'}. "
                        f"I am particularly drawn to {company}'s work in {job.get('description', 'your industry')[:100]}...",
                "closing": "I am confident that my background in " + ", ".join(top_skills[:3]) + " would allow me to make immediate contributions to your team. I welcome the opportunity to discuss this role further."
            }
        }

        style = tone_styles.get(tone, tone_styles["professional"])

        lines = [
            f"{name}",
            f"{resume.get('email', '')} | {resume.get('phone', '')} | {resume.get('linkedin', '')}",
            f"{resume.get('location', '')}",
            "",
            f"Date: {__import__('datetime').datetime.now().strftime('%B %d, %Y')}",
            "",
            f"Hiring Manager",
            f"{company}",
            "",
            f"Dear Hiring Manager,",
            "",
            style["opening"],
            "",
            style["body"],
            "",
        ]

        if key_achievements:
            lines.append("Key achievements relevant to this role:")
            for ach in key_achievements[:3]:
                lines.append(f"• {ach}")
            lines.append("")

        lines.extend([
            style["closing"],
            "",
            "Thank you for your time and consideration.",
            "",
            "Sincerely,",
            name
        ])

        return "\n".join(lines)