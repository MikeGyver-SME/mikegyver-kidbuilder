# Kid Builder - deployment steps (v1.0.1)

Same proven pipeline as YewBuilder / SSTV Studio / PodMix / Voyager
Light-Day. Do each step once, in order. Nothing here needs the Mac -
the build runs on GitHub Actions and lands in TestFlight.

## 0. What is in the zip (so nothing looks missing)

Extract `kidbuilder-v1.0.1.zip` to `E:\Downloads` (the default). You
get one folder, `kidbuilder-v1.0.1\kidbuilder\`, with everything in it:

- `KidBuilder/` - the iPhone app (SwiftUI, 5 tabs, camera block,
  "See my code" tab, Build & Deploy with on-phone FTP)
- `KidBuilder.xcodeproj/` - the Xcode project (v1.0.1 / build 2)
- `kidbuilder_gen.py` - THE GENERATOR: turns tap blocks into the 5
  Yew files (index.html, styles.css, Cargo.toml, Trunk.toml,
  src/main.rs). Run `python3 kidbuilder_gen.py` to regenerate.
- `kidbuilder-server.py` - THE BUILDER SERVER: YewBuilder's server
  plus `/generate-blocks` and `/build-blocks` for Kid Builder.
- `projects/` - THE FIVE STARTER WEB APPS, already generated, each a
  complete Yew app ready for `trunk build --release`:
  - `projects/my-rocket-launch/` - Rocket Launch
  - `projects/counting-stars-quiz/` - Counting Stars Quiz
  - `projects/piano-notes/` - Piano Notes
  - `projects/take-a-photo/` - Take a Photo (camera block)
  - `projects/photo-to-space-sound/` - Photo to Space Sound (SSTV:
    photo to Robot 36 WAV and back; ships `sstv-core.js` +
    `kid-sstv-bridge.js`)
- `scripts/push-kidbuilder.ps1` - push + tag script (starts TestFlight)
- `scripts/run-server.ps1` - one-click start for the builder server
- `.github/workflows/testflight.yml` - GitHub Actions -> TestFlight
- `README.md`, `SERVER-README.md`, this file

If you open only the `KidBuilder/` folder you will see just the app -
the generator and the starters live beside it, at the top of the
`kidbuilder` folder, not inside it.

## 1. Apple - App ID and App Store Connect record first

The workflow fails without these, even with everything else in place.

1. developer.apple.com -> Certificates, Identifiers & Profiles ->
   Identifiers -> App IDs -> App, Explicit bundle ID
   `studio.mikegyver.kidbuilder`, no capabilities, Register.
2. appstoreconnect.apple.com -> Apps -> New App -> iOS, name
   `Kid Builder`, SKU `kidbuilder`, bundle ID
   `studio.mikegyver.kidbuilder`. Full App Store listing details
   (screenshots, description, privacy, pricing) are NOT needed for
   TestFlight internal testing.

## 2. GitHub - repo and secrets

1. Create the repo `MikeGyver-SME/mikegyver-kidbuilder` on GitHub
   (empty, no README - the push script fills it).
2. Repo -> Settings -> Secrets and variables -> Actions -> New
   repository secret, four secrets (same ones the other apps use):
   - `ASC_KEY_ID` - App Store Connect API key ID
   - `ASC_ISSUER_ID` - Issuer ID (UUID from the API key page)
   - `ASC_KEY_P8` - Full contents of the downloaded
     `AuthKey_XXXX.p8` file (including BEGIN / END PRIVATE KEY lines)
   - `TEAM_ID` - Apple Developer Team ID (Membership details page)

## 3. Push + tag (PowerShell on Windows)

```powershell
# Extract kidbuilder-v1.0.1.zip first (E:\Downloads is the default).
# The zip has an inner kidbuilder\ folder, so step into it first:
Set-Location E:\Downloads\kidbuilder-v1.0.1\kidbuilder
powershell -ExecutionPolicy Bypass -File .\scripts\push-kidbuilder.ps1
# uses defaults, tags v1.0.1
```

The tag push starts the "Build and upload KidBuilder to TestFlight"
workflow automatically. Watch it at
`https://github.com/MikeGyver-SME/mikegyver-kidbuilder/actions`.

Per the iOS pre-flight checklist: the push script uses `git status`
(never a failing probe) and `git tag --list` to check for the tag, and
tags only after the push lands. If a run fails, check the workflow log
for the step name before changing code - a missing step means the push
did not trigger the pipeline you think it did.

