#!/usr/bin/env python3
"""
Kid Builder v1 - block-to-Yew generator. Pure Python, stdlib only.

A kid project is a name plus an ordered list of blocks - the same wire
shape the Kid Builder iOS app sends (see KidBuilder/KidBlock.swift):

    {"kind": "title", "text": "My Rocket Launch"}
    {"kind": "words", "text": "Hello!"}
    {"kind": "picture", "base64jpeg": "...", "caption": "My photo"}
    {"kind": "button", "label": "Tap me", "action": "count"|"rocket"|"sound"}
    {"kind": "counter", "label": "Count"}
    {"kind": "rocket"}
    {"kind": "piano", "note": "C"}
    {"kind": "quiz", "question": "1 + 3 = ?", "answers": ["3", "4", "5"],
     "correctIndex": 1}
    {"kind": "timer", "seconds": 10}
    {"kind": "sstv"}

One quiz block is one question; several quiz blocks make a quiz. One
piano block is one key; C..B blocks make the keyboard. A picture block
with an empty base64jpeg renders a camera picker (capture="environment")
instead of a photo, and the photo it takes becomes the photo the SSTV
block encodes.

Output: the 5 Yew files (index.html, styles.css, Cargo.toml, Trunk.toml,
src/main.rs), plus sstv-core.js (the proven SSTV Studio core, copied
with only its 6 em dashes changed to hyphens so the file is plain
ASCII - the DSP code itself is untouched) and kid-sstv-bridge.js when
a project has an sstv block. The DSP stays in JavaScript - the Rust
side only calls the bridge through wasm-bindgen and never reimplements
SSTV.

Rules baked in (from ~/workspace/custom-skills/yew_wasm_trunk_shipping/):
- Trunk.toml: public_url = "./" and filehash = false.
- index.html: data-integrity="none" on the data-trunk rust + css links.
- Every generated file is plain ASCII (no emoji, no em dashes).
- main.rs never uses std::time; animation state lives in
  Rc<RefCell<T>> with a separate frame-counter state driving renders.
- Yew 0.21, yew { version = "0.21", features = ["csr"] }.

Run it:
    python3 kidbuilder_gen.py
generates the 5 starter projects into projects/<slug>/ next to this
file and prints a per-project file list + ASCII check result.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SSTV_CORE_SRC = (
    HERE.parent / "sstv-studio-ios" / "SSTVStudio" / "sstv-core.js"
)
# Fallback: the shipped copy inside projects/photo-to-space-sound/.
# On Mike's PC the extracted zip has no sstv-studio-ios sibling, so
# without this fallback every SSTV project failed with FileNotFoundError
# the first time the phone asked the server to build it (v1.0.0 bug).
SSTV_CORE_FALLBACK = HERE / "projects" / "photo-to-space-sound" / "sstv-core.js"

PIANO_FREQS = {
    "C": 261.63, "D": 293.66, "E": 329.63, "F": 349.23,
    "G": 392.00, "A": 440.00, "B": 493.88,
}
PIANO_NOTES = ["C", "D", "E", "F", "G", "A", "B"]


def slugify(name):
    """Lowercase letters, digits and hyphens only, for folder names."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "kid-app"


def clean_text(text):
    """Plain ASCII text for generated files: strip non-ASCII, tidy space."""
    if text is None:
        return ""
    out = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in str(text))
    return " ".join(out.split())


def rust_str(text):
    """Escape a string for a Rust string literal."""
    s = clean_text(text)
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def html_text(text):
    """Escape a string for HTML text content."""
    s = clean_text(text)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Shared files: Cargo.toml, Trunk.toml, styles.css, index.html
# ---------------------------------------------------------------------------

CARGO_TOML_TEMPLATE = """[package]
name = "__PKG__"
version = "0.1.0"
edition = "2021"

[dependencies]
yew = { version = "0.21", features = ["csr"] }
wasm-bindgen = "0.2"
wasm-bindgen-futures = "0.4"
gloo-timers = "0.3"
js-sys = "0.3"
web-sys = { version = "0.3", features = [
  "Window",
  "Document",
  "Element",
  "HtmlElement",
  "HtmlInputElement",
  "HtmlCanvasElement",
  "CanvasRenderingContext2d",
  "HtmlImageElement",
  "HtmlAnchorElement",
  "Blob",
  "BlobPropertyBag",
  "Url",
  "File",
  "FileList",
  "Event",
  "MouseEvent",
  "AudioContext",
  "BaseAudioContext",
  "OscillatorNode",
  "GainNode",
  "AudioParam",
  "OscillatorType",
  "AudioDestinationNode",
  "AudioNode",
] }

[profile.release]
opt-level = 2
"""

TRUNK_TOML = """[build]
target = "index.html"
dist = "dist"
# Subfolder-safe: Trunk defaults to root-absolute paths ("/x.js"), which
# 404 when the site lives in a subfolder. "./" makes every rebuild emit
# relative paths, so no post-build fix is needed.
public_url = "./"
# Keep filenames stable across rebuilds so index.html and the uploaded
# files can never drift apart (no more hashed names).
filehash = false
"""

