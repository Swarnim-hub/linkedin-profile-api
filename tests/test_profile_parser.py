"""Tests for LinkedIn Profile Parser."""

import pytest
from app.parsers.profile_parser import (
    extract_image_url,
    format_full_name,
    parse_date_point,
    parse_date_range,
    parse_linkedin_profile_data,
)


def test_extract_image_url():
    # Direct url
    assert extract_image_url({"url": "https://example.com/pic.jpg"}) == "https://example.com/pic.jpg"

    # VectorImage with multiple artifacts
    vector_img = {
        "com.linkedin.common.VectorImage": {
            "rootUrl": "https://media.licdn.com/dms/image/v2/",
            "artifacts": [
                {"width": 100, "height": 100, "fileIdentifyingUrlPathSegment": "100_100.jpg"},
                {"width": 800, "height": 800, "fileIdentifyingUrlPathSegment": "800_800.jpg"},
                {"width": 400, "height": 400, "fileIdentifyingUrlPathSegment": "400_400.jpg"},
            ],
        }
    }
    # Should pick 800x800 as largest
    assert extract_image_url(vector_img) == "https://media.licdn.com/dms/image/v2/800_800.jpg"

    # Empty or none
    assert extract_image_url(None) is None
    assert extract_image_url({}) is None


def test_parse_date_point():
    d1 = parse_date_point({"year": 2021, "month": 6, "day": 15})
    assert d1 is not None
    assert d1.year == 2021
    assert d1.month == 6
    assert d1.day == 15
    assert d1.formatted == "2021-06-15"

    d2 = parse_date_point({"year": 2019, "month": 3})
    assert d2 is not None
    assert d2.formatted == "2019-03"

    d3 = parse_date_point({"year": 2020})
    assert d3 is not None
    assert d3.formatted == "2020"

    assert parse_date_point(None) is None
    assert parse_date_point({}) is None


def test_parse_date_range():
    start, end = parse_date_range({
        "startDate": {"year": 2020, "month": 1},
        "endDate": {"year": 2023, "month": 5},
    })
    assert start.formatted == "2020-01"
    assert end.formatted == "2023-05"

    # Present job (no endDate)
    start_cur, end_cur = parse_date_range({
        "startDate": {"year": 2023, "month": 6},
    })
    assert start_cur.formatted == "2023-06"
    assert end_cur is None


