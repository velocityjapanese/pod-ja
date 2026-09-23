# Velocity Japanese Podcast

Daily bilingual Japanese/English podcast video at A2 level with romaji transliteration, generated automatically and uploaded to YouTube.

## Features
- 15-minute conversation between Japanese hosts (Hana & Kenji)
- Japanese text with romaji (English transliteration) + English translation on every frame
- Short 2-line intro, then straight to the topic
- 150 dialogue turns with natural TTS pacing
- Auto-generated YouTube title, description, tags
- Thumbnail from the first video frame (no AI image generation)
- Clean output - intermediate audio auto-cleaned after video creation

## How it works
GitHub Actions runs daily:
1. `podcast_generator.py` - generates script (via Pollinations `openai`) with japanese + romaji + english, TTS audio (edge-tts), and assembles the video with ffmpeg
2. `upload_to_youtube.py` - uploads the video + thumbnail to the Velocity Japanese Podcast YouTube channel

## Secrets required
- `POLLINATIONS_API_KEY` - for script generation
- `AI_MODEL` - model name (default: `openai`)
- `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` - YouTube channel OAuth credentials

## Manual run
```bash
pip install -r requirements.txt
python podcast_generator.py
python upload_to_youtube.py
```
