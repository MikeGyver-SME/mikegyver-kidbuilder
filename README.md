# Kid Builder v1.0.3 - iOS app

Stack blocks, tap **Build & Deploy**, and a real Rust Yew/WASM site
goes live on your Hostek FTP host - built by Colin (8) and Luan (8),
not by a grown-up typing code.

Bundle ID: `studio.mikegyver.kidbuilder` - iOS 17.0+ - SwiftUI -
no third-party dependencies.

## What a kid does

1. **Projects tab** - pick one of the five starters, or make a new
   project. The check mark shows which project the other tabs are
   working on.
2. **Blocks tab** - tap a block to change it, drag to reorder, swipe
   to delete, use "Add a block" for a new one. No code is typed here.
3. **Code tab** - "See my code": the real generated `src/main.rs`,
   fetched from the builder server. Change a block, fetch again, and
   watch the code change.
4. **Build tab** - Build & Deploy, then Open live site.
5. **Settings tab** - builder server address, FTP, password, tests.
   A grown-up sets this up once.

## The five starter projects

| Project | What it is |
| --- | --- |
| My Rocket Launch | Title, words, rocket block, Launch button, Flights counter |
| Counting Stars Quiz | Five quiz questions: odd numbers making square numbers (1+3=4, 1+3+5=9, 1+3+5+7=16, 3x3=9, 1+3+5+7+9=25) |
| Piano Notes | One piano block per note (C D E F G A B) plus a "Play a tune" button |
| Take a Photo | A photo block: take a photo with the camera or pick one from Photos |
| Photo to Space Sound | A photo block plus an SSTV block: photo to space sound (Robot 36) and back |

## The blocks

| Block | What it does on the finished site |
| --- | --- |
| Title | Big words at the top |
| Words | A paragraph |
| Photo | A photo (camera or Photos; stored small, 320x240 JPEG) |
| Button | Tap it: count, launch the rocket, or play a sound |
| Counter | Visitors tap to count |
| Rocket | Flies when the Launch button is pressed |
| Piano note | Plays one note (C-B) |
| Quiz question | Three answers, one right one |
| Timer | Counts down, then rings |
| Space sound (SSTV) | Turns a photo into Robot 36 space sound (downloadable WAV) and turns a WAV back into a photo |

## How Build works - read this first

An iPhone cannot run `cargo` or `trunk`: there is no Rust toolchain on
iOS. So Build is two steps, and the app is honest about it:

1. **Build on your builder server.** The phone sends the project's
   blocks as JSON to a small server you run yourself (your Windows
   PC - the same server family as YewBuilder's `server.py`, extended
   with block endpoints). The server turns the blocks into the five
   Yew files, runs `trunk build --release`, and sends the finished
   `dist/` files back.
2. **Upload from the phone over FTP.** The phone uploads `dist/` to
   `ftp.mikegyver-studio.si` itself, with a plain-FTP client built
   into the app (PASV mode, binary - the `.wasm` file is never
   text-mangled).

The server API the app uses:

- `GET /health` - `{"ok": true, "trunk": "trunk 0.22.1"}`
- `POST /generate-blocks` - `{"project_name", "blocks": [...]}` ->
  `{"success", "log", "files": [{"path", "content"}]}` (Code tab only;
  no build, no deploy)
- `POST /build-blocks` - `{"project_name", "blocks": [...],
  "deploy_path": "/public_html/kids/my-rocket-launch"}` ->
  `{"success", "log", "files": [{"path", "content_base64"}],
  "deploy_path": "..."}`

The block JSON uses a `"kind"` string per block, for example
`{"kind": "title", "text": "My Rocket Launch"}` or
`{"kind": "quiz", "question": "1 + 3 = ?", "answers": ["3", "4", "5"],
"correct_index": 1}`. See `KidBuilder/KidBlock.swift` for the full
model - the Swift enum and the server's generator must agree on it.

Kid projects deploy under `/public_html/kids/<slug>` by default, so
My Rocket Launch lives at
`https://mikegyver-studio.si/kids/my-rocket-launch/`.

## FTP settings (pre-filled)

- Host: `ftp.mikegyver-studio.si`
- Username: `itsmikeg@mikegyver-studio.si`
- Port: `21`
- Deploy folder: per project, `/public_html/kids/<slug>` (change it
  on the Build tab if you want somewhere else)

## FTP password - first time, then remembered

The first time you tap Build with no password saved, the app asks for
the FTP password. It is stored in the **iPhone Keychain** (not
UserDefaults, not a file, not the build log), and every later build
uses it without asking. A grown-up types this part.

Re-entry is always available but optional: Settings -> FTP password has
**Save password** (replace the saved one), **Forget saved password**,
and a **Remember password** toggle. Turn Remember off and the password
is used once for that build and not stored.

The builder server **never sees the password** - it only returns built
files. The password never leaves the phone.

Do not send the FTP password in chat or email. Enter it in the app,
on the phone, the first time.

## Builder server setup (do once, on your Windows PC)

The builder server ships in this zip: `kidbuilder-server.py` +
`kidbuilder_gen.py` + `projects/` (the five generated starters) +
`scripts/run-server.ps1`.

It runs ALONGSIDE the YewBuilder server, on its own port: Kid Builder
on **8081**, YewBuilder on **8080**. It does not replace YewBuilder
and does not touch it - do not stop the "YewBuilder server" scheduled
task, do not change it, and do not point anything YewBuilder at port
8081. YewBuilder keeps working exactly as it does today, whether the
Kid Builder server is running or not, and Kid Builder works whether
the YewBuilder server is running or not. Different folders, different
ports, different apps - stopping one cannot affect the other.

