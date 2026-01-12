#!/usr/bin/env python3
"""
X (Twitter) Monitor - Automatically fetch tweets from specific accounts and push notifications to macOS.

This script uses Nitter (privacy-friendly Twitter frontend) RSS feeds to fetch tweets
and sends macOS notifications for new tweets.

Usage:
    python3 x_monitor.py                    # Check all configured accounts for new tweets
    python3 x_monitor.py --add @username    # Add a new account to monitor
    python3 x_monitor.py --remove @username # Remove an account from monitoring
    python3 x_monitor.py --list             # List all monitored accounts
    python3 x_monitor.py --check @username  # Check a specific account only
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional
from html import unescape
import re

# Configuration
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = SCRIPT_DIR / "config.json"
STATE_FILE = SCRIPT_DIR / "seen_tweets.json"

# Nitter instances to try (in order of preference)
# These are public Nitter instances that provide RSS feeds
# Check https://status.d420.de/ for current instance status
NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://xcancel.com",
    "https://nitter.privacyredirect.com",
    "https://lightbrd.com",
]

# Default configuration
DEFAULT_CONFIG = {
    "accounts": [],
    "check_interval_minutes": 5,
    "max_notifications_per_check": 5,
    "nitter_instance": "https://nitter.poast.org",
    "notification_sound": "default"
}


def load_config() -> dict:
    """Load configuration from file or create default."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Merge with defaults for any missing keys
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Save configuration to file."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_state() -> dict:
    """Load seen tweets state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"seen_tweets": {}, "last_check": {}}


def save_state(state: dict) -> None:
    """Save seen tweets state to file."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def normalize_username(username: str) -> str:
    """Normalize username by removing @ prefix if present."""
    return username.lstrip("@").lower()


