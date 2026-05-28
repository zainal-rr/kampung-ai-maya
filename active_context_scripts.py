import json


COMMON_ESC_SCRIPT = r'''
on esc(t)
    set t to t as string
    set t to my replaceText(t, "\\", "\\\\")
    set t to my replaceText(t, "\"", "\\\"")
    set t to my replaceText(t, return, "\\n")
    set t to my replaceText(t, linefeed, "\\n")
    return t
end esc
on replaceText(t, s, r)
    set oldDelims to AppleScript's text item delimiters
    set AppleScript's text item delimiters to s
    set parts to text items of t
    set AppleScript's text item delimiters to r
    set out to parts as text
    set AppleScript's text item delimiters to oldDelims
    return out
end replaceText
'''


EXCEL_CONTEXT_SCRIPT = r'''
set payload to "{}"
try
    tell application "Microsoft Excel"
        set wbName to name of active workbook
        set wbPath to full name of active workbook
        set wsName to name of active sheet
        set addr to get address of selection
        set valuesText to ""
        set formulasText to ""
        set formatsText to ""
        try
            set rowCount to count rows of selection
            set colCount to count columns of selection
            set maxRows to rowCount
            if maxRows > 8 then set maxRows to 8
            set maxCols to colCount
            if maxCols > 8 then set maxCols to 8
            repeat with r from 1 to maxRows
                set rowVals to {}
                set rowForms to {}
                set rowFormats to {}
                repeat with c from 1 to maxCols
                    set cellRef to cell r of column c of selection
                    set end of rowVals to (value of cellRef as string)
                    set end of rowForms to (formula of cellRef as string)
                    set end of rowFormats to (number format of cellRef as string)
                end repeat
                set valuesText to valuesText & my joinList(rowVals, " | ") & linefeed
                set formulasText to formulasText & my joinList(rowForms, " | ") & linefeed
                set formatsText to formatsText & my joinList(rowFormats, " | ") & linefeed
            end repeat
        end try
        set payload to "{\"workbook\":\"" & my esc(wbName) & "\",\"path\":\"" & my esc(wbPath) & "\",\"sheet\":\"" & my esc(wsName) & "\",\"range\":\"" & my esc(addr) & "\",\"values\":\"" & my esc(valuesText) & "\",\"formulas\":\"" & my esc(formulasText) & "\",\"formats\":\"" & my esc(formatsText) & "\"}"
    end tell
end try
return payload
on joinList(theList, delim)
    set oldDelims to AppleScript's text item delimiters
    set AppleScript's text item delimiters to delim
    set out to theList as string
    set AppleScript's text item delimiters to oldDelims
    return out
end joinList
''' + COMMON_ESC_SCRIPT


WORD_CONTEXT_SCRIPT = r'''
set payload to "{}"
try
    tell application "Microsoft Word"
        set docName to name of active document
        set docPath to full name of active document
        set selectedText to content of selection
        if selectedText is "" then set selectedText to content of paragraph 1 of selection
        set payload to "{\"document\":\"" & my esc(docName) & "\",\"path\":\"" & my esc(docPath) & "\",\"selection\":\"" & my esc(selectedText) & "\"}"
    end tell
end try
return payload
''' + COMMON_ESC_SCRIPT


POWERPOINT_CONTEXT_SCRIPT = r'''
set payload to "{}"
try
    tell application "Microsoft PowerPoint"
        set deckName to name of active presentation
        set deckPath to full name of active presentation
        set slideNum to slide index of slide of active window
        set selectedText to ""
        try
            repeat with shp in selection shape range of active window
                try
                    set selectedText to selectedText & content of text range of text frame of shp & linefeed
                end try
            end repeat
        end try
        set payload to "{\"presentation\":\"" & my esc(deckName) & "\",\"path\":\"" & my esc(deckPath) & "\",\"slide\":\"" & slideNum & "\",\"selection\":\"" & my esc(selectedText) & "\"}"
    end tell
end try
return payload
''' + COMMON_ESC_SCRIPT


GENERIC_TEXT_SCRIPT = r'''
set selectedText to ""
try
    tell application "System Events"
        set focusedElement to value of attribute "AXFocusedUIElement" of first process whose frontmost is true
        try
            set selectedText to value of attribute "AXSelectedText" of focusedElement
        end try
        if selectedText is missing value then set selectedText to ""
    end tell
end try
return selectedText
'''


GENERIC_TEXT_CONTEXT_SCRIPT = r'''
set payload to "{}"
try
    tell application "System Events"
        set proc to first process whose frontmost is true
        set appName to name of proc
        set selectedText to ""
        set windowTitle to ""
        try
            set focusedElement to value of attribute "AXFocusedUIElement" of proc
            try
                set selectedText to value of attribute "AXSelectedText" of focusedElement
            end try
            if selectedText is missing value then set selectedText to ""
        end try
        try
            set windowTitle to name of window 1 of proc
        end try
        set payload to "{\"app\":\"" & my esc(appName) & "\",\"title\":\"" & my esc(windowTitle) & "\",\"selection\":\"" & my esc(selectedText) & "\"}"
    end tell
end try
return payload
''' + COMMON_ESC_SCRIPT