In the extracted `kidbuilder` folder, run (PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-server.ps1
```

It checks Python, cargo and trunk, then listens on port 8081. In the
Kid Builder iPhone app: Settings -> Builder server ->
`http://<this-PC-LAN-IP>:8081` (find the IP with `ipconfig`, e.g.
`http://192.168.1.10:8081`), or the PC's Tailscale IP
(`http://100.x.x.x:8081`) when away from home. Tap **Test builder
connection** - it should report the trunk version. Python is already
allowed through Windows Firewall from YewBuilder, so there is
usually no new prompt.

If you want the Kid Builder server to start at sign-in too, make a
SEPARATE scheduled task for it ("KidBuilder server", pointing at this
folder's `scripts\run-server.ps1`). Never edit the "YewBuilder
server" task to do it.

## Files

| File | What it does |
| --- | --- |
| `KidBuilder/KidBuilderApp.swift` | App entry point |
| `KidBuilder/ContentView.swift` | Projects / Blocks / Code / Build / Settings tabs, Build flow, password sheet, block editor, camera picker |
| `KidBuilder/KidBlock.swift` | Block model (Codable enum with a "kind" discriminator) + KidProject |
| `KidBuilder/KidProjects.swift` | The five starter projects |
| `KidBuilder/KidStore.swift` | Projects (Documents/KidBuilder/projects.json), settings, build log, code fetch, photo downscaling |
| `KidBuilder/KeychainService.swift` | FTP password in the iOS Keychain only |
| `KidBuilder/BuilderService.swift` | POST /generate-blocks + POST /build-blocks + GET /health |
| `KidBuilder/FTPClient.swift` | Plain-FTP uploader (BSD sockets, PASV, binary) |
| `KidBuilder/Info.plist` | Display name, `ITSAppUsesNonExemptEncryption = NO`, camera + photo library usage strings, local-network HTTP allowed for your builder |
| `KidBuilder.xcodeproj/project.pbxproj` | Hand-written project, single app target (no XcodeGen) |
| `.github/workflows/testflight.yml` | GitHub Actions -> fastlane -> TestFlight (same proven pipeline as YewBuilder / SSTV Studio / PodMix / Voyager) |
| `scripts/push-kidbuilder.ps1` | PowerShell push + tag script |

## Building locally

1. Open `KidBuilder.xcodeproj` in Xcode.
2. Select your development team under Signing & Capabilities (signing
   is Automatic; the bundle ID is already
   `studio.mikegyver.kidbuilder`).
3. Build and run on your iPhone - the simulator works for editing
   blocks, but the camera needs a real device, and FTP to a real host
   is best tested on a device on the same network as your builder.
   For TestFlight, use `DEPLOYMENT-STEPS.md`.

## What v1 does NOT do yet

- No live preview inside the app - the finished site is checked in
  Safari with "Open live site" after a build.
- No raw-code editing - kids edit blocks; the Code tab is read-only.
  (Grown-ups who want the editor use YewBuilder.)
- No chat, no accounts, no personal details anywhere. Projects only
  go live under `/kids/` unless a grown-up changes the deploy folder.
- The SSTV sound (Robot 36 encode/decode and the WAV download) lives
  in the generated web app, not in this iOS app - the phone only
  sends the sstv block to the server.

## What I could not verify here

This was built on a Linux machine with no Xcode, so the iOS project
was **not compiled** here. The project file is internally consistent
(all IDs resolve, braces balanced), the icon set is complete (all 9
sizes + the 1024 marketing icon), and the Swift files are balanced -
but the first Xcode / Actions build is the real test. If it throws a
build error, paste it back and I will fix it the same turn.

The builder server endpoints (`/generate-blocks`, `/build-blocks`)
are being built in parallel by another agent and were **not**
available to test against here. The Code tab and the Build tab both
fail with a plain message if the server cannot be reached - they
never show invented code or a fake success.

## Changelog

- **v1.0.3** - Fixes `run-server.ps1`: it used to `Set-Location
  $PSScriptRoot` (the `scripts\` folder) and then run
  `python kidbuilder-server.py`, but the server file lives one level
  up, so Python failed with "can't open file
  '...\scripts\kidbuilder-server.py'". It now changes to the parent
  folder first and throws a clear message if the server file is not
  there. No app code changed; the bump keeps zip, tag, and app
  version in sync. If you already pushed v1.0.2 to TestFlight, do
  NOT re-push for this - just replace the one `run-server.ps1` file
  on the PC, since the app bundle does not contain it. Version
  1.0.3 / build 4.
- **v1.0.2** - The Kid Builder server moves to its own port, 8081.
  YewBuilder stays on 8080, untouched: its server, its scheduled
  task, and its folder are not stopped, changed, or pointed at
  anything new. The v1.0.1 "swap from YewBuilder" instruction was
  wrong and is withdrawn. Also fixes the Settings placeholder to
  show an 8081 example address. Version 1.0.2 / build 3.
- **v1.0.1** - Fixes the two v1.0.0 packaging bugs: the zip now has
  the inner `kidbuilder/` folder the push script expects (v1.0.0 had
  its files at the zip root, so the script threw "Source folder not
  found"), and the generator falls back to the shipped
  `projects/photo-to-space-sound/sstv-core.js` when there is no
  `sstv-studio-ios` folder next to it, so the SSTV starter builds on
  the PC instead of failing with FileNotFoundError. Adds
  `scripts/run-server.ps1` (one-click Kid Builder server start).
  Version 1.0.1 / build 2.
- **v1.0.0** - First build. Five starter projects (Rocket Launch,
  Counting Stars Quiz, Piano Notes, Take a Photo, Photo to Space
  Sound), block editor with camera + photo library (photos downscaled
  to 320x240 JPEG), Code tab from the builder server, Build =
  builder-server Trunk build + on-phone FTP upload, build log, Test
  builder / Test FTP login, TestFlight pipeline.
