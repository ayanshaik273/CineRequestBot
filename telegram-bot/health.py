from flask import Flask, request, jsonify, render_template_string
import threading
import asyncio
import logging
from config import HEALTH_PORT as PORT, API_ID, API_HASH

logger = logging.getLogger(__name__)
app = Flask(__name__)

_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_loop_thread.start()


def run_async(coro, timeout=30):
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=timeout)


@app.route("/")
def health():
    return "Post Search Bot is running.", 200


@app.route("/health")
def healthcheck():
    return "OK", 200


_GEN_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Session Generator</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',sans-serif;background:#0d0d1a;color:#eee;
         display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
    .card{background:#12122a;border:1px solid #2a2a5a;border-radius:16px;
          padding:36px;max-width:460px;width:100%}
    h2{color:#7c6af7;margin-bottom:6px;font-size:1.5rem}
    .sub{color:#888;font-size:.88rem;margin-bottom:28px}
    label{font-size:.82rem;color:#bbb;display:block;margin-bottom:6px}
    input{width:100%;padding:12px 16px;border-radius:8px;border:1px solid #2a2a5a;
          background:#0a0a18;color:#fff;font-size:1rem;outline:none;margin-bottom:4px}
    input:focus{border-color:#7c6af7}
    button{width:100%;margin-top:14px;padding:13px;background:#7c6af7;color:#fff;
           border:none;border-radius:8px;font-size:1rem;cursor:pointer;font-weight:600}
    button:hover{background:#6a5be0}
    button:disabled{background:#333;cursor:not-allowed;color:#666}
    .step{display:none}.step.active{display:block}
    .result{background:#0a180a;border:1px solid #1a4a1a;border-radius:8px;
            padding:14px;font-size:.72rem;word-break:break-all;color:#6fff6f;
            margin-top:16px;line-height:1.6;max-height:160px;overflow-y:auto}
    .copy-btn{background:#1a5a1a;margin-top:10px}
    .copy-btn:hover{background:#155015}
    .err{color:#ff6b6b;font-size:.82rem;margin-top:8px;display:none}
    .note{font-size:.78rem;color:#777;margin-top:14px;text-align:center;line-height:1.6}
    .note b{color:#aaa}
    .badge{display:inline-block;background:#1a1a3a;border:1px solid #3a3a7a;
           border-radius:6px;padding:2px 8px;font-size:.75rem;color:#9a9af7;margin-bottom:20px}
  </style>
</head>
<body>
<div class="card">
  <h2>&#128273; Session Generator</h2>
  <div class="sub">Generate a Pyrogram session string for your Telegram account</div>

  <div class="step active" id="s1">
    <div class="badge">Step 1 of 2 &#8212; Phone Number</div>
    <label>Phone number (with country code)</label>
    <input id="phone" type="tel" placeholder="+911234567890">
    <button id="b1" onclick="sendOtp()">Send OTP &#8594;</button>
    <div class="err" id="e1"></div>
  </div>

  <div class="step" id="s2">
    <div class="badge">Step 2 of 2 &#8212; Verify OTP</div>
    <label>Enter the code you received on Telegram</label>
    <input id="otp" type="number" placeholder="12345" maxlength="6">
    <button id="b2" onclick="signIn()">Verify &amp; Get Session &#8594;</button>
    <div class="err" id="e2"></div>
  </div>

  <div class="step" id="s3">
    <div class="badge">Two-Step Verification</div>
    <label>Your Telegram 2FA password</label>
    <input id="pwd" type="password" placeholder="Password">
    <button id="b3" onclick="submit2fa()">Confirm &#8594;</button>
    <div class="err" id="e3"></div>
  </div>

  <div class="step" id="s4">
    <div class="badge" style="background:#0a180a;border-color:#1a5a1a;color:#6fff6f">&#10003; Done!</div>
    <label>Your SESSION String &#8212; copy it now</label>
    <div class="result" id="sess"></div>
    <button class="copy-btn" onclick="copy()">&#128203; Copy to Clipboard</button>
    <div class="note">
      Add this as an environment variable on Railway:<br>
      <b>Key:</b> SESSION &nbsp;|&nbsp; <b>Value:</b> the string above<br><br>
      Go to: service &#8594; Variables &#8594; New Variable<br>
      Then redeploy &#8212; search will be fully active.
    </div>
  </div>
</div>
<script>
async function api(path,body){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  return r.json();
}
function show(id){document.querySelectorAll('.step').forEach(s=>s.classList.remove('active'));document.getElementById(id).classList.add('active');}
function err(id,msg){const e=document.getElementById(id);e.textContent=msg;e.style.display='block';}

async function sendOtp(){
  const phone=document.getElementById('phone').value.trim();
  if(!phone){return err('e1','Enter your phone number');}
  document.getElementById('e1').style.display='none';
  const b=document.getElementById('b1');b.disabled=true;b.textContent='Sending\u2026';
  const res=await api('/gen/send',{phone});
  b.disabled=false;b.textContent='Send OTP \u2192';
  if(res.ok){show('s2');setTimeout(()=>document.getElementById('otp').focus(),100);}
  else err('e1',res.error||'Failed \u2014 check phone number');
}

async function signIn(){
  const code=document.getElementById('otp').value.trim();
  if(!code){return err('e2','Enter the OTP code');}
  document.getElementById('e2').style.display='none';
  const b=document.getElementById('b2');b.disabled=true;b.textContent='Verifying\u2026';
  const res=await api('/gen/signin',{code});
  b.disabled=false;b.textContent='Verify & Get Session \u2192';
  if(res.ok){document.getElementById('sess').textContent=res.session;show('s4');}
  else if(res.need2fa){show('s3');}
  else err('e2',res.error||'Wrong or expired code \u2014 go back and retry');
}

async function submit2fa(){
  const pwd=document.getElementById('pwd').value.trim();
  document.getElementById('e3').style.display='none';
  const b=document.getElementById('b3');b.disabled=true;b.textContent='Checking\u2026';
  const res=await api('/gen/2fa',{pwd});
  b.disabled=false;b.textContent='Confirm \u2192';
  if(res.ok){document.getElementById('sess').textContent=res.session;show('s4');}
  else err('e3',res.error||'Wrong password');
}

function copy(){
  navigator.clipboard.writeText(document.getElementById('sess').textContent).then(()=>{
    const b=event.target;b.textContent='Copied!';
    setTimeout(()=>{b.textContent='Copy to Clipboard';},2500);
  });
}
</script>
</body>
</html>"""

_state = {}
_pyro_client = None


@app.route("/gen")
def gen_index():
    return render_template_string(_GEN_HTML)


@app.route("/gen/send", methods=["POST"])
def gen_send():
    global _pyro_client, _state
    phone = (request.json or {}).get("phone", "").strip()
    if not phone:
        return jsonify({"ok": False, "error": "Phone number required"})

    async def _do():
        global _pyro_client
        if _pyro_client:
            try:
                await _pyro_client.disconnect()
            except Exception:
                pass
            _pyro_client = None
        from pyrogram import Client as PyroClient
        _pyro_client = PyroClient(
            "_sess_gen", api_id=API_ID, api_hash=API_HASH, in_memory=True
        )
        await _pyro_client.connect()
        sent = await _pyro_client.send_code(phone)
        return sent.phone_code_hash

    try:
        h = run_async(_do())
        _state["phone"] = phone
        _state["hash"]  = h
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/gen/signin", methods=["POST"])
def gen_signin():
    code = (request.json or {}).get("code", "").strip()
    if not code:
        return jsonify({"ok": False, "error": "Code required"})

    async def _do():
        global _pyro_client
        from pyrogram.errors import SessionPasswordNeeded
        try:
            await _pyro_client.sign_in(_state["phone"], _state["hash"], code)
        except SessionPasswordNeeded:
            return None, True
        s = await _pyro_client.export_session_string()
        # Disconnect cleanly — session string is already captured above
        try:
            await _pyro_client.disconnect()
        except Exception:
            pass
        _pyro_client = None
        return s, False

    try:
        session, need2fa = run_async(_do())
        if need2fa:
            return jsonify({"ok": False, "need2fa": True})
        return jsonify({"ok": True, "session": session})
    except Exception as e:
        err_str = str(e)
        if "PHONE_CODE_EXPIRED" in err_str:
            return jsonify({"ok": False, "error": "Code expired — go back and request a new one"})
        if "PHONE_CODE_INVALID" in err_str or "CODE_INVALID" in err_str:
            return jsonify({"ok": False, "error": "Wrong code — check and try again"})
        return jsonify({"ok": False, "error": err_str})


@app.route("/gen/2fa", methods=["POST"])
def gen_2fa():
    pwd = (request.json or {}).get("pwd", "").strip()
    if not pwd:
        return jsonify({"ok": False, "error": "Password required"})

    async def _do():
        global _pyro_client
        await _pyro_client.check_password(pwd)
        s = await _pyro_client.export_session_string()
        # Disconnect cleanly — session string is already captured above
        try:
            await _pyro_client.disconnect()
        except Exception:
            pass
        _pyro_client = None
        return s

    try:
        session = run_async(_do())
        return jsonify({"ok": True, "session": session})
    except Exception as e:
        err_str = str(e)
        if "PASSWORD_HASH_INVALID" in err_str:
            return jsonify({"ok": False, "error": "Wrong password"})
        return jsonify({"ok": False, "error": err_str})


def run_health_server():
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)


def start_health_server():
    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()
    logger.info(f"Health server on port {PORT} — session generator at /gen")
