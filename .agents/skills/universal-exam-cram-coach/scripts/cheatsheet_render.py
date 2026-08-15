#!/usr/bin/env python
# -*- coding: utf-8 -*-
('')
import argparse 
import html as html_mod 
import os 
import re 
import shutil 
import subprocess 
import sys 
import tempfile 
try :
    from .ingestion import workspace_publication_lock 
    from .ingestion .identifiers import is_link_or_reparse 
    from .study_guide_render import GuideError as _GuideAssetError ,_resolve_asset 
    from .validate_workspace import workspace_asset_policy_snapshot 
except ImportError :
    from ingestion import workspace_publication_lock 
    from ingestion .identifiers import is_link_or_reparse 
    from study_guide_render import GuideError as _GuideAssetError ,_resolve_asset 
    from validate_workspace import workspace_asset_policy_snapshot 
for _s in ("stdout","stderr"):
    try :
        getattr (sys ,_s ).reconfigure (encoding ="utf-8")
    except Exception :
        pass 
MIN_MARGIN_MM =12 
FONT_MIN ,FONT_MAX =6.0 ,12.0 
CHARS_PER_PAGE_9PT =5200 
MD_NAME ="cheatsheet.md"
def _die (msg ,code =2 ):
    sys .stderr .write ("cheatsheet_render: "+msg +"\n")
    raise SystemExit (code )
def _assert_contained (ws ,path ,name ):
    ('')
    ws_real =os .path .normcase (os .path .realpath (ws ))
    real =os .path .normcase (os .path .realpath (path ))
    if real !=ws_real and not real .startswith (ws_real +os .sep ):
        _die ("%s 经符号链接 / 父目录逃出工作区——拒绝读取"%name )
_INLINE =[(re .compile (r"\*\*([^*]+)\*\*"),r"<strong>\1</strong>"),(re .compile (r"(?<!\*)\*([^*]+)\*(?!\*)"),r"<em>\1</em>"),(re .compile (r"`([^`]+)`"),r"<code>\1</code>"),(re .compile (r"\[([^\]]+)\]\(([^)\s]+)\)"),r'<span class="lnk">\1</span>'),]
_IMG_RE =re .compile (r"!\[([^\]]*)\]\(([^)\s]+)\)")
def _load_asset_policy (ws ):
    ''
    try :
        snapshot =workspace_asset_policy_snapshot (ws )
    except (OSError ,UnicodeError ,ValueError )as exc :
        _die ("cannot establish the complete workspace asset policy: %s"%exc ,1 )
    if snapshot .get ("unsafe_paths"):
        _die ("workspace contains an unsafe asset declaration: %s"%snapshot ["unsafe_paths"][0 ],1 )
    if snapshot .get ("conflicts"):
        _die ("workspace contains an asset-role/identity conflict: %s"%snapshot ["conflicts"][0 ],1 )
    return snapshot 
def _asset_policy_token (snapshot ):
    ''
    return (snapshot .get ("quiz_rows",[]),snapshot .get ("teaching_rows",[]),snapshot .get ("content_units",[]),frozenset (snapshot .get ("tainted_keys",())),frozenset (snapshot .get ("tainted_identity_keys",())),tuple (snapshot .get ("unsafe_paths",())),tuple (snapshot .get ("conflicts",())),)
def _assert_asset_policy_unchanged (ws ,token ):
    current =_load_asset_policy (ws )
    if _asset_policy_token (current )!=token :
        _die ("workspace asset policy changed during rendering; refusing to publish stale output",1 )
def _img_tag (m ,ws ,asset_policy =None ):
    ''
    alt ,src =m .group (1 ),m .group (2 )
    plain =src .replace ("&amp;","&")
    if ws is None :
        _die ("cheatsheet images require a validated workspace",1 )
    policy =asset_policy if asset_policy is not None else _load_asset_policy (ws )
    try :
        data_uri =_resolve_asset (ws ,plain ,"cheatsheet Markdown image",student_attempt_tainted_keys =policy ,taint_message =("cheatsheet Markdown image is bound to a student_attempt asset: %s"),)
    except _GuideAssetError as exc :
        _die (str (exc ),1 )
    q =lambda x :x .replace ('"',"&quot;").replace ("'","&#x27;")
    return '<img src="%s" alt="%s" style="max-width:100%%;max-height:60mm">'%(q (data_uri ),q (alt ))
def _inline (s ,ws =None ,asset_policy =None ):
    s =html_mod .escape (s ,quote =False )
    s =_IMG_RE .sub (lambda m :_img_tag (m ,ws ,asset_policy ),s )
    for pat ,rep in _INLINE :
        s =pat .sub (rep ,s )
    return s 