STYLES_CSS = """* { box-sizing: border-box; }
body { margin: 0; background: #0b1026; color: #e8eefc; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
.wrap { max-width: 640px; margin: 0 auto; padding: 32px 20px 48px; text-align: center; }
h1 { font-size: 34px; margin: 0 0 8px; color: #ffd23f; }
p { color: #b9c6e8; line-height: 1.6; font-size: 17px; }
.words { font-size: 18px; }
.big { font-size: 64px; font-weight: 800; color: #f5c542; margin: 12px 0; }
button { background: #f5c542; color: #111; border: 0; border-radius: 12px; padding: 14px 24px; font-size: 18px; font-weight: 700; cursor: pointer; margin: 6px; }
button:active { transform: scale(0.97); }
button:disabled { opacity: 0.5; cursor: default; }
button.ghost { background: #22305e; color: #e8eefc; }
.card { background: #141c3d; border-radius: 16px; padding: 20px; margin: 20px 0; }
.msg { color: #9fd8ff; min-height: 24px; }
.feedback { font-size: 20px; font-weight: 700; min-height: 28px; }
.feedback.good { color: #7ddc8a; }
.feedback.bad { color: #ff9d9d; }
.scene { position: relative; height: 340px; background: linear-gradient(#0b1026, #1b2a5e); border-radius: 16px; overflow: hidden; margin: 16px 0; }
.ground { position: absolute; left: 0; right: 0; bottom: 0; height: 48px; background: #2e4a2f; }
.pad { position: absolute; left: 50%; bottom: 48px; width: 110px; height: 10px; margin-left: -55px; background: #666; border-radius: 4px; }
.rocket { position: absolute; left: 50%; margin-left: -36px; width: 72px; }
.rocket svg { display: block; }
.flame { width: 22px; height: 44px; margin: 0 auto; background: #ff9d2e; border-radius: 0 0 12px 12px; }
.star { display: inline-block; width: 28px; height: 28px; background: #f5c542; clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%); -webkit-clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%); vertical-align: middle; }
.piano { display: flex; justify-content: center; gap: 6px; margin: 16px 0; flex-wrap: wrap; }
.key { width: 56px; height: 120px; background: #ffffff; color: #111; border-radius: 0 0 8px 8px; padding-top: 84px; font-size: 20px; }
.key:active { background: #ffd23f; }
.filebtn { display: inline-block; background: #f5c542; color: #111; border-radius: 12px; padding: 14px 24px; font-size: 18px; font-weight: 700; cursor: pointer; margin: 6px; }
.filebtn input { display: none; }
.photo img, .decoded img { max-width: 100%; border-radius: 12px; margin: 12px 0; }
.status { font-size: 18px; font-weight: 700; color: #ffd23f; }
.timer-big { font-size: 72px; font-weight: 800; color: #9fd8ff; margin: 12px 0; }
footer { margin-top: 32px; color: #7e8fb5; font-size: 13px; }
"""

