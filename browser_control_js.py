from __future__ import annotations

import hashlib
import json


def _as_string(script: str) -> str:
    return json.dumps(script)


def _page_text_js(max_chars: int) -> str:
    return (
        "(() => {"
        "const text = document.body ? document.body.innerText : '';"
        f"return text.slice(0, {max(500, max_chars)});"
        "})()"
    )


def _click_js(target: str) -> str:
    return (
        "(() => {"
        f"const target = {json.dumps(target.lower())};"
        "const norm = s => (s || '').toLowerCase().replace(/\\s+/g, ' ').trim();"
        "const visible = e => { const r = e.getBoundingClientRect();"
        "return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };"
        "const label = e => norm(e.innerText || e.value || e.getAttribute('aria-label') || e.title || '');"
        "const nodes = [...document.querySelectorAll('a,button,input,[role=button],[role=link],select,summary')];"
        "const visibleNodes = nodes.filter(e => visible(e));"
        "const match = visibleNodes.find(e => label(e) === target)"
        "|| visibleNodes.find(e => label(e).startsWith(target))"
        "|| visibleNodes.find(e => label(e).includes(target));"
        "if (!match) return 'NOT_FOUND';"
        "match.scrollIntoView({block: 'center', inline: 'center'});"
        "match.click();"
        "return 'CLICKED: ' + label(match).slice(0, 120);"
        "})()"
    )


def _click_exact_last_js(target: str) -> str:
    return (
        "(() => {"
        f"const target = {json.dumps(target.lower())};"
        "const norm = s => (s || '').toLowerCase().replace(/\\s+/g, ' ').trim();"
        "const visible = e => { const r = e.getBoundingClientRect();"
        "return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };"
        "const label = e => norm(e.innerText || e.value || e.getAttribute('aria-label') || e.title || '');"
        "const nodes = [...document.querySelectorAll('a,button,input,[role=button],[role=link],select,summary')];"
        "const matches = nodes.filter(e => visible(e) && label(e) === target);"
        "if (!matches.length) return 'NOT_FOUND';"
        "const match = matches[matches.length - 1];"
        "match.scrollIntoView({block: 'center', inline: 'center'});"
        "match.click();"
        "return 'CLICKED: ' + label(match).slice(0, 120);"
        "})()"
    )


def _click_visible_text_js(target: str) -> str:
    return (
        "(() => {"
        f"const target = {json.dumps(target.lower())};"
        "const norm = s => (s || '').toLowerCase().replace(/\\s+/g, ' ').trim();"
        "const visible = e => { const r = e.getBoundingClientRect();"
        "return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };"
        "const label = e => norm(e.innerText || e.value || e.getAttribute('aria-label') || e.title || '');"
        "const nodes = [...document.querySelectorAll('button,[role=button],[role=combobox],input,select,div,span')];"
        "const matches = nodes.filter(e => visible(e) && label(e) === target)"
        ".map(e => { const r = e.getBoundingClientRect(); return { e, r, area: r.width * r.height }; })"
        ".sort((a,b) => (a.area - b.area) || (a.r.y - b.r.y) || (a.r.x - b.r.x));"
        "if (!matches.length) return 'NOT_FOUND';"
        "const match = matches[0].e;"
        "match.scrollIntoView({block: 'center', inline: 'center'});"
        "const rr = match.getBoundingClientRect();"
        "const cx = rr.left + rr.width / 2, cy = rr.top + rr.height / 2;"
        "for (const type of ['pointerdown','mousedown','pointerup','mouseup','click']) {"
        "match.dispatchEvent(new MouseEvent(type,{bubbles:true,cancelable:true,view:window,clientX:cx,clientY:cy}));"
        "}"
        "return 'CLICKED: ' + label(match).slice(0, 120);"
        "})()"
    )