def browser_context_script(target: str) -> str:
    js = r'''
(() => {
  const sensitive = /(password|passcode|otp|one.time|card|credit|debit|cvv|cvc|secret|api.key|private.key|payment|checkout|booking|submit)/i;
  const clean = (s) => String(s || '').replace(/\s+/g, ' ').trim();
  const isBad = (el) => {
    if (!el) return false;
    const attrs = [
      el.type, el.name, el.id, el.autocomplete, el.placeholder,
      el.getAttribute && el.getAttribute('aria-label'),
      el.closest && el.closest('form') && el.closest('form').innerText
    ].map(clean).join(' ');
    return sensitive.test(attrs);
  };
  const selection = clean(window.getSelection ? window.getSelection().toString() : '');
  let anchorText = '';
  let nearby = '';
  try {
    const sel = window.getSelection && window.getSelection();
    if (sel && sel.rangeCount) {
      let node = sel.getRangeAt(0).commonAncestorContainer;
      if (node && node.nodeType === Node.TEXT_NODE) node = node.parentElement;
      let el = node;
      while (el && el !== document.body && clean(el.innerText).length < selection.length + 80) el = el.parentElement;
      anchorText = clean(el && !isBad(el) ? el.innerText : '');
      nearby = anchorText.slice(0, 2600);
    }
  } catch (e) {}
  const headings = Array.from(document.querySelectorAll('h1,h2,h3,[aria-selected="true"],[aria-current],.active,[class*="active"],[class*="selected"],[class*="day"],[data-day]'))
    .filter(el => !isBad(el))
    .map(el => clean(el.innerText || el.textContent || el.getAttribute('aria-label') || ''))
    .filter(Boolean)
    .slice(0, 40)
    .join('\n');
  const clone = document.body ? document.body.cloneNode(true) : null;
  if (clone) {
    clone.querySelectorAll('script,style,noscript,input,textarea,select,button').forEach(el => {
      if (isBad(el)) el.remove();
    });
  }
  const pageText = clean(clone ? clone.innerText : '');
  const hidden = Array.from(document.querySelectorAll('[hidden],[aria-hidden="false"],[style*="display: none"],[style*="visibility: hidden"]'))
    .filter(el => !isBad(el))
    .map(el => clean(el.innerText || el.textContent || ''))
    .filter(Boolean)
    .slice(0, 20)
    .join('\n');
  return JSON.stringify({
    title: document.title || '',
    url: location.href || '',
    selection,
    anchor: anchorText.slice(0, 2200),
    nearby,
    headings,
    page: pageText.slice(0, 5200),
    hidden: hidden.slice(0, 2200),
    sensitive_context: sensitive.test(location.href || '') || !!document.querySelector('input[type="password"], input[autocomplete*="cc"], input[name*="otp" i], input[id*="otp" i]')
  });
})()
'''
    return f'''
set payload to "{{}}"
try
    tell application "{target}"
        set pageTitle to ""
        set pageUrl to ""
        set selectedText to ""
        set nearbyText to ""
        if (count of windows) > 0 then
            set pageTitle to title of active tab of front window
            set pageUrl to URL of active tab of front window
            try
                set payload to execute active tab of front window javascript {json.dumps(js)}
                return payload
            on error errMsg
                set payload to "{{\\"title\\":\\"" & my esc(pageTitle) & "\\",\\"url\\":\\"" & my esc(pageUrl) & "\\",\\"selection\\":\\"\\",\\"nearby\\":\\"\\",\\"error\\":\\"" & my esc(errMsg) & "\\"}}"
                return payload
            end try
        end if
        set payload to "{{\\"title\\":\\"" & my esc(pageTitle) & "\\",\\"url\\":\\"" & my esc(pageUrl) & "\\",\\"selection\\":\\"" & my esc(selectedText) & "\\",\\"nearby\\":\\"" & my esc(nearbyText) & "\\"}}"
    end tell
end try
return payload
on esc(t)
    set t to t as string
    set t to my replaceText(t, "\\\\", "\\\\\\\\")
    set t to my replaceText(t, "\\"", "\\\\\\"")
    set t to my replaceText(t, return, "\\\\n")
    set t to my replaceText(t, linefeed, "\\\\n")
    return t
end esc
on replaceText(t, s, r)
    set oldDelims to AppleScript's text item delimiters
    set AppleScript's text item delimiters to s
    set parts to text items of t
    set AppleScript's text item delimiters to r
    set out to parts as text
    set AppleScript's text item delimiters to oldDelims
    return out
end replaceText
'''
