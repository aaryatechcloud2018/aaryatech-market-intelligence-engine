"""
YouTube collector.

Two tiers:
1. If YOUTUBE_API_KEY is set, uses the official YouTube Data API v3
   (search.list + commentThreads.list) -- the reliable, sanctioned method.
2. Otherwise, falls back to `youtube_comment_downloader`, which scrapes the
   public comment feed straight from a video's page (no login/key needed)
   for the seed videos listed in config.YOUTUBE_SEED_VIDEO_URLS. This is
   the "closest practical alternative" the task description asked for --
   full search isn't possible without a key, so seed videos must be curated
   by hand instead.

Collects, per RAW_FIELDS: video title, video URL, comment text, username,
date, likes, and reply count where available.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

from src.audience_collection.collectors.base import empty_raw_row, make_comment_id, now_iso
from src.audience_collection.config import (
    BRAND,
    CAMPAIGN_OR_EVENT,
    DEFAULT_PRODUCT,
    YOUTUBE_API_KEY,
    YOUTUBE_SEED_VIDEO_URLS,
)

PLATFORM = "youtube"


def _video_id_from_url(url: str) -> str:
    match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
    if not match:
        raise ValueError(f"Could not parse a video ID from URL: {url}")
    return match.group(1)


def _row_from_comment(
    comment_id: str,
    text: str,
    author: str,
    published: str,
    likes: int,
    reply_count: int,
    video_title: str,
    video_url: str,
) -> dict:
    row = empty_raw_row()
    row.update(
        {
            "comment_id": make_comment_id(PLATFORM, comment_id),
            "platform": PLATFORM,
            "source_url": video_url,
            "thread_or_page_title": video_title,
            "public_username": author,
            "comment_text": text,
            "comment_date": published,
            "collected_at": now_iso(),
            "likes_or_upvotes": likes,
            "reply_count": reply_count,
            "parent_comment_id": "",
            "brand": BRAND,
            "product": DEFAULT_PRODUCT,
            "campaign_or_event": CAMPAIGN_OR_EVENT,
            "raw_status": "COLLECTED",
        }
    )
    return row


def _in_window(iso_date: str, window_start: date, window_end: date) -> bool:
    d = datetime.fromisoformat(iso_date.replace("Z", "+00:00")).date()
    return window_start <= d <= window_end


def _collect_via_official_api(window_start: date, window_end: date) -> list[dict]:
    from googleapiclient.discovery import build  # lazy import, only needed here

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    search_resp = (
        youtube.search()
        .list(q="wealthsimple", part="snippet", type="video", maxResults=15, order="relevance")
        .execute()
    )
    video_ids = [item["id"]["videoId"] for item in search_resp.get("items", [])]
    video_titles = {
        item["id"]["videoId"]: item["snippet"]["title"] for item in search_resp.get("items", [])
    }

    rows: list[dict] = []
    for video_id in video_ids:
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        page_token = None
        while True:
            resp = (
                youtube.commentThreads()
                .list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=100,
                    pageToken=page_token,
                    textFormat="plainText",
                )
                .execute()
            )
            for item in resp.get("items", []):
                top = item["snippet"]["topLevelComment"]["snippet"]
                if not _in_window(top["publishedAt"], window_start, window_end):
                    continue
                rows.append(
                    _row_from_comment(
                        comment_id=item["snippet"]["topLevelComment"]["id"],
                        text=top["textDisplay"],
                        author=top.get("authorDisplayName", "Anonymous"),
                        published=top["publishedAt"],
                        likes=top.get("likeCount", 0),
                        reply_count=item["snippet"].get("totalReplyCount", 0),
                        video_title=video_titles.get(video_id, ""),
                        video_url=video_url,
                    )
                )
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    return rows


def _collect_via_scraper(window_start: date, window_end: date) -> list[dict]:
    from youtube_comment_downloader import SORT_BY_RECENT, YoutubeCommentDownloader

    downloader = YoutubeCommentDownloader()
    rows: list[dict] = []

    for video_url in YOUTUBE_SEED_VIDEO_URLS:
        video_id = _video_id_from_url(video_url)
        comments = downloader.get_comments(video_id, sort_by=SORT_BY_RECENT)
        video_title = ""
        for comment in comments:
            if not video_title:
                video_title = comment.get("video_title", "") or f"YouTube video {video_id}"
            published_ts = comment.get("time_parsed")
            if published_ts is None:
                continue
            published_iso = datetime.fromtimestamp(published_ts, tz=timezone.utc).isoformat()
            if not _in_window(published_iso, window_start, window_end):
                continue
            rows.append(
                _row_from_comment(
                    comment_id=comment["cid"],
                    text=comment.get("text", ""),
                    author=comment.get("author", "Anonymous"),
                    published=published_iso,
                    likes=comment.get("votes", 0) or 0,
                    reply_count=comment.get("reply_count", 0) or 0,
                    video_title=video_title,
                    video_url=video_url,
                )
            )
    return rows


def collect(window_start: date, window_end: date) -> list[dict]:
    """Collect YouTube comments mentioning Wealthsimple within the date window.

    Uses the official Data API v3 if YOUTUBE_API_KEY is set; otherwise
    scrapes the seed videos in config.YOUTUBE_SEED_VIDEO_URLS.
    """
    if YOUTUBE_API_KEY:
        return _collect_via_official_api(window_start, window_end)
    return _collect_via_scraper(window_start, window_end)
