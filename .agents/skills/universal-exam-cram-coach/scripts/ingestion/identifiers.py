''
import hashlib 
import json 
import os 
import re 
import stat 
from pathlib import Path ,PureWindowsPath 
class UnsafePathError (ValueError ):
    ''
_HEX64_RE =re .compile (r"^[0-9a-f]{64}$")
_ID_RE =re .compile (r"^(src|unit|issue|patch)_[0-9a-f]{64}$")
_WINDOWS_FORBIDDEN_COMPONENT_CHARS =frozenset ('<>"|?*')
_WINDOWS_RESERVED_DEVICE_STEMS =frozenset (("CON","PRN","AUX","NUL","CONIN$","CONOUT$")+tuple ("COM%d"%number for number in range (1 ,10 ))+tuple ("LPT%d"%number for number in range (1 ,10 ))+tuple ("COM%s"%number for number in ("\u00b9","\u00b2","\u00b3"))+tuple ("LPT%s"%number for number in ("\u00b9","\u00b2","\u00b3")))
def canonical_json (value ):
    ''
    return json .dumps (value ,ensure_ascii =False ,sort_keys =True ,separators =(",",":"))
def normalize_workspace_path (value ):
    ('')
    if not isinstance (value ,str )or not value or value !=value .strip ():
        raise UnsafePathError ("path must be a non-empty, trimmed string")
    if "\x00"in value :
        raise UnsafePathError ("path contains NUL")
    win =PureWindowsPath (value )
    if win .drive or win .root or value .startswith (("/","\\")):
        raise UnsafePathError ("path must be workspace-relative: %r"%value )
    normalized =value .replace ("\\","/")
    parts =normalized .split ("/")
    if any (part in ("",".","..")for part in parts ):
        raise UnsafePathError ("path contains an empty, dot, or traversal segment: %r"%value )
    if any (":"in part for part in parts ):
        raise UnsafePathError ("path contains a non-portable colon: %r"%value )
    if any (part .endswith ((" ","."))for part in parts ):
        raise UnsafePathError ("path contains a Win32 trailing-space/dot alias: %r"%value )
    if any (any (ord (char )<32 for char in part )for part in parts ):
        raise UnsafePathError ("path contains a non-portable control character: %r"%value )
    if any (any (char in _WINDOWS_FORBIDDEN_COMPONENT_CHARS for char in part )for part in parts ):
        raise UnsafePathError ("path contains a Win32-forbidden character: %r"%value )
    if any (part .split (".",1 )[0 ].upper ()in _WINDOWS_RESERVED_DEVICE_STEMS for part in parts ):
        raise UnsafePathError ("path contains a reserved Win32 device name: %r"%value )
    return "/".join (parts )
def safe_workspace_path (workspace ,relative_path ):
    ''
    rel =normalize_workspace_path (relative_path )
    root =Path (workspace ).resolve ()
    candidate =root .joinpath (*rel .split ("/")).resolve (strict =False )
    try :
        common =os .path .commonpath ((str (root ),str (candidate )))
    except ValueError as exc :
        raise UnsafePathError ("path is on a different filesystem root")from exc 
    if common !=str (root ):
        raise UnsafePathError ("path escapes workspace: %r"%relative_path )
    return candidate 
def is_link_or_reparse (path ):
    ''
    value =str (path )
    if os .path .islink (value ):
        return True 
    isjunction =getattr (os .path ,"isjunction",None )
    if isjunction is not None :
        try :
            if isjunction (value ):
                return True 
        except OSError :
            pass 
    try :
        attrs =getattr (os .lstat (value ),"st_file_attributes",0 )
    except OSError :
        return False 
    return bool (attrs &getattr (stat ,"FILE_ATTRIBUTE_REPARSE_POINT",0 ))
def safe_workspace_entry (workspace ,relative_path ,reject_links =True ):
    ('')
    rel =normalize_workspace_path (relative_path )
    root =Path (workspace ).resolve ()
    current =root 
    for part in rel .split ("/"):
        current =current /part 
        if reject_links and os .path .lexists (str (current ))and is_link_or_reparse (current ):
            raise UnsafePathError ("path contains a symlink/junction/reparse entry: %r"%relative_path )
    resolved =current .resolve (strict =False )
    try :
        common =os .path .commonpath ((str (root ),str (resolved )))
    except ValueError as exc :
        raise UnsafePathError ("path is on a different filesystem root")from exc 
    if common !=str (root ):
        raise UnsafePathError ("path escapes workspace: %r"%relative_path )
    return current 
def file_sha256 (path ):
    digest =hashlib .sha256 ()
    with open (path ,"rb")as stream :
        for block in iter (lambda :stream .read (1024 *1024 ),b""):
            digest .update (block )
    return digest .hexdigest ()
def validate_sha256 (value ,label ="sha256"):
    if not isinstance (value ,str )or not _HEX64_RE .fullmatch (value ):
        raise ValueError ("%s must be a lowercase 64-character SHA-256"%label )
    return value 
def _stable_id (prefix ,payload ):
    digest =hashlib .sha256 (canonical_json (payload ).encode ("utf-8")).hexdigest ()
    return "%s_%s"%(prefix ,digest )
def make_source_id (path ):
    return _stable_id ("src",{"path":normalize_workspace_path (path )})
def _canonical_bbox (bbox ):
    if bbox is None :
        return None 
    return [float (value )for value in bbox ]
def make_unit_id (source_id ,page ,bbox ,kind ,ordinal ):
    return _stable_id ("unit",{"source_id":source_id ,"page":page ,"bbox":_canonical_bbox (bbox ),"kind":kind ,"ordinal":ordinal ,},)
def make_issue_id (source_id ,source_sha256 ,reason_codes ,pages ,evidence ,target_unit_ids ):
    return _stable_id ("issue",{"source_id":source_id ,"source_sha256":source_sha256 ,"reason_codes":list (reason_codes ),"pages":list (pages ),"evidence":list (evidence ),"target_unit_ids":list (target_unit_ids ),},)
def make_patch_id (issue_id ,source_id ,source_sha256 ,operations ,evidence ):
    return _stable_id ("patch",{"issue_id":issue_id ,"source_id":source_id ,"source_sha256":source_sha256 ,"operations":list (operations ),"evidence":list (evidence ),},)
def validate_stable_id (value ,prefix =None ,label ="id"):
    if not isinstance (value ,str )or not _ID_RE .fullmatch (value ):
        raise ValueError ("%s is not a stable ingestion ID"%label )
    if prefix is not None and not value .startswith (prefix +"_"):
        raise ValueError ("%s must use the %s_ prefix"%(label ,prefix ))
    return value 
