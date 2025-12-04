"""
Furgonetka API Client with OAuth 2.0 authentication.

This module handles all communication with the Furgonetka.pl shipping API,
including OAuth token management, shipment creation, and label retrieval.

Documentation: https://furgonetka.pl/api
"""

from __future__ import annotations

import base64
import time
from typing import Dict, Any, Optional
import httpx

from .settings import settings
from .db import SessionLocal, FurgonetkaToken


class FurgonetkaClient:
    """
    Client for Furgonetka.pl shipping API.
    
    Handles OAuth 2.0 authentication with automatic token refresh.
    All tokens are persisted in the database for durability across restarts.
    """
    
    def __init__(self):
        self.base_url = settings.furgonetka_base_url.rstrip("/")
        self.client_id = settings.furgonetka_client_id
        self.client_secret = settings.furgonetka_client_secret
        self.redirect_uri = settings.furgonetka_redirect_uri
        
        # Token state (loaded from database)
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.expires_at: float = 0.0
        
        # Load existing tokens from database
        self._load_tokens()
    
    def _load_tokens(self) -> None:
        """Load OAuth tokens from database."""
        db = SessionLocal()
        try:
            token_row = db.query(FurgonetkaToken).first()
            if token_row:
                self.access_token = token_row.access_token
                self.refresh_token = token_row.refresh_token
                self.expires_at = token_row.expires_at
        finally:
            db.close()
    
    def _save_tokens(self, access_token: str, refresh_token: str, expires_in: int) -> None:
        """
        Save OAuth tokens to database.
        
        Args:
            access_token: New access token from OAuth response
            refresh_token: New refresh token (or existing if not provided)
            expires_in: Token lifetime in seconds
        """
        db = SessionLocal()
        try:
            token_row = db.query(FurgonetkaToken).first()
            if not token_row:
                token_row = FurgonetkaToken()
                db.add(token_row)
            
            token_row.access_token = access_token
            token_row.refresh_token = refresh_token
            token_row.expires_at = time.time() + expires_in
            db.commit()
            
            # Update instance variables
            self.access_token = access_token
            self.refresh_token = refresh_token
            self.expires_at = token_row.expires_at
        finally:
            db.close()
    
    async def _ensure_token(self) -> None:
        """
        Ensure we have a valid access token.
        
        Automatically refreshes the token if it's expired or will expire within 60 seconds.
        Raises RuntimeError if no refresh token is available.
        """
        if not self.access_token or time.time() >= (self.expires_at - 60):
            await self._refresh_access_token()
    
    async def _refresh_access_token(self) -> None:
        """
        Refresh the OAuth access token using the refresh token.
        
        This is called automatically by _ensure_token when needed.
        Raises RuntimeError if refresh fails or no refresh token is available.
        """
        if not self.refresh_token:
            raise RuntimeError(
                "No refresh token available. Please re-authenticate via /furgonetka/oauth/authorize"
            )
        
        url = f"{self.base_url}/oauth/token"
        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
        
        # Save new tokens (refresh_token may or may not be rotated)
        self._save_tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", self.refresh_token),
            expires_in=token_data.get("expires_in", 2592000)  # Default 30 days
        )
    
    async def create_shipment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new shipment in Furgonetka.
        
        Args:
            payload: Shipment data following Furgonetka API schema
                    (see furgonetka_mapper.py for payload structure)
        
        Returns:
            API response containing package_id, tracking_number, etc.
        
        Raises:
            httpx.HTTPStatusError: If API returns an error
            RuntimeError: If authentication fails
        """
        await self._ensure_token()
        
        url = f"{self.base_url}/packages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            # Handle 401 (token expired) - retry once after refresh
            if response.status_code == 401:
                await self._refresh_access_token()
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = await client.post(url, json=payload, headers=headers)
            
            response.raise_for_status()
            return response.json()
    
    async def get_label(self, package_id: str, format: str = "pdf") -> bytes:
        """
        Download shipment label.
        
        Args:
            package_id: Package ID from create_shipment response
            format: Label format - "pdf" or "zpl" (default: "pdf")
        
        Returns:
            Raw label file bytes
        
        Raises:
            httpx.HTTPStatusError: If API returns an error (e.g., 404 if package not found)
        """
        await self._ensure_token()
        
        url = f"{self.base_url}/packages/{package_id}/label"
        params = {"format": format} if format != "pdf" else {}
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/pdf" if format == "pdf" else "text/plain"
        }
        
        async with httpx.AsyncClient(timeout=60) as client:  # Longer timeout for file download
            response = await client.get(url, params=params, headers=headers)
            
            # Handle 401 (token expired)
            if response.status_code == 401:
                await self._refresh_access_token()
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = await client.get(url, params=params, headers=headers)
            
            response.raise_for_status()
            return response.content
    
    async def validate_shipment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate shipment data without creating it.
        
        This is a pre-flight check that verifies addresses, service availability,
        and pricing without actually creating the shipment or charging your account.
        
        Args:
            payload: Same structure as create_shipment
        
        Returns:
            Validation result with potential errors and price estimate
        """
        await self._ensure_token()
        
        url = f"{self.base_url}/packages/validate"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            # Validation endpoint may return 422 with error details - don't raise
            if response.status_code in (200, 422):
                return response.json()
            
            # For other errors, raise
            response.raise_for_status()
            return response.json()
    
    async def get_shipment(self, package_id: str) -> Dict[str, Any]:
        """
        Get shipment details by package ID.
        
        Args:
            package_id: Package ID from create_shipment
        
        Returns:
            Full shipment data including status, tracking info, etc.
        """
        await self._ensure_token()
        
        url = f"{self.base_url}/packages/{package_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    
    async def list_shipments(
        self, 
        page: int = 1, 
        limit: int = 50,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        List shipments with pagination.
        
        Args:
            page: Page number (1-indexed)
            limit: Items per page (max 50)
            filters: Optional filters (e.g., {"status": "created", "date_from": "2025-01-01"})
        
        Returns:
            Paginated list of shipments
        """
        await self._ensure_token()
        
        url = f"{self.base_url}/packages"
        params = {"page": page, "limit": min(limit, 50)}
        if filters:
            params.update(filters)
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
    
    def get_authorization_url(self) -> str:
        """
        Generate OAuth authorization URL for user to visit.
        
        This is the first step in the OAuth flow. User must visit this URL,
        log in to Furgonetka, and authorize the application. They will then be
        redirected back to the redirect_uri with a code parameter.
        
        Returns:
            Full authorization URL
        """
        return (
            f"{self.base_url}/oauth/authorize"
            f"?response_type=code"
            f"&client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&scope=api"
        )
    
    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access tokens.
        
        This is the second step in the OAuth flow, called from the callback endpoint.
        
        Args:
            code: Authorization code from redirect callback
        
        Returns:
            Token response containing access_token, refresh_token, expires_in
        
        Raises:
            httpx.HTTPStatusError: If exchange fails
        """
        url = f"{self.base_url}/oauth/token"
        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
        
        # Save tokens to database
        self._save_tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data.get("expires_in", 2592000)
        )
        
        return token_data

    async def find_package_by_reference(
        self, 
        user_reference: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find existing package in Furgonetka by user reference number.
        
        Args:
            user_reference: Order reference (e.g., "#12345" or "Zamówienie #12345")
        
        Returns:
            Package dict if found, None otherwise
        """
        await self._ensure_token()
        
        url = f"{self.base_url}/packages"
        
        # Try multiple query strategies (API might use exact match or partial)
        # Usually 'user_reference_number' is the most reliable if set correctly
        search_variants = [
            {"user_reference_number": user_reference},
            {"ref": user_reference}
        ]
        
        for params in search_variants:
            params["limit"] = 10  # Possible to have multiple, check logic below
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json"
            }
            
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(url, params=params, headers=headers)
                    
                    if response.status_code == 200:
                        data = response.json()
                        # Furgonetka API list response structure:
                        # { "list": [...] } or { "items": [...] } depending on version
                        packages = []
                        if isinstance(data, dict):
                            packages = data.get("list") or data.get("items") or []
                        elif isinstance(data, list):
                            packages = data
                        
                        # Filter for best match
                        for pkg in packages:
                            pkg_ref = str(pkg.get("user_reference_number") or pkg.get("ref") or "")
                            
                            # Check if the reference matches (allowing for partial like "Order #123")
                            if user_reference in pkg_ref or pkg_ref in user_reference:
                                return pkg
            except Exception as e:
                print(f"[Furgonetka] Search failed for {params}: {e}")
                continue
        
        return None

