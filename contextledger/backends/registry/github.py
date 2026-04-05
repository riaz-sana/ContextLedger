"""GitHub remote RegistryBackend."""

import json
import os
from datetime import datetime, timezone
from typing import Any, List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class GitHubRegistryBackend:
    """RegistryBackend backed by a GitHub repository.

    Stores skill profiles as JSON files in the repository using the GitHub
    Contents API. Requires a GitHub personal access token with repo scope.

    Uses GITHUB_TOKEN and CONTEXTLEDGER_GITHUB_REPO environment variables.
    """

    API_BASE = "https://api.github.com"

    def __init__(
        self,
        repo: str = None,
        token: str = None,
        branch: str = "main",
        profiles_dir: str = "profiles",
    ):
        self._repo = repo or os.environ.get("CONTEXTLEDGER_GITHUB_REPO")
        self._token = token or os.environ.get("GITHUB_TOKEN")
        if not self._token:
            raise ValueError("GITHUB_TOKEN not set")
        if not self._repo:
            raise ValueError(
                "GitHub repo not set. Provide repo param or set CONTEXTLEDGER_GITHUB_REPO"
            )
        self._branch = branch
        self._profiles_dir = profiles_dir

    def _request(self, method: str, path: str, body: dict = None) -> Any:
        """Make an authenticated request to the GitHub API."""
        url = f"{self.API_BASE}/repos/{self._repo}/{path}"
        data = json.dumps(body).encode() if body else None
        req = Request(url, data=data, method=method)
        req.add_header("Authorization", f"token {self._token}")
        req.add_header("Accept", "application/vnd.github.v3+json")
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            if e.code == 404:
                return None
            raise

    def _profile_path(self, name: str, version: str = None) -> str:
        """Build the file path for a profile in the repo."""
        if version:
            return f"{self._profiles_dir}/{name}/{version}.json"
        return f"{self._profiles_dir}/{name}/latest.json"

    def list_profiles(self, filter: Optional[dict] = None) -> List[Any]:
        """List all profiles in the remote registry."""
        result = self._request("GET", f"contents/{self._profiles_dir}?ref={self._branch}")
        if result is None:
            return []
        entries = []
        for item in result:
            if item.get("type") == "dir":
                entry = {"name": item["name"]}
                if filter:
                    if all(entry.get(k) == v for k, v in filter.items()):
                        entries.append(entry)
                else:
                    entries.append(entry)
        return entries

    def get_profile(self, name: str, version: Optional[str] = None) -> Optional[dict]:
        """Get a profile by name and optional version."""
        path = self._profile_path(name, version)
        result = self._request("GET", f"contents/{path}?ref={self._branch}")
        if result is None:
            return None
        import base64

        content = base64.b64decode(result["content"]).decode()
        return json.loads(content)

    def save_profile(self, bundle: dict) -> str:
        """Save a skill profile bundle to the GitHub repository."""
        name = bundle["name"]
        version = bundle.get("version", "latest")
        path = self._profile_path(name, version)
        content_bytes = json.dumps(bundle, indent=2).encode()
        import base64

        encoded = base64.b64encode(content_bytes).decode()

        # Check if file exists to get its SHA (required for updates)
        existing = self._request("GET", f"contents/{path}?ref={self._branch}")
        body = {
            "message": f"Save profile {name} v{version}",
            "content": encoded,
            "branch": self._branch,
        }
        if existing and "sha" in existing:
            body["sha"] = existing["sha"]

        self._request("PUT", f"contents/{path}", body)

        # Also save as latest
        if version != "latest":
            latest_path = self._profile_path(name)
            existing_latest = self._request(
                "GET", f"contents/{latest_path}?ref={self._branch}"
            )
            latest_body = {
                "message": f"Update latest for {name}",
                "content": encoded,
                "branch": self._branch,
            }
            if existing_latest and "sha" in existing_latest:
                latest_body["sha"] = existing_latest["sha"]
            self._request("PUT", f"contents/{latest_path}", latest_body)

        return name

    def fork_profile(self, parent_name: str, new_name: str) -> dict:
        """Fork an existing profile under a new name."""
        parent = self.get_profile(parent_name)
        if parent is None:
            raise ValueError(f"Profile '{parent_name}' not found")
        now = datetime.now(timezone.utc).isoformat()
        forked = dict(parent)
        forked["name"] = new_name
        forked["parent"] = parent_name
        forked["version"] = "1.0.0"
        forked["created_at"] = now
        forked["updated_at"] = now
        self.save_profile(forked)
        return forked

    def list_versions(self, name: str) -> List[str]:
        """List all version strings for a given profile name."""
        result = self._request(
            "GET", f"contents/{self._profiles_dir}/{name}?ref={self._branch}"
        )
        if result is None:
            return []
        versions = []
        for item in result:
            if item.get("type") == "file" and item["name"].endswith(".json"):
                ver = item["name"].removesuffix(".json")
                if ver != "latest":
                    versions.append(ver)
        return versions

    def get_diff(self, name_a: str, name_b: str) -> Any:
        """Compute a semantic diff between two profiles."""
        profile_a = self.get_profile(name_a)
        profile_b = self.get_profile(name_b)
        if profile_a is None:
            raise ValueError(f"Profile '{name_a}' not found")
        if profile_b is None:
            raise ValueError(f"Profile '{name_b}' not found")

        keys_a = set(profile_a.keys())
        keys_b = set(profile_b.keys())
        all_keys = keys_a | keys_b

        changed = []
        added = []
        removed = []
        for key in all_keys:
            if key in keys_a and key not in keys_b:
                removed.append(key)
            elif key not in keys_a and key in keys_b:
                added.append(key)
            elif profile_a[key] != profile_b[key]:
                changed.append(key)

        return {
            "profile_a": name_a,
            "profile_b": name_b,
            "changed_sections": changed,
            "added_sections": added,
            "removed_sections": removed,
        }
