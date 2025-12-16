"""
URL validation utilities to prevent SSRF (Server-Side Request Forgery) attacks.

This module provides functions to validate URLs before making HTTP requests,
blocking access to internal networks, private IPs, and dangerous schemes.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse
from typing import Tuple

# Schemes that are never allowed
BLOCKED_SCHEMES = frozenset({"file", "ftp", "gopher", "data", "javascript", "vbscript"})

# Hostnames that are explicitly blocked
BLOCKED_HOSTS = frozenset({
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",  # GCP metadata
    "metadata.internal",
    "169.254.169.254",  # AWS/Azure/GCP metadata endpoint
})


def is_private_ip(ip_str: str) -> bool:
    """
    Check if an IP address is private, loopback, link-local, or otherwise internal.
    
    Args:
        ip_str: IP address as string (IPv4 or IPv6)
    
    Returns:
        True if the IP is private/internal, False if it's public
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        # Invalid IP address format - treat as unsafe
        return True


def resolve_hostname(hostname: str) -> str | None:
    """
    Resolve a hostname to its IP address.
    
    Args:
        hostname: The hostname to resolve
    
    Returns:
        The resolved IP address, or None if resolution fails
    """
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return None


def validate_url(url: str) -> Tuple[bool, str]:
    """
    Validate that a URL is safe to fetch (prevents SSRF attacks).
    
    Checks:
    - Scheme must be http or https
    - Hostname must not be a known internal host
    - Resolved IP must not be private/internal
    
    Args:
        url: The URL to validate
    
    Returns:
        Tuple of (is_valid, error_message)
        If valid, error_message is empty string
    """
    if not url:
        return False, "URL is empty"
    
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"
    
    # Check scheme
    scheme = (parsed.scheme or "").lower()
    if scheme in BLOCKED_SCHEMES:
        return False, f"Blocked scheme: {scheme}"
    
    if scheme not in {"http", "https"}:
        return False, f"Only HTTP(S) allowed, got: {scheme}"
    
    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        return False, "No hostname in URL"
    
    hostname_lower = hostname.lower()
    
    # Check against blocked hosts
    if hostname_lower in BLOCKED_HOSTS:
        return False, f"Blocked host: {hostname}"
    
    # Check for IP address directly in URL
    try:
        ip = ipaddress.ip_address(hostname)
        if is_private_ip(str(ip)):
            return False, f"Private IP not allowed: {hostname}"
        # It's a valid public IP
        return True, ""
    except ValueError:
        # Not an IP address, it's a hostname - need to resolve it
        pass
    
    # Resolve hostname and check the resulting IP
    resolved_ip = resolve_hostname(hostname)
    if resolved_ip is None:
        return False, f"Could not resolve hostname: {hostname}"
    
    if is_private_ip(resolved_ip):
        return False, f"Hostname resolves to private IP: {hostname} -> {resolved_ip}"
    
    return True, ""


def is_url_safe(url: str) -> bool:
    """
    Simple boolean check if URL is safe to fetch.
    
    Args:
        url: The URL to validate
    
    Returns:
        True if safe, False otherwise
    """
    is_valid, _ = validate_url(url)
    return is_valid

