# streamergta6yuio[clips] — automated YouTube Shorts starter

This starter automates **one authorized clip per scheduled run** (8 attempts/day, every 3 hours).
It does not discover or scrape random streamer videos. It only accepts clips from an owner-operated
feed and checks each item against your manually maintained allowlist.

## Important: what must exist before it can run hands-off

You need all of these:
1. A YouTube channel that you are allowed to manage, with its owner/guardian handling account settings as required.
2. A Google Cloud project with YouTube Data API v3 enabled and OAuth credentials.
3. A long-lived OAuth refresh token stored as a GitHub Actions secret.
4. At least one streamer who has explicitly granted permission for reposting on YouTube, including edited Shorts.
5. That streamer (or an authorized clipping service) must provide a **stable JSON feed** containing direct downloadable MP4 URLs. A permission statement or a public clip page alone is not a downloadable media feed.

There is no universal, reliable public feed of GTA 6 clips whose owners have all approved reposting. Do not assume that a streamer's Twitch/YouTube clip setting means you may re-upload their clip to another channel. Keep written permission and follow any conditions they set.

## Architecture

Streamer-approved JSON feed → allowlist check → FFmpeg vertical conversion + original text overlay
→ YouTube Data API upload → saved de-duplication state.

The GitHub Actions schedule runs in GitHub's cloud. Your PC does not need to stay on.

## Free-tier notes

- GitHub-hosted standard runners are free for public repositories. Public repository code is visible to everyone; never commit credentials, tokens, private feed URLs, or private clip files.
- This workflow runs 8 times/day. It processes at most one clip per run, so the target is normally 8/day (within your requested 6–10 range), not a guarantee.
- If the workflow needs lengthy downloads or encoding, free-tier suitability depends on runtime and GitHub's current limits.
- YouTube API upload quota currently supports up to 100 `videos.insert` calls/day by default; this project uses at most 8/day.
- YouTube API uploads can be public, but channel/account settings and Google authorization still apply.
- Google OAuth consent screen left in **Testing** can cause refresh tokens to expire after 7 days. Configure the OAuth app appropriately and check Google's current verification/consent requirements.

## 1. Create the repository

Create a **public** GitHub repository named `gta6-clips-automation` and upload the contents of this folder.
Public repositories are used here to avoid consuming the private-repository Actions minute allowance. The workflow only runs on a schedule or manual dispatch, not on pull requests.

## 2. Add GitHub Actions secrets

Repository → Settings → Secrets and variables → Actions → New repository secret:

- `YT_CLIENT_ID` — OAuth client ID
- `YT_CLIENT_SECRET` — OAuth client secret
- `YT_REFRESH_TOKEN` — refresh token for the channel you control
- `CLIP_FEED_URL` — HTTPS URL to the streamer-approved JSON feed

Never put these values in `config.json`, source code, chat, or a commit.

## 3. Configure approved streamers

Edit `approved_streamers.json`. Add a streamer only after receiving explicit written permission.
The `permission_reference` should point to a public permission statement or a private record you keep;
do not put private contracts or personal details in this public repository. For a private permission record,
use a short non-sensitive reference such as `permission-record-01`.

## 4. Feed format

The HTTPS feed must return JSON in this shape:

```json
{
  "clips": [
    {
      "id": "unique-clip-id",
      "streamer": "ExampleStreamer",
      "video_url": "https://creator.example/clips/clip-001.mp4",
      "permission_reference": "permission-record-01",
      "title": "Unexpected GTA 6 moment",
      "commentary": "The unexpected twist makes this moment memorable.",
      "description": "Edited clip shared with the creator's permission.",
      "tags": ["GTA6", "gaming", "shorts"]
    }
  ]
}
```

The feed must be operated by the streamer or a service they authorize. `video_url` must be a direct HTTPS MP4 download URL.
The `commentary` field should be original context/commentary, not copied streamer dialogue or a claim that the streamer endorses your channel.
The script adds a small channel label and text overlay from the feed's title/commentary fields. It does **not** generate speech-to-text subtitles or automatically discover clips.

## 5. Google / YouTube setup

1. In Google Cloud Console, create a project and enable **YouTube Data API v3**.
2. Configure OAuth consent and create OAuth client credentials.
3. Authorize the YouTube channel using the `youtube.upload` scope and offline access.
4. Store the resulting refresh token in `YT_REFRESH_TOKEN`.
5. Make sure the OAuth consent setup is not left in a short-lived Testing configuration if you expect unattended operation.
6. Do not share credentials. Revoke the OAuth grant in your Google Account if you no longer want the automation to upload.

## 6. Start the workflow

GitHub → Actions → `Publish approved Shorts` → Run workflow.
After the first successful test, the schedule runs every 3 hours (UTC). That is 8 scheduled attempts/day.
A scheduled attempt may find no eligible new clip and then do nothing.

## Safety and quality controls

- Only allowlist entries are eligible.
- The clip's streamer and permission reference must match the allowlist.
- Duplicate clip IDs are skipped.
- One clip maximum per run.
- The workflow will not invent permissions or search for unauthorized downloads.
- Review the streamer agreement for attribution, editing, monetization, territory, and takedown requirements.
- Add meaningful original commentary/context. Simple reposting, even with captions or a watermark, may not qualify for YouTube monetization.
- Keep the channel's audience and video settings age-appropriate and follow YouTube's rules.

## Troubleshooting

- **No clip uploaded:** the feed may be empty, the streamer may not be allowlisted, the permission reference may not match, or the item may already be processed.
- **401 / invalid_grant:** re-authorize YouTube and replace the refresh token secret. Check OAuth consent publishing status.
- **403 quota / access:** check YouTube Data API enablement, quota, OAuth scope, and channel permissions.
- **FFmpeg error:** ensure the feed URL is a direct MP4 file and the clip is a supported format.
- **No uploads for several days:** GitHub scheduled workflows can be delayed or disabled by repository inactivity; check Actions and GitHub's current scheduling policy.

This is a starter project, not a promise of guaranteed free hosting, guaranteed clip supply, or guaranteed monetization.
