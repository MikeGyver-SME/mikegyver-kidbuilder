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
    let count = use_state(|| 0i32);
    let phase = use_state(|| Phase::Ready);
    let flights = use_state(|| 0i32);
    let clock = use_mut_ref(|| 0.0f64);
    let frame = use_state(|| 0u32);
    let interval = use_mut_ref(|| None::<Interval>);

    let on_count = {
        let count = count.clone();
        Callback::from(move |_| count.set(*count + 1))
    };

    // Stop the flight ticker once the rocket has landed.
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
    };

    let t = *clock.borrow();
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
    let rise_pct = 55.0 * p;

    html! {
        <div class="wrap">
        <h1>{ "My Rocket Launch" }</h1>
        <p class="words">{ "Hi, I am Colin! Press Launch and watch my rocket fly up into the sky and come back down." }</p>
        <div class="scene">
            <div class="ground"></div>
            <div class="pad"></div>
            <div class="rocket" style={format!("bottom: calc(48px + {:.1}%);", rise_pct)}>
                <svg viewBox="0 0 120 200" width="72" height="120">
<path d="M60,6 C78,32 88,56 88,82 L32,82 C32,56 42,32 60,6 Z" fill="#f2f2f2" stroke="#222" stroke-width="2" />
<rect x="32" y="82" width="56" height="12" fill="#1a1a1a" />
<rect x="32" y="94" width="56" height="76" fill="#f5f5f5" stroke="#bbb" stroke-width="1" />
<circle cx="60" cy="118" r="7" fill="#9fd8ff" stroke="#222" stroke-width="2" />
<path d="M32,166 L14,198 L32,192 Z" fill="#1a1a1a" />
<path d="M88,166 L106,198 L88,192 Z" fill="#1a1a1a" />
</svg>
                { if flying { html! { <div class="flame"></div> } } else { html! {} } }
            </div>
        </div>
        <p class="status">{ rocket_status(t, done) }</p>
        <p>{ format!("Flights: {}", *flights) }</p>
        <div>
            <button onclick={on_launch} disabled={flying}>{ if done { "Launch again" } else { "Launch" } }</button>
            <button onclick={on_reset_rocket} class="ghost">{ "Reset" }</button>
        </div>
        <div class="card">
            <p>{ "Flights" }</p>
            <div class="big">{ *count }</div>
            <button onclick={on_count}>{ "Tap to count" }</button>
        </div>
        <footer>{ "Kid Builder - MikeGyver Studio | Sharing is Caring" }</footer>
        </div>
    }
}

fn main() {
    yew::Renderer::<App>::new().render();
}