def get_tweet_id(link: str, title: str) -> str:
    """Generate a unique ID for a tweet based on its link and title."""
    content = f"{link}:{title}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def clean_html(text: str) -> str:
    """Remove HTML tags and decode HTML entities."""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    clean = unescape(clean)
    # Clean up whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def fetch_rss_feed(username: str, nitter_instance: str) -> Optional[str]:
    """Fetch RSS feed for a Twitter user from a Nitter instance."""
    # Nitter RSS feed URL format: https://instance/{username}/rss
    url = f"{nitter_instance}/{username}/rss"
    
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml, */*"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error fetching feed for @{username} from {nitter_instance}: {e.code} {e.reason}")
        return None
    except urllib.error.URLError as e:
        print(f"URL Error fetching feed for @{username} from {nitter_instance}: {e.reason}")
        return None
    except Exception as e:
        print(f"Error fetching feed for @{username} from {nitter_instance}: {e}")
        return None


def parse_rss_feed(xml_content: str) -> list:
    """Parse RSS feed XML and return list of tweets."""
    tweets = []
    
    try:
        root = ET.fromstring(xml_content)
        
        # Handle different RSS formats
        channel = root.find("channel")
        if channel is None:
            # Try Atom format
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)
            for entry in entries:
                title = entry.find("atom:title", ns)
                link = entry.find("atom:link", ns)
                published = entry.find("atom:published", ns)
                content = entry.find("atom:content", ns)
                
                tweet = {
                    "title": clean_html(title.text) if title is not None and title.text else "",
                    "link": link.get("href") if link is not None else "",
                    "published": published.text if published is not None and published.text else "",
                    "content": clean_html(content.text) if content is not None and content.text else ""
                }
                tweet["id"] = get_tweet_id(tweet["link"], tweet["title"])
                tweets.append(tweet)
        else:
            # Standard RSS format
            items = channel.findall("item")
            for item in items:
                title = item.find("title")
                link = item.find("link")
                pub_date = item.find("pubDate")
                description = item.find("description")
                
                tweet = {
                    "title": clean_html(title.text) if title is not None and title.text else "",
                    "link": link.text if link is not None and link.text else "",
                    "published": pub_date.text if pub_date is not None and pub_date.text else "",
                    "content": clean_html(description.text) if description is not None and description.text else ""
                }
                tweet["id"] = get_tweet_id(tweet["link"], tweet["title"])
                tweets.append(tweet)
                
    except ET.ParseError as e:
        print(f"Error parsing RSS feed: {e}")
        return []
    
    return tweets


def send_notification(title: str, message: str, url: str = "", sound: str = "default") -> bool:
    """Send a macOS notification using osascript."""
    # Escape special characters for AppleScript
    title = title.replace('"', '\\"').replace("'", "\\'")
    message = message.replace('"', '\\"').replace("'", "\\'")
    
    # Truncate message if too long
    if len(message) > 200:
        message = message[:197] + "..."
    
    # Build AppleScript command
    script = f'display notification "{message}" with title "{title}"'
    if sound and sound != "none":
        script += f' sound name "{sound}"'
    
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            timeout=10
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error sending notification: {e}")
        return False
    except FileNotFoundError:
        # osascript not available (not on macOS)
        print(f"[Notification] {title}: {message}")
        return True
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False


def check_account(username: str, config: dict, state: dict) -> list:
    """Check a single account for new tweets and return new tweets."""
    username = normalize_username(username)
    new_tweets = []
    
    # Try each Nitter instance until one works
    nitter_instance = config.get("nitter_instance", NITTER_INSTANCES[0])
    instances_to_try = [nitter_instance] + [i for i in NITTER_INSTANCES if i != nitter_instance]
    
    xml_content = None
    for instance in instances_to_try:
        xml_content = fetch_rss_feed(username, instance)
        if xml_content:
            break
    
    if not xml_content:
        print(f"Failed to fetch feed for @{username} from all Nitter instances")
        return []
    
    tweets = parse_rss_feed(xml_content)
    
    if not tweets:
        print(f"No tweets found for @{username}")
        return []
    
    # Get seen tweets for this user
    seen_ids = set(state.get("seen_tweets", {}).get(username, []))
    
    # Find new tweets
    for tweet in tweets:
        if tweet["id"] not in seen_ids:
            new_tweets.append(tweet)
            seen_ids.add(tweet["id"])
    
    # Update state
    if "seen_tweets" not in state:
        state["seen_tweets"] = {}
    state["seen_tweets"][username] = list(seen_ids)[-100:]  # Keep last 100 tweet IDs
    
    if "last_check" not in state:
        state["last_check"] = {}
    state["last_check"][username] = datetime.now().isoformat()
    
    return new_tweets


def check_all_accounts(config: dict, state: dict) -> dict:
    """Check all configured accounts for new tweets."""
    results = {}
    accounts = config.get("accounts", [])
    
    if not accounts:
        print("No accounts configured. Use --add @username to add accounts.")
        return results
    
    for username in accounts:
        username = normalize_username(username)
        print(f"Checking @{username}...")
        new_tweets = check_account(username, config, state)
        results[username] = new_tweets
        
        # Send notifications for new tweets
        max_notifications = config.get("max_notifications_per_check", 5)
        sound = config.get("notification_sound", "default")
        
        for i, tweet in enumerate(new_tweets[:max_notifications]):
            title = f"@{username} posted"
            message = tweet.get("title") or tweet.get("content", "New tweet")
            send_notification(title, message, tweet.get("link", ""), sound)
            time.sleep(0.5)  # Small delay between notifications
        
        if len(new_tweets) > max_notifications:
            remaining = len(new_tweets) - max_notifications
            send_notification(
                f"@{username}",
                f"And {remaining} more new tweets...",
                "",
                sound
            )
    
    return results


def add_account(username: str, config: dict) -> bool:
    """Add an account to the monitoring list."""
    username = normalize_username(username)
    
    if username in [normalize_username(a) for a in config.get("accounts", [])]:
        print(f"Account @{username} is already being monitored.")
        return False
    
    if "accounts" not in config:
        config["accounts"] = []
    
    config["accounts"].append(username)
    save_config(config)
    print(f"Added @{username} to monitoring list.")
    return True


def remove_account(username: str, config: dict) -> bool:
    """Remove an account from the monitoring list."""
    username = normalize_username(username)
    
    accounts = config.get("accounts", [])
    normalized_accounts = [normalize_username(a) for a in accounts]
    
    if username not in normalized_accounts:
        print(f"Account @{username} is not in the monitoring list.")
        return False
    
    # Find and remove the account
    for i, acc in enumerate(accounts):
        if normalize_username(acc) == username:
            accounts.pop(i)
            break
    
    config["accounts"] = accounts
    save_config(config)
    print(f"Removed @{username} from monitoring list.")
    return True


def list_accounts(config: dict) -> None:
    """List all monitored accounts."""
    accounts = config.get("accounts", [])
    
    if not accounts:
        print("No accounts are being monitored.")
        print("Use --add @username to add accounts.")
        return
    
    print("Monitored accounts:")
    for username in accounts:
        print(f"  @{username}")
    
    print(f"\nTotal: {len(accounts)} account(s)")
    print(f"Check interval: {config.get('check_interval_minutes', 5)} minutes")
    print(f"Nitter instance: {config.get('nitter_instance', NITTER_INSTANCES[0])}")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor X (Twitter) accounts and send notifications for new tweets."
    )
    parser.add_argument(
        "--add",
        metavar="USERNAME",
        help="Add an account to monitor (e.g., --add @elonmusk)"
    )
    parser.add_argument(
        "--remove",
        metavar="USERNAME",
        help="Remove an account from monitoring"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all monitored accounts"
    )
    parser.add_argument(
        "--check",
        metavar="USERNAME",
        help="Check a specific account only"
    )
    parser.add_argument(
        "--set-interval",
        type=int,
        metavar="MINUTES",
        help="Set the check interval in minutes"
    )
    parser.add_argument(
        "--set-nitter",
        metavar="URL",
        help="Set the Nitter instance URL (e.g., https://nitter.poast.org)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output (only show errors)"
    )
    
    args = parser.parse_args()
    
    # Load configuration and state
    config = load_config()
    state = load_state()
    
    # Handle commands
    if args.add:
        add_account(args.add, config)
        return
    
    if args.remove:
        remove_account(args.remove, config)
        return
    
    if args.list:
        list_accounts(config)
        return
    
    if args.set_interval:
        config["check_interval_minutes"] = args.set_interval
        save_config(config)
        print(f"Check interval set to {args.set_interval} minutes.")
        return
    
    if args.set_nitter:
        config["nitter_instance"] = args.set_nitter
        save_config(config)
        print(f"Nitter instance set to {args.set_nitter}")
        return
    
    if args.check:
        username = normalize_username(args.check)
        print(f"Checking @{username}...")
        new_tweets = check_account(username, config, state)
        save_state(state)
        
        if new_tweets:
            print(f"Found {len(new_tweets)} new tweet(s):")
            for tweet in new_tweets:
                print(f"  - {tweet.get('title', 'No title')[:80]}")
                if tweet.get("link"):
                    print(f"    {tweet['link']}")
        else:
            print("No new tweets.")
        return
    
    # Default: check all accounts
    if not args.quiet:
        print(f"X Monitor - Checking {len(config.get('accounts', []))} account(s)...")
    
    results = check_all_accounts(config, state)
    save_state(state)
    
    # Summary
    total_new = sum(len(tweets) for tweets in results.values())
    if not args.quiet:
        if total_new > 0:
            print(f"\nFound {total_new} new tweet(s) total.")
        else:
            print("\nNo new tweets found.")


if __name__ == "__main__":
    main()
