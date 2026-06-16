from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FrequentSite:
    id: str
    domain: str
    name: str
    base_url: str
    category: str
    child_skill: str
    policy: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class FrequentSiteMatch:
    site: FrequentSite
    reason: str


_SITE_ROWS: tuple[tuple[str, str, str, str, str, str, str, tuple[str, ...]], ...] = (
    ('google_search', 'google.com', 'Google', 'https://www.google.com', 'research', 'google_search', 'safe search and page inspection only', ('google search',)),
    ('google_images', 'images.google.com', 'Google Images', 'https://www.google.com/imghp', 'research', 'google_images', 'visual reference search only', ('google images', 'image search', 'images')),
    ('youtube', 'youtube.com', 'YouTube', 'https://www.youtube.com', 'research', 'youtube_research', 'open, search, summarize visible public content', ('youtube',)),
    ('reddit', 'reddit.com', 'Reddit', 'https://www.reddit.com', 'research', 'reddit_research', 'open and summarize public threads; no posting', ('reddit',)),
    ('kaggle', 'kaggle.com', 'Kaggle', 'https://www.kaggle.com', 'research', 'research_site_open', 'open and inspect datasets/notebooks; no uploads', ('kaggle',)),
    ('civitai', 'civitai.com', 'Civitai', 'https://civitai.com', 'research', 'research_site_open', 'open and inspect model pages; no downloads unless requested', ('civitai',)),
    ('airbnb', 'airbnb.com', 'Airbnb', 'https://www.airbnb.com', 'travel', 'airbnb_stay_search', 'search and compare stays; stop before reserve, login, payment, passport, card, or final submit', ('airbnb',)),
    ('booking_com', 'booking.com', 'Booking.com', 'https://www.booking.com', 'travel', 'booking_com_hotel_search', 'search and compare hotels; stop before booking, login, payment, card, or final submit', ('booking.com', 'booking com', 'booking')),
    ('agoda', 'agoda.com', 'Agoda', 'https://www.agoda.com', 'travel', 'travel_site_open', 'open and compare visible travel options; stop before booking/payment', ('agoda',)),
    ('trip_com', 'trip.com', 'Trip.com', 'https://www.trip.com', 'travel', 'travel_site_open', 'open and compare visible travel options; stop before booking/payment', ('trip.com', 'trip com')),
    ('airasia', 'airasia.com', 'AirAsia', 'https://www.airasia.com', 'travel', 'travel_site_open', 'open and compare visible flight options; stop before booking/payment/passenger details', ('airasia', 'air asia')),
    ('wanderlog', 'wanderlog.com', 'Wanderlog', 'https://wanderlog.com', 'travel', 'travel_site_open', 'open and inspect itinerary context; no account edits unless requested', ('wanderlog',)),
    ('skyscanner', 'skyscanner.com.my', 'Skyscanner', 'https://www.skyscanner.com.my', 'travel', 'travel_site_open', 'open and compare visible flight options; stop before booking/payment', ('skyscanner',)),
    ('klook', 'klook.com', 'Klook', 'https://www.klook.com', 'travel', 'travel_site_open', 'open and compare activities; stop before checkout/payment', ('klook',)),
    ('star_dream', 'stardreamcruises.com', 'StarDream Cruises', 'https://www.stardreamcruises.com', 'travel', 'travel_site_open', 'open and compare cruise information; stop before booking/payment', ('stardream', 'star dream', 'star dream cruises')),
    ('github', 'github.com', 'GitHub', 'https://github.com', 'ai_dev', 'ai_dashboard_open', 'open and inspect repositories/issues; no pushes, secrets, settings changes, or destructive actions', ('github', 'git hub')),
    ('gcp_console', 'console.cloud.google.com', 'Google Cloud Console', 'https://console.cloud.google.com', 'ai_dev', 'google_cloud_console', 'open and inspect dashboard state; no billing, IAM, deploys, deletes, or credential changes without approval', ('google cloud console', 'gcp console', 'cloud console')),
    ('ai_studio', 'aistudio.google.com', 'Google AI Studio', 'https://aistudio.google.com', 'ai_dev', 'ai_dashboard_open', 'open and inspect prompts/models; no key or account changes', ('ai studio', 'google ai studio')),
    ('xai_console', 'console.x.ai', 'xAI Console', 'https://console.x.ai', 'ai_dev', 'ai_dashboard_open', 'open and inspect console/docs; no API key exposure or account changes', ('xai console', 'x.ai console', 'x ai console')),
    ('openai_platform', 'platform.openai.com', 'OpenAI Platform', 'https://platform.openai.com', 'ai_dev', 'ai_dashboard_open', 'open and inspect platform pages; no API key exposure or billing changes', ('openai platform', 'open ai platform')),
    ('claude_platform', 'platform.claude.com', 'Claude Platform', 'https://platform.claude.com', 'ai_dev', 'ai_dashboard_open', 'open and inspect platform pages; no key or billing changes', ('claude platform', 'anthropic console')),
    ('runpod_console', 'console.runpod.io', 'Runpod Console', 'https://console.runpod.io', 'ai_dev', 'ai_dashboard_open', 'open and inspect pods; no start/stop/delete or billing changes without approval', ('runpod', 'runpod console')),
    ('cloudflare_dashboard', 'dash.cloudflare.com', 'Cloudflare Dashboard', 'https://dash.cloudflare.com', 'ai_dev', 'ai_dashboard_open', 'open and inspect dashboard state; no DNS, deployment, access, or billing changes without approval', ('cloudflare', 'cloudflare dashboard')),
    ('local_labsoft', 'labsoft dashboards', 'Labsoft Dashboards', 'https://kampung.labsoft.uk', 'local_dashboard', 'local_dashboard_open', 'open and inspect configured dashboards; no destructive admin actions', ('kampung labsoft', 'labsoft', 'netlab', 'hruniverse')),
    ('localhost', 'localhost', 'Localhost', 'http://localhost', 'local_dashboard', 'local_dashboard_open', 'open and inspect local development pages; no destructive actions', ('localhost', '127.0.0.1')),
    ('gmail', 'mail.google.com', 'Gmail', 'https://mail.google.com', 'communication_sensitive', 'communication_site_open', 'open and inspect visible mail only when requested; no sending, deleting, or exposing private content without explicit instruction', ('gmail', 'google mail', 'mail.google.com')),
    ('telegram_web', 'web.telegram.org', 'Telegram Web', 'https://web.telegram.org', 'communication_sensitive', 'communication_site_open', "open only when requested; Maya's Telegram chat remains the preferred Telegram channel", ('telegram web', 'web telegram')),
    ('linkedin', 'linkedin.com', 'LinkedIn', 'https://www.linkedin.com', 'communication_sensitive', 'communication_site_open', 'open and inspect visible pages; no posting, messaging, or profile edits without explicit confirmation', ('linkedin', 'linked in')),
    ('maybank', 'maybank2u.com.my', 'Maybank2u', 'https://www.maybank2u.com.my', 'sensitive_finance', 'sensitive_site_open', 'open only; never read, fill, reveal, submit, or store bank credentials, OTPs, account numbers, cards, payment forms, or private financial data', ('maybank', 'maybank2u', 'maybank 2u')),
)


FREQUENT_SITES: tuple[FrequentSite, ...] = tuple(FrequentSite(*row) for row in _SITE_ROWS)
