"""
Run once on your own computer to authorize the YouTube channel.
Requires a Google OAuth Desktop app client-secret JSON downloaded from Cloud Console.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secret.json",
    scopes=SCOPES,
)
credentials = flow.run_local_server(
    host="localhost",
    port=0,
    access_type="offline",
    prompt="consent",
)

if not credentials.refresh_token:
    raise SystemExit(
        "No refresh token was returned. Check OAuth consent settings and try again."
    )

print("\nCopy this refresh token directly into the GitHub secret YT_REFRESH_TOKEN.")
print("Do not post it in chat, commit it, or send it to anyone.\n")
print(credentials.refresh_token)
