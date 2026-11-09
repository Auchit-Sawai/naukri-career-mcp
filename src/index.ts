/**
 * Naukri Career Management Plugin for DeepSeek Harness
 * ======================================================
 * Provides tools for Naukri.com profile management, job search,
 * application tracking, and resume optimization via MCP server.
 */

import { z } from "zod";

// Import tool implementations
import { naukriAuditProfile } from "./tools/naukri_audit_profile.js";
import { naukriGetProfile } from "./tools/naukri_get_profile.js";
import { naukriProposeProfileChanges } from "./tools/naukri_propose_profile_changes.js";
import { naukriApplyProfileChanges } from "./tools/naukri_apply_profile_changes.js";
import { naukriUpdateHeadline } from "./tools/naukri_update_headline.js";
import { naukriUpdateSummary } from "./tools/naukri_update_summary.js";
import { naukriUpdateSkills } from "./tools/naukri_update_skills.js";
import { naukriUpdateExperience } from "./tools/naukri_update_experience.js";
import { naukriUpdatePreferences } from "./tools/naukri_update_preferences.js";
import { naukriSearchJobs } from "./tools/naukri_search_jobs.js";
import { naukriGetJobDetails } from "./tools/naukri_get_job_details.js";
import { naukriMatchJobToResume } from "./tools/naukri_match_job_to_resume.js";
import { naukriFindMatchingJobs } from "./tools/naukri_find_matching_jobs.js";
import { naukriTrackApplication } from "./tools/naukri_track_application.js";
import { naukriUpdateApplicationStatus } from "./tools/naukri_update_application_status.js";
import { naukriGetApplications } from "./tools/naukri_get_applications.js";
import { naukriGetApplicationStats } from "./tools/naukri_get_application_stats.js";
import { naukriParseResume } from "./tools/naukri_parse_resume.js";
import { naukriGenerateTailoredResume } from "./tools/naukri_generate_tailored_resume.js";
import { naukriGenerateCoverLetter } from "./tools/naukri_generate_cover_letter.js";
import { naukriLogin } from "./tools/naukri_login.js";
import { naukriLoginWithOtp } from "./tools/naukri_login_with_otp.js";
import { naukriGetProfileCompleteness } from "./tools/naukri_get_profile_completeness.js";
import { naukriExportData } from "./tools/naukri_export_data.js";
import { naukriCheckSession } from "./tools/naukri_check_session.js";
import { naukriEnsureSession } from "./tools/naukri_ensure_session.js";