INDEX_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>__TITLE__ - Kid Builder</title>
<link data-trunk rel="rust" data-wasm-opt="0" data-integrity="none" />
<link data-trunk rel="css" href="styles.css" data-integrity="none" />
__SSTV_LINKS__</head>
<body>
<div id="app"></div>
__SSTV_SCRIPTS__</body>
</html>
"""

SSTV_LINKS = """<link data-trunk rel="copy-file" href="sstv-core.js" />
<link data-trunk rel="copy-file" href="kid-sstv-bridge.js" />
"""
SSTV_SCRIPTS = """<script src="./sstv-core.js"></script>
<script src="./kid-sstv-bridge.js"></script>
"""

# ---------------------------------------------------------------------------
# kid-sstv-bridge.js - small wrapper around the proven sstv-core.js.
# The DSP lives in the core; this only moves images and WAV bytes around.
# encodeSSTV(rgba, width, height, modeName, sampleRate) -> Float32Array
# decodeSSTV(samples, sampleRate, modeHint) -> {ok, mode, rgba, width, height}
# ---------------------------------------------------------------------------

BRIDGE_JS = """// Kid Builder SSTV bridge - plain JavaScript, no build step.
// It talks to sstv-core.js (loaded just before this file) and to the
// Yew app through window.kidSstvEncode / window.kidSstvDecode.
// Both functions return a Promise of a string: a blob URL or data URL
// on success, or a string starting with "ERROR: " on failure, so the
// Rust side can show a plain message instead of crashing.
(function () {
  "use strict";
  var SAMPLE_RATE = 44100;
  var MODE = "Robot 36";

  function loadImage(dataUrl) {
    return new Promise(function (resolve, reject) {
      var img = new Image();
      img.onload = function () { resolve(img); };
      img.onerror = function () { reject(new Error("Could not load the photo.")); };
      img.src = dataUrl;
    });
  }

  function encodeWav(samples, sampleRate) {
    var n = samples.length;
    var buf = new ArrayBuffer(44 + n * 2);
    var v = new DataView(buf);
    function str(off, s) {
      for (var i = 0; i < s.length; i++) v.setUint8(off + i, s.charCodeAt(i));
    }
    str(0, "RIFF");
    v.setUint32(4, 36 + n * 2, true);
    str(8, "WAVE");
    str(12, "fmt ");
    v.setUint32(16, 16, true);
    v.setUint16(20, 1, true); // PCM
    v.setUint16(22, 1, true); // mono
    v.setUint32(24, sampleRate, true);
    v.setUint32(28, sampleRate * 2, true);
    v.setUint16(32, 2, true); // block align
    v.setUint16(34, 16, true); // bits per sample
    str(36, "data");
    v.setUint32(40, n * 2, true);
    for (var i = 0; i < n; i++) {
      var s = samples[i];
      if (s > 1) s = 1;
      if (s < -1) s = -1;
      v.setInt16(44 + i * 2, Math.round(s * 32767), true);
    }
    return new Blob([buf], { type: "audio/wav" });
  }

  function parseWav(arrayBuffer) {
    var v = new DataView(arrayBuffer);
    function str(off) {
      return String.fromCharCode(
        v.getUint8(off), v.getUint8(off + 1),
        v.getUint8(off + 2), v.getUint8(off + 3));
    }
    if (str(0) !== "RIFF" || str(8) !== "WAVE") {
      throw new Error("That file is not a WAV file.");
    }
    var fmt = null, dataOff = -1, dataLen = 0;
    var off = 12;
    while (off + 8 <= v.byteLength) {
      var id = str(off);
      var len = v.getUint32(off + 4, true);
      if (id === "fmt ") {
        fmt = {
          audioFormat: v.getUint16(off + 8, true),
          channels: v.getUint16(off + 10, true),
          sampleRate: v.getUint32(off + 12, true),
          bits: v.getUint16(off + 22, true),
        };
      } else if (id === "data") {
        dataOff = off + 8;
        dataLen = len;
        break;
      }
      off += 8 + len;
    }
    if (!fmt || dataOff < 0) throw new Error("That WAV file has no sound in it.");
    var count = fmt.bits === 16 ? Math.floor(dataLen / 2) : Math.floor(dataLen / 4);
    var out = new Float32Array(count);
    if (fmt.audioFormat === 3) {
      // float samples
      for (var i = 0; i < count; i++) out[i] = v.getFloat32(dataOff + i * 4, true);
    } else {
      // 16-bit PCM samples
      for (var j = 0; j < count; j++) out[j] = v.getInt16(dataOff + j * 2, true) / 32768;
    }
    if (fmt.channels === 2) {
      var half = new Float32Array(Math.floor(count / 2));
      for (var k = 0; k < half.length; k++) half[k] = out[k * 2];
      return { samples: half, sampleRate: fmt.sampleRate };
    }
    return { samples: out, sampleRate: fmt.sampleRate };
  }

  window.kidSstvEncode = function (imageDataUrl, mode) {
    return loadImage(imageDataUrl).then(function (img) {
      if (typeof encodeSSTV !== "function") {
        return "ERROR: The SSTV sound maker (sstv-core.js) did not load.";
      }
      var canvas = document.createElement("canvas");
      canvas.width = 320;
      canvas.height = 240;
      var ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, 320, 240);
      var rgba = ctx.getImageData(0, 0, 320, 240).data;
      var samples = encodeSSTV(rgba, 320, 240, mode || MODE, SAMPLE_RATE);
      var blob = encodeWav(samples, SAMPLE_RATE);
      return URL.createObjectURL(blob);
    }).catch(function (err) {
      return "ERROR: " + (err && err.message ? err.message : "Could not make the sound.");
    });
  };

  window.kidSstvDecode = function (arrayBuffer) {
    return new Promise(function (resolve) {
      try {
        if (typeof decodeSSTV !== "function") {
          resolve("ERROR: The SSTV decoder (sstv-core.js) did not load.");
          return;
        }
        var wav = parseWav(arrayBuffer);
        var res = decodeSSTV(wav.samples, wav.sampleRate, "auto");
        if (!res.ok) {
          resolve("ERROR: " + (res.reason || "No SSTV photo found in that sound."));
          return;
        }
        var canvas = document.createElement("canvas");
        canvas.width = res.width;
        canvas.height = res.height;
        var ctx = canvas.getContext("2d");
        var imageData = ctx.createImageData(res.width, res.height);
        imageData.data.set(res.rgba);
        ctx.putImageData(imageData, 0, 0);
        resolve(canvas.toDataURL("image/png"));
      } catch (err) {
        resolve("ERROR: " + (err && err.message ? err.message : "Could not decode that sound."));
      }
    });
  };
})();
"""

# ---------------------------------------------------------------------------
# Starter projects (the 5 Mike picked)
# ---------------------------------------------------------------------------

STARTERS = [
    {
        "name": "My Rocket Launch",
        "slug": "my-rocket-launch",
        "blocks": [
            {"kind": "title", "text": "My Rocket Launch"},
            {"kind": "words", "text": "Hi, I am Colin! Press Launch and watch my rocket fly up into the sky and come back down."},
            {"kind": "rocket"},
            {"kind": "button", "label": "Launch", "action": "rocket"},
            {"kind": "counter", "label": "Flights"},
        ],
    },
    {
        "name": "Counting Stars Quiz",
        "slug": "counting-stars-quiz",
        "blocks": [
            {"kind": "title", "text": "Counting Stars Quiz"},
            {"kind": "words", "text": "Odd numbers are magic. Add them up and you get square numbers! Try the quiz."},
            {"kind": "quiz", "question": "What is 1?", "answers": ["1", "2", "3"], "correctIndex": 0},
            {"kind": "quiz", "question": "What is 1 + 3?", "answers": ["3", "4", "5"], "correctIndex": 1},
            {"kind": "quiz", "question": "What is 1 + 3 + 5?", "answers": ["8", "9", "10"], "correctIndex": 1},
            {"kind": "quiz", "question": "What is 1 + 3 + 5 + 7?", "answers": ["15", "16", "17"], "correctIndex": 1},
            {"kind": "quiz", "question": "What is 1 + 3 + 5 + 7 + 9?", "answers": ["24", "25", "26"], "correctIndex": 1},
            {"kind": "counter", "label": "Stars"},
        ],
    },
    {
        "name": "Piano Notes",
        "slug": "piano-notes",
        "blocks": [
            {"kind": "title", "text": "Piano Notes"},
            {"kind": "words", "text": "Hi, I am Colin! I play piano. Tap a note to hear it, then press Play a tune to hear them all together."},
            {"kind": "piano", "note": "C"},
            {"kind": "piano", "note": "D"},
            {"kind": "piano", "note": "E"},
            {"kind": "piano", "note": "F"},
            {"kind": "piano", "note": "G"},
            {"kind": "piano", "note": "A"},
            {"kind": "piano", "note": "B"},
            {"kind": "button", "label": "Play a tune", "action": "sound"},
        ],
    },
    {
        "name": "Take a Photo",
        "slug": "take-a-photo",
        "blocks": [
            {"kind": "title", "text": "Take a Photo"},
            {"kind": "words", "text": "Tap the photo block below to take a photo with the camera, or pick one from your photos. Your photo is made small before it is saved, so it loads fast for everyone."},
            {"kind": "picture", "base64jpeg": "", "caption": "My photo"},
        ],
    },
    {
        "name": "Photo to Space Sound",
        "slug": "photo-to-space-sound",
        "blocks": [
            {"kind": "title", "text": "Photo to Space Sound"},
            {"kind": "words", "text": "Turn your photo into space sound, and turn space sound back into a photo. Robot 36."},
            {"kind": "words", "text": "Astronauts on the Space Station send photos this way. Your photo becomes a funny squeaky sound, and the sound can become a photo again."},
            {"kind": "picture", "base64jpeg": "", "caption": "My photo for space"},
            {"kind": "sstv"},
        ],
    },
]


def project_kinds(blocks):
    return {b.get("kind") for b in blocks if isinstance(b, dict)}


def project_needs(blocks):
    """Which shared features this project's blocks need."""
    kinds = project_kinds(blocks)
    needs = {
        "count": "counter" in kinds or any(
            b.get("kind") == "button" and b.get("action") == "count" for b in blocks
        ),
        "rocket": "rocket" in kinds or any(
            b.get("kind") == "button" and b.get("action") == "rocket" for b in blocks
        ),
        "audio": "piano" in kinds or any(
            b.get("kind") == "button" and b.get("action") == "sound" for b in blocks
        ),
        "quiz": "quiz" in kinds,
        "timer": "timer" in kinds,
        "photo": any(b.get("kind") == "picture" for b in blocks)
        or "sstv" in kinds,
        "sstv": "sstv" in kinds,
    }
    return needs


def quiz_questions(blocks):
    questions = []
    for b in blocks:
        if b.get("kind") != "quiz":
            continue
        answers = [clean_text(a) for a in (b.get("answers") or [])][:4]
        if len(answers) < 2:
            continue
        correct = b.get("correctIndex", b.get("correct_index", 0))
        try:
            correct = int(correct)
        except (TypeError, ValueError):
            correct = 0
        correct = max(0, min(correct, len(answers) - 1))
        questions.append((clean_text(b.get("question", "Quiz?")), answers, correct))
    # All answer lists must be the same length: the Rust quiz table is
    # one array type, so pad shorter lists with "?" (never the right one).
    width = max((len(a) for _, a, _ in questions), default=0)
    return [
        (q, a + ["?"] * (width - len(a)), c) for q, a, c in questions
    ]


