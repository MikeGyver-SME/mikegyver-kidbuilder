# Kid Builder - deployment steps (v1.0.3)

Same proven pipeline as YewBuilder / SSTV Studio / PodMix / Voyager
Light-Day. Do each step once, in order. Nothing here needs the Mac -
the build runs on GitHub Actions and lands in TestFlight.

## 0. What is in the zip (so nothing looks missing)

Extract `kidbuilder-v1.0.3.zip` to `E:\Downloads` (the default). You
get one folder, `kidbuilder-v1.0.3\kidbuilder\`, with everything in it:

- `KidBuilder/` - the iPhone app (SwiftUI, 5 tabs, camera block,
  "See my code" tab, Build & Deploy with on-phone FTP)
- `KidBuilder.xcodeproj/` - the Xcode project (v1.0.3 / build 4)
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

## How it works (the whole loop, in plain terms)

An iPhone cannot run `cargo` or `trunk` - there is no Rust toolchain
on iOS. So a kid's tap-blocks become a live website in four steps,
and the phone and the PC each do only the part they can do:

1. **The phone sends blocks.** Colin taps blocks together in the Kid
   Builder app. When he taps Build & Deploy, the phone sends the
   project as JSON (a list of blocks, plus any photo) to the builder
   server on your Windows PC - over the home LAN, or over Tailscale
   when away from home.
2. **The PC builds it.** The builder server turns the blocks into the
   5 real Yew files with `kidbuilder_gen.py` (the same generator that
   made the `projects/` starters), runs `trunk build --release`, and
   sends the finished `dist/` files back to the phone as base64.
   The "See my code" tab uses the same path without the build step:
   it asks the server for the generated `src/main.rs` and shows it.
3. **The phone uploads it.** The phone uploads `dist/` to
   `ftp.mikegyver-studio.si` itself, with its built-in FTP client.
   The FTP password lives in the iPhone Keychain and never leaves
   the phone - the builder server never sees it.
4. **It goes live.** The site lands under `/public_html/kids/<slug>/`,
   so My Rocket Launch is `https://mikegyver-studio.si/kids/my-rocket-launch/`.

## YewBuilder is not touched by any of this

This is the part that matters most. Kid Builder and YewBuilder are
two separate systems that happen to share a PC and a toolchain:

| | YewBuilder | Kid Builder |
| --- | --- | --- |
| iPhone app | YewBuilder | Kid Builder |
| Server folder | `E:\Downloads\yewbuilder-v1.0.5\yewbuilder\server\` | `E:\Downloads\kidbuilder-v1.0.3\kidbuilder\` |
| Server file | `server.py` | `kidbuilder-server.py` |
| Port | **8080** | **8081** |
| Starts by | "YewBuilder server" scheduled task, at sign-in | By hand with `run-server.ps1`, when the kids build |
| App's server address | `http://100.104.56.36:8080` | `http://100.104.56.36:8081` (same PC, other port) |
| Deploys to | `/public_html/<app>` | `/public_html/kids/<slug>` |

Nothing in these steps stops, edits, or re-points the YewBuilder
server or its scheduled task. The Kid Builder server is a second
process on a second port. Either server can be started, stopped, or
crashed without the other noticing: kill the Kid Builder server and
YewBuilder still builds; kill the YewBuilder server and Kid Builder
still builds. They share only the installed Rust + trunk toolchain,
which neither of them changes. If you ever want the Kid Builder
server to start at sign-in too, make a SEPARATE scheduled task for
it ("KidBuilder server") - never edit the "YewBuilder server" task.

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
# Extract kidbuilder-v1.0.3.zip first (E:\Downloads is the default).
# The zip has an inner kidbuilder\ folder, so step into it first:
Set-Location E:\Downloads\kidbuilder-v1.0.3\kidbuilder
powershell -ExecutionPolicy Bypass -File .\scripts\push-kidbuilder.ps1
# uses defaults, tags v1.0.3
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

## 5. Builder server on the PC (a second server, alongside YewBuilder)