def md_to_html_body (md ,ws =None ,asset_policy =None ):
    ''
    if asset_policy is not None :
        _die ("caller-supplied asset policy is not trusted; pass only the workspace",1 )
    asset_policy =(_load_asset_policy (ws )if ws is not None and _IMG_RE .search (md or "")else None )
    out ,in_ul ,in_ol ,in_table =[],False ,False ,False 
    def close_lists ():
        nonlocal in_ul ,in_ol ,in_table 
        if in_ul :
            out .append ("</ul>")
            in_ul =False 
        if in_ol :
            out .append ("</ol>")
            in_ol =False 
        if in_table :
            out .append ("</table>")
            in_table =False 
    for line in (md or "").splitlines ():
        s =line .rstrip ()
        if not s .strip ():
            close_lists ()
            continue 
        m =re .match (r"^(#{1,4})\s+(.*)$",s )
        if m :
            close_lists ()
            n =len (m .group (1 ))
            out .append ("<h%d>%s</h%d>"%(n ,_inline (m .group (2 ),ws ,asset_policy ),n ))
            continue 
        if re .match (r"^\s*(?:---+|\*\*\*+)\s*$",s ):
            close_lists ()
            out .append ("<hr/>")
            continue 
        if re .match (r"^\s*\|[\s:\-|]+\|?\s*$",s ):
            continue 
        if s .lstrip ().startswith ("|"):
            cells =[c .strip ()for c in s .strip ().strip ("|").split ("|")]
            if not in_table :
                close_lists ()
                out .append ('<table>')
                in_table =True 
                out .append ("<tr>"+"".join ("<th>%s</th>"%_inline (c ,ws ,asset_policy )for c in cells )+"</tr>")
            else :
                out .append ("<tr>"+"".join ("<td>%s</td>"%_inline (c ,ws ,asset_policy )for c in cells )+"</tr>")
            continue 
        m =re .match (r"^\s*[-*]\s+(.*)$",s )
        if m :
            if in_table or in_ol :
                close_lists ()
            if not in_ul :
                out .append ("<ul>")
                in_ul =True 
            out .append ("<li>%s</li>"%_inline (m .group (1 ),ws ,asset_policy ))
            continue 
        m =re .match (r"^\s*\d+[.)]\s+(.*)$",s )
        if m :
            if in_table or in_ul :
                close_lists ()
            if not in_ol :
                out .append ("<ol>")
                in_ol =True 
            out .append ("<li>%s</li>"%_inline (m .group (1 ),ws ,asset_policy ))
            continue 
        close_lists ()
        out .append ("<p>%s</p>"%_inline (s ,ws ,asset_policy ))
    close_lists ()
    return "\n".join (out )
def chars_per_page (font_pt ,columns ):
    ''
    base =CHARS_PER_PAGE_9PT *(9.0 /font_pt )**2 
    return base *(1.08 if columns >=3 else 1.0 )
def pick_font (total_chars ,pages ):
    ('')
    for font in [x /2.0 for x in range (int (FONT_MAX *2 ),int (FONT_MIN *2 )-1 ,-1 )]:
        cols =3 if font <7.5 else 2 
        if total_chars <=chars_per_page (font ,cols )*pages :
            return font ,cols 
    return FONT_MIN ,3 
def render_html (md ,font_pt ,columns ,margin_mm =MIN_MARGIN_MM ,title ="Cheatsheet",ws =None ,asset_policy =None ):
    if asset_policy is not None :
        _die ("caller-supplied asset policy is not trusted; pass only the workspace",1 )
    if margin_mm <MIN_MARGIN_MM :
        margin_mm =MIN_MARGIN_MM 
    body =md_to_html_body (md ,ws )
    return """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>%s</title>
<style>
@page { size: A4; margin: %dmm; }
html, body { margin: 0; padding: 0; }
body { font: %.1fpt/%.2f "Segoe UI", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
       column-count: %d; column-gap: 4mm; column-fill: auto; }
h1 { font-size: %.1fpt; margin: 0 0 2pt; column-span: all; }
h2 { font-size: %.1fpt; margin: 3pt 0 1pt; border-bottom: .5pt solid #999; break-after: avoid; }
h3, h4 { font-size: %.1fpt; margin: 2pt 0 1pt; break-after: avoid; }
p, li { margin: 0 0 1pt; }
ul, ol { margin: 0 0 1pt; padding-left: 9pt; }
table { border-collapse: collapse; width: 100%%; margin: 1pt 0; }
th, td { border: .5pt solid #aaa; padding: .5pt 2pt; text-align: left; }
code { font-family: Consolas, monospace; font-size: 92%%; background: #f2f2f2; padding: 0 1pt; }
hr { border: none; border-top: .5pt solid #bbb; margin: 2pt 0; }
section, .block { break-inside: avoid; }
</style></head><body>
%s
</body></html>
"""%(html_mod .escape (title ),margin_mm ,font_pt ,1.22 ,columns ,font_pt *1.5 ,font_pt *1.2 ,font_pt *1.05 ,body )
def find_browser ():
    if os .environ .get ("EXAMPREP_NO_BROWSER")=="1":
        return None 
    for name in ("msedge","chrome","chromium","google-chrome"):
        p =shutil .which (name )
        if p :
            return p 
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",r"C:\Program Files\Google\Chrome\Application\chrome.exe","/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if os .path .isfile (p ):
            return p 
    return None 
