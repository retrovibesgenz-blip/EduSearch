from flask import Flask, request, Response, send_from_directory
import requests as req
from urllib.parse import urljoin, quote, urlparse, parse_qs, unquote
import re

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
                q = parse_qs(p.query)
                if "uddg" in q:
                    real = unquote(q["uddg"][0])
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
