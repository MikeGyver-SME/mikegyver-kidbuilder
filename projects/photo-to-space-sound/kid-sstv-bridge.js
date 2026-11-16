// Kid Builder SSTV bridge - plain JavaScript, no build step.
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
