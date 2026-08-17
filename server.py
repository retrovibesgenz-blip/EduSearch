from flask import Flask, request, Response, send_from_directory, redirect
import requests as req
from urllib.parse import urljoin, quote, urlparse, parse_qs, unquote
import re
import html as htmllib

app = Flask(__name__, static_folder=".", static_url_path="")

S = req.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "DNT": "1",
})

STRIP = {
    "content-encoding", "transfer-encoding", "connection", "content-length",
    "content-security-policy", "content-security-policy-report-only",
    "x-frame-options", "x-content-type-options", "strict-transport-security",
    "cross-origin-opener-policy", "cross-origin-embedder-policy",
    "cross-origin-resource-policy", "permissions-policy",
    "x-xss-protection", "report-to", "nel",
}

INJECT = """<script>(function(){
if(window.__eduproxy) return; window.__eduproxy=1;
var _P=window.parent;
try{Object.defineProperty(window,'top',{get:function(){return window.self},configurable:true})}catch(e){}
try{Object.defineProperty(window,'parent',{get:function(){return window.self},configurable:true})}catch(e){}
var P='/proxy?url=';
function px(u){
  if(!u||u.indexOf('/proxy?url=')!==-1) return u;
  if(/^https?:\\/\\//.test(u)) return P+encodeURIComponent(u);
  return u;
}
var _fetch=window.fetch;
window.fetch=function(input,opts){
  try{
    if(typeof input==='string') input=px(input);
    else if(input&&input.url) input=new Request(px(input.url),input);
  }catch(e){}
  return _fetch.call(this,input,opts);
};
var _xopen=XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open=function(){
  try{if(typeof arguments[1]==='string') arguments[1]=px(arguments[1]);}catch(e){}
  return _xopen.apply(this,arguments);
};
var BASE=document.querySelector('base');
var baseHref=BASE?BASE.href:'';
function resolve(href){
  if(!href) return null;
  if(/^(javascript:|data:|blob:|mailto:|tel:|#)/.test(href)) return null;
  try{return new URL(href,baseHref||location.href).href;}catch(e){return null;}
}
document.addEventListener('click',function(e){
  var a=e.target.closest('a');
  if(!a)return;
  var raw=a.getAttribute('href');
  if(!raw||raw.startsWith('#')||raw.startsWith('javascript:'))return;
  var url=resolve(raw);
  if(url&&/^https?:/.test(url)){
    e.preventDefault();e.stopPropagation();
    _P.postMessage({t:'nav',url:url},'*');
  }
},true);
document.addEventListener('submit',function(e){
  var f=e.target;
  if(f.tagName!=='FORM')return;
  e.preventDefault();e.stopPropagation();
  try{
    var act=f.getAttribute('action')||'';
    var u=new URL(act,baseHref||location.href);
    if(f.method.toUpperCase()==='GET'){
      new FormData(f).forEach(function(v,k){u.searchParams.set(k,v)});
    }
    _P.postMessage({t:'nav',url:u.toString()},'*');
  }catch(ex){}
},true);
})();</script>
"""

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/script.js")
def script():
    return send_from_directory(".", "script.js", mimetype="application/javascript")

@app.route("/search")
def search_page():
    q = request.args.get("q", "").strip()
    if not q:
        return redirect("/")

    results = []
    try:
        from bs4 import BeautifulSoup
        r = S.get("https://html.duckduckgo.com/html/", params={"q": q}, timeout=10, verify=False)
        soup = BeautifulSoup(r.text, "html.parser")
        for el in soup.select(".result"):
            if "result--ad" in (el.get("class") or []):
                continue
            a = el.select_one(".result__a")
            snip = el.select_one(".result__snippet")
            disp = el.select_one(".result__url")
            if not a:
                continue
            href = a.get("href", "")
            if href.startswith("//"):
                href = "https:" + href
            if "duckduckgo.com/l/" in href:
                p = urlparse(href)
                qs = parse_qs(p.query)
                if "uddg" in qs:
                    href = unquote(qs["uddg"][0])
            if not href.startswith("http"):
                continue
            try:
                domain = urlparse(href).hostname or ""
            except Exception:
                domain = ""
            results.append({
                "title": a.get_text(strip=True),
                "url": href,
                "snippet": snip.get_text(strip=True) if snip else "",
                "display": disp.get_text(strip=True) if disp else domain,
                "domain": domain,
            })
    except ImportError:
        return _search_fallback(q)
    except Exception:
        pass

    return _render_search(q, results)


