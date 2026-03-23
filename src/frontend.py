LANDING_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>TicketSwap → Calendar</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,700;1,9..40,400&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  :root{
    --bg:#0b0c10; --surface:#151820; --border:#252a36;
    --text:#e4e6ec; --muted:#8a8fa0; --accent:#00d4aa;
    --accent-dim:#00d4aa22; --error:#f05e5e; --font:'DM Sans',sans-serif;
    --mono:'DM Mono',monospace;
  }
  html{font-family:var(--font);background:var(--bg);color:var(--text);line-height:1.6}
  body{min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:2rem 1rem}

  .grain{position:fixed;inset:0;pointer-events:none;opacity:.035;
    background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  }

  .container{max-width:520px;width:100%;margin-top:clamp(2rem,10vh,8rem)}

  h1{font-size:clamp(1.6rem,4vw,2.2rem);font-weight:700;letter-spacing:-.03em;
    line-height:1.15;margin-bottom:.5rem}
  h1 span{color:var(--accent)}
  .subtitle{color:var(--muted);font-size:.95rem;margin-bottom:2.5rem;max-width:38ch}

  .input-group{display:flex;gap:.5rem;margin-bottom:1rem}
  input[type="url"]{flex:1;background:var(--surface);border:1px solid var(--border);
    border-radius:10px;padding:.75rem 1rem;color:var(--text);font-size:.9rem;
    font-family:var(--mono);outline:none;transition:border-color .2s}
  input[type="url"]:focus{border-color:var(--accent)}
  input[type="url"]::placeholder{color:var(--muted);opacity:.6}

  button{background:var(--accent);color:var(--bg);border:none;border-radius:10px;
    padding:.75rem 1.5rem;font-size:.9rem;font-weight:600;cursor:pointer;
    font-family:var(--font);white-space:nowrap;transition:opacity .15s}
  button:hover{opacity:.85}
  button:disabled{opacity:.5;cursor:not-allowed}

  .error{color:var(--error);font-size:.82rem;margin-bottom:1rem;min-height:1.2em}

  .result{background:var(--surface);border:1px solid var(--border);border-radius:14px;
    padding:1.5rem;display:none;animation:fadeIn .3s ease}
  .result.show{display:block}
  .result h2{font-size:.85rem;color:var(--muted);font-weight:500;
    text-transform:uppercase;letter-spacing:.06em;margin-bottom:1rem}
  .feed-url{background:var(--bg);border:1px solid var(--border);border-radius:8px;
    padding:.65rem .85rem;font-family:var(--mono);font-size:.78rem;color:var(--accent);
    word-break:break-all;margin-bottom:1rem;position:relative;cursor:pointer;
    transition:background .15s}
  .feed-url:hover{background:#0d0e13}
  .feed-url .copy-hint{position:absolute;right:.6rem;top:50%;transform:translateY(-50%);
    font-size:.7rem;color:var(--muted);font-family:var(--font)}

  .instructions{color:var(--muted);font-size:.82rem;line-height:1.7}
  .instructions li{margin-bottom:.35rem}
  .instructions code{font-family:var(--mono);color:var(--text);font-size:.78rem;
    background:var(--bg);padding:.15em .4em;border-radius:4px}

  footer{margin-top:auto;padding-top:3rem;color:var(--muted);font-size:.75rem;
    text-align:center;opacity:.5}

  @keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
</style>
</head>
<body>
<div class="grain"></div>

<div class="container">
  <h1>TicketSwap → <span>Calendar</span></h1>
  <p class="subtitle">
    Paste your TicketSwap calendar URL and get an ICS feed you can subscribe to in iOS, Google Calendar, or Outlook.
  </p>

  <div class="input-group">
    <input type="url" id="url-input"
           placeholder="https://www.ticketswap.be/user/.../events-calendar"
           spellcheck="false" autocomplete="off"/>
    <button id="submit-btn" onclick="handleSubmit()">Get feed</button>
  </div>
  <div class="error" id="error"></div>

  <div class="result" id="result">
    <h2>Your ICS feed</h2>

    <div class="feed-url" id="webcal-url" onclick="copyUrl('webcal')" title="Click to copy">
      <span id="webcal-text"></span>
      <span class="copy-hint">copy</span>
    </div>

    <div class="feed-url" id="https-url" onclick="copyUrl('https')" title="Click to copy">
      <span id="https-text"></span>
      <span class="copy-hint">copy</span>
    </div>

    <h2 style="margin-top:1.25rem">How to subscribe</h2>
    <ol class="instructions">
      <li><strong>iPhone/iPad:</strong> Go to <code>Settings</code> → <code>Calendar</code> → <code>Accounts</code> → <code>Add Account</code> → <code>Other</code> → <code>Add Subscribed Calendar</code> → paste the <code>webcal://</code> URL.</li>
      <li><strong>Google Calendar:</strong> Other calendars → <code>From URL</code> → paste the <code>https://</code> URL.</li>
      <li><strong>Outlook:</strong> Add calendar → <code>Subscribe from web</code> → paste the <code>https://</code> URL.</li>
    </ol>
  </div>
</div>

<footer>Not affiliated with TicketSwap. Built by <a href="https://www.linkedin.com/in/nysjorn/" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:underline">Jorn</a>.</footer>

<script>
const inp = document.getElementById('url-input');
const btn = document.getElementById('submit-btn');
const err = document.getElementById('error');
const res = document.getElementById('result');

let feedUrls = {};

async function handleSubmit() {
  err.textContent = '';
  res.classList.remove('show');
  btn.disabled = true;
  btn.textContent = 'Loading…';

  try {
    const resp = await fetch('/api/register', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ ticketswap_url: inp.value.trim() })
    });
    let data;
    try {
      data = await resp.json();
    } catch (_) {
      const text = await resp.text().catch(() => '');
      throw new Error(`${resp.status}: ${text || 'Something went wrong'}`);
    }
    if (!resp.ok) throw new Error(data.detail || `${resp.status}: Something went wrong`);

    feedUrls = { webcal: data.webcal_url, https: data.ics_url };
    document.getElementById('webcal-text').textContent = data.webcal_url;
    document.getElementById('https-text').textContent = data.ics_url;
    res.classList.add('show');
  } catch (e) {
    err.textContent = e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Get feed';
  }
}

function copyUrl(type) {
  const url = feedUrls[type];
  if (!url) return;
  const el = document.getElementById(type === 'webcal' ? 'webcal-url' : 'https-url');
  const hint = el.querySelector('.copy-hint');
  navigator.clipboard.writeText(url).then(() => {
    hint.textContent = 'copied!';
    setTimeout(() => hint.textContent = 'copy', 1500);
  }).catch(() => {
    hint.textContent = 'failed!';
    setTimeout(() => hint.textContent = 'copy', 1500);
  });
}

inp.addEventListener('keydown', e => { if (e.key === 'Enter') handleSubmit(); });
</script>
</body>
</html>
"""
