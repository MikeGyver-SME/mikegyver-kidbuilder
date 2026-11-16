# Kid Builder server

A small stdlib-only Python server (no pip packages) that turns the Kid
Builder iOS app's tap blocks into real Yew/WASM sites. It is the
YewBuilder builder server (`~/workspace/yewbuilder/server/server.py`)
with two block endpoints added. `/health` and `/build` are unchanged,
so YewBuilder keeps working against this server.

## What it does

An iPhone cannot run `cargo` or `trunk`, so this server builds for it:

1. The phone sends a project's blocks to `POST /build-blocks`.
2. The server turns the blocks into the 5 Yew files with
   `kidbuilder_gen.py` (the one place that knows how to turn blocks
   into code, so the phone and the server can never disagree),
   runs `trunk build --release`, and sends the finished `dist/`
   files back as base64.
3. The phone uploads `dist/` to FTP itself. The server NEVER sees
   the FTP password.

`POST /generate-blocks` only makes the source files - it never builds.
That is the endpoint behind the app's Code tab ("See my code"): the
Rust a kid sees is the real file the server generated from their
blocks.

## Run it

On your Windows PC, in this folder. Needs Rust + trunk first:

```
winget install Rustlang.Rustup
rustup default stable
rustup target add wasm32-unknown-unknown
cargo install trunk
powershell -ExecutionPolicy Bypass -File .\scripts\run-server.ps1
```

`run-server.ps1` checks the toolchain and starts
`kidbuilder-server.py` on port 8081. Or run `python
kidbuilder-server.py` directly. This server runs ALONGSIDE the
YewBuilder server (port 8080) - it does not replace it. Do not stop
the YewBuilder server or its scheduled task, and do not point
YewBuilder at port 8081.

It listens on `http://0.0.0.0:8081` by default (override with the
`PORT` environment variable or a port number argument). Put that
machine's LAN IP - or its Tailscale IP when you are away from home,
exactly like YewBuilder - in the Kid Builder iPhone app's Settings,
for example `http://192.168.1.10:8081`. YewBuilder keeps its own
`http://192.168.1.10:8080` in its own app. The PC must be on with the
server running when a kid taps Build.

Check it is alive: `GET /health` returns `{"ok": true, "trunk": ...,
"cargo": ...}`. If it says `ok: false`, install the toolchain above.

## API

- `GET /health` - toolchain check.
- `POST /build` - the original YewBuilder endpoint: 5 source files in,
  built `dist/` files out. Unchanged.
- `POST /generate-blocks` - `{"project_name": "...", "blocks": [...]}`.
  Returns `{"success": true, "log": "...", "files": [{"path",
  "content"}]}`.
- `POST /build-blocks` - `{"project_name": "...", "blocks": [...],
  "deploy_path": "/public_html/kids/my-rocket-launch"}`. Returns the
  same shape as `/build`, with `deploy_path` echoed back. The deploy
  folder is validated (no `..` escapes) and normalised; the phone
  uploads to exactly the echoed folder.

Block shapes are the iOS app's wire shapes (see
`KidBuilder/KidBlock.swift`): `title`/`words` take `text`, `picture`
takes `base64jpeg` + `caption` (empty photo = camera picker on the
finished page), `button` takes `label` + `action` (`count`, `rocket`,
`sound`), `counter` takes `label`, `rocket` takes nothing, `piano`
takes one `note`, `quiz` takes one `question` + `answers` +
`correctIndex`, `timer` takes `seconds`, `sstv` takes nothing.

## The SSTV project

The Photo to Space Sound project ships two extra files:
`sstv-core.js` (the proven SSTV Studio Robot 36/72 encoder + decoder,
with only its 6 em dashes changed to hyphens so the file is plain
ASCII) and `kid-sstv-bridge.js` (a small wrapper: photo to Robot 36
WAV, WAV back to photo). The server allows exactly those two extra
paths and nothing else. The DSP stays in JavaScript; the generated
Rust only calls the bridge and shows a plain message if it did not load.

v1.0.4 note: app-only fix (Swift compile error in the block
editor); the server is unchanged from v1.0.3.

v1.0.3 note: `scripts/run-server.ps1` used to look for this file
inside `scripts\` and failed with "can't open file". It now changes
to the `kidbuilder\` folder first. If you already have v1.0.2
extracted, replacing that one script file is enough - no re-extract
and no app re-push needed.

v1.0.2 note: the server moved to its own port, 8081. The v1.0.1
"replaces the YewBuilder server" instruction was wrong and is
withdrawn - YewBuilder stays on 8080, untouched, and the Kid Builder
server runs alongside it.

v1.0.1 note: the generator reads the SSTV core from
`~/workspace/sstv-studio-ios/` when it is there, and falls back to the
shipped `projects/photo-to-space-sound/sstv-core.js` when it is not -
so the SSTV starter builds on the PC from the zip alone. Verified
here in Node: encode 37.91 s at 44.1 kHz, decode back Robot 36,
320x240, 241 syncs, mean per-channel difference about 11.

## Files here

- `kidbuilder_gen.py` - the block-to-Yew generator (stdlib only).
  Run `python3 kidbuilder_gen.py` to regenerate the 5 starter
  projects into `projects/<slug>/`.
- `kidbuilder-server.py` - this server.
- `projects/` - the 5 generated starter projects, ready to build.