def _search_fallback(q):
    return redirect(f"/proxy?url=https://html.duckduckgo.com/html/?q={quote(q)}")


def _render_search(q, results):
    q_esc = htmllib.escape(q)

    rows = []
    for r in results:
        title = htmllib.escape(r["title"])
        url_esc = htmllib.escape(r["url"])
        snip = htmllib.escape(r["snippet"])
        disp = htmllib.escape(r["display"])
        domain = htmllib.escape(r["domain"])
        fav = f"https://www.google.com/s2/favicons?domain={domain}&sz=16"
        rows.append(
            f'<div class="res">'
            f'<div class="res-top"><img class="fav" src="{fav}" width="16" height="16" onerror="this.style.display=\'none\'"><span class="res-dom">{disp}</span></div>'
            f'<a class="res-t" href="#" data-u="{url_esc}">{title}</a>'
            f'<p class="res-s">{snip}</p>'
            f'</div>'
        )

    body = "\n".join(rows) if rows else '<p class="nores">No results found — try different keywords.</p>'
    count = f'<p class="count">About {len(results)} results</p>' if results else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EduSearch – {q_esc}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#fafbfc;color:#111827;min-height:100vh}}
.hdr{{display:flex;align-items:center;gap:14px;padding:10px 20px;background:#fff;border-bottom:1px solid #e5e7eb;position:sticky;top:0;z-index:10;box-shadow:0 1px 4px rgba(0,0,0,.04)}}
.logo{{font-size:20px;font-weight:800;letter-spacing:-.5px;cursor:pointer;white-space:nowrap;flex-shrink:0}}
.logo span{{color:#4f46e5}}
.sbox{{display:flex;flex:1;max-width:580px;background:#f3f4f6;border:1.5px solid #e5e7eb;border-radius:24px;overflow:hidden;transition:border-color .15s,box-shadow .15s,background .15s}}
.sbox:focus-within{{border-color:#4f46e5;box-shadow:0 0 0 3px rgba(79,70,229,.1);background:#fff}}
.sbox input{{flex:1;padding:9px 16px;background:none;border:none;outline:none;font-size:14px;color:#111827;min-width:0}}
.sbox button{{padding:8px 18px;background:#4f46e5;color:#fff;border:none;cursor:pointer;font-size:13px;font-weight:600;border-radius:0 24px 24px 0;transition:background .12s;flex-shrink:0}}
.sbox button:hover{{background:#6366f1}}
.wrap{{max-width:660px;margin:0 auto;padding:18px 20px}}
.count{{font-size:12px;color:#9ca3af;margin-bottom:18px}}
.res{{margin-bottom:22px}}
.res-top{{display:flex;align-items:center;gap:7px;margin-bottom:2px}}
.fav{{border-radius:2px;flex-shrink:0}}
.res-dom{{font-size:12px;color:#6b7280;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.res-t{{display:block;font-size:17px;font-weight:500;color:#1a0dab;line-height:1.3;margin-bottom:4px;cursor:pointer}}
.res-t:hover{{text-decoration:underline}}
.res-s{{font-size:13px;color:#4d5156;line-height:1.6}}
.nores{{color:#6b7280;padding:32px 0;font-size:15px}}
</style>
</head>
<body>
<div class="hdr">
  <div class="logo" id="logoBtn">Edu<span>Search</span></div>
  <form class="sbox" id="sf">
    <input id="sq" name="q" value="{q_esc}" autocomplete="off" placeholder="Search anything…" autofocus>
    <button type="submit">Search</button>
  </form>
</div>
<div class="wrap">
  {count}
  {body}
</div>
<script>
(function(){{
  var P=window.parent;
  document.getElementById('logoBtn').onclick=function(){{P.postMessage({{t:'home'}},'*');}};
  document.getElementById('sf').onsubmit=function(e){{
    e.preventDefault();
    var q=document.getElementById('sq').value.trim();
    if(q)P.postMessage({{t:'search',q:q}},'*');
  }};
  document.addEventListener('click',function(e){{
    var a=e.target.closest('[data-u]');
    if(a){{e.preventDefault();P.postMessage({{t:'nav',url:a.dataset.u}},'*');}}
  }});
}})();
</script>
</body>
</html>"""


@app.route("/proxy")
def proxy():
    url = request.args.get("url", "").strip()
    if not url:
        return "", 204

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "duckduckgo.com/l/" in url and "uddg" in qs:
        url = unquote(qs["uddg"][0])
    elif parsed.hostname and "google" in parsed.hostname and parsed.path == "/url" and "q" in qs:
        url = unquote(qs["q"][0])

    try:
        resp = S.get(url, timeout=15, allow_redirects=True, verify=False)
    except req.exceptions.Timeout:
        return err("Connection timed out — try again"), 504
    except req.exceptions.ConnectionError:
        return err("Could not connect to that site"), 502
    except Exception as e:
        return err(str(e)), 500

    ct = resp.headers.get("Content-Type", "")
    final_url = resp.url

    if "text/html" in ct:
        text = resp.text
        text = re.sub(r'<base[^>]*>', '', text, flags=re.IGNORECASE)
        base_tag = f'<base href="{final_url}">'
        text = re.sub(r'\s+integrity\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+crossorigin(?:\s*=\s*["\'][^"\']*["\'])?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<meta\s+http-equiv=["\']Content-Security-Policy["\'][^>]*>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<meta\s+http-equiv=["\']X-Frame-Options["\'][^>]*>', '', text, flags=re.IGNORECASE)

        def fix_ddg_redirect(m):
            full = m.group(0)
            try:
                href = m.group(1) or m.group(2)
                p = urlparse(href.replace("&amp;", "&"))
                q2 = parse_qs(p.query)
                if "uddg" in q2:
                    real = unquote(q2["uddg"][0])
                    return full.replace(href, real)
            except Exception:
                pass
            return full

        text = re.sub(r'href="(//duckduckgo\.com/l/\?[^"]*)"', fix_ddg_redirect, text)
        text = re.sub(r"href='(//duckduckgo\.com/l/\?[^']*)'", fix_ddg_redirect, text)

        inject = INJECT + base_tag
        if re.search(r'<head[^>]*>', text, re.IGNORECASE):
            text = re.sub(r'(<head[^>]*>)', r'\1' + inject, text, count=1, flags=re.IGNORECASE)
        elif '<html' in text.lower():
            text = re.sub(r'(<html[^>]*>)', r'\1<head>' + inject + '</head>', text, count=1, flags=re.IGNORECASE)
        else:
            text = inject + text

        body = text.encode("utf-8", errors="replace")

    elif "text/css" in ct:
        css = resp.text
        parsed = urlparse(final_url)
        css_base = final_url[:final_url.rfind('/') + 1] if '/' in parsed.path else final_url
        def fix_css_url(m):
            raw = (m.group(1) or m.group(2) or m.group(3)).strip()
            if not raw or raw.startswith(('data:', 'blob:', '#')):
                return m.group(0)
            abs_url = urljoin(css_base, raw)
            return f'url("/proxy?url={quote(abs_url, safe="")}")'
        css = re.sub(r'url\(\s*"([^"]*)"\s*\)', fix_css_url, css)
        css = re.sub(r"url\(\s*'([^']*)'\s*\)", fix_css_url, css)
        css = re.sub(r'url\(\s*([^"\')][^)]*?)\s*\)', fix_css_url, css)
        body = css.encode("utf-8", errors="replace")
    else:
        body = resp.content

    hdrs = [(k, v) for k, v in resp.headers.items() if k.lower() not in STRIP]
    r = Response(body, resp.status_code, hdrs)
    r.headers["Content-Type"] = ct or "application/octet-stream"
    r.headers["Access-Control-Allow-Origin"] = "*"
    r.headers["X-Frame-Options"] = "ALLOWALL"
    return r

def err(msg):
    return f"""<html><body style="margin:0;display:flex;align-items:center;justify-content:center;
    height:100vh;background:#fafafa;font-family:system-ui;color:#111;text-align:center">
    <div><h2 style="font-size:18px;margin-bottom:8px">Could not load page</h2>
    <p style="color:#666;font-size:14px">{msg}</p>
    <p style="color:#999;font-size:12px;margin-top:16px">Try a different URL or check your connection</p></div></body></html>"""

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print("\n  EduSearch running at http://localhost:5000\n")
    app.run(debug=True, port=5000, host="0.0.0.0")
