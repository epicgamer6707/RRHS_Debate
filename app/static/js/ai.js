// ── In-browser AI (free, no server cost) ────────────────────────────────────
// Loads a small open-source model into the visitor's own browser via WebGPU
// (MLC WebLLM) and runs inference locally. First load downloads/caches the
// model (~1GB); after that it's fast. No API key, no per-request cost.
// Pinned, exact version from jsDelivr so the third-party code can never change
// underneath us. Bump deliberately if upgrading.
const WEBLLM_URL = "https://cdn.jsdelivr.net/npm/@mlc-ai/web-llm@0.2.79/+esm";
// 1B model: small download (~0.8GB) and fast on a school laptop. Plenty for
// turning requests into search keywords and explaining evidence.
const MODEL_ID = "Llama-3.2-1B-Instruct-q4f16_1-MLC";

let _enginePromise = null;
let _statusEls = [];

function _setStatus(msg) {
    _statusEls.forEach(el => { if (el) el.textContent = msg; });
}

async function _getEngine() {
    if (_enginePromise) return _enginePromise;
    _enginePromise = (async () => {
        _setStatus("Loading AI model (first time only, ~1-2 min)...");
        const webllm = await import(WEBLLM_URL);
        const engine = new webllm.MLCEngine();
        engine.setInitProgressCallback(p => _setStatus(p.text || "Loading AI model..."));
        await engine.reload(MODEL_ID);
        _setStatus("");
        return engine;
    })();
    return _enginePromise;
}

window.RRHSAI = {
    supported() { return typeof navigator !== "undefined" && !!navigator.gpu; },
    bindStatus(el) { if (el) _statusEls.push(el); },
    async ask(prompt, system) {
        if (!this.supported()) {
            throw new Error("In-browser AI needs a WebGPU browser (Chrome or Edge on a computer).");
        }
        const engine = await _getEngine();
        const messages = [];
        if (system) messages.push({ role: "system", content: system });
        messages.push({ role: "user", content: prompt });
        const reply = await engine.chat.completions.create({ messages, temperature: 0.4 });
        return reply.choices[0].message.content;
    },
};