def piano_note_list(blocks):
    notes = []
    for b in blocks:
        if b.get("kind") == "piano":
            n = clean_text(b.get("note", "")).upper()
            if n in PIANO_FREQS and n not in notes:
                notes.append(n)
    return notes or list(PIANO_NOTES)


def timer_seconds(blocks):
    for b in blocks:
        if b.get("kind") == "timer":
            try:
                return max(1, int(b.get("seconds", 10)))
            except (TypeError, ValueError):
                return 10
    return 10


def embedded_photo(blocks):
    """Data URL of the first picture block that carries photo bytes."""
    for b in blocks:
        if b.get("kind") == "picture":
            data = (b.get("base64jpeg") or "").strip()
            if data:
                return "data:image/jpeg;base64," + "".join(data.split())
    return None


# ---------------------------------------------------------------------------
# main.rs generation
# ---------------------------------------------------------------------------

RUST_HEADER = """use gloo_timers::callback::Interval;
use wasm_bindgen::JsValue;
use std::cell::RefCell;
use std::rc::Rc;
use wasm_bindgen::prelude::*;
use wasm_bindgen::JsCast;
use wasm_bindgen_futures::JsFuture;
use web_sys::{
    AudioContext, BaseAudioContext, Blob, CanvasRenderingContext2d,
    Event, GainNode, HtmlAnchorElement, HtmlCanvasElement, HtmlImageElement,
    HtmlInputElement, OscillatorType,
};
use yew::prelude::*;

// Kid Builder app. Generated from tap blocks - no Rust was typed by hand.
// Flight plan for the rocket: 12 seconds total, up for 6, back down for 6.
const FLIGHT_SECONDS: f64 = 12.0;

#[derive(Clone, PartialEq)]
enum Phase {
    Ready,
    Flying,
    Done,
}

fn rocket_status(t: f64, done: bool) -> &'static str {
    if done {
        "Landed! Your rocket came back home."
    } else if t <= 0.0 {
        "On the pad. Ready to fly."
    } else if t < 6.0 {
        "LIFTOFF! Going up, up, up!"
    } else {
        "Coming back down. Get ready to catch it!"
    }
}

// Play one note on a lazily-created AudioContext (created on the first
// tap, so the browser allows sound). Triangle wave, gentle envelope.
fn play_tone(audio: &Rc<RefCell<Option<AudioContext>>>, freq: f64, secs: f64) {
    let mut slot = audio.borrow_mut();
    if slot.is_none() {
        match AudioContext::new() {
            Ok(ctx) => *slot = Some(ctx),
            Err(_) => return,
        }
    }
    let Some(ctx) = slot.as_ref() else {
        return;
    };
    let _ = ctx.resume();
    let t0 = ctx.current_time() + 0.05;
    let Ok(osc) = ctx.create_oscillator() else {
        return;
    };
    osc.set_type(OscillatorType::Triangle);
    osc.frequency().set_value(freq as f32);
    let Ok(gain) = ctx.create_gain() else {
        return;
    };
    let _ = gain.gain().set_value_at_time(0.0, t0);
    let _ = gain.gain().linear_ramp_to_value_at_time(0.4, t0 + 0.02);
    let _ = gain
        .gain()
        .exponential_ramp_to_value_at_time(0.001, t0 + secs);
    let _ = osc.connect_with_audio_node(&gain);
    let _ = gain.connect_with_audio_node(&ctx.destination());
    let _ = osc.start_with_when(t0);
    let _ = osc.stop_with_when(t0 + secs + 0.05);
}

// Download any URL (blob URL or data URL) as a file, via an anchor click.
fn download_url(href: &str, filename: &str) {
    let Some(win) = web_sys::window() else {
        return;
    };
    let Some(doc) = win.document() else {
        return;
    };
    let Ok(a) = doc.create_element("a") else {
        return;
    };
    let Ok(a) = a.dyn_into::<HtmlAnchorElement>() else {
        return;
    };
    a.set_href(href);
    a.set_download(filename);
    a.click();
}

// Call a window function by name and await its Promise, returning the
// string it resolves to (or None when the function is missing).
async fn call_bridge(name: &str, args: &[JsValue]) -> Option<String> {
    let win = web_sys::window()?;
    let win_val = JsValue::from(win);
    let val = js_sys::Reflect::get(&win_val, &JsValue::from_str(name)).ok()?;
    if val.is_undefined() || val.is_null() {
        return None;
    }
    let func: js_sys::Function = val.dyn_into().ok()?;
    let res = if args.len() == 2 {
        func.call2(&win_val, &args[0], &args[1]).ok()?
    } else if args.len() == 1 {
        func.call1(&win_val, &args[0]).ok()?
    } else {
        func.call0(&win_val).ok()?
    };
    let promise: js_sys::Promise = res.dyn_into().ok()?;
    let out = JsFuture::from(promise).await.ok()?;
    out.as_string()
}
"""

ROCKET_SVG = """<svg viewBox="0 0 120 200" width="72" height="120">
<path d="M60,6 C78,32 88,56 88,82 L32,82 C32,56 42,32 60,6 Z" fill="#f2f2f2" stroke="#222" stroke-width="2" />
<rect x="32" y="82" width="56" height="12" fill="#1a1a1a" />
<rect x="32" y="94" width="56" height="76" fill="#f5f5f5" stroke="#bbb" stroke-width="1" />
<circle cx="60" cy="118" r="7" fill="#9fd8ff" stroke="#222" stroke-width="2" />
<path d="M32,166 L14,198 L32,192 Z" fill="#1a1a1a" />
<path d="M88,166 L106,198 L88,192 Z" fill="#1a1a1a" />
</svg>"""


