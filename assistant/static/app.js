// Nerdio setup chat. The server is stateless: the transcript and answers live in this tab.
(() => {
  const KEY = "nerdio-setup-v1";
  const log = document.getElementById("log");
  const form = document.getElementById("ask");
  const text = document.getElementById("text");
  const send = document.getElementById("send");
  let state = load();

  function load() {
    try { return JSON.parse(sessionStorage.getItem(KEY)) || fresh(); } catch { return fresh(); }
  }
  function fresh() { return { messages: [], answers: {}, view: [] }; }
  function save() { try { sessionStorage.setItem(KEY, JSON.stringify(state)); } catch { /* private mode */ } }

  function escape(s) {
    return s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function inline(s) {
    return escape(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([^\]]+)\]\((https:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  }
  // A small, safe Markdown subset: paragraphs, bullet lists, code fences, inline code, bold, https links.
  function render(md) {
    const out = [];
    const parts = md.split(/```[a-z]*\n?/);
    parts.forEach((part, i) => {
      if (i % 2 === 1) { out.push(`<pre><button type="button" class="copy">Copy</button><code>${escape(part.replace(/\n$/, ""))}</code></pre>`); return; }
      part.split(/\n{2,}/).forEach(block => {
        const lines = block.split("\n").filter(l => l.trim());
        if (!lines.length) return;
        if (lines.every(l => /^\s*[-*] /.test(l))) {
          out.push("<ul>" + lines.map(l => `<li>${inline(l.replace(/^\s*[-*] /, ""))}</li>`).join("") + "</ul>");
        } else {
          out.push(`<p>${lines.map(inline).join("<br>")}</p>`);
        }
      });
    });
    return out.join("");
  }

  function show(role, body) {
    const div = document.createElement("div");
    div.className = "msg " + role;
    if (role === "bot") div.innerHTML = render(body); else div.textContent = body;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  log.addEventListener("click", e => {
    if (!e.target.classList.contains("copy")) return;
    const code = e.target.parentElement.querySelector("code").textContent;
    navigator.clipboard.writeText(code).then(() => { e.target.textContent = "Copied"; setTimeout(() => e.target.textContent = "Copy", 1500); });
  });

  form.addEventListener("submit", async e => {
    e.preventDefault();
    const said = text.value.trim();
    if (!said) return;
    text.value = "";
    send.disabled = true;
    show("me", said);
    state.view.push(["me", said]);
    const waiting = show("bot typing", "Thinking…");
    try {
      const res = await fetch("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: said, messages: state.messages, answers: state.answers }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.statusText);
      state.messages = data.messages;
      state.answers = data.answers;
      waiting.remove();
      show("bot", data.reply || "(no reply)");
      state.view.push(["bot", data.reply || ""]);
      save();
    } catch (err) {
      waiting.remove();
      show("bot err", "Something went wrong: " + err.message);
      state.view.pop();
      text.value = said;
    } finally {
      send.disabled = false;
      text.focus();
    }
  });

  text.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
  });

  document.getElementById("reset").addEventListener("click", () => {
    if (!confirm("Start a new conversation? Your answers in this tab will be cleared.")) return;
    state = fresh(); save(); log.innerHTML = "";
  });

  fetch("/api/me").then(r => r.json()).then(d => { if (d.name) document.getElementById("who").textContent = d.name; }).catch(() => {});
  state.view.forEach(([role, body]) => show(role, body));
})();