def _target_visible_js(target: str) -> str:
    return (
        "(() => {"
        f"const target = {json.dumps(target.lower())};"
        "const norm = s => (s || '').toLowerCase().replace(/\\s+/g, ' ').trim();"
        "const visible = e => { const r = e.getBoundingClientRect();"
        "return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };"
        "const label = e => norm(e.innerText || e.value || e.getAttribute('aria-label') || e.title || '');"
        "const nodes = [...document.querySelectorAll('a,button,input,[role=button],[role=link],select,summary')];"
        "const visibleNodes = nodes.filter(e => visible(e));"
        "return visibleNodes.some(e => label(e) === target || label(e).startsWith(target) || label(e).includes(target));"
        "})()"
    )


def _elements_js(max_items: int) -> str:
    return (
        "(() => {"
        "const norm=s=>(s||'').replace(/\\s+/g,' ').trim();"
        "const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};"
        "const label=e=>norm(e.innerText||e.value||e.getAttribute('aria-label')||e.placeholder||e.name||e.title||'');"
        "const nodes=[...document.querySelectorAll('a,button,input,textarea,select,[role=button],[role=link],summary')];"
        "return JSON.stringify(nodes.filter(visible).map(e=>({kind:e.tagName.toLowerCase(),label:label(e)})).filter(x=>x.label).slice(0,"
        f"{max(1, max_items)}"
        "));"
        "})()"
    )


def _fill_js(target: str, value: str) -> str:
    return (
        "(() => {"
        f"const target={json.dumps(target.lower())};"
        f"const value={json.dumps(value)};"
        "const norm=s=>(s||'').toLowerCase().replace(/\\s+/g,' ').trim();"
        "const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};"
        "const label=e=>norm(e.getAttribute('aria-label')||e.placeholder||e.name||e.id||'');"
        "const nodes=[...document.querySelectorAll('input,textarea,select')];"
        "const match=nodes.find(e=>visible(e)&&label(e).includes(target));"
        "if(!match)return 'NOT_FOUND';"
        "match.focus(); match.value=value;"
        "match.dispatchEvent(new Event('input',{bubbles:true}));"
        "match.dispatchEvent(new Event('change',{bubbles:true}));"
        "return 'FILLED: '+(label(match)||target).slice(0,120);"
        "})()"
    )


def _click_price_result_js(target: str) -> str:
    return (
        "(() => {"
        f"const target={json.dumps(target.lower())};"
        "const norm=s=>(s||'').toLowerCase().replace(/\\s+/g,' ').trim();"
        "const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};"
        "const price=s=>/\\b(MYR|RM)\\s*[\\d,]+/i.test(s||'');"
        "const bad=s=>/(filter|currency|privacy|terms|feedback|help center|google account|main menu|change appearance)/i.test(s||'');"
        "const nodes=[...document.querySelectorAll('a,[role=link],button,[role=button],li,div')];"
        "let candidates=nodes.filter(e=>visible(e)).map(e=>{const r=e.getBoundingClientRect();const t=(e.innerText||e.getAttribute('aria-label')||e.title||'').replace(/\\s+/g,' ').trim();const area=r.width*r.height;return {e,r,t,n:norm(t),area}})"
        ".filter(x=>x.t.length>12&&x.t.length<450&&price(x.t)&&!bad(x.t));"
        "if(!candidates.length){"
        "const priceNodes=[...document.querySelectorAll('a,[role=link],button,[role=button],li,div,span')].filter(e=>visible(e)&&price(e.innerText||e.textContent||''));"
        "for(const node of priceNodes){let p=node;let depth=0;while(p&&depth<8){const role=(p.getAttribute&&p.getAttribute('role'))||'';const tag=(p.tagName||'').toLowerCase();const t=(p.innerText||p.textContent||'').replace(/\\s+/g,' ').trim();if((tag==='a'||tag==='button'||role==='link'||role==='button'||getComputedStyle(p).cursor==='pointer')&&t.length>12&&t.length<600&&!bad(t)){const r=p.getBoundingClientRect();candidates.push({e:p,r,t,n:norm(t),area:r.width*r.height});break;}p=p.parentElement;depth++;}}"
        "}"
        "if(target)candidates=candidates.filter(x=>x.n.includes(target));"
        "if(!candidates.length)return 'NOT_FOUND';"
        "candidates.sort((a,b)=>(a.r.y-b.r.y)||(a.area-b.area)||(a.r.x-b.r.x));"
        "const chosen=candidates[0];"
        "chosen.e.scrollIntoView({block:'center',inline:'center'});"
        "const rr=chosen.e.getBoundingClientRect();"
        "const cx=rr.left+rr.width/2, cy=rr.top+rr.height/2;"
        "for(const type of ['pointerdown','mousedown','pointerup','mouseup','click']){"
        "chosen.e.dispatchEvent(new MouseEvent(type,{bubbles:true,cancelable:true,view:window,clientX:cx,clientY:cy}));"
        "}"
        "return 'CLICKED: '+chosen.t.slice(0,180);"
        "})()"
    )