def generate_main_rs(name, blocks):
    needs = project_needs(blocks)
    questions = quiz_questions(blocks)
    notes = piano_note_list(blocks) if needs["audio"] else []
    timer_start = timer_seconds(blocks) if needs["timer"] else 10
    photo0 = embedded_photo(blocks)
    # A "Stars" counter shows the quiz score, not its own tap count,
    # so the tap-count state is only needed for a real counter card or
    # a button whose action is "count".
    count_needed = any(
        b.get("kind") == "button" and b.get("action") == "count" for b in blocks
    ) or any(
        b.get("kind") == "counter"
        and not (needs["quiz"] and clean_text(b.get("label", "")).lower() == "stars")
        for b in blocks
    )

    state = []
    if count_needed:
        state.append("    let count = use_state(|| 0i32);")
    if needs["rocket"]:
        state.append("    let phase = use_state(|| Phase::Ready);")
        state.append("    let flights = use_state(|| 0i32);")
        state.append("    let clock = use_mut_ref(|| 0.0f64);")
        state.append("    let frame = use_state(|| 0u32);")
        state.append("    let interval = use_mut_ref(|| None::<Interval>);")
    if needs["audio"]:
        state.append("    let audio = use_mut_ref(|| None::<AudioContext>);")
        state.append("    let last_note = use_state(|| None::<String>);")
    if needs["quiz"]:
        state.append("    let quiz_idx = use_state(|| 0usize);")
        state.append("    let quiz_score = use_state(|| 0i32);")
        state.append("    let quiz_feedback = use_state(|| None::<String>);")
        state.append("    let quiz_answered = use_state(|| false);")
        state.append("    let quiz_done = use_state(|| false);")
    if needs["timer"]:
        state.append("    let timer_clock = use_mut_ref(|| 0.0f64);")
        state.append("    let timer_frame = use_state(|| 0u32);")
        state.append("    let timer_running = use_state(|| false);")
        state.append("    let timer_interval = use_mut_ref(|| None::<Interval>);")
    if needs["photo"]:
        if photo0:
            state.append(
                "    let photo_url = use_state(|| Some(%s.to_string()));"
                % rust_str(photo0)
            )
        else:
            state.append("    let photo_url = use_state(|| None::<String>);")
        state.append("    let photo_msg = use_state(|| None::<String>);")
    if needs["sstv"]:
        state.append("    let decoded_url = use_state(|| None::<String>);")
        state.append("    let sstv_msg = use_state(|| None::<String>);")
        state.append("    let sstv_busy = use_state(|| false);")

    cb = []
    if count_needed:
        cb.append(
            """    let on_count = {
        let count = count.clone();
        Callback::from(move |_| count.set(*count + 1))
    };"""
        )
    if needs["rocket"]:
        cb.append(
            """    // Stop the flight ticker once the rocket has landed.
    {
        let interval = interval.clone();
        let phase = phase.clone();
        use_effect_with((*phase).clone(), move |p| {
            if *p == Phase::Done {
                *interval.borrow_mut() = None;
            }
            || ()
        });
    }

    let on_launch = {
        let phase = phase.clone();
        let clock = clock.clone();
        let frame = frame.clone();
        let interval = interval.clone();
        let flights = flights.clone();
        Callback::from(move |_| {
            *clock.borrow_mut() = 0.0;
            frame.set(0);
            phase.set(Phase::Flying);
            let c2 = clock.clone();
            let f2 = frame.clone();
            let p2 = phase.clone();
            let fl2 = flights.clone();
            let iv = Interval::new(50, move || {
                if *p2 == Phase::Done {
                    return;
                }
                let mut t = c2.borrow_mut();
                *t += 0.05;
                let now = *t;
                drop(t);
                f2.set((now * 20.0) as u32);
                if now >= FLIGHT_SECONDS {
                    fl2.set(*fl2 + 1);
                    p2.set(Phase::Done);
                }
            });
            *interval.borrow_mut() = Some(iv);
        })
    };

    let on_reset_rocket = {
        let phase = phase.clone();
        let clock = clock.clone();
        let frame = frame.clone();
        let interval = interval.clone();
        Callback::from(move |_| {
            *interval.borrow_mut() = None;
            *clock.borrow_mut() = 0.0;
            frame.set(0);
            phase.set(Phase::Ready);
        })
    };"""
        )
    if needs["audio"]:
        cb.append(
            """    let play_note = {
        let audio = audio.clone();
        let last_note = last_note.clone();
        move |freq: f64, name: &'static str| {
            let a2 = audio.clone();
            let l2 = last_note.clone();
            Callback::from(move |_| {
                play_tone(&a2, freq, 0.8);
                l2.set(Some(name.to_string()));
            })
        }
    };"""
        )
    if needs["quiz"] and questions:
        q_lit = ",\n        ".join(
            "(%s, [%s], %d)"
            % (
                rust_str(q),
                ", ".join(rust_str(a) for a in answers),
                correct,
            )
            for q, answers, correct in questions
        )
        cb.append(
            """    const QUIZ: [(&str, [&str; %d], usize); %d] = [
        %s
    ];

    let on_answer = {
        let quiz_idx = quiz_idx.clone();
        let quiz_score = quiz_score.clone();
        let quiz_feedback = quiz_feedback.clone();
        let quiz_answered = quiz_answered.clone();
        let quiz_done = quiz_done.clone();
        Callback::from(move |choice: usize| {
            if *quiz_answered || *quiz_done {
                return;
            }
            let (_, _, correct) = QUIZ[*quiz_idx];
            if choice == correct {
                quiz_score.set(*quiz_score + 1);
                quiz_feedback.set(Some("Right! Well done.".to_string()));
                quiz_answered.set(true);
            } else {
                quiz_feedback.set(Some("Not quite - try again.".to_string()));
            }
        })
    };

    let on_next = {
        let quiz_idx = quiz_idx.clone();
        let quiz_feedback = quiz_feedback.clone();
        let quiz_answered = quiz_answered.clone();
        let quiz_done = quiz_done.clone();
        Callback::from(move |_| {
            if *quiz_idx + 1 >= QUIZ.len() {
                quiz_done.set(true);
            } else {
                quiz_idx.set(*quiz_idx + 1);
            }
            quiz_feedback.set(None);
            quiz_answered.set(false);
        })
    };

    let on_quiz_again = {
        let quiz_idx = quiz_idx.clone();
        let quiz_score = quiz_score.clone();
        let quiz_feedback = quiz_feedback.clone();
        let quiz_answered = quiz_answered.clone();
        let quiz_done = quiz_done.clone();
        Callback::from(move |_| {
            quiz_idx.set(0);
            quiz_score.set(0);
            quiz_feedback.set(None);
            quiz_answered.set(false);
            quiz_done.set(false);
        })
    };"""
            % (len(questions[0][1]), len(questions), q_lit)
        )
    if needs["timer"]:
        cb.append(
            """    let on_timer = {
        let timer_clock = timer_clock.clone();
        let timer_frame = timer_frame.clone();
        let timer_running = timer_running.clone();
        let timer_interval = timer_interval.clone();
        Callback::from(move |_| {
            if *timer_running {
                *timer_interval.borrow_mut() = None;
                timer_running.set(false);
                return;
            }
            *timer_clock.borrow_mut() = __TIMER_START__ as f64;
            timer_frame.set(0);
            timer_running.set(true);
            let c2 = timer_clock.clone();
            let f2 = timer_frame.clone();
            let r2 = timer_running.clone();
            let i2 = timer_interval.clone();
            let iv = Interval::new(100, move || {
                if !*r2 {
                    return;
                }
                let mut t = c2.borrow_mut();
                *t -= 0.1;
                let now = *t;
                drop(t);
                f2.set((now * 10.0).max(0.0) as u32);
                if now <= 0.0 {
                    r2.set(false);
                    *i2.borrow_mut() = None;
                }
            });
            *timer_interval.borrow_mut() = Some(iv);
        })
    };

    let on_timer_reset = {
        let timer_clock = timer_clock.clone();
        let timer_frame = timer_frame.clone();
        let timer_running = timer_running.clone();
        let timer_interval = timer_interval.clone();
        Callback::from(move |_| {
            *timer_interval.borrow_mut() = None;
            *timer_clock.borrow_mut() = __TIMER_START__ as f64;
            timer_frame.set(0);
            timer_running.set(false);
        })
    };""".replace(
                "__TIMER_START__", str(timer_start)
            )
        )
    if needs["photo"]:
        cb.append(
            """    // Photo picker: read the file, draw it small (320x240) on a
    // canvas, and keep the small photo as a data URL. The SSTV block
    // encodes this same photo, so the two blocks share one picture.
    let on_photo = {
        let photo_url = photo_url.clone();
        let photo_msg = photo_msg.clone();
        Callback::from(move |e: Event| {
            let Some(target) = e.target() else {
                return;
            };
            let Ok(input) = target.dyn_into::<HtmlInputElement>() else {
                return;
            };
            let Some(files) = input.files() else {
                return;
            };
            let Some(file) = files.get(0) else {
                return;
            };
            let blob: &Blob = file.unchecked_ref();
            let Ok(url) = web_sys::Url::create_object_url_with_blob(blob) else {
                return;
            };
            let Ok(img) = HtmlImageElement::new() else {
                return;
            };
            let img2 = img.clone();
            let photo_url2 = photo_url.clone();
            let photo_msg2 = photo_msg.clone();
            let onload = Closure::wrap(Box::new(move || {
                let Some(win) = web_sys::window() else {
                    return;
                };
                let Some(doc) = win.document() else {
                    return;
                };
                let Ok(canvas_el) = doc.create_element("canvas") else {
                    return;
                };
                let Ok(canvas) = canvas_el.dyn_into::<HtmlCanvasElement>() else {
                    return;
                };
                canvas.set_width(320);
                canvas.set_height(240);
                let Ok(ctx_val) = canvas.get_context("2d") else {
                    return;
                };
                let Some(ctx_val) = ctx_val else {
                    return;
                };
                let Ok(ctx) = ctx_val.dyn_into::<CanvasRenderingContext2d>() else {
                    return;
                };
                if ctx
                    .draw_image_with_html_image_element_and_dw_and_dh(
                        &img2, 0.0, 0.0, 320.0, 240.0,
                    )
                    .is_err()
                {
                    photo_msg2.set(Some("Could not read that photo.".to_string()));
                    return;
                }
                let Ok(data) = canvas.to_data_url() else {
                    return;
                };
                photo_url2.set(Some(data));
                photo_msg2.set(Some("Photo ready!".to_string()));
            }) as Box<dyn FnMut()>);
            img.set_onload(Some(onload.as_ref().unchecked_ref()));
            onload.forget();
            img.set_src(&url);
        })
    };

    let on_download_photo = {
        let photo_url = photo_url.clone();
        Callback::from(move |_| {
            if let Some(url) = (*photo_url).clone() {
                download_url(&url, "my-photo.png");
            }
        })
    };"""
        )
    if needs["sstv"]:
        cb.append(
            """    let on_encode = {
        let photo_url = photo_url.clone();
        let sstv_msg = sstv_msg.clone();
        let sstv_busy = sstv_busy.clone();
        Callback::from(move |_| {
            let Some(url) = (*photo_url).clone() else {
                sstv_msg.set(Some("Take a photo first, then make the sound.".to_string()));
                return;
            };
            sstv_busy.set(true);
            let msg2 = sstv_msg.clone();
            let busy2 = sstv_busy.clone();
            wasm_bindgen_futures::spawn_local(async move {
                msg2.set(Some("Making the space sound...".to_string()));
                match call_bridge(
                    "kidSstvEncode",
                    &[
                        JsValue::from_str(&url),
                        JsValue::from_str("Robot 36"),
                    ],
                )
                .await
                {
                    Some(s) if s.starts_with("blob:") => {
                        download_url(&s, "my-photo-robot36.wav");
                        msg2.set(Some(
                            "Saved my-photo-robot36.wav - play it for a friend!".to_string(),
                        ));
                    }
                    Some(s) => msg2.set(Some(s)),
                    None => msg2.set(Some(
                        "The SSTV sound maker did not load. Check the page files and try again."
                            .to_string(),
                    )),
                }
                busy2.set(false);
            });
        })
    };

    // Decode picker: read the WAV as bytes, hand them to the bridge,
    // and show the photo that comes back (or the plain error message).
    let on_decode = {
        let decoded_url = decoded_url.clone();
        let sstv_msg = sstv_msg.clone();
        Callback::from(move |e: Event| {
            let Some(target) = e.target() else {
                return;
            };
            let Ok(input) = target.dyn_into::<HtmlInputElement>() else {
                return;
            };
            let Some(files) = input.files() else {
                return;
            };
            let Some(file) = files.get(0) else {
                return;
            };
            let blob: &Blob = file.unchecked_ref();
            let Ok(promise) = blob.array_buffer() else {
                return;
            };
            let decoded2 = decoded_url.clone();
            let msg2 = sstv_msg.clone();
            wasm_bindgen_futures::spawn_local(async move {
                msg2.set(Some("Listening to the sound...".to_string()));
                let Ok(buf) = JsFuture::from(promise).await else {
                    msg2.set(Some("Could not read that WAV file.".to_string()));
                    return;
                };
                match call_bridge("kidSstvDecode", &[buf]).await {
                    Some(s) if s.starts_with("data:image") => {
                        decoded2.set(Some(s));
                        msg2.set(Some("Decoded! Here is the photo from the sound.".to_string()));
                    }
                    Some(s) => msg2.set(Some(s)),
                    None => msg2.set(Some(
                        "The SSTV decoder did not load. Check the page files and try again."
                            .to_string(),
                    )),
                }
            });
        })
    };"""
        )

    # Read-only values the HTML needs (frame counters drive re-renders).
    reads = []
    if needs["rocket"]:
        reads.append(
            """    let t = *clock.borrow();
    let _ = *frame; // frame changes drive the re-renders; t is read from the ref
    let flying = *phase == Phase::Flying;
    let done = *phase == Phase::Done;
    let p = if t <= 0.0 {
        0.0
    } else if t < 6.0 {
        t / 6.0
    } else {
        (1.0 - (t - 6.0) / 6.0).max(0.0)
    };
    let rise_pct = 55.0 * p;"""
        )
    if needs["timer"]:
        reads.append(
            """    let timer_t = *timer_clock.borrow();
    let _ = *timer_frame;
    let timer_left = timer_t.max(0.0);"""
        )
    if needs["quiz"]:
        reads.append(
            """    let quiz_q: &str = if *quiz_done { "" } else { QUIZ[*quiz_idx].0 };
    let quiz_choices: &[&str] = if *quiz_done { &[] } else { &QUIZ[*quiz_idx].1 };"""
        )

    html = []
    for b in blocks:
        kind = b.get("kind")
        if kind == "title":
            html.append(
                '        <h1>{ %s }</h1>' % rust_str(b.get("text", "My App"))
            )
        elif kind == "words":
            html.append(
                '        <p class="words">{ %s }</p>' % rust_str(b.get("text", ""))
            )
        elif kind == "picture":
            caption = clean_text(b.get("caption", "My photo"))
            if clean_text(b.get("base64jpeg")):
                html.append(
                    """        <div class="card photo">
            <p>{ %s }</p>
            { if let Some(url) = (*photo_url).clone() {
                html! { <img src={url} alt={%s} /> }
            } else {
                html! {}
            } }
        </div>"""
                    % (rust_str(caption), rust_str(caption))
                )
            else:
                html.append(
                    """        <div class="card photo">
            <label class="filebtn">{ "Take a photo" }
                <input type="file" accept="image/*" capture="environment" onchange={on_photo} />
            </label>
            <p>{ %s }</p>
            { if let Some(url) = (*photo_url).clone() {
                html! { <img src={url} alt={%s} /> }
            } else {
                html! {}
            } }
            <div>
                <button onclick={on_download_photo} disabled={photo_url.is_none()}>{ "Download my photo" }</button>
            </div>
            <p class="msg">{ (*photo_msg).clone().unwrap_or_default() }</p>
        </div>"""
                    % (rust_str(caption), rust_str(caption))
                )
        elif kind == "button":
            label = rust_str(b.get("label", "Tap me"))
            action = b.get("action", "count")
            if action == "rocket" and needs["rocket"]:
                # The rocket scene already has its own Launch button; a
                # second identical button next to it would only confuse.
                if "rocket" not in project_kinds(blocks):
                    html.append(
                        '        <button onclick={on_launch} disabled={flying}>{ %s }</button>'
                        % label
                    )
            elif action == "sound" and needs["audio"]:
                html.append(
                    """        <button onclick={{
            let audio = audio.clone();
            Callback::from(move |_: web_sys::MouseEvent| {
                play_tone(&audio, 261.63, 0.5);
                play_tone(&audio, 329.63, 0.5);
                play_tone(&audio, 392.00, 0.5);
            })
        }}>{ %s }</button>"""
                    % label
                )
            else:
                html.append(
                    '        <button onclick={on_count}>{ %s }</button>' % label
                )
        elif kind == "counter":
            label = rust_str(b.get("label", "Count"))
            if needs["quiz"] and clean_text(b.get("label", "")).lower() == "stars":
                html.append(
                    """        <div class="card">
            <p>{ %s }</p>
            <div><span class="star"></span>{ " " }<span class="big">{ *quiz_score }</span></div>
        </div>"""
                    % label
                )
            else:
                html.append(
                    """        <div class="card">
            <p>{ %s }</p>
            <div class="big">{ *count }</div>
            <button onclick={on_count}>{ "Tap to count" }</button>
        </div>"""
                    % label
                )
        elif kind == "rocket":
            html.append(
                """        <div class="scene">
            <div class="ground"></div>
            <div class="pad"></div>
            <div class="rocket" style={format!("bottom: calc(48px + {:.1}%);", rise_pct)}>
                __ROCKET_SVG__
                { if flying { html! { <div class="flame"></div> } } else { html! {} } }
            </div>
        </div>
        <p class="status">{ rocket_status(t, done) }</p>
        <p>{ format!("Flights: {}", *flights) }</p>
        <div>
            <button onclick={on_launch} disabled={flying}>{ if done { "Launch again" } else { "Launch" } }</button>
            <button onclick={on_reset_rocket} class="ghost">{ "Reset" }</button>
        </div>""".replace("__ROCKET_SVG__", ROCKET_SVG)
            )
        elif kind == "piano":
            if "##PIANO##" not in html:
                html.append("##PIANO##")
        elif kind == "quiz":
            if "##QUIZ##" not in html:
                html.append("##QUIZ##")
        elif kind == "timer":
            html.append(
                """        <div class="card">
            <p>{ "Timer" }</p>
            <div class="timer-big">{ format!("{:.0}", timer_left) }</div>
            <p>{ if *timer_running { "Counting down..." } else if timer_left <= 0.0 { "Time is up!" } else { "Press Start to count down." } }</p>
            <div>
                <button onclick={on_timer}>{ if *timer_running { "Stop" } else { "Start" } }</button>
                <button onclick={on_timer_reset} class="ghost">{ "Reset" }</button>
            </div>
        </div>"""
            )
        elif kind == "sstv":
            html.append(
                """        <div class="card sstv">
            <p>{ "Make the space sound from your photo, or turn a space sound back into a photo." }</p>
            <div>
                <button onclick={on_encode} disabled={*sstv_busy || photo_url.is_none()}>{ "Make SSTV sound" }</button>
            </div>
            <label class="filebtn">{ "Decode a WAV back" }
                <input type="file" accept="audio/wav,audio/*" onchange={on_decode} />
            </label>
            { if let Some(url) = (*decoded_url).clone() {
                html! { <div class="decoded"><img src={url} alt="Decoded photo" /></div> }
            } else {
                html! {}
            } }
            <p class="msg">{ (*sstv_msg).clone().unwrap_or_default() }</p>
        </div>"""
            )

    # Piano keys and quiz questions render once, in place of the first
    # piano / quiz block, so a keyboard of 7 blocks stays one keyboard.
    if needs["audio"] and notes:
        keys = "\n".join(
            '                <button class="key" onclick={play_note(%.2f, "%s")}>{ "%s" }</button>'
            % (PIANO_FREQS[n], n, n)
            for n in notes
        )
        piano_html = """        <div class="piano">
%s
        </div>
        <p class="msg">{ (*last_note).clone().map(|n| format!("Last note: {}", n)).unwrap_or_default() }</p>""" % keys
        html = [piano_html if h == "##PIANO##" else h for h in html]
    if needs["quiz"] and questions:
        quiz_html = """        <div class="card">
            { if *quiz_done {
                html! {
                    <>
                        <p class="feedback good">{ "You did it! You finished the quiz." }</p>
                        <p>{ format!("Stars: {}", *quiz_score) }</p>
                        <button onclick={on_quiz_again}>{ "Play again" }</button>
                    </>
                }
            } else {
                html! {
                    <>
                        <p>{ format!("Question {} of {}", *quiz_idx + 1, QUIZ.len()) }</p>
                        <p class="words">{ quiz_q }</p>
                        <div>
                            { for quiz_choices.iter().enumerate().map(|(i, c)| {
                                let a = on_answer.clone();
                                html! {
                                    <button onclick={Callback::from(move |_| a.emit(i))}>{ *c }</button>
                                }
                            }) }
                        </div>
                        <p class={if (*quiz_feedback).clone().unwrap_or_default().starts_with("Right") { "feedback good" } else { "feedback bad" }}>{ (*quiz_feedback).clone().unwrap_or_default() }</p>
                        { if *quiz_answered {
                            html! { <button onclick={on_next}>{ if *quiz_idx + 1 >= QUIZ.len() { "See my stars" } else { "Next question" } }</button> }
                        } else {
                            html! {}
                        } }
                    </>
                }
            } }
        </div>"""
        html = [quiz_html if h == "##QUIZ##" else h for h in html]

    body = "\n".join(html)
    footer = (
        '\n        <footer>{ "Kid Builder - MikeGyver Studio | Sharing is Caring" }</footer>'
    )
    main_rs = (
        RUST_HEADER
        + "\n#[function_component(App)]\nfn app() -> Html {\n"
        + "\n".join(state)
        + "\n\n"
        + "\n\n".join(cb)
        + ("\n\n" + "\n".join(reads) if reads else "")
        + "\n\n    html! {\n        <div class=\"wrap\">\n"
        + body
        + footer
        + "\n        </div>\n    }\n}\n\nfn main() {\n    yew::Renderer::<App>::new().render();\n}\n"
    )
    return main_rs

