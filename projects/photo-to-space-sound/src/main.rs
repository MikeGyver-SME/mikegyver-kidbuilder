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
    let photo_url = use_state(|| None::<String>);
    let photo_msg = use_state(|| None::<String>);
    let decoded_url = use_state(|| None::<String>);
    let sstv_msg = use_state(|| None::<String>);
    let sstv_busy = use_state(|| false);

    // Photo picker: read the file, draw it small (320x240) on a
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
        Callback::from(move |_: web_sys::MouseEvent| {
            if let Some(url) = (*photo_url).clone() {
                download_url(&url, "my-photo.png");
            }
        })
    };

    let on_encode = {
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
    };

    html! {
        <div class="wrap">
        <h1>{ "Photo to Space Sound" }</h1>
        <p class="words">{ "Turn your photo into space sound, and turn space sound back into a photo. Robot 36." }</p>
        <p class="words">{ "Astronauts on the Space Station send photos this way. Your photo becomes a funny squeaky sound, and the sound can become a photo again." }</p>
        <div class="card photo">
            <label class="filebtn">{ "Take a photo" }
                <input type="file" accept="image/*" capture="environment" onchange={on_photo} />
            </label>
            <p>{ "My photo for space" }</p>
            { if let Some(url) = (*photo_url).clone() {
                html! { <img src={url} alt={"My photo for space"} /> }
            } else {
                html! {}
            } }
            <div>
                <button onclick={on_download_photo} disabled={photo_url.is_none()}>{ "Download my photo" }</button>
            </div>
            <p class="msg">{ (*photo_msg).clone().unwrap_or_default() }</p>
        </div>
        <div class="card sstv">
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
        </div>
        <footer>{ "Kid Builder - MikeGyver Studio | Sharing is Caring" }</footer>
        </div>
    }
}

fn main() {
    yew::Renderer::<App>::new().render();
}