def _click_search_result_js(target: str, rank: int) -> str:
    return (
        "(() => {"
        f"const target={json.dumps(target.lower())};"
        f"const rank={max(1, min(10, int(rank)))};"
        "const norm=s=>(s||'').toLowerCase().replace(/\\s+/g,' ').trim();"
        "const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};"
        "const pageHost=location.hostname.toLowerCase();"
        "const isYouTube=/youtube\\.com$/.test(pageHost);"
        "const isReddit=/(^|\\.)reddit\\.com$/.test(pageHost);"
        "const badHref=h=>!h||/google\\.[^/]+\\/(search|preferences|advanced_search|intl|policies)|accounts\\.google|support\\.google|javascript:|[?&]entry_point=/i.test(h);"
        "const badText=t=>/(cached|similar|translate this page|privacy|terms|settings|tools|feedback|sign in|images|videos|maps|shopping|news|home|shorts|subscriptions|library|history|you|premium)$/i.test(t)||/monthly players/i.test(t);"
        "const siteAllowed=x=>{"
        "if(isYouTube)return /\\/watch\\?v=/.test(x.href)||/\\/shorts\\//.test(x.href);"
        "if(isReddit)return /\\/comments\\//.test(x.href)||/\\/r\\/[^/]+\\/comments\\//.test(x.href);"
        "return true;"
        "};"
        "const siteScore=x=>{"
        "if(isYouTube&&/\\/watch\\?v=/.test(x.href))return 0;"
        "if(isYouTube&&/\\/shorts\\//.test(x.href))return 1;"
        "if(isReddit&&/\\/comments\\//.test(x.href))return 0;"
        "if(x.e.querySelector&&x.e.querySelector('h3'))return 0;"
        "return 2;"
        "};"
        "const ytTitle=e=>{const host=e.closest('ytd-video-renderer,ytd-rich-item-renderer,ytd-compact-video-renderer,ytd-grid-video-renderer')||e;"
        "const title=host.querySelector('#video-title,a#video-title,yt-formatted-string#video-title');"
        "return (title&&(title.title||title.getAttribute('aria-label')||title.innerText||title.textContent))||e.title||e.getAttribute('aria-label')||e.innerText||'';};"
        "const linkText=e=>isYouTube?ytTitle(e):(e.innerText||e.getAttribute('aria-label')||e.title||'');"
        "const nodes=[...document.querySelectorAll('a[href]')];"
        "let candidates=nodes.filter(visible).map(e=>{"
        "const r=e.getBoundingClientRect();"
        "const t=linkText(e).replace(/\\s+/g,' ').trim();"
        "return {e,r,t,n:norm(t),href:e.href};"
        "}).filter(x=>x.t.length>=8&&x.t.length<260&&!badHref(x.href)&&!badText(x.t)&&siteAllowed(x));"
        "if(target)candidates=candidates.filter(x=>x.n.includes(target));"
        "const unique=[]; const seen=new Set();"
        "for(const c of candidates.sort((a,b)=>(siteScore(a)-siteScore(b))||(a.r.y-b.r.y)||(a.r.x-b.r.x))){"
        "const key=c.href.split('#')[0]; if(seen.has(key)) continue; seen.add(key); unique.push(c);"
        "}"
        "if(unique.length<rank)return 'NOT_FOUND';"
        "const chosen=unique[rank-1];"
        "chosen.e.scrollIntoView({block:'center',inline:'center'});"
        "const rr=chosen.e.getBoundingClientRect();"
        "const cx=rr.left+rr.width/2, cy=rr.top+rr.height/2;"
        "for(const type of ['pointerdown','mousedown','pointerup','mouseup','click']){"
        "chosen.e.dispatchEvent(new MouseEvent(type,{bubbles:true,cancelable:true,view:window,clientX:cx,clientY:cy}));"
        "}"
        "return 'CLICKED_RESULT: '+chosen.t.slice(0,160)+' | '+chosen.href;"
        "})()"
    )