def generate_project(project):
    """Turn one project dict into {path: content} for its Yew files."""
    name = clean_text(project.get("name", "My App")) or "My App"
    slug = project.get("slug") or slugify(name)
    slug = slugify(slug)
    blocks = project.get("blocks") or []
    if not isinstance(blocks, list):
        raise ValueError("blocks must be a list")
    kinds = project_kinds(blocks)
    unknown = sorted(k for k in kinds if k not in (
        "title", "words", "picture", "button", "counter",
        "rocket", "piano", "quiz", "timer", "sstv",
    ))
    if unknown:
        raise ValueError("Unknown block kind(s): %s" % ", ".join(unknown))

    files = {}
    files["index.html"] = INDEX_HTML_TEMPLATE.replace(
        "__TITLE__", html_text(name)
    ).replace(
        "__SSTV_LINKS__", SSTV_LINKS if "sstv" in kinds else ""
    ).replace(
        "__SSTV_SCRIPTS__", SSTV_SCRIPTS if "sstv" in kinds else ""
    )
    files["styles.css"] = STYLES_CSS
    files["Cargo.toml"] = CARGO_TOML_TEMPLATE.replace("__PKG__", slug)
    files["Trunk.toml"] = TRUNK_TOML
    files["src/main.rs"] = generate_main_rs(name, blocks)
    if "sstv" in kinds:
        core_src = SSTV_CORE_SRC if SSTV_CORE_SRC.is_file() else SSTV_CORE_FALLBACK
        if not core_src.is_file():
            raise FileNotFoundError(
                "sstv-core.js not found at %s or %s - cannot build an SSTV project"
                % (SSTV_CORE_SRC, SSTV_CORE_FALLBACK)
            )
        core = core_src.read_text(encoding="utf-8")
        # The proven core carries 6 em dashes (comments + one message
        # string). Every shipped file must be plain ASCII, so swap them
        # for hyphens; the DSP code is byte-for-byte the same otherwise.
        files["sstv-core.js"] = core.replace("\u2014", "-")
        files["kid-sstv-bridge.js"] = BRIDGE_JS
    return slug, files


def ascii_check(files):
    """Return {path: count of bytes > 127} for every file."""
    result = {}
    for path, content in files.items():
        raw = content.encode("utf-8")
        result[path] = sum(1 for b in raw if b > 127)
    return result


def write_project(out_dir, slug, files):
    out = Path(out_dir) / slug
    for path, content in files.items():
        dest = out / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return out


def main(argv=None):
    out_dir = HERE / "projects"
    print("Kid Builder v1 - generating starter projects into %s" % out_dir)
    all_ok = True
    for project in STARTERS:
        slug, files = generate_project(project)
        check = ascii_check(files)
        bad = {p: n for p, n in check.items() if n}
        out = write_project(out_dir, slug, files)
        print("\n%s (%s)" % (project["name"], slug))
        for path in sorted(files):
            print("  %s (%d chars)" % (path, len(files[path])))
        if bad:
            all_ok = False
            print("  ASCII CHECK FAILED: %s" % bad)
        else:
            print("  ASCII check: OK (0 bytes above 127 in every file)")
        print("  wrote: %s" % out)
    if not all_ok:
        print("\nSome files failed the ASCII check.")
        return 1
    print("\nAll %d starter projects generated." % len(STARTERS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
