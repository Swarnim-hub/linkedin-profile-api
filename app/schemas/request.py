"""Request schemas and validation for LinkedIn Profile API."""

import re
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator


class ProfileRequest(BaseModel):
    """Input payload for profile scraping request."""

    linkedin_url: str = Field(
        ...,
        description="LinkedIn profile URL (e.g., https://www.linkedin.com/in/williamhgates/) or public identifier",
        examples=["https://www.linkedin.com/in/williamhgates/"],
    )

    @property
    def public_identifier(self) -> str:
        """Extract and normalize the public identifier (slug) from the LinkedIn URL or input."""
        raw = self.linkedin_url.strip()

        # Handle full URL or path
        if "linkedin.com" in raw or raw.startswith("http://") or raw.startswith("https://"):
            # Ensure scheme exists for urllib
            if not raw.startswith("http://") and not raw.startswith("https://"):
                raw = "https://" + raw

            parsed = urlparse(raw)
            path_parts = [p for p in parsed.path.strip("/").split("/") if p]

            # Standard format: /in/{identifier}
            if "in" in path_parts:
                in_idx = path_parts.index("in")
                if in_idx + 1 < len(path_parts):
                    return path_parts[in_idx + 1]
            elif path_parts:
                return path_parts[-1]

        # Handle raw identifier or relative path like /in/username or username
        cleaned = raw.strip("/").split("?")[0].split("#")[0]
        if cleaned.startswith("in/"):
            cleaned = cleaned[3:]

        # Validate slug characters (alphanumeric, dashes, underscores)
        slug_match = re.search(r"^[a-zA-Z0-9_\-]+$", cleaned)
        if slug_match:
            return cleaned

        return cleaned

    @field_validator("linkedin_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("LinkedIn URL or profile identifier cannot be empty.")
        return v