def _search_result_options_js(max_items: int) -> str:
    return (
        "(() => {"
        f"const maxItems={max(1, min(20, int(max_items)))};"
        "const norm=s=>(s||'').toLowerCase().replace(/\\s+/g,' ').trim();"
        "const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};"
        "const pageHost=location.hostname.toLowerCase();"
        "const isYouTube=/youtube\\.com$/.test(pageHost);"
        "const isReddit=/(^|\\.)reddit\\.com$/.test(pageHost);"
        "const badHref=h=>!h||/google\\.[^/]+\\/(search|preferences|advanced_search|intl|policies)|accounts\\.google|support\\.google|javascript:|[?&]entry_point=/i.test(h);"
        "const badText=t=>/(cached|similar|translate this page|privacy|terms|settings|tools|feedback|sign in|images|videos|maps|shopping|news|home|shorts|subscriptions|library|history|you|premium)$/i.test(t)||/monthly players/i.test(t);"
        "const siteAllowed=x=>{"
        "if(isYouTube)return /\\/watch\\?v=/.test(x.href)||/\\/shorts\\//.test(x.href);"
        "if(isReddit)return /\\/comments\\//.test(x.href)||/\\/r\\/[^/]+\\/comments\\//.test(x.href);"
        "return true;"
        "};"
        "const siteScore=x=>{"
        "if(isYouTube&&/\\/watch\\?v=/.test(x.href))return 0;"
        "if(isYouTube&&/\\/shorts\\//.test(x.href))return 1;"
        "if(isReddit&&/\\/comments\\//.test(x.href))return 0;"
        "if(x.e.querySelector&&x.e.querySelector('h3'))return 0;"
        "return 2;"
        "};"
        "const ytTitle=e=>{const host=e.closest('ytd-video-renderer,ytd-rich-item-renderer,ytd-compact-video-renderer,ytd-grid-video-renderer')||e;"
        "const title=host.querySelector('#video-title,a#video-title,yt-formatted-string#video-title');"
        "return (title&&(title.title||title.getAttribute('aria-label')||title.innerText||title.textContent))||e.title||e.getAttribute('aria-label')||e.innerText||'';};"
        "const linkText=e=>isYouTube?ytTitle(e):(e.innerText||e.getAttribute('aria-label')||e.title||'');"
        "let candidates=[...document.querySelectorAll('a[href]')].filter(visible).map(e=>{"
        "const r=e.getBoundingClientRect();"
        "const t=linkText(e).replace(/\\s+/g,' ').trim();"
        "return {e,r,t,n:norm(t),href:e.href};"
        "}).filter(x=>x.t.length>=8&&x.t.length<260&&!badHref(x.href)&&!badText(x.t)&&siteAllowed(x));"
        "const unique=[]; const seen=new Set();"
        "for(const c of candidates.sort((a,b)=>(siteScore(a)-siteScore(b))||(a.r.y-b.r.y)||(a.r.x-b.r.x))){"
        "const key=c.href.split('#')[0]; if(seen.has(key)) continue; seen.add(key); unique.push({label:c.t.slice(0,180),href:c.href});"
        "if(unique.length>=maxItems)break;"
        "}"
        "return JSON.stringify(unique);"
        "})()"
    )


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _modal_state(text: str) -> str:
    lowered = text.lower()
    markers = ("cookie", "accept", "dialog", "modal", "continue", "confirm")
    return ",".join(marker for marker in markers if marker in lowered)[:120]
