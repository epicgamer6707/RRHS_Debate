// ── In-browser AI (free, no server cost) ────────────────────────────────────
// Loads a small open-source model into the visitor's own browser via WebGPU
// (MLC WebLLM) and runs inference locally. No API key, no per-request cost.
// Pinned, exact version from jsDelivr so the third-party code can't change.
const WEBLLM_URL = "https://cdn.jsdelivr.net/npm/@mlc-ai/web-llm@0.2.79/+esm";

// Prefer a small, fast model, but fall back to whatever this WebLLM version
// actually ships — hardcoding one exact id is fragile across versions.
const PREFERRED = [
    /Llama-3\.2-1B-Instruct-q4f16_1/i,
    /Llama-3\.2-1B-Instruct/i,
    /Qwen2\.5-1\.5B-Instruct/i,
    /Llama-3\.1-8B-Instruct-q4f16_1/i,
];

let _enginePromise = null;
let _statusEls = [];

function _setStatus(msg) {
    _statusEls.forEach(el => { if (el) el.textContent = msg; });
}

function _pickModel(webllm) {
    const ids = (webllm.prebuiltAppConfig && webllm.prebuiltAppConfig.model_list || [])
        .map(m => m.model_id);
    for (const re of PREFERRED) {
        const hit = ids.find(id => re.test(id));
        if (hit) return hit;
    }
    // last resort: any small instruct model, else the first available
    return ids.find(id => /1B|1\.5B/i.test(id) && /Instruct/i.test(id)) || ids[0];
}

async function _getEngine() {
    if (_enginePromise) return _enginePromise;
    _enginePromise = (async () => {
        _setStatus("Loading AI model (first time only)…");
        let webllm;
        try {
            webllm = await import(WEBLLM_URL);
        } catch (e) {
            throw new Error("Couldn't load the AI library (network/CDN blocked).");
        }
        const modelId = _pickModel(webllm);
        if (!modelId) throw new Error("No compatible AI model found.");
        const engine = new webllm.MLCEngine();
        engine.setInitProgressCallback(p => _setStatus(p.text || "Loading AI model…"));
        await engine.reload(modelId);
        _setStatus("");
        return engine;
    })();
    _enginePromise.catch(() => { _enginePromise = null; });  // allow retry after failure
    return _enginePromise;
}

window.RRHSAI = {
    supported() { return typeof navigator !== "undefined" && !!navigator.gpu; },
    bindStatus(el) { if (el && !_statusEls.includes(el)) _statusEls.push(el); },
    // onToken(partialText) is called as tokens stream in (optional).
    async ask(prompt, system, onToken) {
        if (!this.supported()) {
            throw new Error("In-browser AI needs WebGPU — use Chrome or Edge on a computer (not a phone or Safari).");
        }
        const engine = await _getEngine();
        const messages = [];
        if (system) messages.push({ role: "system", content: system });
        messages.push({ role: "user", content: prompt });

        let full = "";
        try {
            const chunks = await engine.chat.completions.create({
                messages, temperature: 0.4, stream: true,
            });
            for await (const chunk of chunks) {
                const delta = (chunk.choices && chunk.choices[0] && chunk.choices[0].delta
                    && chunk.choices[0].delta.content) || "";
                if (delta) { full += delta; if (onToken) onToken(full); }
            }
        } catch (streamErr) {
            // Some setups don't support streaming — fall back to one-shot.
            const reply = await engine.chat.completions.create({ messages, temperature: 0.4 });
            full = (reply.choices && reply.choices[0] && reply.choices[0].message
                && reply.choices[0].message.content) || "";
            if (full && onToken) onToken(full);
        }
        full = (full || "").trim();
        if (!full) throw new Error("The model finished but returned no text. Try again.");
        return full;
    },
};
