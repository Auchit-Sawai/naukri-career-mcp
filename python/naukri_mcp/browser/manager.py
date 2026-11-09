"""
Browser Manager for Naukri Automation
======================================
Playwright-based browser automation for Naukri.com interactions.
"""

import asyncio
import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
import json

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Playwright browser for Naukri automation."""

    def __init__(self, headless: bool = True, profile_dir: Optional[str] = None):
        self.headless = headless
        configured_profile = profile_dir or os.environ.get("NAUKRI_BROWSER_PROFILE_DIR")
        self.profile_dir = str(Path(configured_profile).expanduser()) if configured_profile else str(Path.home() / ".naukri_mcp_browser")
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._logged_in = False

    async def initialize(self) -> None:
        """Initialize Playwright browser."""
        logger.info("Starting Playwright...")
        self.playwright = await async_playwright().start()

        # Use persistent context for session persistence
        self.browser = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ],
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        self.context = self.browser
        self.page = await self.context.new_page()

        # Add stealth scripts
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
        """)

        logger.info("Browser initialized successfully")

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """Login to Naukri.com."""
        if not self.page:
            raise RuntimeError("Browser not initialized")

        try:
            logger.info("Navigating to Naukri login...")
            await self.page.goto("https://www.naukri.com/nlogin/login", wait_until="networkidle")

            # Wait for login form
            await self.page.wait_for_selector("#usernameField", timeout=10000)

            # Fill credentials
            await self.page.fill("#usernameField", email)
            await self.page.fill("#passwordField", password)

            # Click login button
            await self.page.click("button[type='submit']")

            # Wait for redirect or dashboard
            await self.page.wait_for_url("**/mnjuser/**", timeout=30000)

            self._logged_in = True
            logger.info("Login successful")
            return {"success": True, "message": "Logged in successfully"}

        except Exception as e:
            logger.error(f"Login failed: {e}")
            return {"success": False, "error": str(e)}

    async def is_logged_in(self) -> bool:
        """Check if logged in by visiting profile page."""
        if not self.page:
            return False

        try:
            await self.page.goto("https://www.naukri.com/mnjuser/profile", wait_until="domcontentloaded", timeout=10000)
            await asyncio.sleep(2)
            # Check for profile elements
            await self.page.wait_for_selector("span.fullname, .profile-header, .profile-wrapper", timeout=5000)
            self._logged_in = True
            return True
        except Exception:
            self._logged_in = False
            return False

    async def login_with_otp(self, phone: str, otp: Optional[str] = None) -> Dict[str, Any]:
        """Login to Naukri.com using phone number and OTP.
        
        Args:
            phone: 10-digit phone number (e.g., "9876543210")
            otp: OTP code if already received. If None, waits for user input via browser.
        """
        if not self.page:
            raise RuntimeError("Browser not initialized")

        try:
            logger.info("Navigating to Naukri login...")
            await self.page.goto("https://www.naukri.com/nlogin/login", wait_until="networkidle")

            # Wait for login form
            await self.page.wait_for_selector("#usernameField", timeout=10000)

            # Click "Login with OTP" link/button
            try:
                await self.page.click("text=Login with OTP", timeout=5000)
            except Exception:
                try:
                    await self.page.click("text=OTP", timeout=3000)
                except Exception:
                    logger.warning("Could not find 'Login with OTP' button, trying alternative")
                    await self.page.click("a[href*='otp'], button:has-text('OTP')", timeout=3000)

            # Wait for OTP form
            await self.page.wait_for_selector("input[placeholder*='mobile'], input[placeholder*='phone'], input[name='mobile'], #mobileNumber", timeout=10000)

            # Fill phone number
            phone_selector = "input[placeholder*='mobile'], input[placeholder*='phone'], input[name='mobile'], #mobileNumber"
            await self.page.fill(phone_selector, phone)

            # Click "Get OTP" / "Send OTP" button
            await self.page.click("button:has-text('Get OTP'), button:has-text('Send OTP'), button:has-text('Submit'), button[type='submit']", timeout=5000)

            # Wait for OTP input field to appear
            await self.page.wait_for_selector("input[placeholder*='OTP'], input[placeholder*='otp'], input[name='otp'], input[maxlength='6']", timeout=10000)

            if otp:
                # Use provided OTP
                await self.page.fill("input[placeholder*='OTP'], input[placeholder*='otp'], input[name='otp'], input[maxlength='6']", otp)
                await self.page.click("button:has-text('Verify'), button:has-text('Submit'), button[type='submit']", timeout=5000)
            else:
                # Wait for user to enter OTP manually in the browser (headless=False mode)
                logger.info("Waiting for user to enter OTP in browser...")
                await self.page.wait_for_url("**/mnjuser/**", timeout=120000)

            # Wait for redirect to dashboard
            await self.page.wait_for_url("**/mnjuser/**", timeout=30000)

            self._logged_in = True
            logger.info("OTP login successful")
            return {"success": True, "message": "Logged in successfully with OTP"}

        except Exception as e:
            logger.error(f"OTP login failed: {e}")
            return {"success": False, "error": str(e)}

    async def check_session_status(self) -> Dict[str, Any]:
        """
        Check session status and detect expiry.
        Returns dict with status info including whether session is valid,
        time since last activity, and recommended action.
        """
        if not self.page:
            return {"valid": False, "reason": "Browser not initialized", "action": "initialize"}

        try:
            # Try to access profile page. Naukri may serve an Akamai denial page
            # for direct profile navigation; do not mistake that for logout.
            await self.page.goto("https://www.naukri.com/mnjuser/profile", wait_until="domcontentloaded", timeout=10000)
            await asyncio.sleep(2)

            # Check for login redirect or session expiry indicators
            current_url = self.page.url
            page_content = await self.page.content()
            page_text = (await self.page.locator("body").inner_text()).lower()

            if "access denied" in page_text or "errors.edgesuite.net" in page_content.lower():
                # Verify whether Naukri still recognizes the browser session by
                # visiting its authenticated dashboard route.
                await self.page.goto("https://www.naukri.com/mnjuser/homepage", wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(5)
                dashboard_url = self.page.url.lower()
                dashboard_title = (await self.page.title()).lower()
                dashboard_text = (await self.page.locator("body").inner_text()).lower()

                if ("/mnjuser/" in dashboard_url
                        and "login" not in dashboard_url
                        and "signin" not in dashboard_url
                        and "login" not in dashboard_title
                        and "sign in" not in dashboard_text):
                    # A private route alone does not prove authentication.
                    # Require a rendered account/profile marker, not a loading
                    # shell, generic page title, or redirect loop.
                    try:
                        await self.page.wait_for_selector(
                            "a[href*='/mnjuser/profile'], [class*='user-details'], [class*='profile']",
                            timeout=10000,
                        )
                    except Exception:
                        return {
                            "valid": False,
                            "reason": "Dashboard route reached but account markers did not load; session is unverified",
                            "action": "verify",
                            "current_url": self.page.url,
                        }

                    return {
                        "valid": True,
                        "reason": "Authenticated dashboard account markers found; direct profile route is blocked by access control",
                        "action": "none",
                        "current_url": self.page.url,
                    }

                return {
                    "valid": False,
                    "reason": "Profile route was denied and dashboard did not confirm an authenticated session",
                    "action": "verify",
                    "current_url": self.page.url,
                }

            # Check for session expiry indicators
            if "login" in current_url.lower() or "signin" in current_url.lower():
                return {
                    "valid": False,
                    "reason": "Redirected to login page - session expired",
                    "action": "relogin",
                    "current_url": current_url
                }

            # Check for session expiry messages in page content
            expiry_indicators = [
                "session expired",
                "session timeout",
                "please login again",
                "your session has expired",
                "login to continue"
            ]

            page_text = page_content.lower()
            for indicator in expiry_indicators:
                if indicator in page_text:
                    return {
                        "valid": False,
                        "reason": f"Session expiry detected: {indicator}",
                        "action": "relogin",
                        "current_url": current_url
                    }

            # Check for profile elements to confirm valid session
            try:
                await self.page.wait_for_selector("span.fullname, .profile-header", timeout=3000)
                return {
                    "valid": True,
                    "reason": "Session active",
                    "action": "none",
                    "current_url": current_url
                }
            except Exception:
                return {
                    "valid": False,
                    "reason": "Profile elements not found - possible session issue",
                    "action": "verify",
                    "current_url": current_url
                }

        except Exception as e:
            return {
                "valid": False,
                "reason": f"Error checking session: {str(e)}",
                "action": "error",
                "error": str(e)
            }

    async def ensure_valid_session(self, email: str = None, password: str = None) -> Dict[str, Any]:
        """
        Ensure we have a valid session. If not, attempt to re-login.
        Requires email and password for re-login if session expired.
        """
        status = await self.check_session_status()

        if status["valid"]:
            return {"success": True, "status": status}

        # Session invalid - try to re-login if credentials provided
        if email and password and status["action"] in ["relogin", "verify"]:
            logger.info("Attempting to re-login...")
            login_result = await self.login(email, password)
            if login_result.get("success"):
                # Verify new session
                verify_status = await self.check_session_status()
                if verify_status["valid"]:
                    return {"success": True, "status": verify_status, "relogged": True}
                else:
                    return {"success": False, "reason": "Re-login failed", "status": verify_status}
            else:
                return {"success": False, "reason": "Login failed", "login_result": login_result}

        return {"success": False, "status": status, "message": "Session invalid and no credentials provided for re-login"}

    async def get_profile(self, profile_url: Optional[str] = None) -> Dict[str, Any]:
        """Fetch and parse Naukri profile using validated selectors."""
        if not self.page:
            raise RuntimeError("Browser not initialized")

        url = profile_url or "https://www.naukri.com/mnjuser/profile"
        await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)  # Wait for dynamic content

        # Extract profile data using validated selectors
        profile_data = await self.page.evaluate("""() => {
            const getText = (sel) => {
                const el = document.querySelector(sel);
                return el ? el.innerText.trim() : null;
            };

            const getAllText = (sel) => {
                return Array.from(document.querySelectorAll(sel)).map(el => el.innerText.trim()).filter(t => t);
            };

            const getAttribute = (sel, attr) => {
                const el = document.querySelector(sel);
                return el ? el.getAttribute(attr) : null;
            };

            // Headline - multiple possible locations
            let headline = null;
            const headlineSelectors = [
                "div.card.mt15 div.widgetCont div.prefill.typ-14Medium > div",
                "div.txt-wrapper.col div.row div.s12 div.subhdn div.desg.typ-16Bold > div",
                "span.resumeHeadline",
                ".resumeHeadline",
                "[data-testid='headline']"
            ];
            for (const sel of headlineSelectors) {
                const text = getText(sel);
                if (text && text.length > 10) {
                    headline = text;
                    break;
                }
            }

            // Name
            const name = getText("span.fullname");

            // Skills - chip elements (collect once, used for both skills and experience parsing)
            const allSkills = getAllText("span.chip.typ-14Medium, span.chip, .keySkills span.chip");

            // Experience - use a Map to track unique entries by title+company
            const experience = [];
            const seenExperiences = new Set();

            function addExperience(title, company, duration, description, is_current = false) {
                if (!title || !company) return;
                const key = (title + "|" + company).toLowerCase();
                if (seenExperiences.has(key)) return;
                seenExperiences.add(key);
                experience.push({title, company, duration: duration || "", description: description || "", is_current});
            }

            // Current/most recent position (in header area)
            const currentTitle = getText("div.txt-wrapper.col div.row div.s12 div.subhdn div.desg.typ-16Bold > div");
            const currentCompany = getText("div.row div.s12 div.subhdn div.desg.typ-16Bold div div.typ-14Medium.mt4");
            const currentDuration = getText("div.row div.s12 div.subhdn div.desg.typ-16Bold div div.typ-14Medium.mt4 + *, span.experienceType, .experienceType");

            if (currentTitle) {
                addExperience(currentTitle, currentCompany, currentDuration, "", true);
            }

            // Past positions (in employment list - first pattern)
            document.querySelectorAll("div.card div.widgetCont div.row.emp-list div.item.title.typ-14Bold").forEach(item => {
                const titleEl = item.querySelector("span.truncate.emp-desg");
                const companyEl = item.parentElement?.querySelector("div.typ-14Medium");
                const durationEl = item.parentElement?.querySelector("span.experienceType, div.experienceType");

                const title = titleEl ? titleEl.innerText.trim() : null;
                const company = companyEl ? companyEl.innerText.trim() : null;
                const duration = durationEl ? durationEl.innerText.trim() : null;

                addExperience(title, company, duration, "", false);
            });

            // Also check for employment list items (second pattern)
            document.querySelectorAll("div.row.emp-list div.item").forEach(item => {
                const titleEl = item.querySelector("span.truncate.emp-desg, span.emp-desg, .title, span.truncate");
                const companyEl = item.querySelector("div.typ-14Medium, .org-name");
                const durationEl = item.querySelector("span.experienceType, .experienceType, .duration, span.duration");

                const title = titleEl ? titleEl.innerText.trim() : null;
                const company = companyEl ? companyEl.innerText.trim() : null;
                const duration = durationEl ? durationEl.innerText.trim() : null;

                addExperience(title, company, duration, "", false);
            });

            // Skills (from key skills section) - use allSkills collected earlier
            const skills = allSkills;

            // Projects
            const projects = [];
            document.querySelectorAll("div.row.emp-list div.item.projects").forEach(item => {
                const nameEl = item.querySelector("span.chip, .project-name");
                const descEl = item.querySelector("div.prefill, .description");

                const name = nameEl ? nameEl.innerText.trim() : null;
                const description = descEl ? descEl.innerText.trim() : null;

                if (name) projects.push({name, description});
            });

            // Education
            const education = [];
            document.querySelectorAll("div.card div.widgetCont div.prefill.typ-14Medium").forEach(item => {
                const text = item.innerText.trim();
                if (text.toLowerCase().includes('mba') || text.toLowerCase().includes('bachelor') ||
                    text.toLowerCase().includes('master') || text.toLowerCase().includes('degree') ||
                    text.toLowerCase().includes('university') || text.toLowerCase().includes('college') ||
                    text.toLowerCase().includes('institute')) {
                    // Try to parse degree, institute, year
                    education.push({raw: text, degree: text, institute: "", year: ""});
                }
            });

            // Resume file
            const resume_file = getText("div.truncate.exten, .resume-name-inline .truncate.exten");

            // Quick links / sections available
            const quickLinks = [];
            document.querySelectorAll("div.card.quickLink ul.collection li.collection-item span.text").forEach(el => {
                quickLinks.push(el.innerText.trim());
            });

            return {
                name: getText("span.fullname"),
                headline,
                skills,
                experience,
                education,
                projects,
                resume_file,
                quick_links: quickLinks,
                raw_text: document.body.innerText.substring(0, 10000)  // For debugging
            };
        }""")

        return profile_data

    async def get_profile_completeness(self) -> Dict[str, Any]:
        """Get profile completeness score from Naukri using validated selectors."""
        if not self.page:
            raise RuntimeError("Browser not initialized")

        await self.page.goto("https://www.naukri.com/mnjuser/profile", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)

        completeness = await self.page.evaluate("""() => {
            const scoreEl = document.querySelector(".profile-completeness .score, [data-testid='completeness-score']");
            const score = scoreEl ? parseInt(scoreEl.innerText.match(/\\d+/)?.[0] || '0') : 0;

            const missing = [];
            document.querySelectorAll(".incomplete-section, .missing-field").forEach(el => {
                missing.push(el.innerText.trim());
            });

            return {score, missing};
        }""")

        return completeness

    async def _is_challenge_page(self, content: str) -> bool:
        """True only for an access-denied / bot-challenge page, not a normal page."""
        title = (await self.page.title()).lower() if self.page else ""
        text = content.lower()
        return (
            "access denied" in title
            or "just a moment" in title
            or "attention required" in title
            or "verify you are human" in text
            or "cf-challenge" in text
        )

    async def search_jobs(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search jobs on Naukri using validated selectors."""
        if not self.page:
            raise RuntimeError("Browser not initialized")

        # Build search URL
        params = []
        if criteria.get("keywords"):
            params.append(f"k={'%20'.join(criteria['keywords'])}")
        if criteria.get("location"):
            params.append(f"l={criteria['location']}")
        if criteria.get("experience_min"):
            params.append(f"experience={criteria['experience_min']}")
        if criteria.get("salary_min"):
            params.append(f"salary={criteria['salary_min']}")

        search_url = f"https://www.naukri.com/jobs?{'&'.join(params)}"
        if criteria.get("posted_within_days"):
            search_url += f"&postedWithin={criteria['posted_within_days']}"

        logger.info(f"Searching jobs: {search_url}")
        await self.page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)  # Wait for dynamic content

        # Check for Cloudflare challenge
        content = await self.page.content()
        # Detect the challenge page itself; normal Naukri pages also load Cloudflare scripts,
        # so matching the word "cloudflare" anywhere gave false "blocked" results.
        if await self._is_challenge_page(content):
            logger.warning("Cloudflare challenge detected on search page")
            return [{"error": "Cloudflare challenge - search page blocked"}]

        # Wait for job listings using validated selectors
        try:
            await self.page.wait_for_selector("li.styles_jlc__list-item__cAWRu, div.cust-job-tuple.layout-wrapper.lay-2.sjw__tuple", timeout=15000)
        except Exception:
            logger.warning("Job listing selectors not found, trying alternative")
            try:
                await self.page.wait_for_selector("div.srp-jobtuple-wrapper", timeout=10000)
            except Exception:
                return [{"error": "Job listings not found - selectors may have changed"}]

        # Extract job listings using validated selectors
        limit = criteria.get('limit', 50)
        jobs = await self.page.evaluate(f"""() => {{
            const jobs = [];

            // Try multiple selectors for job cards
            const selectors = [
                "li.styles_jlc__list-item__cAWRu",
                "div.cust-job-tuple.layout-wrapper.lay-2.sjw__tuple",
                "div.srp-jobtuple-wrapper"
            ];

            let elements = [];
            for (const sel of selectors) {{
                elements = document.querySelectorAll(sel);
                if (elements.length > 0) break;
            }}

            const limit = {limit};
            elements.forEach((el, idx) => {{
                if (idx >= limit) return;

                // Try multiple selectors for each field
                const titleEl = el.querySelector("div.row div.info h2 a, h2 a.title, a.title, .title a");
                const companyEl = el.querySelector("div.row div.info div.company, div.company, .comp-name");
                const locationEl = el.querySelector("div.row div.info span.location, span.location, .loc");
                const expEl = el.querySelector("div.row div.info span.exp, span.exp, .experience");
                const salaryEl = el.querySelector("div.row div.info span.salary, span.salary, .salary");
                const ratingEl = el.querySelector("span.rating, .rating, .star-rating");
                const descEl = el.querySelector("div.row div.info div.job-desc, div.description, .job-desc");
                const linkEl = el.querySelector("a[href*='/job-listings/'], a[href*='/jobs/'], h2 a");

                const title = titleEl ? titleEl.innerText.trim() : null;
                const company = companyEl ? companyEl.innerText.trim() : null;
                const location = locationEl ? locationEl.innerText.trim() : null;
                const experience = expEl ? expEl.innerText.trim() : null;
                const salary = salaryEl ? salaryEl.innerText.trim() : null;
                const rating = ratingEl ? ratingEl.innerText.trim() : null;
                const description = descEl ? descEl.innerText.trim() : null;
                const url = linkEl ? linkEl.href : null;

                // Also try to get job ID from data attributes
                const jobId = el.getAttribute("data-job-id") || el.getAttribute("data-id");

                if (title && company) {{
                    jobs.push({{title, company, location, experience, salary, rating, description, url, jobId}});
                }}
            }});

            return jobs;
        }}""")

        # Add search metadata to each job
        for job in jobs:
            job["search_keywords"] = criteria.get("keywords", [])
            job["search_location"] = criteria.get("location", "")
            job["searched_at"] = asyncio.get_event_loop().time()

        return jobs

    async def get_job_details(self, job_url: str) -> Dict[str, Any]:
        """Get detailed job description using validated selectors."""
        if not self.page:
            raise RuntimeError("Browser not initialized")

        await self.page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(2)

        # Check for Cloudflare
        content = await self.page.content()
        # Detect the challenge page itself; normal Naukri pages also load Cloudflare scripts,
        # so matching the word "cloudflare" anywhere gave false "blocked" results.
        if await self._is_challenge_page(content):
            return {"error": "Cloudflare challenge - job detail page blocked"}

        job_data = await self.page.evaluate("""() => {
            const getText = (sel) => {
                const el = document.querySelector(sel);
                return el ? el.innerText.trim() : null;
            };

            const getHtml = (sel) => {
                const el = document.querySelector(sel);
                return el ? el.innerHTML : null;
            };

            // Try multiple selectors for each field
            const title = getText("h1.jd-header-title, h1.job-title, .jd-header-title, .job-title");
            const company = getText(".jd-header-comp-name, .company-name, .jd-comp-name");
            const location = getText(".jd-header-location, .location, .job-location");
            const experience = getText(".exp, .experience, .job-experience");
            const salary = getText(".salary, .sal, .jd-salary");
            const description = getText(".job-desc, .job-description, .description, .JD-description");
            const description_html = getHtml(".job-desc, .job-description, .description, .JD-description");
            const requirements = getText(".requirements, .key-requirements, .JD-requirements");
            const skills = Array.from(document.querySelectorAll(".key-skills .skill, .tags .tag, .chip, .skill-tag")).map(el => el.innerText.trim());
            const posted_date = getText(".posted-date, .job-posted, .posted-on");
            const job_type = getText(".job-type, .employment-type, .jobType");
            const company_description = getText(".company-desc, .about-company, .company-description");

            // Rating
            const rating = getText(".rating, .star-rating, .company-rating");

            // Application deadline
            const deadline = getText(".deadline, .application-deadline, .apply-by");

            // Number of applications
            const applications = getText(".applications-count, .applicants, .total-applications");

            return {
                title,
                company,
                location,
                experience,
                salary,
                description,
                description_html,
                requirements,
                skills,
                posted_date,
                job_type,
                company_description,
                rating,
                deadline,
                applications
            };
        }""")

        return job_data

    async def update_profile_headline(self, new_headline: str) -> Dict[str, Any]:
        """Update profile headline."""
        if not self.page:
            raise RuntimeError("Browser not initialized")

        await self.page.goto("https://www.naukri.com/mnjuser/profile", wait_until="networkidle")

        # Click edit headline
        try:
            await self.page.click(".profile-headline .edit, .headline .edit-btn, [data-testid='edit-headline']", timeout=5000)
            await self.page.wait_for_selector("input[name='headline'], textarea[name='headline']", timeout=5000)

            # Fill new headline
            await self.page.fill("input[name='headline'], textarea[name='headline']", new_headline)

            # Save
            await self.page.click("button:has-text('Save'), .save-btn, [data-testid='save-headline']")
            await self.page.wait_for_timeout(2000)

            return {"success": True, "message": "Headline updated"}
        except Exception as e:
            logger.error(f"Failed to update headline: {e}")
            return {"success": False, "error": str(e)}

    async def update_profile_summary(self, new_summary: str) -> Dict[str, Any]:
        """Update profile summary."""
        if not self.page:
            raise RuntimeError("Browser not initialized")

        await self.page.goto("https://www.naukri.com/mnjuser/profile", wait_until="networkidle")

        try:
            await self.page.click(".profile-summary .edit, .summary .edit-btn, [data-testid='edit-summary']", timeout=5000)
            await self.page.wait_for_selector("textarea[name='summary'], .summary-editor", timeout=5000)

            await self.page.fill("textarea[name='summary'], .summary-editor", new_summary)
            await self.page.click("button:has-text('Save'), .save-btn, [data-testid='save-summary']")
            await self.page.wait_for_timeout(2000)

            return {"success": True, "message": "Summary updated"}
        except Exception as e:
            logger.error(f"Failed to update summary: {e}")
            return {"success": False, "error": str(e)}

    async def update_profile_skills(self, skills: List[str]) -> Dict[str, Any]:
        """Update profile skills."""
        if not self.page:
            raise RuntimeError("Browser not initialized")

        await self.page.goto("https://www.naukri.com/mnjuser/profile", wait_until="networkidle")

        try:
            await self.page.click(".key-skills .edit, .skills .edit-btn, [data-testid='edit-skills']", timeout=5000)
            await self.page.wait_for_selector(".skill-input, input[placeholder*='skill']", timeout=5000)

            # Clear existing and add new skills
            for skill in skills:
                await self.page.fill(".skill-input, input[placeholder*='skill']", skill)
                await self.page.press(".skill-input, input[placeholder*='skill']", "Enter")
                await self.page.wait_for_timeout(500)

            await self.page.click("button:has-text('Save'), .save-btn, [data-testid='save-skills']")
            await self.page.wait_for_timeout(2000)

            return {"success": True, "message": f"Updated {len(skills)} skills"}
        except Exception as e:
            logger.error(f"Failed to update skills: {e}")
            return {"success": False, "error": str(e)}

    async def apply_to_job(self, job_url: str) -> Dict[str, Any]:
        """Apply to a job (requires manual confirmation)."""
        if not self.page:
            raise RuntimeError("Browser not initialized")

        await self.page.goto(job_url, wait_until="networkidle")

        try:
            # Click apply button
            await self.page.click("button:has-text('Apply'), .apply-btn, [data-testid='apply-button']", timeout=5000)

            # Handle any modals or forms
            await self.page.wait_for_timeout(2000)

            return {"success": True, "message": "Application initiated - please complete manually"}
        except Exception as e:
            logger.error(f"Failed to apply: {e}")
            return {"success": False, "error": str(e)}

    async def close(self) -> None:
        """Close browser."""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser closed")

    async def take_screenshot(self, path: str) -> None:
        """Take screenshot for debugging."""
        if self.page:
            await self.page.screenshot(path=path, full_page=True)

