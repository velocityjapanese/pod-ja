"""
Set the Velocity Japanese Podcast YouTube channel description (About section).
"""
import os, json
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

CHANNEL_DESCRIPTION = "🎙️ Velocity Japanese Podcast - 日本語を自然に学ぼう\n\n毎日配信のバイリンガル日本語ポッドキャスト。Hana と Kenji の A2 レベルの会話で、日本語を自然に学べます。全ての日本語にローマ字（romaji）と英語訳が付いています。\n\nDaily bilingual Japanese podcast with romaji transliteration. Simple A2-level conversations between Hana and Kenji. Every Japanese line includes romaji and English translation.\n\n📚 WHAT YOU'LL GET:\n• Daily bilingual conversations (Japanese + English + Romaji)\n• Natural pronunciation from native speakers\n• Practical vocabulary for everyday life\n• Short, easy-to-follow episodes\n\n🇯🇵 How to use this podcast:\n1. Listen to the Japanese, try to understand\n2. Read the romaji transliteration\n3. Check the English translation\n4. Repeat the phrases out loud\n\n🔔 Subscribe and turn on notifications so you never miss a lesson.\n\n📅 New episodes every day!\n\n#LearnJapanese #JapanesePodcast #Bilingual #LanguageLearning"


def _get_creds():
    cid = os.getenv("YT_CLIENT_ID")
    csecret = os.getenv("YT_CLIENT_SECRET")
    refresh = os.getenv("YT_REFRESH_TOKEN")
    if cid and csecret and refresh:
        return Credentials(None, refresh_token=refresh,
                           token_uri="https://oauth2.googleapis.com/token",
                           client_id=cid, client_secret=csecret)
    tok_file = Path(__file__).parent / "token.json"
    candidates = [
        tok_file,
        Path(r'C:\Users\kreg9\Downloads\kreggscode\open code\bots\youtube refresh tokens bot\token_Vheelocityin Japanese podcast.json'),
    ]
    for c in candidates:
        if c.exists():
            tok = json.load(open(c, encoding='utf-8'))
            return Credentials(None, refresh_token=tok['refresh_token'],
                               token_uri="https://oauth2.googleapis.com/token",
                               client_id=tok['client_id'], client_secret=tok['client_secret'])
    raise ValueError("No YouTube credentials found")


def main():
    creds = _get_creds()
    creds.refresh(Request())
    service = build("youtube", "v3", credentials=creds)
    channels = service.channels().list(part="brandingSettings", mine=True).execute()
    channel_id = channels["items"][0]["id"]
    branding = dict(channels["items"][0]["brandingSettings"])
    branding.setdefault("channel", {})
    branding["channel"]["description"] = CHANNEL_DESCRIPTION
    body = {"id": channel_id, "brandingSettings": branding}
    resp = service.channels().update(part="brandingSettings", body=body).execute()
    new_desc = resp["brandingSettings"]["channel"].get("description", "")
    print("Channel:", channel_id)
    print("Description set to", len(new_desc), "chars")


if __name__ == "__main__":
    main()
