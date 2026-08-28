"""Structured response models for LinkedIn Profile data."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class DatePoint(BaseModel):
    """Normalized date representation (year, month, day)."""
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    formatted: Optional[str] = None  # e.g., "2021-06" or "2021"


class ExperienceItem(BaseModel):
    """Individual work experience item."""
    title: Optional[str] = Field(None, description="Job title")
    company_name: Optional[str] = Field(None, description="Company name")
    company_linkedin_url: Optional[str] = Field(None, description="Company LinkedIn profile URL")
    company_logo_url: Optional[str] = Field(None, description="Company logo image URL")
    location: Optional[str] = Field(None, description="Job location")
    employment_type: Optional[str] = Field(None, description="Full-time, Part-time, Contract, etc.")
    start_date: Optional[DatePoint] = Field(None, description="Start date")
    end_date: Optional[DatePoint] = Field(None, description="End date (null if current position)")
    is_current: bool = Field(False, description="Whether this is the current job")
    description: Optional[str] = Field(None, description="Role summary and achievements")


class EducationItem(BaseModel):
    """Individual education item."""
    school_name: Optional[str] = Field(None, description="School / University name")
    school_linkedin_url: Optional[str] = Field(None, description="School LinkedIn URL")
    school_logo_url: Optional[str] = Field(None, description="School logo image URL")
    degree: Optional[str] = Field(None, description="Degree earned")
    field_of_study: Optional[str] = Field(None, description="Major / Field of study")
    start_date: Optional[DatePoint] = Field(None, description="Start date")
    end_date: Optional[DatePoint] = Field(None, description="Graduation / End date")
    grade: Optional[str] = Field(None, description="Grade / GPA / Honors")
    activities: Optional[str] = Field(None, description="Societies and activities")
    description: Optional[str] = Field(None, description="Additional notes or description")


class SkillItem(BaseModel):
    """Individual skill item."""
    name: str = Field(..., description="Skill name")


class CertificationItem(BaseModel):
    """Individual certification or license item."""
    name: Optional[str] = Field(None, description="Certification name")
    authority: Optional[str] = Field(None, description="Issuing organization")
    url: Optional[str] = Field(None, description="Credential URL")
    license_number: Optional[str] = Field(None, description="License or credential ID")
    start_date: Optional[DatePoint] = Field(None, description="Issue date")
    end_date: Optional[DatePoint] = Field(None, description="Expiration date")


class LanguageItem(BaseModel):
    """Individual language item."""
    name: Optional[str] = Field(None, description="Language name")
    proficiency: Optional[str] = Field(None, description="Proficiency level (Native, Fluent, Professional, etc.)")


class VolunteerItem(BaseModel):
    """Individual volunteer experience item."""
    role: Optional[str] = Field(None, description="Volunteer role")
    organization_name: Optional[str] = Field(None, description="Organization name")
    cause: Optional[str] = Field(None, description="Cause supported")
    start_date: Optional[DatePoint] = Field(None, description="Start date")
    end_date: Optional[DatePoint] = Field(None, description="End date")
    description: Optional[str] = Field(None, description="Role description")


class HonorItem(BaseModel):
    """Individual honor or award item."""
    title: Optional[str] = Field(None, description="Award / Honor title")
    issuer: Optional[str] = Field(None, description="Issuing organization")
    issue_date: Optional[DatePoint] = Field(None, description="Date issued")
    description: Optional[str] = Field(None, description="Description")


class ProjectItem(BaseModel):
    """Individual project item."""
    title: Optional[str] = Field(None, description="Project title")
    url: Optional[str] = Field(None, description="Project URL")
    start_date: Optional[DatePoint] = Field(None, description="Start date")
    end_date: Optional[DatePoint] = Field(None, description="End date")
    description: Optional[str] = Field(None, description="Description")


class ProfileResponse(BaseModel):
    """Complete structured LinkedIn Profile response model."""
    public_identifier: str = Field(..., description="LinkedIn vanity slug / member identifier")
    profile_url: str = Field(..., description="Canonical LinkedIn profile URL")
    first_name: Optional[str] = Field(None, description="Member first name")
    last_name: Optional[str] = Field(None, description="Member last name")
    full_name: Optional[str] = Field(None, description="Full formatted name")
    headline: Optional[str] = Field(None, description="Professional headline")
    location: Optional[str] = Field(None, description="Formatted location string")
    about: Optional[str] = Field(None, description="Profile summary / About section")
    industry: Optional[str] = Field(None, description="Industry name")
    profile_picture_url: Optional[str] = Field(None, description="High-resolution profile picture URL")
    background_image_url: Optional[str] = Field(None, description="Background / banner image URL")
    connections_count: Optional[int] = Field(None, description="Number of connections (e.g. 500+)")
    follower_count: Optional[int] = Field(None, description="Number of followers")
    
    # Core sections
    experience: List[ExperienceItem] = Field(default_factory=list, description="Work experiences")
    education: List[EducationItem] = Field(default_factory=list, description="Educations")
    skills: List[SkillItem] = Field(default_factory=list, description="Skills")
    certifications: List[CertificationItem] = Field(default_factory=list, description="Certifications and licenses")
    languages: List[LanguageItem] = Field(default_factory=list, description="Languages spoken")
    
    # Supplementary sections
    volunteer_experience: List[VolunteerItem] = Field(default_factory=list, description="Volunteer experiences")
    honors: List[HonorItem] = Field(default_factory=list, description="Honors and awards")
    projects: List[ProjectItem] = Field(default_factory=list, description="Featured projects")

    # API metadata
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp when profile was fetched")
    is_cached: bool = Field(False, description="Whether this response was served from cache")
