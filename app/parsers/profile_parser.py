"""Parser for LinkedIn Voyager API raw JSON payloads into structured Pydantic models."""

import logging
from typing import Any, Dict, List, Optional

from app.schemas.response import (
    CertificationItem,
    DatePoint,
    EducationItem,
    ExperienceItem,
    HonorItem,
    LanguageItem,
    ProfileResponse,
    ProjectItem,
    SkillItem,
    VolunteerItem,
)

logger = logging.getLogger(__name__)


def extract_image_url(image_obj: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract the highest resolution image URL from a LinkedIn VectorImage object."""
    if not image_obj or not isinstance(image_obj, dict):
        return None

    # Check for direct URL
    if "url" in image_obj and isinstance(image_obj["url"], str):
        return image_obj["url"]

    # LinkedIn VectorImage structure
    vector_img = image_obj.get("com.linkedin.common.VectorImage", image_obj)
    if not isinstance(vector_img, dict):
        return None

    root_url = vector_img.get("rootUrl")
    artifacts = vector_img.get("artifacts", [])

    if not root_url or not artifacts:
        return None

    # Pick largest artifact by width or height
    best_artifact = None
    max_dim = -1
    for art in artifacts:
        if isinstance(art, dict):
            w = art.get("width", 0) or 0
            h = art.get("height", 0) or 0
            dim = max(w, h)
            if dim > max_dim:
                max_dim = dim
                best_artifact = art

    if best_artifact and "fileIdentifyingUrlPathSegment" in best_artifact:
        segment = best_artifact["fileIdentifyingUrlPathSegment"]
        return f"{root_url}{segment}"

    return None


def parse_date_point(raw_date: Optional[Dict[str, Any]]) -> Optional[DatePoint]:
    """Parse LinkedIn date dictionary (year, month, day) into DatePoint."""
    if not raw_date or not isinstance(raw_date, dict):
        return None

    year = raw_date.get("year")
    month = raw_date.get("month")
    day = raw_date.get("day")

    if year is None:
        return None

    parts = [f"{year:04d}"]
    if month is not None:
        parts.append(f"{month:02d}")
        if day is not None:
            parts.append(f"{day:02d}")

    formatted = "-".join(parts)
    return DatePoint(year=year, month=month, day=day, formatted=formatted)


def parse_date_range(raw_range: Optional[Dict[str, Any]]) -> tuple[Optional[DatePoint], Optional[DatePoint]]:
    """Extract start_date and end_date from timePeriod or dateRange."""
    if not raw_range or not isinstance(raw_range, dict):
        return None, None

    # Format 1: timePeriod: {startDate: {...}, endDate: {...}}
    # Format 2: dateRange: {start: {...}, end: {...}}
    start_raw = raw_range.get("startDate") or raw_range.get("start")
    end_raw = raw_range.get("endDate") or raw_range.get("end")

    start_date = parse_date_point(start_raw)
    end_date = parse_date_point(end_raw)

    return start_date, end_date


def format_full_name(first: Optional[str], last: Optional[str]) -> Optional[str]:
    """Combine first and last name."""
    parts = [p.strip() for p in (first, last) if p and p.strip()]
    return " ".join(parts) if parts else None


def parse_legacy_profile_view(raw: Dict[str, Any], public_id: str) -> ProfileResponse:
    """Parse LinkedIn's legacy /identity/profiles/{id}/profileView endpoint response."""
    profile_data = raw.get("profile", {})
    mini_profile = profile_data.get("miniProfile", {})

    first_name = profile_data.get("firstName") or mini_profile.get("firstName")
    last_name = profile_data.get("lastName") or mini_profile.get("lastName")
    full_name = format_full_name(first_name, last_name)

    headline = profile_data.get("headline") or mini_profile.get("occupation")
    about = profile_data.get("summary")

    # Location
    location = profile_data.get("locationName")
    if not location and "geoCountryName" in profile_data:
        location = profile_data.get("geoCountryName")

    # Profile Images
    profile_pic = extract_image_url(mini_profile.get("picture")) or extract_image_url(profile_data.get("picture"))
    bg_pic = extract_image_url(mini_profile.get("backgroundImage")) or extract_image_url(profile_data.get("backgroundImage"))

    industry = profile_data.get("industryName")

    # Experience
    experiences: List[ExperienceItem] = []
    pos_group_view = raw.get("positionGroupView", {})
    for group in pos_group_view.get("elements", []):
        mini_company = group.get("miniCompany", {})
        comp_name = mini_company.get("name") or group.get("name")
        comp_urn = mini_company.get("universalName")
        comp_url = f"https://www.linkedin.com/company/{comp_urn}/" if comp_urn else None
        comp_logo = extract_image_url(mini_company.get("logo"))

        for pos in group.get("positions", []):
            start_date, end_date = parse_date_range(pos.get("timePeriod"))
            experiences.append(
                ExperienceItem(
                    title=pos.get("title"),
                    company_name=pos.get("companyName") or comp_name,
                    company_linkedin_url=comp_url,
                    company_logo_url=comp_logo,
                    location=pos.get("locationName"),
                    employment_type=pos.get("employmentType"),
                    start_date=start_date,
                    end_date=end_date,
                    is_current=end_date is None and start_date is not None,
                    description=pos.get("description"),
                )
            )

    # Fallback to direct positionView if positionGroupView empty
    if not experiences:
        pos_view = raw.get("positionView", {})
        for pos in pos_view.get("elements", []):
            start_date, end_date = parse_date_range(pos.get("timePeriod"))
            comp_name = pos.get("companyName")
            comp_urn = pos.get("companyUrn")
            comp_url = f"https://www.linkedin.com/company/{comp_urn}/" if comp_urn else None
            experiences.append(
                ExperienceItem(
                    title=pos.get("title"),
                    company_name=comp_name,
                    company_linkedin_url=comp_url,
                    company_logo_url=extract_image_url(pos.get("company", {}).get("logo")),
                    location=pos.get("locationName"),
                    employment_type=pos.get("employmentType"),
                    start_date=start_date,
                    end_date=end_date,
                    is_current=end_date is None and start_date is not None,
                    description=pos.get("description"),
                )
            )

    # Education
    educations: List[EducationItem] = []
    edu_view = raw.get("educationView", {})
    for edu in edu_view.get("elements", []):
        start_date, end_date = parse_date_range(edu.get("timePeriod"))
        school = edu.get("school", {})
        school_logo = extract_image_url(school.get("logo"))
        school_urn = school.get("universalName")
        school_url = f"https://www.linkedin.com/school/{school_urn}/" if school_urn else None
        educations.append(
            EducationItem(
                school_name=edu.get("schoolName"),
                school_linkedin_url=school_url,
                school_logo_url=school_logo,
                degree=edu.get("degreeName"),
                field_of_study=edu.get("fieldOfStudy"),
                start_date=start_date,
                end_date=end_date,
                grade=edu.get("grade"),
                activities=edu.get("activities"),
                description=edu.get("notes") or edu.get("description"),
            )
        )

    # Skills
    skills: List[SkillItem] = []
    skill_view = raw.get("skillView", {})
    for sk in skill_view.get("elements", []):
        name = sk.get("name")
        if name:
            skills.append(SkillItem(name=name))

    # Certifications
    certifications: List[CertificationItem] = []
    cert_view = raw.get("certificationView", {})
    for cert in cert_view.get("elements", []):
        start_date, end_date = parse_date_range(cert.get("timePeriod"))
        certifications.append(
            CertificationItem(
                name=cert.get("name"),
                authority=cert.get("authority"),
                url=cert.get("url"),
                license_number=cert.get("licenseNumber"),
                start_date=start_date,
                end_date=end_date,
            )
        )

    # Languages
    languages: List[LanguageItem] = []
    lang_view = raw.get("languageView", {})
    for lang in lang_view.get("elements", []):
        name = lang.get("name")
        if name:
            languages.append(
                LanguageItem(
                    name=name,
                    proficiency=lang.get("proficiency"),
                )
            )

    # Volunteer Experience
    volunteers: List[VolunteerItem] = []
    vol_view = raw.get("volunteerExperienceView", {})
    for vol in vol_view.get("elements", []):
        start_date, end_date = parse_date_range(vol.get("timePeriod"))
        volunteers.append(
            VolunteerItem(
                role=vol.get("role"),
                organization_name=vol.get("organizationName"),
                cause=vol.get("cause"),
                start_date=start_date,
                end_date=end_date,
                description=vol.get("description"),
            )
        )

    # Honors & Awards
    honors: List[HonorItem] = []
    honor_view = raw.get("honorView", {})
    for h in honor_view.get("elements", []):
        issue_date = parse_date_point(h.get("issueDate"))
        honors.append(
            HonorItem(
                title=h.get("title"),
                issuer=h.get("issuer") or h.get("occupation"),
                issue_date=issue_date,
                description=h.get("description"),
            )
        )

    # Projects
    projects: List[ProjectItem] = []
    proj_view = raw.get("projectView", {})
    for proj in proj_view.get("elements", []):
        start_date, end_date = parse_date_range(proj.get("timePeriod"))
        projects.append(
            ProjectItem(
                title=proj.get("title"),
                url=proj.get("url"),
                start_date=start_date,
                end_date=end_date,
                description=proj.get("description"),
            )
        )

    canonical_slug = mini_profile.get("publicIdentifier") or public_id

    return ProfileResponse(
        public_identifier=canonical_slug,
        profile_url=f"https://www.linkedin.com/in/{canonical_slug}/",
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
        headline=headline,
        location=location,
        about=about,
        industry=industry,
        profile_picture_url=profile_pic,
        background_image_url=bg_pic,
        connections_count=None,
        experience=experiences,
        education=educations,
        skills=skills,
        certifications=certifications,
        languages=languages,
        volunteer_experience=volunteers,
        honors=honors,
        projects=projects,
    )


def parse_dash_profile(raw: Dict[str, Any], public_id: str) -> ProfileResponse:
    """Parse LinkedIn's Dash normalized /identity/dash/profiles endpoint response.
    
    In Dash normalized JSON, entities are listed in the 'included' array, differentiated by '$type'.
    """
    included = raw.get("included", [])

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    headline: Optional[str] = None
    about: Optional[str] = None
    location: Optional[str] = None
    industry: Optional[str] = None
    profile_pic: Optional[str] = None
    bg_pic: Optional[str] = None

    experiences: List[ExperienceItem] = []
    educations: List[EducationItem] = []
    skills: List[SkillItem] = []
    certifications: List[CertificationItem] = []
    languages: List[LanguageItem] = []
    volunteers: List[VolunteerItem] = []
    honors: List[HonorItem] = []
    projects: List[ProjectItem] = []

    for item in included:
        if not isinstance(item, dict):
            continue

        item_type = item.get("$type", "")

        # Profile entity
        if "identity.profile.Profile" in item_type or item_type.endswith(".Profile"):
            first_name = item.get("firstName") or first_name
            last_name = item.get("lastName") or last_name
            headline = item.get("headline") or headline
            about = item.get("summary") or about
            location = item.get("locationName") or item.get("geoCountryName") or location
            industry = item.get("industryName") or industry

            # Picture resolution
            pic_obj = item.get("profilePicture", {}).get("displayImageReference", {})
            if not profile_pic:
                profile_pic = extract_image_url(pic_obj) or extract_image_url(item.get("picture"))
            if not bg_pic:
                bg_pic = extract_image_url(item.get("backgroundPicture"))

        # Position / Experience entity
        elif "identity.profile.Position" in item_type or "PositionGroup" in item_type or item_type.endswith(".Position"):
            start_date, end_date = parse_date_range(item.get("dateRange") or item.get("timePeriod"))
            comp_name = item.get("companyName")
            comp_urn = item.get("companyUrn")
            comp_url = f"https://www.linkedin.com/company/{comp_urn}/" if comp_urn else None
            logo_obj = item.get("companyLogo") or item.get("company", {}).get("logo")

            experiences.append(
                ExperienceItem(
                    title=item.get("title"),
                    company_name=comp_name,
                    company_linkedin_url=comp_url,
                    company_logo_url=extract_image_url(logo_obj),
                    location=item.get("locationName"),
                    employment_type=item.get("employmentType"),
                    start_date=start_date,
                    end_date=end_date,
                    is_current=end_date is None and start_date is not None,
                    description=item.get("description"),
                )
            )

        # Education entity
        elif "identity.profile.Education" in item_type or item_type.endswith(".Education"):
            start_date, end_date = parse_date_range(item.get("dateRange") or item.get("timePeriod"))
            school_logo = extract_image_url(item.get("schoolLogo") or item.get("school", {}).get("logo"))
            educations.append(
                EducationItem(
                    school_name=item.get("schoolName"),
                    school_logo_url=school_logo,
                    degree=item.get("degreeName"),
                    field_of_study=item.get("fieldOfStudy"),
                    start_date=start_date,
                    end_date=end_date,
                    grade=item.get("grade"),
                    activities=item.get("activities"),
                    description=item.get("description") or item.get("notes"),
                )
            )

        # Skill entity
        elif "identity.profile.Skill" in item_type or item_type.endswith(".Skill"):
            name = item.get("name")
            if name:
                skills.append(SkillItem(name=name))

        # Certification entity
        elif "identity.profile.Certification" in item_type or item_type.endswith(".Certification"):
            start_date, end_date = parse_date_range(item.get("dateRange") or item.get("timePeriod"))
            certifications.append(
                CertificationItem(
                    name=item.get("name"),
                    authority=item.get("authority"),
                    url=item.get("url"),
                    license_number=item.get("licenseNumber"),
                    start_date=start_date,
                    end_date=end_date,
                )
            )

        # Language entity
        elif "identity.profile.Language" in item_type or item_type.endswith(".Language"):
            name = item.get("name")
            if name:
                languages.append(
                    LanguageItem(
                        name=name,
                        proficiency=item.get("proficiency"),
                    )
                )

        # Volunteer entity
        elif "Volunteer" in item_type:
            start_date, end_date = parse_date_range(item.get("dateRange") or item.get("timePeriod"))
            volunteers.append(
                VolunteerItem(
                    role=item.get("role"),
                    organization_name=item.get("organizationName"),
                    cause=item.get("cause"),
                    start_date=start_date,
                    end_date=end_date,
                    description=item.get("description"),
                )
            )

        # Honor entity
        elif "Honor" in item_type:
            issue_date = parse_date_point(item.get("issueDate"))
            honors.append(
                HonorItem(
                    title=item.get("title"),
                    issuer=item.get("issuer"),
                    issue_date=issue_date,
                    description=item.get("description"),
                )
            )

        # Project entity
        elif "Project" in item_type:
            start_date, end_date = parse_date_range(item.get("dateRange") or item.get("timePeriod"))
            projects.append(
                ProjectItem(
                    title=item.get("title"),
                    url=item.get("url"),
                    start_date=start_date,
                    end_date=end_date,
                    description=item.get("description"),
                )
            )

    full_name = format_full_name(first_name, last_name)

    return ProfileResponse(
        public_identifier=public_id,
        profile_url=f"https://www.linkedin.com/in/{public_id}/",
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
        headline=headline,
        location=location,
        about=about,
        industry=industry,
        profile_picture_url=profile_pic,
        background_image_url=bg_pic,
        connections_count=None,
        experience=experiences,
        education=educations,
        skills=skills,
        certifications=certifications,
        languages=languages,
        volunteer_experience=volunteers,
        honors=honors,
        projects=projects,
    )


def parse_linkedin_profile_data(raw_data: Dict[str, Any], public_id: str) -> ProfileResponse:
    """Master parser entrypoint that auto-detects and parses any LinkedIn profile payload."""
    if not isinstance(raw_data, dict):
        raise ValueError("Invalid LinkedIn response: expected a JSON object.")

    # Check if this is a Dash normalized response (has 'included' list)
    if "included" in raw_data and isinstance(raw_data["included"], list):
        return parse_dash_profile(raw_data, public_id)

    # Check if this is a legacy profileView response
    if "profile" in raw_data or "positionGroupView" in raw_data or "educationView" in raw_data:
        return parse_legacy_profile_view(raw_data, public_id)

    # If it's a raw profile dictionary without profileView wrapper
    if "firstName" in raw_data or "headline" in raw_data:
        return parse_legacy_profile_view({"profile": raw_data}, public_id)

    # Fallback to dash parser
    return parse_dash_profile(raw_data, public_id)