// Tool definitions for DSH plugin
export const toolDefinitions = [
  {
    name: "naukri_audit_profile",
    description: "Audit Naukri profile for completeness, missing sections, and optimization opportunities. Compares against resume if provided.",
    schema: z.object({
      profile_url: z.string().url().optional().describe("Naukri profile URL (optional, uses saved session)"),
      resume_path: z.string().optional().describe("Path to resume file for comparison (PDF/DOCX)")
    }),
    handler: naukriAuditProfile
  },
  {
    name: "naukri_get_profile",
    description: "Fetch and parse current Naukri profile data including headline, summary, skills, experience, education, certifications, projects, and preferences.",
    schema: z.object({
      profile_url: z.string().url().optional().describe("Naukri profile URL (optional)")
    }),
    handler: naukriGetProfile
  },
  {
    name: "naukri_propose_profile_changes",
    description: "Propose optimized profile changes (headline, summary, skills, experience, preferences) based on resume and target roles. Returns proposal for review - does NOT apply changes.",
    schema: z.object({
      resume_path: z.string().describe("Path to updated resume (PDF/DOCX)"),
      target_roles: z.array(z.string()).optional().describe("Target job titles/roles"),
      target_industries: z.array(z.string()).optional().describe("Target industries")
    }),
    handler: naukriProposeProfileChanges
  },
  {
    name: "naukri_apply_profile_changes",
    description: "Apply approved profile changes to Naukri.com. Requires explicit confirmation. Shows proposed changes before applying.",
    schema: z.object({
      proposal_id: z.number().describe("Proposal ID from naukri_propose_profile_changes"),
      confirm: z.boolean().describe("Explicit confirmation to apply changes")
    }),
    handler: naukriApplyProfileChanges
  },
  {
    name: "naukri_update_headline",
    description: "Update professional headline with optimized version. Requires explicit confirmation.",
    schema: z.object({
      new_headline: z.string().min(10).max(250).describe("New professional headline (10-250 chars)"),
      confirm: z.boolean().describe("Explicit confirmation to apply")
    }),
    handler: naukriUpdateHeadline
  },
  {
    name: "naukri_update_summary",
    description: "Update profile summary with optimized version. Requires explicit confirmation.",
    schema: z.object({
      new_summary: z.string().min(50).describe("New profile summary (min 50 chars)"),
      confirm: z.boolean().describe("Explicit confirmation to apply")
    }),
    handler: naukriUpdateSummary
  },
  {
    name: "naukri_update_skills",
    description: "Update technical/functional skills with optimized keywords. Requires explicit confirmation.",
    schema: z.object({
      skills: z.array(z.string()).min(1).max(30).describe("List of skills to add/update (max 30)"),
      confirm: z.boolean().describe("Explicit confirmation to apply")
    }),
    handler: naukriUpdateSkills
  },
  {
    name: "naukri_update_experience",
    description: "Update employment history from resume data. Note: Complex experience edits may require manual Naukri UI interaction.",
    schema: z.object({
      experience: z.array(z.object({
        title: z.string(),
        company: z.string(),
        duration: z.string().optional(),
        location: z.string().optional(),
        description: z.string().optional(),
        achievements: z.array(z.string()).optional()
      })).describe("Experience entries"),
      confirm: z.boolean().describe("Explicit confirmation to apply")
    }),
    handler: naukriUpdateExperience
  },
  {
    name: "naukri_update_preferences",
    description: "Update job preferences (titles, locations, industries, salary). Note: May require manual Naukri UI interaction.",
    schema: z.object({
      preferences: z.object({
        preferredRoles: z.array(z.string()).optional(),
        preferredIndustries: z.array(z.string()).optional(),
        preferredLocations: z.array(z.string()).optional(),
        expectedSalary: z.string().optional(),
        noticePeriod: z.string().optional(),
        jobType: z.array(z.string()).optional()
      }).describe("Job preferences object"),
      confirm: z.boolean().describe("Explicit confirmation to apply")
    }),
    handler: naukriUpdatePreferences
  },
  // Job Search Tools
  {
    name: "naukri_search_jobs",
    description: "Search Naukri.com for jobs matching criteria. Returns job listings with basic info.",
    schema: z.object({
      keywords: z.array(z.string()).optional().describe("Search keywords"),
      location: z.string().optional().describe("Job location"),
      experience_min: z.number().int().min(0).optional().describe("Minimum years of experience"),
      experience_max: z.number().int().min(0).optional().describe("Maximum years of experience"),
      salary_min: z.number().optional().describe("Minimum salary (LPA)"),
      job_types: z.array(z.string()).optional().describe("Job types (full-time, contract, etc.)"),
      companies: z.array(z.string()).optional().describe("Target companies"),
      posted_within_days: z.number().int().default(30).describe("Posted within N days"),
      limit: z.number().int().default(50).describe("Maximum results")
    }),
    handler: naukriSearchJobs
  },
  {
    name: "naukri_get_job_details",
    description: "Get detailed job description from a Naukri job posting URL including requirements, skills, and company info.",
    schema: z.object({
      job_url: z.string().url().describe("Naukri job posting URL")
    }),
    handler: naukriGetJobDetails
  },
  {
    name: "naukri_match_job_to_resume",
    description: "Match a job description against resume and calculate compatibility score with detailed skill gap analysis.",
    schema: z.object({
      job_url: z.string().url().describe("Job posting URL"),
      resume_path: z.string().describe("Path to resume file (PDF/DOCX)"),
      job_data: z.record(z.any()).optional().describe("Pre-fetched job data (optional)")
    }),
    handler: naukriMatchJobToResume
  },
  {
    name: "naukri_find_matching_jobs",
    description: "Search jobs and automatically match against resume, returning only jobs above minimum match score.",
    schema: z.object({
      resume_path: z.string().describe("Path to resume file (PDF/DOCX)"),
      keywords: z.array(z.string()).optional().describe("Search keywords (auto-extracted from resume if not provided)"),
      location: z.string().optional().describe("Job location"),
      min_match_score: z.number().default(70).describe("Minimum match score (0-100)"),
      limit: z.number().int().default(20).describe("Maximum results")
    }),
    handler: naukriFindMatchingJobs
  },
  // Application Tracking Tools
  {
    name: "naukri_track_application",
    description: "Record a job application in local database with job details, match score, and notes.",
    schema: z.object({
      job_url: z.string().url().describe("Job posting URL"),
      job_title: z.string().describe("Job title"),
      company: z.string().describe("Company name"),
      location: z.string().optional().describe("Job location"),
      applied_date: z.string().optional().describe("Application date (ISO format, defaults to now)"),
      status: z.enum(["applied", "screening", "interview", "offer", "rejected", "withdrawn"]).default("applied").describe("Application status"),
      match_score: z.number().optional().describe("Resume-job match score"),
      notes: z.string().optional().describe("Additional notes")
    }),
    handler: naukriTrackApplication
  },
  {
    name: "naukri_update_application_status",
    description: "Update application status and add interview rounds, recruiter communications, and notes.",
    schema: z.object({
      application_id: z.number().describe("Application ID from database"),
      status: z.enum(["applied", "screening", "interview", "offer", "rejected", "withdrawn"]).describe("New status"),
      interview_round: z.number().int().optional().describe("Interview round number"),
      interview_date: z.string().optional().describe("Interview date (ISO format)"),
      interview_type: z.string().optional().describe("Interview type (phone, video, onsite, technical, hr)"),
      recruiter_name: z.string().optional().describe("Recruiter name"),
      recruiter_contact: z.string().optional().describe("Recruiter contact info (email or phone)"),
      notes: z.string().optional().describe("Notes about the update")
    }),
    handler: naukriUpdateApplicationStatus
  },
  {
    name: "naukri_get_applications",
    description: "Get tracked applications with optional filters for status, company, date range.",
    schema: z.object({
      status: z.string().optional().describe("Filter by status"),
      company: z.string().optional().describe("Filter by company"),
      date_from: z.string().optional().describe("Filter from date (ISO format)"),
      date_to: z.string().optional().describe("Filter to date (ISO format)"),
      limit: z.number().int().default(100).describe("Maximum results")
    }),
    handler: naukriGetApplications
  },
  {
    name: "naukri_get_application_stats",
    description: "Get application statistics and pipeline summary including conversion rates.",
    schema: z.object({
      date_from: z.string().optional().describe("From date (ISO format)"),
      date_to: z.string().optional().describe("To date (ISO format)")
    }),
    handler: naukriGetApplicationStats
  },
  // Resume Tools
  {
    name: "naukri_parse_resume",
    description: "Parse resume file (PDF/DOCX) and extract structured data including skills, experience, education, achievements.",
    schema: z.object({
      resume_path: z.string().describe("Path to resume file")
    }),
    handler: naukriParseResume
  },
  {
    name: "naukri_generate_tailored_resume",
    description: "Generate a tailored resume for a specific job, highlighting matching skills and experience.",
    schema: z.object({
      resume_path: z.string().describe("Base resume path"),
      job_url: z.string().url().describe("Job posting URL"),
      job_data: z.record(z.any()).optional().describe("Pre-fetched job data (optional)"),
      output_path: z.string().describe("Output file path")
    }),
    handler: naukriGenerateTailoredResume
  },
  {
    name: "naukri_generate_cover_letter",
    description: "Generate a customized cover letter for a job application with selectable tone.",
    schema: z.object({
      resume_path: z.string().describe("Resume path"),
      job_url: z.string().url().describe("Job posting URL"),
      job_data: z.record(z.any()).optional().describe("Pre-fetched job data (optional)"),
      output_path: z.string().describe("Output file path"),
      tone: z.enum(["professional", "enthusiastic", "concise", "detailed"]).default("professional").describe("Cover letter tone")
    }),
    handler: naukriGenerateCoverLetter
  },
  // Utility Tools
  {
    name: "naukri_login",
    description: "Explain that login must be completed by the user in a visible browser; never collect credentials",
    schema: z.object({}),
    handler: naukriLogin
  },
  {
    name: "naukri_login_with_otp",
    description: "Start a phone + OTP login in the visible browser; the user types the OTP in the browser (never sent to the model).",
    schema: z.object({
      phone: z.string().regex(/^\d{10}$/, "10-digit phone number")
    }),
    handler: naukriLoginWithOtp
  },
  {
    name: "naukri_check_session",
    description: "Check Naukri session status and detect expiry. Returns session validity and recommended action.",
    schema: z.object({}),
    handler: naukriCheckSession
  },
  {
    name: "naukri_ensure_session",
    description: "Check the existing session without accepting credentials",
    schema: z.object({}),
    handler: naukriEnsureSession
  },
  {
    name: "naukri_get_profile_completeness",
    description: "Get profile completeness score and missing section recommendations from Naukri.",
    schema: z.object({
      profile_url: z.string().url().optional().describe("Profile URL (optional)")
    }),
    handler: naukriGetProfileCompleteness
  },
  {
    name: "naukri_export_data",
    description: "Export tracked data (jobs, applications, profile history) to CSV or JSON.",
    schema: z.object({
      format: z.enum(["csv", "json"]).default("csv").describe("Export format"),
      output_dir: z.string().default("./exports").describe("Output directory"),
      data_types: z.array(z.string()).default(["applications", "jobs", "profile_history"]).describe("Data types to export")
    }),
    handler: naukriExportData
  }
];

// Plugin metadata
export const pluginMetadata = {
  name: "naukri-career-management",
  version: "0.1.0",
  description: "Naukri.com career management: profile optimization, job search, application tracking, resume tailoring"
};

// Export for DSH plugin system - this will be picked up by the DSH runtime
export default {
  ...pluginMetadata,
  tools: toolDefinitions
};

