use gloo_timers::callback::Interval;
use js_sys::JsValue;
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
    let quiz_idx = use_state(|| 0usize);
    let quiz_score = use_state(|| 0i32);
    let quiz_feedback = use_state(|| None::<String>);
    let quiz_answered = use_state(|| false);
    let quiz_done = use_state(|| false);

    const QUIZ: [(&str, [&str; 3], usize); 5] = [
        ("What is 1?", ["1", "2", "3"], 0),
        ("What is 1 + 3?", ["3", "4", "5"], 1),
        ("What is 1 + 3 + 5?", ["8", "9", "10"], 1),
        ("What is 1 + 3 + 5 + 7?", ["15", "16", "17"], 1),
        ("What is 1 + 3 + 5 + 7 + 9?", ["24", "25", "26"], 1)
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
                quiz_feedback.set(Some("Right! That makes a square number.".to_string()));
                quiz_answered.set(true);
            } else {
                quiz_feedback.set(Some("Not quite - count the stars and try again.".to_string()));
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
    };

    let quiz_q: &str = if *quiz_done { "" } else { QUIZ[*quiz_idx].0 };
    let quiz_choices: &[&str] = if *quiz_done { &[] } else { &QUIZ[*quiz_idx].1 };

    html! {
        <div class="wrap">
        <h1>{ "Counting Stars Quiz" }</h1>
        <p class="words">{ "Odd numbers are magic. Add them up and you get square numbers! Try the quiz." }</p>
        <div class="card">
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
        </div>
        <div class="card">
            <p>{ "Stars" }</p>
            <div><span class="star"></span>{ " " }<span class="big">{ *quiz_score }</span></div>
        </div>
        <footer>{ "Kid Builder - MikeGyver Studio | Sharing is Caring" }</footer>
        </div>
    }
}

fn main() {
    yew::Renderer::<App>::new().render();
}