The Kid Builder server runs on port **8081**, next to the YewBuilder
server on port **8080**. Do NOT stop the YewBuilder server. Do NOT
touch the "YewBuilder server" scheduled task. It keeps running exactly
as it does today, and YewBuilder keeps using it.

1. In the extracted `kidbuilder` folder:
   ```powershell
   Set-Location E:\Downloads\kidbuilder-v1.0.3\kidbuilder
   powershell -ExecutionPolicy Bypass -File .\scripts\run-server.ps1
   ```
   It checks Python, cargo and trunk, then prints
   `KidBuilder server on http://0.0.0.0:8081`. Leave that window open
   while the kids build - the PC must be on with the server running.
   Python is already allowed through Windows Firewall from YewBuilder,
   so there is usually no new prompt.
   Before you run it, check you are in the right folder: PowerShell
   should show `PS E:\Downloads\kidbuilder-v1.0.3\kidbuilder>`. If it
   shows `kidbuilder-v1.0.1` or `kidbuilder-v1.0.2`, you are about to
   run the old script - `Set-Location` to the v1.0.3 folder first.
   (v1.0.3 also fixes the script itself: it used to look for the
   server file inside `scripts\`, where it does not live.)
2. Check both servers are up, in two windows: the YewBuilder window
   says port 8080, the Kid Builder window says port 8081. If you ever
   see two windows both claiming 8080, one of them is the old v1.0.1
   server - stop it and use v1.0.3.
3. If you want the Kid Builder server to start at sign-in too, make a
   SEPARATE scheduled task ("KidBuilder server", pointing at this
   folder's `scripts\run-server.ps1`). Never edit the "YewBuilder
   server" task to do it.

## 6. First launch on the phone (the part only you can do)

1. In the app: Settings -> Builder server ->
   `http://<PC-LAN-IP>:8081` -> **Test builder connection** (should show
   the trunk version). Find the LAN IP with `ipconfig` on the PC
   (e.g. `http://192.168.1.10:8081`); away from home, use the PC's
   Tailscale IP (`http://100.x.x.x:8081`). This is the Kid Builder
   address - YewBuilder keeps its own `...:8080` address in its own
   app, untouched.
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

- `can't open file '...\scripts\kidbuilder-server.py'` - the old
  `run-server.ps1` (v1.0.1 / v1.0.2) looked for the server file
  inside `scripts\`; it lives one level up, in the `kidbuilder\`
  folder. Fixed in v1.0.3: replace `scripts\run-server.ps1` with the
  v1.0.3 copy, or extract the v1.0.3 zip. Also check the banner: if
  it says port 8080 or the path names v1.0.1, PowerShell is sitting
  in an old extract, not the folder you think - run `Get-Location`.
- `Source folder not found: ...\kidbuilder-v1.0.3\kidbuilder` - you
  extracted an old v1.0.0 zip (no inner folder) or extracted to the
  wrong place. Use `kidbuilder-v1.0.3.zip` and check the path exists.
- `Tag v1.0.3 already exists` - the tag was already pushed. Check the
  Actions tab: if that run is green, the build is already on its way.
- Workflow run missing or stale - push to main alone does not start
  this workflow; only a `v*` tag push does. Tag by hand only after
  confirming the push landed (`git status` clean, commit on GitHub).
- Build stuck at Missing Compliance in TestFlight - answer "None of
  the algorithms mentioned above" (see step 4).
- `sstv-core.js not found` from the server - fixed in v1.0.1: the
  generator now falls back to the shipped copy in
  `projects/photo-to-space-sound/`. If you still see it, you are
  running the old server file - replace it with the v1.0.3 one.
- Two server windows both on 8080, or Kid Builder's Test builder
  connection answers on 8080 - you are running the old v1.0.1 server.
  Stop it; v1.0.3 listens on 8081 and the YewBuilder server keeps 8080.
- Distribution certificate limit in the workflow log - revoke only
  ONE old distribution certificate in the portal, then re-run the
  workflow with no code change.