def print_to_pdf (browser ,html_path ,pdf_path ,timeout =120 ):
    if os .path .exists (pdf_path ):
        os .remove (pdf_path )
    url ="file:///"+os .path .abspath (html_path ).replace ("\\","/")
    args =[browser ,"--headless=new","--disable-gpu","--no-pdf-header-footer","--print-to-pdf=%s"%os .path .abspath (pdf_path ),url ]
    r =subprocess .run (args ,capture_output =True ,timeout =timeout )
    if r .returncode !=0 or not os .path .isfile (pdf_path ):
        _die ("无头浏览器打印失败（%s）：%s"%(os .path .basename (browser ),(r .stderr or b"")[:300 ].decode ("utf-8","replace")),1 )
def pdf_page_count (pdf_path ):
    ''
    with open (pdf_path ,"rb")as f :
        data =f .read ()
    return len (re .findall (rb"/Type\s*/Page\b(?!s)",data ))
def _artifact_snapshot (path ,label ):
    ''
    if not os .path .lexists (path ):
        return None 
    if is_link_or_reparse (path )or not os .path .isfile (path ):
        _die ("%s is not a regular non-reparse file; refusing publication"%label ,1 )
    try :
        with open (path ,"rb")as stream :
            return stream .read ()
    except OSError as exc :
        _die ("cannot snapshot %s before publication: %s"%(label ,exc ),1 )
def _restore_artifact (path ,payload ):
    ''
    if payload is None :
        if os .path .lexists (path ):
            os .remove (path )
        return 
    directory =os .path .dirname (path )
    fd ,temporary =tempfile .mkstemp (prefix =".cheatsheet.rollback-",suffix ="-"+os .path .basename (path ),dir =directory ,)
    try :
        with os .fdopen (fd ,"wb")as stream :
            stream .write (payload )
            stream .flush ()
            os .fsync (stream .fileno ())
        os .replace (temporary ,path )
    finally :
        if os .path .lexists (temporary ):
            try :
                os .remove (temporary )
            except OSError :
                pass 
def _publish_rendered_artifacts (html_stage ,html_path ,pdf_stage ,pdf_path ):
    ('')
    html_before =_artifact_snapshot (html_path ,"cheatsheet.html")
    pdf_before =_artifact_snapshot (pdf_path ,"cheatsheet.pdf")
    stale_pdf_existed =pdf_before is not None 
    try :
        os .replace (html_stage ,html_path )
        if pdf_stage is not None :
            os .replace (pdf_stage ,pdf_path )
        elif os .path .lexists (pdf_path ):
            os .remove (pdf_path )
    except BaseException as exc :
        rollback_errors =[]
        for path ,payload in ((pdf_path ,pdf_before ),(html_path ,html_before )):
            try :
                _restore_artifact (path ,payload )
            except BaseException as rollback_exc :
                rollback_errors .append ("%s: %s"%(os .path .basename (path ),rollback_exc ))
        if rollback_errors :
            _die ("artifact publication failed (%s) and rollback was incomplete: %s"%(exc ,"; ".join (rollback_errors )),1 )
        _die ("artifact publication failed; prior HTML/PDF were restored: %s"%exc ,1 )
    return stale_pdf_existed and pdf_stage is None 
