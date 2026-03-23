LANDING_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>TicketSwap → Calendar</title>
<style>
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

  :root{
    --font:-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text","Helvetica Neue",Arial,sans-serif;
    --mono:"SF Mono","Menlo","Courier New",monospace;
    --bg:#f5f5f7; --surface:#ffffff; --surface-2:#f5f5f7; --border:#d2d2d7;
    --text:#1d1d1f; --text-secondary:#6e6e73; --text-tertiary:#86868b;
    --accent:#0071e3; --accent-hover:#0077ed; --accent-text:#ffffff;
    --error:#ff3b30;
    --shadow-sm:0 1px 3px rgba(0,0,0,.08),0 1px 2px rgba(0,0,0,.06);
    --shadow-md:0 4px 16px rgba(0,0,0,.10),0 1px 4px rgba(0,0,0,.06);
    --radius-sm:8px; --radius-md:12px; --radius-lg:18px; --radius-pill:980px;
  }

  @media(prefers-color-scheme:dark){
    :root{
      --bg:#000000; --surface:#1c1c1e; --surface-2:#2c2c2e; --border:#3a3a3c;
      --text:#f5f5f7; --text-secondary:#aeaeb2; --text-tertiary:#636366;
      --accent:#0a84ff; --accent-hover:#409cff;
      --shadow-sm:0 1px 3px rgba(0,0,0,.3);
      --shadow-md:0 4px 20px rgba(0,0,0,.5);
    }
  }

  html{font-family:var(--font);background:var(--bg);color:var(--text);
    line-height:1.47059;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}
  body{min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:2rem 1rem}

  .container{max-width:680px;width:100%;margin-top:clamp(3rem,12vh,9rem)}

  h1{font-size:clamp(1.8rem,4.5vw,2.6rem);font-weight:700;letter-spacing:-.025em;
    line-height:1.1;margin-bottom:.75rem}
  h1 span{color:var(--accent)}
  .subtitle{color:var(--text-secondary);font-size:1.0625rem;margin-bottom:2.5rem;
    max-width:46ch;line-height:1.6;font-weight:400}

  .input-group{display:flex;gap:.625rem;margin-bottom:.5rem}
  input[type="url"]{flex:1;background:var(--surface);border:1px solid var(--border);
    border-radius:var(--radius-md);padding:.75rem 1rem;color:var(--text);font-size:.9375rem;
    font-family:var(--mono);outline:none;box-shadow:var(--shadow-sm);
    transition:border-color .2s ease,box-shadow .2s ease}
  input[type="url"]:focus{border-color:var(--accent);
    box-shadow:0 0 0 3px rgba(0,113,227,.25)}
  input[type="url"]::placeholder{color:var(--text-tertiary)}

  button{background:var(--accent);color:var(--accent-text);border:none;
    border-radius:var(--radius-pill);padding:.75rem 1.375rem;font-size:.9375rem;
    font-weight:600;font-family:var(--font);letter-spacing:-.01em;cursor:pointer;
    white-space:nowrap;-webkit-user-select:none;user-select:none;
    transition:background .15s ease,transform .1s ease}
  button:hover{background:var(--accent-hover)}
  button:active{transform:scale(.97)}
  button:disabled{opacity:.4;cursor:not-allowed;transform:none}

  .error{color:var(--error);font-size:.8125rem;min-height:1.25em;
    margin-bottom:.5rem;padding-left:.25rem}

  .result{background:var(--surface);border:1px solid var(--border);
    border-radius:var(--radius-lg);padding:1.5rem;display:none;
    box-shadow:var(--shadow-md);
    animation:slideUp .3s cubic-bezier(.25,.46,.45,.94)}
  .result.show{display:block}
  .result h2{font-size:.6875rem;font-weight:600;color:var(--text-secondary);
    text-transform:uppercase;letter-spacing:.08em;margin-bottom:.75rem}

  .feed-url{background:var(--surface-2);border:1px solid var(--border);
    border-radius:var(--radius-md);padding:.75rem 1rem;font-family:var(--mono);
    font-size:.8125rem;color:var(--accent);margin-bottom:.75rem;cursor:pointer;
    display:flex;align-items:center;justify-content:space-between;gap:.75rem;
    transition:background .15s ease}
  .feed-url:hover{background:var(--border)}
  .url-text{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
  .copy-hint{flex-shrink:0;font-size:.75rem;color:var(--text-tertiary);
    font-family:var(--font);font-weight:500;transition:color .15s}
  .feed-url:hover .copy-hint{color:var(--accent)}

  .instructions{color:var(--text-secondary);font-size:.875rem;line-height:1.6;
    padding-left:1.25rem}
  .instructions li{margin-bottom:.5rem}
  .instructions strong{color:var(--text);font-weight:600}
  .instructions code{font-family:var(--mono);font-size:.8125rem;color:var(--text);
    background:var(--surface-2);padding:.1em .4em;border-radius:4px;
    border:1px solid var(--border)}

  footer{margin-top:auto;padding-top:3rem;color:var(--text-tertiary);
    font-size:.75rem;text-align:center}
  footer a{color:inherit;text-decoration:underline}

  @keyframes slideUp{
    from{opacity:0;transform:translateY(12px)}
    to{opacity:1;transform:translateY(0)}
  }
</style>
</head>
<body>

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
      <span class="url-text" id="webcal-text"></span>
      <span class="copy-hint">copy</span>
    </div>

    <div class="feed-url" id="https-url" onclick="copyUrl('https')" title="Click to copy">
      <span class="url-text" id="https-text"></span>
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

<footer>Not affiliated with TicketSwap. Built by <a href="https://www.linkedin.com/in/nysjorn/" target="_blank" rel="noopener noreferrer">Jorn</a>.</footer>

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
  btn.textContent = 'Loading\u2026';

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
