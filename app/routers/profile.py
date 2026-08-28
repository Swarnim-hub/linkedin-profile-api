"""Profile scraping endpoints."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.config import settings
from app.schemas.request import ProfileRequest
from app.schemas.response import ProfileResponse
from app.services.cache import get_cached_profile, set_cached_profile
from app.services.linkedin_client import LinkedInAPIError, LinkedInClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Profile"])


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> None:
    """Validate API key header if settings.API_KEY is configured."""
    if settings.API_KEY:
        if not x_api_key or x_api_key != settings.API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-API-Key header.",
            )


@router.post(
    "/profile",
    response_model=ProfileResponse,
    summary="Scrape LinkedIn Profile by URL",
    description=(
        "Accepts a LinkedIn profile URL (or public identifier) and returns structured JSON "
        "including name, headline, location, about, experience, education, skills, certifications, "
        "languages, and profile images."
    ),
    dependencies=[Depends(verify_api_key)],
    responses={
        200: {"description": "Structured LinkedIn profile data"},
        400: {"description": "Invalid LinkedIn URL or public identifier"},
        401: {"description": "Authentication failure (invalid API key or expired LinkedIn session)"},
        404: {"description": "LinkedIn profile not found"},
        429: {"description": "Rate limited by LinkedIn"},
        502: {"description": "Bad Gateway - LinkedIn Voyager API error"},
    },
)
async def get_profile_by_post(payload: ProfileRequest) -> ProfileResponse:
    """Fetch LinkedIn profile via POST body."""
    return await _process_profile_request(payload)


@router.get(
    "/profile",
    response_model=ProfileResponse,
    summary="Scrape LinkedIn Profile by URL (GET)",
    description="Convenience GET endpoint accepting a LinkedIn profile URL as a query parameter.",
    dependencies=[Depends(verify_api_key)],
)
async def get_profile_by_get(
    url: str = Query(
        ...,
        description="LinkedIn profile URL or public slug",
        examples=["https://www.linkedin.com/in/williamhgates/"],
    )
) -> ProfileResponse:
    """Fetch LinkedIn profile via GET query parameter."""
    payload = ProfileRequest(linkedin_url=url)
    return await _process_profile_request(payload)


async def _process_profile_request(payload: ProfileRequest) -> ProfileResponse:
    """Core logic to fetch, parse, and cache profile data."""
    public_id = payload.public_identifier
    if not public_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract a valid LinkedIn profile identifier from the provided URL.",
        )

    # 1. Check cache
    cached = get_cached_profile(public_id)
    if cached:
        return cached

    # 2. Fetch from LinkedIn
    client = LinkedInClient()
    try:
        profile = await client.get_profile(public_id)
    except LinkedInAPIError as e:
        logger.error(f"LinkedIn API error for {public_id}: {e.message} (status {e.status_code})")
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": e.message,
                "detail": e.detail,
                "public_identifier": public_id,
            },
        )
    except Exception as e:
        logger.exception(f"Unexpected error while scraping {public_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected internal error occurred: {str(e)}",
        )

    # 3. Store in cache
    set_cached_profile(public_id, profile)

    return profile
