# VCT Connect 1688 browser capture

This is a local, unpacked Chrome extension for a buyer who is already viewing a 1688 offer. Clicking **Capture this offer** reads a short allowlist of visible page text and sends it to the signed-in VCT Connect account. It does not run automatically or request persistent access to 1688.

## Development setup

1. Put the existing Clerk publishable key in `frontend/apps/web/.env.local` as `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (the web app already uses this file). Use the same Clerk development instance for web and extension.
2. From the repository root, run `npm install --prefix frontend --legacy-peer-deps`, then `npm run build --prefix frontend/apps/extension`.
3. Enable Clerk **Native API**. Register the extension's development origin by running `.\.venv\Scripts\python.exe scripts\configure_clerk_extension_origin.py` from the repository root. The script reads the ignored `.env.clerk`, preserves existing allowed origins, and registers `chrome-extension://klggcepemjjbphjclpiabgpfgdbgiljj`.
4. Add that exact origin to the backend's `CLERK_AUTHORIZED_PARTIES` alongside the web origin, then restart the backend. The repository's `.env.example` shows the format.
5. Open `chrome://extensions`, enable **Developer mode**, choose **Load unpacked**, and select `frontend/apps/extension/build`. Confirm Chrome shows extension ID `klggcepemjjbphjclpiabgpfgdbgiljj`.
6. Start the existing database, backend, and web app. The local extension build calls `http://127.0.0.1:3000`. A deployment build can set `VCT_WEB_ORIGIN` to its HTTPS origin before running the build command; the deployed backend must also allow the stable extension origin.

Open the extension and choose **Sign in on VCT Connect**. Complete sign-in in the web tab using the same Chrome profile, then return to a supported `https://detail.1688.com/offer/<id>.html` page and reopen the popup. Clerk Sync Host shares the web session with the extension; the extension no longer performs sign-in redirects inside the short-lived popup. Development builds sync from the exact web origin (default `http://127.0.0.1:3000`); production builds sync from the Clerk Frontend API host. Do not use `localhost` when this build is configured for `127.0.0.1`.

Click **Capture this offer**. After the capture is saved and its owner-scoped status loads, the extension automatically opens the web result in a new tab. **Open web result** remains available to reopen it. If result loading fails after submission, use **Reload last result**; the last analysis ID, source URL, and Clerk owner ID are stored locally so recovery is scoped to the signed-in account. If 1688 only shows a challenge or the chosen fields are absent, the result records a parse failure without supplier claims.

After rebuilding, reload the extension from `chrome://extensions` before testing. Clerk's SDK uses the `cookies` permission to sync the VCT Connect session from the configured host; no 1688 cookie is read. If the popup reports that sign-in is taking too long, open VCT Connect, confirm web sign-in completed, then close and reopen the popup.

Only source URL, offer ID, optional canonical URL, and selected visible supplier, title, and price text are transmitted. No 1688 cookies, passwords, storage, full HTML, scripts, request headers, or arbitrary page JSON are read or sent. The result is labeled `EXTENSION_DOM` and is not an official 1688 API response or risk score.

If Windows reserves API port 8000, start Uvicorn with `--port 8080` instead. In the web app's PowerShell terminal, set `$env:API_INTERNAL_ORIGIN='http://127.0.0.1:8080'` before `npm run dev --prefix frontend`. The extension still uses web port 3000. Check reserved ports with `netsh interface ipv4 show excludedportrange protocol=tcp`.

The manifest's public `key` fixes the unpacked extension ID. It is not a signing key or a credential. Keep any private signing key for future store distribution outside the repository.