def main (argv =None ,_state_locked =False ):
    ap =argparse .ArgumentParser (description ="cheatsheet.md → dense printable HTML/PDF "  "(stdlib; local headless Edge/Chrome for PDF)")
    ap .add_argument ("--workspace",required =True )
    ap .add_argument ("--pages",type =int ,required =True ,help ="target page count (user-specified)")
    ap .add_argument ("--font-size",type =float ,default =0 ,help ="override the fitted font size")
    ap .add_argument ("--margin-mm",type =int ,default =MIN_MARGIN_MM ,help ="page margin, floored at %dmm (printer edge-eating)"%MIN_MARGIN_MM )
    ap .add_argument ("--html-only",action ="store_true")
    args =ap .parse_args (argv )
    if args .pages <=0 :
        _die ("--pages 必须为正整数")
    if args .font_size and not (FONT_MIN <=args .font_size <=FONT_MAX ):
        _die ("--font-size 须在 %.1f–%.1f pt 之间"%(FONT_MIN ,FONT_MAX ))
    ws =os .path .abspath (args .workspace )
    if not os .path .isdir (ws )or is_link_or_reparse (ws ):
        _die ("--workspace must be an existing non-symlink directory")
    if not _state_locked :
        with workspace_publication_lock (ws ):
            return main (argv ,_state_locked =True )
    md_path =os .path .join (ws ,MD_NAME )
    if is_link_or_reparse (md_path ):
        _die ("%s 是符号链接——可能指向工作区外，拒绝读取（请替换为真实文件）"%MD_NAME )
    if not os .path .isfile (md_path ):
        _die ("找不到 %s——先让 exam-cheatsheet 编译出小抄，再来渲染"%MD_NAME )
    _assert_contained (ws ,md_path ,MD_NAME )
    with open (md_path ,"r",encoding ="utf-8")as f :
        md =f .read ()
    asset_policy =_load_asset_policy (ws )
    asset_policy_token =_asset_policy_token (asset_policy )
    total =len (re .sub (r"\s+","",md ))
    if args .font_size :
        font ,cols =args .font_size ,(3 if args .font_size <7.5 else 2 )
    else :
        font ,cols =pick_font (total ,args .pages )
    html_path =os .path .join (ws ,"cheatsheet.html")
    pdf_path =os .path .join (ws ,"cheatsheet.pdf")
    for p ,name in ((html_path ,"cheatsheet.html"),(pdf_path ,"cheatsheet.pdf")):
        if os .path .lexists (p )and is_link_or_reparse (p ):
            _die ("%s 是符号链接（可能指向工作区外）——拒绝写入，请先移除该链接"%name ,1 )
    browser =None if args .html_only else find_browser ()
    font_locked =bool (args .font_size )
    html_stage =os .path .join (ws ,".cheatsheet.rendering.html")
    pdf_stage =os .path .join (ws ,".cheatsheet.rendering.pdf")
    got =None 
    stale_pdf_removed =False 
    try :
        for attempt in range (4 ):
            for stage in (html_stage ,pdf_stage ):
                if os .path .lexists (stage ):
                    try :
                        os .remove (stage )
                    except OSError as e :
                        _die ("无法清理残留临时文件 %s（%s）——拒绝写入，请手动清理后重试"%(stage ,e ),1 )
            try :
                with open (html_stage ,"x",encoding ="utf-8")as f :
                    f .write (render_html (md ,font ,cols ,args .margin_mm ,ws =ws ))
            except FileExistsError :
                _die ("临时文件 %s 在清理后被重新创建（疑似并发或劫持）——拒绝写入"%html_stage ,1 )
            if args .html_only or not browser :
                break 
            print_to_pdf (browser ,html_stage ,pdf_stage )
            got =pdf_page_count (pdf_stage )
            if got ==args .pages or font_locked :
                break 
            if got >args .pages and font >FONT_MIN :
                font =max (FONT_MIN ,font -0.5 )
                cols =3 if font <7.5 else 2 
            elif got <args .pages and font <FONT_MAX :
                font =min (FONT_MAX ,font +0.5 )
                cols =3 if font <7.5 else 2 
            else :
                break 
        _assert_asset_policy_unchanged (ws ,asset_policy_token )
        for p ,name in ((html_path ,"cheatsheet.html"),(pdf_path ,"cheatsheet.pdf")):
            if os .path .lexists (p )and is_link_or_reparse (p ):
                _die ("%s became a symbolic link during rendering; refusing publication"%name ,1 )
        stale_pdf_removed =_publish_rendered_artifacts (html_stage ,html_path ,pdf_stage if browser and not args .html_only else None ,pdf_path ,)
    finally :
        for stage in (html_stage ,pdf_stage ):
            if os .path .lexists (stage ):
                try :
                    os .remove (stage )
                except OSError :
                    pass 
    print ("[+] cheatsheet.html：字号 %.1fpt · %d 栏 · 边距 %dmm（≥%dmm 打印安全）"%(font ,cols ,max (args .margin_mm ,MIN_MARGIN_MM ),MIN_MARGIN_MM ))
    if args .html_only :
        return 0 
    if not browser :
        stale =("；已移除过期的 cheatsheet.pdf（它不是本次产物）"if stale_pdf_removed else "")
        sys .stderr .write ("cheatsheet_render: no_browser: 本机未找到 Edge/Chrome——已生成 "  "cheatsheet.html，请打开后 Ctrl+P 打印为 PDF（边距选默认、勾选背景图形）%s\n"%stale )
        raise SystemExit (3 )
    got =pdf_page_count (pdf_path )if got is None else got 
    print ("[+] cheatsheet.pdf：%d 页（目标 %d 页%s）"%(got ,args .pages ,""if got ==args .pages else "——已尽力拟合，可用 --font-size 微调"))
    return 0 
if __name__ =="__main__":
    sys .exit (main ())
