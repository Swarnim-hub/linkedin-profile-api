"""Reverse-engineered LinkedIn Voyager API client.

Directly hits LinkedIn internal endpoints using session cookies (li_at, JSESSIONID).
Does not use a browser or browser automation.
"""

import json
import logging
import re
from typing import Any, Dict, Optional
import httpx

from app.config import settings
from app.parsers.profile_parser import parse_linkedin_profile_data
from app.schemas.response import ProfileResponse, ExperienceItem, EducationItem

logger = logging.getLogger(__name__)


class LinkedInAPIError(Exception):
    """Exception raised for LinkedIn API errors."""

    def __init__(self, message: str, status_code: int = 500, detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


class LinkedInClient:
    """Async client for interacting directly with LinkedIn's Voyager API."""

    BASE_VOYAGER_URL = "https://www.linkedin.com/voyager/api"

    def __init__(
        self,
        li_at: Optional[str] = None,
        jsessionid: Optional[str] = None,
        user_agent: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.li_at = li_at or settings.LINKEDIN_LI_AT
        self.jsessionid = jsessionid or settings.LINKEDIN_JSESSIONID
        self.user_agent = user_agent or settings.DEFAULT_USER_AGENT
        self.timeout = timeout or settings.REQUEST_TIMEOUT_SECONDS

    def _get_headers(self) -> Dict[str, str]:
        """Construct standard HTTP headers for authenticating with LinkedIn Voyager API."""
        headers = {
            "user-agent": self.user_agent,
            "accept": "application/vnd.linkedin.normalized+json+2.1, application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9",
            "x-restli-protocol-version": "2.0.0",
            "x-li-lang": "en_US",
            "sec-ch-ua": '"Chromium";v="125", "Not.A/Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

        # Build cookie and csrf token
        cookies = []
        if self.li_at:
            cookies.append(f"li_at={self.li_at.strip()}")

        if self.jsessionid:
            raw_jsessionid = self.jsessionid.strip()
            # Standard CSRF header uses JSESSIONID value without quotes
            csrf_token = raw_jsessionid.strip('"')
            headers["csrf-token"] = csrf_token
            # Cookie header contains quoted JSESSIONID
            cookies.append(f'JSESSIONID="{csrf_token}"')

        if cookies:
            headers["cookie"] = "; ".join(cookies)

        return headers

    async def fetch_profile_raw(self, public_id: str) -> Dict[str, Any]:
        """Fetch raw profile JSON from LinkedIn internal Voyager endpoints."""
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            # Candidate 1: Dash profiles endpoint with full entities decorator
            dash_url = (
                f"{self.BASE_VOYAGER_URL}/identity/dash/profiles"
                f"?q=memberIdentity&memberIdentity={public_id}"
                f"&decorationId=com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-35"
            )

            try:
                logger.info(f"Attempting Dash endpoint for {public_id}")
                resp = await client.get(dash_url, headers=headers)

                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        return data

                # If 401 or 403, credentials are invalid or missing
                if resp.status_code in (401, 403):
                    logger.warning(f"LinkedIn authentication failed (HTTP {resp.status_code})")
                    if not self.li_at:
                        raise LinkedInAPIError(
                            message="LinkedIn credentials missing. Set LINKEDIN_LI_AT and LINKEDIN_JSESSIONID.",
                            status_code=401,
                            detail="Session cookie 'li_at' is required to reverse-engineer LinkedIn Voyager APIs.",
                        )
                    raise LinkedInAPIError(
                        message="LinkedIn session expired or unauthorized.",
                        status_code=401,
                        detail="The provided li_at cookie or JSESSIONID has expired or been challenged by LinkedIn.",
                    )

                if resp.status_code == 429:
                    raise LinkedInAPIError(
                        message="Rate limited by LinkedIn.",
                        status_code=429,
                        detail="Too many requests. Please wait before making more requests.",
                    )

            except httpx.RequestError as e:
                logger.warning(f"Dash request failed: {e}")

            # Candidate 2: Legacy profileView endpoint
            legacy_url = f"{self.BASE_VOYAGER_URL}/identity/profiles/{public_id}/profileView"
            try:
                logger.info(f"Attempting legacy profileView endpoint for {public_id}")
                resp = await client.get(legacy_url, headers=headers)

                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        return data

                if resp.status_code == 404:
                    raise LinkedInAPIError(
                        message=f"LinkedIn profile '{public_id}' not found.",
                        status_code=404,
                        detail="Profile does not exist or is set to private.",
                    )
            except httpx.RequestError as e:
                logger.warning(f"Legacy profileView request failed: {e}")

            # Candidate 3: Dash profiles endpoint without specific decoration
            generic_dash_url = (
                f"{self.BASE_VOYAGER_URL}/identity/dash/profiles"
                f"?q=memberIdentity&memberIdentity={public_id}"
            )
            try:
                logger.info(f"Attempting generic Dash endpoint for {public_id}")
                resp = await client.get(generic_dash_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        return data
            except httpx.RequestError as e:
                logger.warning(f"Generic dash request failed: {e}")

            # Candidate 4: Graceful public HTML JSON-LD fallback (if Voyager fails or no cookies provided)
            logger.info(f"Attempting public fallback extraction for {public_id}")
            public_url = f"https://www.linkedin.com/in/{public_id}/"
            public_headers = {
                "user-agent": self.user_agent,
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "accept-language": "en-US,en;q=0.9",
            }
            try:
                resp = await client.get(public_url, headers=public_headers)
                if resp.status_code == 200:
                    fallback_data = self._extract_public_json_ld(resp.text, public_id)
                    if fallback_data:
                        return fallback_data

                if resp.status_code == 404:
                    raise LinkedInAPIError(
                        message=f"LinkedIn profile '{public_id}' not found.",
                        status_code=404,
                    )
            except httpx.RequestError as e:
                logger.error(f"Public fallback request failed: {e}")

            raise LinkedInAPIError(
                message=f"Could not retrieve LinkedIn profile data for '{public_id}'.",
                status_code=502,
                detail="All LinkedIn endpoints failed or returned empty data.",
            )

    def _extract_public_json_ld(self, html_text: str, public_id: str) -> Optional[Dict[str, Any]]:
        """Extract schema.org JSON-LD or embedded JSON metadata from public LinkedIn HTML."""
        # Find JSON-LD script tags
        matches = re.findall(r'<script type="application/ld\+json">([^<]+)</script>', html_text)
        for m in matches:
            try:
                data = json.loads(m.strip())
                if isinstance(data, dict) and data.get("@type") == "Person":
                    # Convert Person schema into normalized structure parseable by our parser
                    first = data.get("givenName")
                    last = data.get("familyName")
                    full = data.get("name")
                    headline = data.get("jobTitle")
                    works_for = data.get("worksFor", [])
                    alumni_of = data.get("alumniOf", [])
                    image = data.get("image", {}).get("contentUrl") if isinstance(data.get("image"), dict) else data.get("image")
                    description = data.get("description")
                    address = data.get("address", {})
                    location = address.get("addressLocality") if isinstance(address, dict) else None

                    # Build compatible synthetic dict
                    experiences = []
                    if isinstance(works_for, list):
                        for wf in works_for:
                            if isinstance(wf, dict):
                                experiences.append({
                                    "title": headline,
                                    "companyName": wf.get("name"),
                                    "locationName": location,
                                })
                    elif isinstance(works_for, dict):
                        experiences.append({
                            "title": headline,
                            "companyName": works_for.get("name"),
                            "locationName": location,
                        })

                    educations = []
                    if isinstance(alumni_of, list):
                        for ao in alumni_of:
                            if isinstance(ao, dict):
                                educations.append({
                                    "schoolName": ao.get("name"),
                                })
                    elif isinstance(alumni_of, dict):
                        educations.append({
                            "schoolName": alumni_of.get("name"),
                        })

                    return {
                        "profile": {
                            "firstName": first,
                            "lastName": last,
                            "headline": headline,
                            "summary": description,
                            "locationName": location,
                            "picture": {"url": image} if image else None,
                            "miniProfile": {
                                "publicIdentifier": public_id,
                                "firstName": first,
                                "lastName": last,
                                "occupation": headline,
                                "picture": {"url": image} if image else None,
                            }
                        },
                        "positionView": {"elements": experiences},
                        "educationView": {"elements": educations},
                        "skillView": {"elements": []},
                        "certificationView": {"elements": []},
                        "languageView": {"elements": []},
                    }
            except (json.JSONDecodeError, Exception) as err:
                logger.debug(f"JSON-LD parse error: {err}")

        return None

    async def get_profile(self, public_id: str) -> ProfileResponse:
        """Fetch and parse a LinkedIn profile by its public identifier."""
        raw_data = await self.fetch_profile_raw(public_id)
        profile = parse_linkedin_profile_data(raw_data, public_id)
        return profile