## 4. TestFlight

1. When the workflow is green, App Store Connect -> TestFlight -> iOS -
   the build appears within minutes. If it sits at Missing Compliance,
   answer "None of the algorithms mentioned above" (the app implements
   no encryption of its own; it only uses standard HTTPS + Keychain).
2. Install from TestFlight on your iPhone, accept the invite if needed.

## 5. Builder server on the PC (swap from YewBuilder)

The Kid Builder server REPLACES the YewBuilder server on this PC: it
keeps `/health` and `/build`, so YewBuilder keeps working, and adds
`/generate-blocks` and `/build-blocks`. Do not run both at once -
both use port 8080.

1. Stop the old YewBuilder server first. If it runs as the scheduled
   task "YewBuilder server", stop that task (Task Scheduler -> find it
   -> End). If it runs in a PowerShell window, press Ctrl+C there.
2. In the extracted `kidbuilder` folder:
   ```powershell
   Set-Location E:\Downloads\kidbuilder-v1.0.1\kidbuilder
   powershell -ExecutionPolicy Bypass -File .\scripts\run-server.ps1
   ```
   It checks Python, cargo and trunk, then prints
   `KidBuilder server on http://0.0.0.0:8080`. Leave that window open
   while the kids build - the PC must be on with the server running.
   Windows Firewall will ask the first time: allow Python on private
   networks.
3. If you want it to start at sign-in like the YewBuilder server did,
   point a scheduled task at this folder's `scripts\run-server.ps1`
   instead of the old YewBuilder one (same settings as before: At
   Log On, highest privileges, restart on failure). Do not point two
   tasks at the same port.

## 6. First launch on the phone (the part only you can do)

1. In the app: Settings -> Builder server ->
   `http://<PC-LAN-IP>:8080` -> **Test builder connection** (should show
   the trunk version). Find the LAN IP with `ipconfig` on the PC
   (e.g. `http://192.168.1.10:8080`); away from home, use the PC's
   Tailscale IP (`http://100.x.x.x:8080`).
2. Settings -> FTP: host, username and port are pre-filled. The deploy
   folder is also editable right on the Build tab before each build -
   whatever is entered there is where that build goes (kid projects
   default to `/public_html/kids/<slug>`). Folders that do not exist
   yet are created automatically.
3. Tap the **Projects** tab, pick My Rocket Launch, then the **Build**
   tab -> **Build & Deploy**. The first time, it asks for the FTP
   password - enter it there, on the phone. It saves to the Keychain,
   so later builds do not ask again.
4. Watch the build log. On success it prints the live URL - tap
   **Open live site** to check it in Safari. My Rocket Launch lives at
   `https://mikegyver-studio.si/kids/my-rocket-launch/`.
5. Repeat for the other four starters. Each deploys under
   `/public_html/kids/<slug>`:
   - Counting Stars Quiz -> `/kids/counting-stars-quiz/`
   - Piano Notes -> `/kids/piano-notes/`
   - Take a Photo -> `/kids/take-a-photo/`
   - Photo to Space Sound -> `/kids/photo-to-space-sound/`

If the build step fails, the log shows the trunk output from the
server - paste that back and the fix is usually in the server setup,
not in the app. If the Code tab says it cannot reach the builder,
check the builder address in Settings and that the PC is on.

## Troubleshooting

- `Source folder not found: ...\kidbuilder-v1.0.1\kidbuilder` - you
  extracted an old v1.0.0 zip (no inner folder) or extracted to the
  wrong place. Use `kidbuilder-v1.0.1.zip` and check the path exists.
- `Tag v1.0.1 already exists` - the tag was already pushed. Check the
  Actions tab: if that run is green, the build is already on its way.
- Workflow run missing or stale - push to main alone does not start
  this workflow; only a `v*` tag push does. Tag by hand only after
  confirming the push landed (`git status` clean, commit on GitHub).
- Build stuck at Missing Compliance in TestFlight - answer "None of
  the algorithms mentioned above" (see step 4).
- `sstv-core.js not found` from the server - fixed in v1.0.1: the
  generator now falls back to the shipped copy in
  `projects/photo-to-space-sound/`. If you still see it, you are
  running the old server file - replace it with the v1.0.1 one.
- Distribution certificate limit in the workflow log - revoke only
  ONE old distribution certificate in the portal, then re-run the
  workflow with no code change.