def test_parse_legacy_profile_view():
    raw_fixture = {
        "profile": {
            "firstName": "Satya",
            "lastName": "Nadella",
            "headline": "Chairman and CEO at Microsoft",
            "summary": "Experienced technology executive leading cloud innovation.",
            "locationName": "Greater Seattle Area",
            "industryName": "Information Technology & Services",
            "miniProfile": {
                "publicIdentifier": "satyanadella",
                "picture": {
                    "com.linkedin.common.VectorImage": {
                        "rootUrl": "https://media.licdn.com/dms/image/",
                        "artifacts": [
                            {"width": 400, "height": 400, "fileIdentifyingUrlPathSegment": "satya_400.jpg"}
                        ]
                    }
                }
            }
        },
        "positionGroupView": {
            "elements": [
                {
                    "miniCompany": {
                        "name": "Microsoft",
                        "universalName": "microsoft",
                    },
                    "positions": [
                        {
                            "title": "Chairman and CEO",
                            "companyName": "Microsoft",
                            "locationName": "Redmond, WA",
                            "employmentType": "Full-time",
                            "timePeriod": {
                                "startDate": {"year": 2014, "month": 2}
                            },
                            "description": "Leading transformation at Microsoft."
                        }
                    ]
                }
            ]
        },
        "educationView": {
            "elements": [
                {
                    "schoolName": "The University of Chicago Booth School of Business",
                    "degreeName": "Master of Business Administration (MBA)",
                    "fieldOfStudy": "Business",
                    "timePeriod": {
                        "startDate": {"year": 1995},
                        "endDate": {"year": 1997}
                    }
                }
            ]
        },
        "skillView": {
            "elements": [
                {"name": "Cloud Computing"},
                {"name": "Enterprise Software"},
                {"name": "Leadership"}
            ]
        },
        "certificationView": {
            "elements": [
                {
                    "name": "Executive Leadership",
                    "authority": "Harvard Business School",
                    "timePeriod": {
                        "startDate": {"year": 2010}
                    }
                }
            ]
        },
        "languageView": {
            "elements": [
                {"name": "English", "proficiency": "NATIVE_OR_BILINGUAL"},
                {"name": "Telugu", "proficiency": "NATIVE_OR_BILINGUAL"}
            ]
        }
    }

    result = parse_linkedin_profile_data(raw_fixture, "satyanadella")

    assert result.public_identifier == "satyanadella"
    assert result.first_name == "Satya"
    assert result.last_name == "Nadella"
    assert result.full_name == "Satya Nadella"
    assert result.headline == "Chairman and CEO at Microsoft"
    assert result.location == "Greater Seattle Area"
    assert result.about == "Experienced technology executive leading cloud innovation."
    assert result.profile_picture_url == "https://media.licdn.com/dms/image/satya_400.jpg"

    # Experience
    assert len(result.experience) == 1
    exp = result.experience[0]
    assert exp.title == "Chairman and CEO"
    assert exp.company_name == "Microsoft"
    assert exp.company_linkedin_url == "https://www.linkedin.com/company/microsoft/"
    assert exp.is_current is True
    assert exp.start_date.formatted == "2014-02"

    # Education
    assert len(result.education) == 1
    edu = result.education[0]
    assert edu.school_name == "The University of Chicago Booth School of Business"
    assert edu.degree == "Master of Business Administration (MBA)"
    assert edu.start_date.formatted == "1995"
    assert edu.end_date.formatted == "1997"

    # Skills
    assert len(result.skills) == 3
    assert [s.name for s in result.skills] == ["Cloud Computing", "Enterprise Software", "Leadership"]

    # Certifications
    assert len(result.certifications) == 1
    assert result.certifications[0].name == "Executive Leadership"
    assert result.certifications[0].authority == "Harvard Business School"

    # Languages
    assert len(result.languages) == 2
    assert result.languages[0].name == "English"
    assert result.languages[1].name == "Telugu"


def test_parse_dash_normalized_profile():
    dash_fixture = {
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
                "firstName": "Bill",
                "lastName": "Gates",
                "headline": "Co-chair, Bill & Melinda Gates Foundation",
                "summary": "Co-chair of the Bill & Melinda Gates Foundation.",
                "locationName": "Seattle, Washington, United States",
                "profilePicture": {
                    "displayImageReference": {
                        "com.linkedin.common.VectorImage": {
                            "rootUrl": "https://media.licdn.com/dms/image/",
                            "artifacts": [
                                {"width": 500, "height": 500, "fileIdentifyingUrlPathSegment": "bill_500.jpg"}
                            ]
                        }
                    }
                }
            },
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Position",
                "title": "Co-chair",
                "companyName": "Bill & Melinda Gates Foundation",
                "companyUrn": "bill-melinda-gates-foundation",
                "locationName": "Seattle, WA",
                "dateRange": {
                    "start": {"year": 2000}
                },
                "description": "Guided by the belief that every life has equal value."
            },
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Education",
                "schoolName": "Harvard University",
                "degreeName": "Applied Mathematics",
                "dateRange": {
                    "start": {"year": 1973},
                    "end": {"year": 1975}
                }
            },
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Skill",
                "name": "Philanthropy"
            },
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Skill",
                "name": "Software Development"
            },
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Language",
                "name": "English",
                "proficiency": "NATIVE"
            }
        ]
    }

    result = parse_linkedin_profile_data(dash_fixture, "williamhgates")

    assert result.public_identifier == "williamhgates"
    assert result.full_name == "Bill Gates"
    assert result.headline == "Co-chair, Bill & Melinda Gates Foundation"
    assert result.profile_picture_url == "https://media.licdn.com/dms/image/bill_500.jpg"
    assert len(result.experience) == 1
    assert result.experience[0].title == "Co-chair"
    assert result.experience[0].company_name == "Bill & Melinda Gates Foundation"
    assert len(result.education) == 1
    assert result.education[0].school_name == "Harvard University"
    assert len(result.skills) == 2
    assert len(result.languages) == 1
