use gloo_timers::callback::Interval;
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

#[function_component(App)]
fn app() -> Html {
    let audio = use_mut_ref(|| None::<AudioContext>);
    let last_note = use_state(|| None::<String>);

    let play_note = {
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
    };

    html! {
        <div class="wrap">
        <h1>{ "Piano Notes" }</h1>
        <p class="words">{ "Hi, I am Colin! I play piano. Tap a note to hear it, then press Play a tune to hear them all together." }</p>
        <div class="piano">
                <button class="key" onclick={play_note(261.63, "C")}>{ "C" }</button>
                <button class="key" onclick={play_note(293.66, "D")}>{ "D" }</button>
                <button class="key" onclick={play_note(329.63, "E")}>{ "E" }</button>
                <button class="key" onclick={play_note(349.23, "F")}>{ "F" }</button>
                <button class="key" onclick={play_note(392.00, "G")}>{ "G" }</button>
                <button class="key" onclick={play_note(440.00, "A")}>{ "A" }</button>
                <button class="key" onclick={play_note(493.88, "B")}>{ "B" }</button>
        </div>
        <p class="msg">{ (*last_note).clone().map(|n| format!("Last note: {}", n)).unwrap_or_default() }</p>
        <button onclick={{
            let audio = audio.clone();
            Callback::from(move |_| {
                play_tone(&audio, 261.63, 0.5);
                play_tone(&audio, 329.63, 0.5);
                play_tone(&audio, 392.00, 0.5);
            })
        }}>{ "Play a tune" }</button>
        <footer>{ "Kid Builder - MikeGyver Studio | Sharing is Caring" }</footer>
        </div>
    }
}

fn main() {
    yew::Renderer::<App>::new().render();
}
