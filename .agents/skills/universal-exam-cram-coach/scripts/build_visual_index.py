#!/usr/bin/env python
# -*- coding: utf-8 -*-
('')
import argparse 
import copy 
import datetime 
import hashlib 
import json 
import os 
import re 
import sys 
import tempfile 
try :
    from .import exam_start 
    from .ingestion import workspace_publication_lock 
    from .ingestion .identifiers import is_link_or_reparse 
    from .image_validation import (is_valid_png_file as _shared_is_valid_png_file ,png_validation_error as _shared_png_validation_error ,)
    from .validate_workspace import workspace_asset_policy_snapshot 
    from .asset_policy import (audit_asset_policy ,is_student_attempt_tainted ,iter_asset_declarations ,physical_asset_key ,workspace_asset_is_student_attempt ,)
except ImportError :
    import exam_start 
    from ingestion import workspace_publication_lock 
    from ingestion .identifiers import is_link_or_reparse 
    from image_validation import (is_valid_png_file as _shared_is_valid_png_file ,png_validation_error as _shared_png_validation_error ,)
    from validate_workspace import workspace_asset_policy_snapshot 
    from asset_policy import (audit_asset_policy ,is_student_attempt_tainted ,iter_asset_declarations ,physical_asset_key ,workspace_asset_is_student_attempt ,)
for _s in ("stdout","stderr"):
    try :
        getattr (sys ,_s ).reconfigure (encoding ="utf-8")
    except Exception :
        pass 
HERE =os .path .dirname (os .path .abspath (__file__ ))
if HERE not in sys .path :
    sys .path .insert (0 ,HERE )
try :
    from build_raw_input_from_workspace import ALWAYS_PRUNE ,_is_leftover_workspace ,_is_workspace_root 
except Exception :
    ALWAYS_PRUNE ={".git","__pycache__","node_modules",".venv","venv",".idea",".vscode"}
    def _is_leftover_workspace (path ,name ):
        return False 
    def _is_workspace_root (path ):
        return False 
VISUAL_KIND_WORDS ={"figure":("figure","fig.","illustration","插图","如图","下图","上图"),"table":("table","tabular","表格","数据表"),"diagram":("diagram","schematic","示意图","结构图","装置图","受力图","解剖图","机械结构","状态机","state machine"),"chart":("chart","bar chart","pie chart","柱状图","饼图","统计图"),"graph":("graph","curve","waveform","曲线","波形","信号图","函数图"),"plot":("plot","scatter","散点","坐标图","sample path"),"screenshot":("screenshot","截图","运行结果","界面图","console output"),"circuit":("circuit","电路","原理图"),"tree":("tree","树状","二叉树","决策树"),"map":("map","地图"),"geometry":("geometry","几何图","三角形","venn","文氏图","韦恩图"),"flowchart":("flowchart","flow chart","流程图"),}
_FIGREF_RE =re .compile (r"(?<![A-Za-z0-9])(?:figure|fig\.?|table|图|表)\s*\d",re .I )
_AXIS_WORDS =("x-axis","y-axis","x轴","y轴","横轴","纵轴","坐标轴","图例","legend","axis")
_MIN_DRAWINGS =4 
_COLUMN_GAP_RE =re .compile (r"\S[ \t]{5,}\S")
def _compile_words (words ):
    ('')
    out =[]
    for w in words :
        if all (ord (c )<128 for c in w ):
            out .append (re .compile (r"(?<![A-Za-z0-9])"+re .escape (w )+r"(?![A-Za-z0-9])",re .I ))
        else :
            out .append (w )
    return out 
VISUAL_KIND_PATTERNS ={k :_compile_words (ws )for k ,ws in VISUAL_KIND_WORDS .items ()}
_AXIS_PATTERNS =_compile_words (_AXIS_WORDS )
def _any_hit (text ,patterns ):
    return any (p .search (text )if hasattr (p ,"search")else (p in text )for p in patterns )
def classify_page (text ,images =0 ,drawings =0 ):
    ('')
    t =(text or "").lower ()
    kinds =sorted (k for k ,pats in VISUAL_KIND_PATTERNS .items ()if _any_hit (t ,pats ))
    layout_table =sum (1 for line in (text or "").splitlines ()if _COLUMN_GAP_RE .search (line ))>=3 
    if layout_table and "table"not in kinds :
        kinds .append ("table")
        kinds .sort ()
    structural =(images or 0 )>0 or (drawings or 0 )>=_MIN_DRAWINGS 
    figref =bool (_FIGREF_RE .search (t ))
    axis =_any_hit (t ,_AXIS_PATTERNS )
    return {"has_visual":bool (structural or figref or axis or kinds ),"visual_kinds":kinds ,"signals":{"images":int (images or 0 ),"drawings":int (drawings or 0 ),"structural":structural ,"layout_table":layout_table ,"figref":figref ,"axis":axis },}
class RealBackend (object ):
    ''
    def __init__ (self ):
        self ._pypdf =self ._fitz =self ._pdfium =None 
        try :
            import pypdf 
            self ._pypdf =pypdf 
        except Exception :
            pass 
        try :
            import fitz 
            self ._fitz =fitz 
        except Exception :
            pass 
        try :
            import pypdfium2 
            from PIL import Image 
            self ._pdfium =pypdfium2 
        except Exception :
            pass 
        self .name ="+".join (n for n ,m in (("pypdf",self ._pypdf ),("pymupdf",self ._fitz ),("pypdfium2",self ._pdfium ))if m )or "none"
    def can_text (self ):
        return self ._pypdf is not None or self ._fitz is not None 
    def can_media (self ):
        return self ._fitz is not None 
    def can_render (self ):
        return self ._fitz is not None or self ._pdfium is not None 
    def pages_text (self ,pdf_path ):
        if self ._pypdf is not None :
            try :
                reader =self ._pypdf .PdfReader (pdf_path )
                return [(p .extract_text ()or "")for p in reader .pages ]
            except Exception :
                if self ._fitz is None :
                    raise 
        doc =self ._fitz .open (pdf_path )
        try :
            return [doc [i ].get_text ()or ""for i in range (doc .page_count )]
        finally :
            doc .close ()
    def pages_media (self ,pdf_path ):
        ''
        if self ._fitz is None :
            return None 
        doc =self ._fitz .open (pdf_path )
        try :
            out =[]
            for i in range (doc .page_count ):
                page =doc [i ]
                try :
                    imgs =len (page .get_images (full =True ))
                except Exception :
                    imgs =0 
                try :
                    draws =len (page .get_drawings ())
                except Exception :
                    draws =0 
                out .append ((imgs ,draws ))
            return out 
        finally :
            doc .close ()
    def render_page_png (self ,pdf_path ,page_index ):
        if self ._fitz is not None :
            try :
                doc =self ._fitz .open (pdf_path )
                try :
                    return doc [page_index ].get_pixmap (dpi =150 ).tobytes ("png")
                finally :
                    doc .close ()
            except Exception :
                pass 
        if self ._pdfium is not None :
            try :
                import io 
                pdf =self ._pdfium .PdfDocument (pdf_path )
                img =pdf [page_index ].render (scale =2.0 ).to_pil ()
                buf =io .BytesIO ()
                img .save (buf ,format ="PNG")
                return buf .getvalue ()
            except Exception :
                return None 
        return None 
def _die (msg ,code =2 ):
    sys .stderr .write ("build_visual_index: "+msg +"\n")
    raise SystemExit (code )
def _read_json (path ,label ):
    if not os .path .isfile (path ):
        _die ("找不到%s: %s"%(label ,path ))
    try :
        with open (path ,"r",encoding ="utf-8")as f :
            return json .load (f )
    except ValueError as e :
        _die ("%s 不是合法 JSON: %s"%(label ,e ))
def _rel_posix (root ,path ):
    return os .path .relpath (path ,root ).replace ("\\","/")
def _canonical_rel_posix (root ,path ):
    ('')
    return _rel_posix (os .path .realpath (root ),os .path .realpath (path ))
def _atomic_write_bytes (path ,payload ):
    ''
    directory =os .path .dirname (path )or "."
    if os .path .lexists (path )and (is_link_or_reparse (path )or not os .path .isfile (path )):
        raise OSError ("refusing symbolic-link or special-file destination: %s"%path )
    os .makedirs (directory ,exist_ok =True )
    fd ,tmp =tempfile .mkstemp (prefix =".%s."%os .path .basename (path ),suffix =".tmp",dir =directory )
    try :
        with os .fdopen (fd ,"wb")as out :
            out .write (payload )
            out .flush ()
            os .fsync (out .fileno ())
        os .replace (tmp ,path )
    except Exception :
        try :
            os .unlink (tmp )
        except OSError :
            pass 
        raise 
def _png_structure_error (payload ):
    ('')
    return _shared_png_validation_error (payload )
def _is_structurally_valid_png_file (path ):
    return _shared_is_valid_png_file (path )
def _validated_png_payload (payload ,label ):
    ''
    if not isinstance (payload ,(bytes ,bytearray )):
        _die ("%s render backend returned a non-bytes PNG payload"%label )
    payload =bytes (payload )
    error =_png_structure_error (payload )
    if error :
        _die ("%s render backend returned a malformed PNG: %s"%(label ,error ))
    return payload 
def _snapshot_file_states (paths ):
    ''
    states ,seen =[],set ()
    for path in paths :
        absolute =os .path .abspath (path )
        key =os .path .normcase (os .path .normpath (absolute ))
        if key in seen :
            continue 
        seen .add (key )
        if not os .path .lexists (absolute ):
            states .append ((absolute ,False ,None ))
            continue 
        if is_link_or_reparse (absolute )or not os .path .isfile (absolute ):
            raise OSError ("transaction target is link-backed or non-regular: %s"%absolute )
        with open (absolute ,"rb")as stream :
            states .append ((absolute ,True ,stream .read ()))
    return states 
def _restore_file_states (states ):
    ''
    failures =[]
    for path ,existed ,payload in reversed (states ):
        try :
            if existed :
                _atomic_write_bytes (path ,payload )
            elif os .path .lexists (path ):
                if is_link_or_reparse (path )or not os .path .isfile (path ):
                    raise OSError ("rollback target became unsafe: %s"%path )
                os .remove (path )
        except OSError as exc :
            failures .append ("%s: %s"%(path ,exc ))
    if failures :
        raise OSError ("; ".join (failures ))
def _stage_bytes (path ,payload ):
    directory =os .path .dirname (path )or "."
    fd ,temporary =tempfile .mkstemp (prefix =".%s."%os .path .basename (path ),suffix =".tmp",dir =directory )
    try :
        with os .fdopen (fd ,"wb")as stream :
            stream .write (payload )
            stream .flush ()
            os .fsync (stream .fileno ())
    except BaseException :
        try :
            os .unlink (temporary )
        except OSError :
            pass 
        raise 
    return temporary 
def _publish_bytes_transactionally (payloads ):
    ''
    normalized ,seen =[],set ()
    for path ,payload in payloads :
        absolute =os .path .abspath (path )
        key =os .path .normcase (os .path .normpath (absolute ))
        if key in seen :
            raise OSError ("transaction contains duplicate destination: %s"%absolute )
        seen .add (key )
        if os .path .lexists (absolute )and (is_link_or_reparse (absolute )or not os .path .isfile (absolute )):
            raise OSError ("transaction destination is link-backed or non-regular: %s"%absolute )
        normalized .append ((absolute ,bytes (payload )))
    if not normalized :
        return 
    states =_snapshot_file_states (path for path ,_payload in normalized )
    created_dirs =[]
    staged =[]
    try :
        for path ,_payload in normalized :
            directory =os .path .dirname (path )or "."
            if not os .path .isdir (directory ):
                os .makedirs (directory ,exist_ok =True )
                created_dirs .append (directory )
        for path ,payload in normalized :
            staged .append ([_stage_bytes (path ,payload ),path ])
        try :
            for entry in staged :
                os .replace (entry [0 ],entry [1 ])
                entry [0 ]=None 
        except OSError as exc :
            try :
                _restore_file_states (states )
            except OSError as rollback_exc :
                raise OSError ("%s; rollback failed: %s"%(exc ,rollback_exc ))
            raise 
    finally :
        for temporary ,_path in staged :
            if temporary and os .path .exists (temporary ):
                try :
                    os .unlink (temporary )
                except OSError :
                    pass 
        for directory in sorted (set (created_dirs ),key =len ,reverse =True ):
            try :
                os .rmdir (directory )
            except OSError :
                pass 
def _replace_list_records_in_place (target ,source ):
    ''
    if len (target )!=len (source ):
        target [:]=copy .deepcopy (source )
        return 
    for index ,value in enumerate (source ):
        current =target [index ]
        if isinstance (current ,dict )and isinstance (value ,dict ):
            current .clear ()
            current .update (copy .deepcopy (value ))
        else :
            target [index ]=copy .deepcopy (value )
def _path_has_link_or_reparse_component (root ,path ):
    ('')
    root_abs =os .path .abspath (root )
    path_abs =os .path .abspath (path )
    try :
        rel =os .path .relpath (path_abs ,root_abs )
    except ValueError :
        return True 
    if rel ==os .pardir or rel .startswith (os .pardir +os .sep ):
        return True 
    current =root_abs 
    if os .path .lexists (current )and is_link_or_reparse (current ):
        return True 
    for part in (()if rel =="."else rel .split (os .sep )):
        current =os .path .join (current ,part )
        if os .path .lexists (current )and is_link_or_reparse (current ):
            return True 
    return False 
def _safe_workspace_dir (ws ,path ,label ,create =False ):
    ''
    ws_abs ,path_abs =os .path .abspath (ws ),os .path .abspath (path )
    if is_link_or_reparse (ws_abs ):
        _die ("--workspace 本身不能是符号链接: %s"%ws_abs )
    try :
        lexical_inside =(os .path .commonpath ([os .path .normcase (path_abs ),os .path .normcase (ws_abs )])==os .path .normcase (ws_abs ))
    except ValueError :
        lexical_inside =False 
    if not lexical_inside or _path_has_link_or_reparse_component (ws_abs ,path_abs ):
        _die ("%s 必须是工作区内且不含符号链接的目录: %s"%(label ,path_abs ))
    if create :
        try :
            os .makedirs (path_abs ,exist_ok =True )
        except OSError as exc :
            _die ("无法创建 %s：%s"%(label ,exc ))
    if not os .path .isdir (path_abs ):
        _die ("%s 不是目录: %s"%(label ,path_abs ))
    ws_real ,path_real =os .path .realpath (ws_abs ),os .path .realpath (path_abs )
    try :
        real_inside =(os .path .commonpath ([os .path .normcase (path_real ),os .path .normcase (ws_real )])==os .path .normcase (ws_real ))
    except ValueError :
        real_inside =False 
    if not real_inside :
        _die ("%s 解析到工作区外: %s"%(label ,path_abs ))
    return path_abs 
def _safe_workspace_file (ws ,path ,label ):
    ''
    ws_abs ,path_abs =os .path .abspath (ws ),os .path .abspath (path )
    try :
        inside =(os .path .commonpath ([os .path .normcase (path_abs ),os .path .normcase (ws_abs )])==os .path .normcase (ws_abs ))
    except ValueError :
        inside =False 
    if not inside or _path_has_link_or_reparse_component (ws_abs ,path_abs ):
        _die ("%s 必须是工作区内且不含符号链接的普通文件: %s"%(label ,path_abs ))
    if not os .path .isfile (path_abs ):
        _die ("找不到%s或目标不是普通文件: %s"%(label ,path_abs ))
    return path_abs 
def _safe_wiki_file (ws ,wiki_file ):
    ''
    if (not isinstance (wiki_file ,str )or not wiki_file .strip ()or os .path .basename (wiki_file )!=wiki_file or wiki_file in (".","..")):
        return None ,"unsafe wiki filename"
    wiki_dir =os .path .join (ws ,"references","wiki")
    path =os .path .join (wiki_dir ,wiki_file )
    if (_path_has_link_or_reparse_component (ws ,wiki_dir )or _path_has_link_or_reparse_component (ws ,path )):
        return None ,"wiki path contains a symbolic-link component"
    ws_real ,path_real =os .path .realpath (ws ),os .path .realpath (path )
    try :
        inside =(os .path .commonpath ([os .path .normcase (path_real ),os .path .normcase (ws_real )])==os .path .normcase (ws_real ))
    except ValueError :
        inside =False 
    if not inside :
        return None ,"wiki path resolves outside workspace"
    if not os .path .isfile (path ):
        return None ,"wiki file is missing or not regular"
    return path ,None 
def _sha256_regular_file (ws ,rel ):
    ''
    path =os .path .join (ws ,*rel .split ("/"))
    if _path_has_link_or_reparse_component (ws ,path )or not os .path .isfile (path ):
        return None 
    ws_real ,path_real =os .path .realpath (ws ),os .path .realpath (path )
    try :
        if os .path .commonpath ([os .path .normcase (path_real ),os .path .normcase (ws_real )])!=os .path .normcase (ws_real ):
            return None 
    except ValueError :
        return None 
    digest =hashlib .sha256 ()
    try :
        with open (path ,"rb")as source :
            for chunk in iter (lambda :source .read (1024 *1024 ),b""):
                digest .update (chunk )
    except OSError :
        return None 
    return digest .hexdigest ()
def _sha256_root_file (root ,rel ):
    ''
    norm =str (rel or "").replace ("\\","/")
    parts =norm .split ("/")
    if (not norm or os .path .isabs (norm )or re .match (r"^[A-Za-z]:",norm )or any (part in ("",".","..")for part in parts )):
        return None 
    current =os .path .abspath (root )
    for part in parts :
        current =os .path .join (current ,part )
        if os .path .lexists (current )and is_link_or_reparse (current ):
            return None 
    root_real ,path_real =os .path .realpath (root ),os .path .realpath (current )
    try :
        inside =os .path .commonpath ([os .path .normcase (path_real ),os .path .normcase (root_real )])==os .path .normcase (root_real )
    except ValueError :
        inside =False 
    if not inside or not os .path .isfile (current ):
        return None 
    digest =hashlib .sha256 ()
    try :
        with open (current ,"rb")as source :
            for chunk in iter (lambda :source .read (1024 *1024 ),b""):
                digest .update (chunk )
    except OSError :
        return None 
    return digest .hexdigest ()
def _manifest_result_sha256 (value ):
    ''
    payload ={key :val for key ,val in value .items ()if key !="integrity"}
    raw =json .dumps (payload ,ensure_ascii =False ,sort_keys =True ,separators =(",",":"),allow_nan =False ).encode ("utf-8")
    return hashlib .sha256 (raw ).hexdigest ()
def _integrity_snapshot (ws ,args ,backend ,warnings ,item_layers =(),coverage =None ,fig_files =None ):
    ('')
    rels ={"references/quiz_bank.json"}
    if os .path .lexists (os .path .join (ws ,".ingest")):
        rels .add (".ingest/content_units.jsonl")
    for optional_rel in ("references/teaching_examples.json","references/teaching_baseline.json","ingest_report.json"):
        if os .path .lexists (os .path .join (ws ,*optional_rel .split ("/"))):
            rels .add (optional_rel )
    wiki_dir =os .path .join (ws ,"references","wiki")
    if (os .path .isdir (wiki_dir )and not _path_has_link_or_reparse_component (ws ,wiki_dir )):
        rels .update ("references/wiki/"+fn for fn in sorted (os .listdir (wiki_dir ))if fn .lower ().endswith (".md")and os .path .isfile (os .path .join (wiki_dir ,fn ))and not is_link_or_reparse (os .path .join (wiki_dir ,fn )))
    for layer in item_layers :
        for item in layer or []:
            if not isinstance (item ,dict ):
                continue 
            for asset in item .get ("assets")or []:
                raw =asset .get ("path")if isinstance (asset ,dict )else None 
                rel =str (raw or "").strip ().replace ("\\","/")
                if (rel and "://"not in rel and not rel .startswith ("/")and not re .match (r"^[A-Za-z]:",rel )and ".."not in rel .split ("/")):
                    rels .add (rel )
    for page in (coverage or {}).get ("pages")or []:
        if not isinstance (page ,dict ):
            continue 
        for raw in page .get ("asset_paths")or []:
            rel =str (raw or "").strip ().replace ("\\","/")
            if rel :
                rels .add (rel )
    inputs ={}
    for rel in sorted (rels ):
        digest =_sha256_regular_file (ws ,rel )
        if digest is None :
            warnings .append ("integrity_input_unreadable: %s（视觉索引 freshness 无法建立）"%rel )
            continue 
        inputs [rel ]={"sha256":digest }
    material_inputs ={}
    materials_root =os .path .abspath (args .materials )if args .materials else None 
    for rel in sorted ((fig_files or {}).keys ()):
        digest =_sha256_root_file (materials_root ,rel )if materials_root else None 
        if digest is None :
            warnings .append ("integrity_material_unreadable: %s（原始 PDF freshness 无法建立）"%rel )
            continue 
        material_inputs [rel ]={"sha256":digest }
    inventory =sorted (_rel_posix (materials_root ,path )for path in (_material_pdf_paths (materials_root )if materials_root else []))
    inventory_sha256 =hashlib .sha256 (json .dumps (inventory ,ensure_ascii =False ,separators =(",",":")).encode ("utf-8")).hexdigest ()
    return {"schema_version":2 ,"generated_at":datetime .datetime .now (datetime .timezone .utc ).isoformat ().replace ("+00:00","Z"),"mode":{"materials_scan":bool (args .materials ),"materials_root":materials_root ,"apply_questions":bool (args .apply ),"apply_wiki":bool (args .apply_wiki ),"backend":str (getattr (backend ,"name",type (backend ).__name__ )),},"inputs":inputs ,"materials":material_inputs ,"material_inventory_sha256":inventory_sha256 ,}
def _material_pdf_paths (materials ):
    ''
    pdfs =[]
    for base ,dirs ,files in os .walk (materials ):
        for d in list (dirs ):
            full =os .path .join (base ,d )
            if d in ALWAYS_PRUNE or _is_leftover_workspace (full ,d )or _is_workspace_root (full ):
                dirs .remove (d )
        for fn in sorted (files ):
            if fn .lower ().endswith (".pdf"):
                pdfs .append (os .path .join (base ,fn ))
    return sorted (pdfs )
def scan_materials (materials ,backend ,warnings ):
    ('')
    pdfs =_material_pdf_paths (materials )
    if not pdfs :
        warnings .append ("no_pdfs_found: 材料目录里没有扫到任何 PDF（路径给错或目录为空？）——疑漏交叉核对未运行")
    if pdfs and not backend .can_text ():
        _die ("材料里有 PDF 但缺文本后端——pip install pypdf（或 pymupdf）后重跑",3 )
    if pdfs and not backend .can_media ():
        warnings .append ("no_media_backend: 缺 PyMuPDF（pip install pymupdf），无法枚举页内图片/矢量对象——"  "结构信号缺失，仅靠文字信号，召回会打折")
    out ={}
    for pdf in sorted (pdfs ):
        rel =_rel_posix (materials ,pdf )
        try :
            texts =backend .pages_text (pdf )
        except Exception as e :
            warnings .append ("pdf_text_failed: %s (%s)"%(rel ,e ))
            continue 
        media =None 
        if backend .can_media ():
            try :
                media =backend .pages_media (pdf )
            except Exception as e :
                warnings .append ("media_failed: %s (%s)——该文件仅文字信号，召回打折"%(rel ,e ))
        visual ={}
        for i ,text in enumerate (texts ):
            if "\x00"in (text or ""):
                warnings .append ("nul_text: %s p.%d（提取文本含 %d 个 NUL 字节——该页可能把图/空间布局"  "退化成二进制残渣，须对照原页复核）"%(rel ,i +1 ,(text or "").count ("\x00")))
            imgs ,draws =(media [i ]if media and i <len (media )else (0 ,0 ))
            cls =classify_page (text ,images =imgs ,drawings =draws )
            if cls ["has_visual"]:
                visual [i +1 ]=cls 
        out [rel ]={"pages":len (texts ),"visual":visual }
    return out 
def _prompt_side_assets (q ):
    side ={"question_context","figure","diagram","table"}
    return [a for a in (q .get ("assets")or [])if isinstance (a ,dict )and a .get ("role")in side ]
def _answer_side_assets (q ):
    side ={"answer_context","worked_solution"}
    return [a for a in (q .get ("assets")or [])if isinstance (a ,dict )and a .get ("role")in side ]
def _usable_asset (ws ,a ):
    ''
    try :
        import validate_workspace as V 
        full ,unsafe =V ._asset_safety (ws ,a .get ("path"))
    except Exception :
        return bool (a .get ("path"))
    usable =bool ((not unsafe )and full and os .path .isfile (full )and os .access (full ,os .R_OK )and not is_link_or_reparse (full ))
    if usable and str (full ).lower ().endswith (".png"):
        usable =_is_structurally_valid_png_file (full )
    return usable 
def _usable_prompt_asset (ws ,a ):
    ''
    return _usable_asset (ws ,a )
_AUDITED_PROMPT_ASSET_TYPES ={"crop_image","diagram","table_image"}
def _usable_audited_prompt_asset (ws ,a ):
    ('')
    return (isinstance (a ,dict )and a .get ("type")in _AUDITED_PROMPT_ASSET_TYPES and _usable_asset (ws ,a ))
def _file_indexed (fig_files ,source_file ):
    ('')
    if not source_file :
        return False 
    sf =str (source_file ).replace ("\\","/")
    if sf in fig_files :
        return True 
    if "/"in sf :
        return False 
    return any (os .path .basename (r )==sf for r in fig_files )
def _visual_hits (fig_files ,source_file ,pages ):
    ('')
    if not source_file or not pages :
        return []
    sf =str (source_file ).replace ("\\","/")
    if sf in fig_files :
        vis =fig_files [sf ]["visual"]
        return sorted (p for p in pages if isinstance (p ,int )and p in vis )
    if "/"in sf :
        return []
    hits =set ()
    for rel ,info in fig_files .items ():
        if os .path .basename (rel )==sf :
            hits .update (p for p in pages if isinstance (p ,int )and p in info ["visual"])
    return sorted (hits )
def build_question_index (ws ,bank ,fig_files ,warnings =None ,source_layer ="quiz_bank",shared_prompt_answer_pages =None ):
    ('')
    questions ,prompt_suspects ,answer_suspects =[],[],[]
    per_chapter ={}
    warnings =warnings if warnings is not None else []
    unindexed =set ()
    shared_prompt_answer_pages =set (shared_prompt_answer_pages or ())
    for q in bank :
        if not isinstance (q ,dict )or q .get ("id")is None :
            continue 
        qid =str (q ["id"])
        requires =q .get ("requires_assets")is True 
        maybe =q .get ("maybe_requires_assets")is True 
        prompt_assets =[a .get ("path")for a in _prompt_side_assets (q )if a .get ("path")]
        usable_prompt =any (_usable_prompt_asset (ws ,a )for a in _prompt_side_assets (q ))
        audited_prompt =any (_usable_audited_prompt_asset (ws ,a )for a in _prompt_side_assets (q ))
        answer_assets =[a .get ("path")for a in _answer_side_assets (q )if a .get ("path")]
        usable_answer =any (_usable_asset (ws ,a )for a in _answer_side_assets (q ))
        try :
            import validate_workspace as V 
            official_sources =V .MATERIAL_SOURCES 
        except Exception :
            official_sources ={"teacher","material"}
        official_src =q .get ("source")in official_sources and q .get ("ai_generated")is not True 
        has_answer =official_src and any (q .get (k )not in (None ,"",[])for k in ("answer","answer_keywords"))
        q_hits =_visual_hits (fig_files ,q .get ("source_file"),q .get ("source_pages"))
        a_hits =_visual_hits (fig_files ,q .get ("answer_source_file")or q .get ("source_file"),q .get ("answer_source_pages"))
        item_prompt_pages =_resolved_page_pairs (fig_files ,q .get ("source_file"),q .get ("source_pages"))
        item_shared_pages =sorted (item_prompt_pages &shared_prompt_answer_pages )
        item_shared_refs =[{"source_file":source ,"page":page }for source ,page in item_shared_pages ]
        if fig_files and q .get ("source_file")and q .get ("source_pages")and not _file_indexed (fig_files ,q .get ("source_file")):
            sf_disp =str (q .get ("source_file"))
            if sf_disp not in unindexed :
                unindexed .add (sf_disp )
                warnings .append ("source_pdf_not_indexed: %s（题目出处 PDF 不在 --materials 扫描结果里，"  "这些题的疑漏不可核对）"%sf_disp )
        ans_sf =q .get ("answer_source_file")or q .get ("source_file")
        if fig_files and ans_sf and q .get ("answer_source_pages")and not _file_indexed (fig_files ,ans_sf ):
            sf_disp =str (ans_sf )
            key ="answer:"+sf_disp 
            if key not in unindexed :
                unindexed .add (key )
                warnings .append ("answer_source_pdf_not_indexed: %s（答案出处 PDF 不在 --materials 扫描结果里，"  "答案侧视觉疑漏不可核对）"%sf_disp )
        chap =q .get ("chapter")if q .get ("chapter")is not None else q .get ("phase")
        rec ={"id":qid ,"chapter":chap ,"source_layer":source_layer ,"requires_assets":requires ,"maybe_requires_assets":maybe ,"prompt_assets":prompt_assets ,"answer_assets":answer_assets ,"source_file":q .get ("source_file"),"source_pages":q .get ("source_pages"),"has_official_answer":has_answer ,"answer_source_file":q .get ("answer_source_file"),"answer_source_pages":q .get ("answer_source_pages"),"question_pages_visual":q_hits ,"answer_pages_visual":(a_hits if q .get ("answer_source_pages")else None ),"shared_prompt_answer_pages":item_shared_refs ,"has_audited_prompt_asset":audited_prompt ,}
        questions .append (rec )
        ch =str (chap )if chap is not None else "?"
        c =per_chapter .setdefault (ch ,{"questions":0 ,"requires":0 ,"maybe":0 ,"suspects":0 ,"prompt_suspects":0 ,"answer_suspects":0 ,"shared_prompt_answer_blockers":0 })
        c ["questions"]+=1 
        c ["requires"]+=int (requires )
        c ["maybe"]+=int (maybe )
        declared_but_unusable =(requires or maybe )and not usable_prompt 
        inferred_unlabelled =bool (q_hits )and not requires and not maybe and not usable_prompt 
        shared_unresolved =bool (item_shared_pages )and not audited_prompt 
        if declared_but_unusable or inferred_unlabelled or shared_unresolved :
            c ["suspects"]+=1 
            c ["prompt_suspects"]+=1 
            c ["shared_prompt_answer_blockers"]+=int (shared_unresolved )
            candidate_pages =q_hits or [p for p in (q .get ("source_pages")or [])if isinstance (p ,int )and not isinstance (p ,bool )and p >=1 ]
            reason =("题面页同时也是答案页；整页截图会提前泄露答案，须提供经审核的独立题面裁剪图"if shared_unresolved else "题目已声明 requires_assets/maybe_requires_assets，但没有可读的题面 asset"if declared_but_unusable else "题目出处页面命中视觉页（结构/排版/词面信号），但当前来源层未标图依赖且无可用题面 asset")
            suspect ={"id":qid ,"chapter":chap ,"source_layer":source_layer ,"source_file":q .get ("source_file"),"visual_pages":candidate_pages ,"reason":reason }
            if shared_unresolved :
                suspect .update ({"blocker":"shared_prompt_answer_page","auto_apply_blocked":True ,"shared_prompt_answer_pages":item_shared_refs ,})
                warnings .append ("shared_prompt_answer_page: %s:%s 的题面页与答案页重合（%s）；"  "禁止自动挂整页题面图，须提供可读的 crop_image/diagram/table_image"%(source_layer ,qid ,"、".join ("%s p.%d"%(r ["source_file"],r ["page"])for r in item_shared_refs )))
            prompt_suspects .append (suspect )
        if a_hits and not usable_answer :
            c ["answer_suspects"]+=1 
            answer_suspects .append ({"id":qid ,"chapter":chap ,"source_layer":source_layer ,"source_file":ans_sf ,"visual_pages":a_hits ,"reason":"答案出处页面命中视觉页，但当前来源层没有可用 answer_context/worked_solution asset"})
    return questions ,per_chapter ,prompt_suspects ,answer_suspects 
_SAFE_NAME_RE =re .compile (r"[^A-Za-z0-9_\-]+")
def _live_visual_asset_policy (ws ):
    ''
    try :
        snapshot =workspace_asset_policy_snapshot (ws )
    except ValueError as exc :
        _die ("cannot load complete live workspace asset policy: %s"%exc )
    problems =list (snapshot .get ("unsafe_paths")or ())+list (snapshot .get ("conflicts")or ())
    if problems :
        _die ("live workspace asset policy is not publishable: %s"%problems [0 ])
    return snapshot 
def _merged_policy_owners (live ,supplied =None ,extra =()):
    ''
    output ={"quiz_rows":[],"teaching_rows":[],"content_units":[]}
    for layer in output :
        seen =set ()
        for collection in (live .get (layer )or (),(supplied or {}).get (layer )or (),(extra or {}).get (layer )or (),):
            for row in collection :
                identity =id (row )
                if identity not in seen :
                    output [layer ].append (row )
                    seen .add (identity )
    return output 
def _effective_tainted_keys (live ,supplied =None ):
    return set (live .get ("tainted_keys")or ())|set (supplied or ())
def _require_standard_visual_asset_root (ws ,asset_root ,label ):
    ''
    expected =os .path .abspath (os .path .join (ws ,"references","assets"))
    supplied =os .path .abspath (asset_root )
    if os .path .normcase (os .path .normpath (supplied ))!=os .path .normcase (os .path .normpath (expected )):
        _die ("%s must be exactly <workspace>/references/assets: %s"%(label ,asset_root ))
    if _path_has_link_or_reparse_component (ws ,expected ):
        _die ("%s rejects a link/reparse-backed references/assets path"%label )
    ws_real =os .path .realpath (ws )
    root_real =os .path .realpath (expected )
    try :
        inside =os .path .commonpath ([os .path .normcase (root_real ),os .path .normcase (ws_real )])==os .path .normcase (ws_real )
    except ValueError :
        inside =False 
    if not inside :
        _die ("%s resolved outside the workspace: %s"%(label ,asset_root ))
    return root_real 
def _planned_repair_assets (ws ,asset_root ,bank ,suspects ,side ):
    ''
    ws_abs =os .path .realpath (ws )
    root_abs =os .path .realpath (asset_root )
    by_id ={str (item .get ("id")):item for item in (bank or ())if isinstance (item ,dict )and item .get ("id")is not None }
    output =[]
    for suspect in suspects or ():
        if side =="prompt"and suspect .get ("blocker")=="shared_prompt_answer_page":
            continue 
        item_id =str (suspect .get ("id"))
        item =by_id .get (item_id )
        if item is None :
            continue 
        fallback_source =((item .get ("answer_source_file")or item .get ("source_file"))if side =="answer"else item .get ("source_file"))
        source_file =str (suspect .get ("source_file")or fallback_source or "").replace ("\\","/")
        layer =str (suspect .get ("source_layer")or "quiz_bank")
        digest_seed ="%s\0%s\0%s\0%s"%(layer ,item_id ,side ,source_file )
        digest =hashlib .sha1 (digest_seed .encode ("utf-8")).hexdigest ()[:8 ]
        role ="answer_context"if side =="answer"else "question_context"
        for page in suspect .get ("visual_pages")or ():
            if type (page )is not int or page <1 :
                raise ValueError ("repair suspect %s has invalid page %r"%(item_id ,page ))
            name ="%s_%s%s_p%d.png"%(_SAFE_NAME_RE .sub ("_",item_id )[:60 ],digest ,"_answer"if side =="answer"else "",page ,)
            full_path =os .path .join (root_abs ,name )
            relative_path =_rel_posix (ws_abs ,full_path )
            key =physical_asset_key (relative_path )
            if key is None :
                raise ValueError ("repair target is not a canonical workspace asset path: %r"%relative_path )
            output .append ({"item":item ,"item_id":item_id ,"source_layer":layer ,"source_file":source_file ,"side":side ,"role":role ,"page":page ,"full_path":full_path ,"path":relative_path ,"key":key ,})
    return output 
def _repair_policy_collections (ws ,bank ,suspects ,policy_rows =None ):
    ''
    live =_live_visual_asset_policy (ws )
    layers ={str (suspect .get ("source_layer")or "quiz_bank")for suspect in (suspects or ())}
    if len (layers )>1 :
        raise ValueError ("one repair call cannot mix quiz and teaching source layers")
    if layers =={"teaching_examples"}:
        quiz_rows =list (live .get ("quiz_rows")or ())
        teaching_rows =list (bank or ())
    else :
        quiz_rows =list (bank or ())
        teaching_rows =list (live .get ("teaching_rows")or ())
    content_units =list (live .get ("content_units")or ())
    owners =_merged_policy_owners (live ,policy_rows ,{"quiz_rows":quiz_rows ,"teaching_rows":teaching_rows ,"content_units":content_units ,},)
    return quiz_rows ,teaching_rows ,content_units ,owners ,live 
_REPAIR_WRITER_ID ="build_visual_index.repair.v1"
def _iter_asset_owner_records (row ):
    ''
    if not isinstance (row ,dict ):
        return 
    if row .get ("asset_path")is not None or row .get ("asset_role")is not None :
        yield row .get ("asset_path"),row .get ("asset_role"),row 
    for asset in row .get ("assets")or ():
        if isinstance (asset ,dict ):
            yield asset .get ("path"),asset .get ("role"),asset 
    metadata =row .get ("metadata")
    if isinstance (metadata ,dict ):
        for asset in metadata .get ("assets")or ():
            if isinstance (asset ,dict ):
                yield asset .get ("path"),asset .get ("role"),asset 
def _repair_owner_same_item_side (plan ,owner ):
    expected_layer ="teaching"if plan ["source_layer"]=="teaching_examples"else "quiz"
    if owner .get ("layer")!=expected_layer or owner .get ("role")!=plan ["role"]:
        return False 
    row =owner .get ("row")
    if not isinstance (row ,dict )or str (row .get ("id"))!=plan ["item_id"]:
        return False 
    left =str (row .get ("chapter")or row .get ("phase")or row .get ("chapter_id")or "")
    item =plan ["item"]
    right =str (item .get ("chapter")or item .get ("phase")or item .get ("chapter_id")or "")
    return not left or not right or left ==right 
def _repair_owner_is_refreshable (ws ,plan ,owner ):
    ''
    declaration =owner .get ("declaration")
    if not isinstance (declaration ,dict ):
        return False 
    if not (_repair_owner_same_item_side (plan ,owner )and declaration .get ("generated_by")==_REPAIR_WRITER_ID and declaration .get ("source_layer")==plan ["source_layer"]and declaration .get ("source_file")==plan ["source_file"]and declaration .get ("source_page")==plan ["page"]and declaration .get ("side")==plan ["side"]):
        return False 
    expected =declaration .get ("sha256")
    if not isinstance (expected ,str )or not re .fullmatch (r"[0-9a-f]{64}",expected ):
        return False 
    try :
        with open (plan ["full_path"],"rb")as stream :
            actual =hashlib .sha256 (stream .read ()).hexdigest ()
    except OSError :
        return False 
    return actual ==expected 
def _candidate_repair_policy_errors (ws ,plans ,quiz_rows ,teaching_rows ,content_units ,ownership_rows =None ):
    ('')
    errors =[]
    candidate_collections =(("quiz",list (quiz_rows or ())),("teaching",list (teaching_rows or ())),("content-unit",list (content_units or ())),)
    if ownership_rows is None :
        collections =candidate_collections 
    else :
        collections =(("quiz",list (ownership_rows .get ("quiz_rows")or ())),("teaching",list (ownership_rows .get ("teaching_rows")or ())),("content-unit",list (ownership_rows .get ("content_units")or ())),)
    existing ={}
    for layer ,rows in collections :
        for index ,row in enumerate (rows ):
            for path ,role ,declaration in _iter_asset_owner_records (row ):
                key =physical_asset_key (path )
                if key is not None :
                    existing .setdefault (key ,[]).append ({"row":row ,"layer":layer ,"index":index ,"path":path ,"role":role ,"declaration":declaration ,})
    planned_by_key ={}
    for plan in plans :
        previous =planned_by_key .get (plan ["key"])
        if previous is not None and (previous ["item"]is not plan ["item"]or previous ["role"]!=plan ["role"]or previous ["source_file"]!=plan ["source_file"]or previous ["page"]!=plan ["page"]):
            errors .append ("repair target %s is shared by multiple planned operations"%plan ["path"])
        else :
            planned_by_key [plan ["key"]]=plan 
        owners =existing .get (plan ["key"],())
        target_exists =os .path .lexists (plan ["full_path"])
        if target_exists and (is_link_or_reparse (plan ["full_path"])or not os .path .isfile (plan ["full_path"])):
            errors .append ("repair target %s is non-regular or link-backed"%plan ["path"])
        refreshable_owner =False 
        for owner in owners :
            same_item_side =_repair_owner_same_item_side (plan ,owner )
            stale_same_item_side =(not target_exists and same_item_side and not _usable_asset (ws ,{"path":owner ["path"]})and (owner ["row"]is plan ["item"]or (isinstance (owner .get ("declaration"),dict )and owner ["declaration"].get ("source_file")==plan ["source_file"])))
            if stale_same_item_side :
                continue 
            if target_exists and _repair_owner_is_refreshable (ws ,plan ,owner ):
                refreshable_owner =True 
                continue 
            errors .append ("repair target %s is already owned by %s[%d] role=%r path=%r"%(plan ["path"],owner ["layer"],owner ["index"],owner ["role"],owner ["path"]))
        if target_exists and not refreshable_owner :
            errors .append ("repair target %s already exists without current same-side/source "  "writer ownership"%plan ["path"])
    candidates ={}
    for plan in plans :
        ident =id (plan ["item"])
        candidate =candidates .get (ident )
        if candidate is None :
            candidate =dict (plan ["item"])
            current_assets =plan ["item"].get ("assets")
            candidate ["assets"]=list (current_assets )if isinstance (current_assets ,list )else []
            candidates [ident ]=candidate 
        if not any (isinstance (asset ,dict )and physical_asset_key (asset .get ("path"))==plan ["key"]and asset .get ("role")==plan ["role"]for asset in candidate ["assets"]):
            candidate ["assets"].append ({"path":plan ["path"],"role":plan ["role"],"type":"page_image","generated_by":_REPAIR_WRITER_ID ,"source_layer":plan ["source_layer"],"source_file":plan ["source_file"],"source_page":plan ["page"],"side":plan ["side"],})
        if plan ["side"]=="prompt":
            candidate ["maybe_requires_assets"]=True 
    def replaced (rows ):
        return [candidates .get (id (row ),row )for row in rows ]
    audit =audit_asset_policy (quiz_rows =replaced (list (quiz_rows or ())),teaching_rows =replaced (list (teaching_rows or ())),content_units =list (content_units or ()),)
    errors .extend (audit ["invalid_declarations"])
    errors .extend (audit ["conflicts"])
    return errors 
def _preflight_repair_assets (ws ,asset_root ,repair_sets ,policy_rows ):
    ''
    plans =[]
    for bank ,suspects ,side in repair_sets :
        plans .extend (_planned_repair_assets (ws ,asset_root ,bank ,suspects ,side ))
    errors =_candidate_repair_policy_errors (ws ,plans ,policy_rows .get ("quiz_rows")or (),policy_rows .get ("teaching_rows")or (),policy_rows .get ("content_units")or (),)
    if errors :
        _die ("--apply candidate asset policy rejected before write: %s"%errors [0 ])
    return plans 
def _apply_page_suspects_legacy (ws ,materials ,bank ,suspects ,backend ,asset_root ,warnings ,side ,tainted_keys =None ,policy_rows =None ,preflight_done =False ):
    ('')
    return _apply_page_suspects (ws ,materials ,bank ,suspects ,backend ,asset_root ,warnings ,side ,tainted_keys =tainted_keys ,policy_rows =policy_rows ,preflight_done =preflight_done ,)
def _resolve_apply_pdf (materials ,source_file ,item_id ,batch_warnings ):
    ''
    sf =str (source_file or "").replace ("\\","/")
    if (os .path .isabs (sf )or re .match (r"^[A-Za-z]:",sf )or "://"in sf or ".."in sf .split ("/")):
        batch_warnings .append ("apply_skip_unsafe_source: %s (unsafe source_file: %s)"%(item_id ,sf ))
        return sf ,None 
    candidate =os .path .join (materials ,sf .replace ("/",os .sep ))
    if os .path .isfile (candidate ):
        pdf =candidate 
    elif "/"not in sf :
        matches =[]
        for base ,dirs ,files in os .walk (materials ):
            for directory in list (dirs ):
                full =os .path .join (base ,directory )
                if (directory in ALWAYS_PRUNE or _is_leftover_workspace (full ,directory )or _is_workspace_root (full )):
                    dirs .remove (directory )
            if sf in files :
                matches .append (os .path .join (base ,sf ))
        if len (matches )==1 :
            pdf =matches [0 ]
        else :
            code ="ambiguous"if matches else "no_pdf"
            batch_warnings .append ("apply_skip_%s: %s (%s; matches=%d)"%(code ,item_id ,sf ,len (matches )))
            return sf ,None 
    else :
        batch_warnings .append ("apply_skip_no_pdf: %s (%s)"%(item_id ,sf ))
        return sf ,None 
    materials_real =os .path .realpath (materials )
    pdf_real =os .path .realpath (pdf )
    try :
        inside =os .path .commonpath ([os .path .normcase (pdf_real ),os .path .normcase (materials_real )])==os .path .normcase (materials_real )
    except ValueError :
        inside =False 
    if not inside :
        batch_warnings .append ("apply_skip_outside_materials: %s (%s)"%(item_id ,sf ))
        return sf ,None 
    return sf ,pdf 
def _apply_page_suspects (ws ,materials ,bank ,suspects ,backend ,asset_root ,warnings ,side ,tainted_keys =None ,policy_rows =None ,preflight_done =False ):
    ''
    batch_warnings =[]
    if side =="prompt":
        allowed =[]
        for suspect in suspects :
            if suspect .get ("blocker")!="shared_prompt_answer_page":
                allowed .append (suspect )
                continue 
            batch_warnings .append ("apply_skip_shared_prompt_answer_page: %s (prompt and answer share a page)"%suspect .get ("id"))
        suspects =allowed 
    if not suspects :
        warnings .extend (batch_warnings )
        return 0 
    if not backend .can_render ():
        _die ("--apply requires a PDF page rendering backend",3 )
    root_abs =_require_standard_visual_asset_root (ws ,asset_root ,"--apply --asset-root")
    try :
        (quiz_rows ,teaching_rows ,content_units ,ownership_rows ,live_policy )=_repair_policy_collections (ws ,bank ,suspects ,policy_rows )
        plans =_planned_repair_assets (ws ,root_abs ,bank ,suspects ,side )
        errors =_candidate_repair_policy_errors (ws ,plans ,quiz_rows ,teaching_rows ,content_units ,ownership_rows =ownership_rows ,)
    except ValueError as exc :
        _die ("--apply candidate asset policy could not be built: %s"%exc )
    if errors :
        _die ("--apply candidate asset policy rejected before write: %s"%errors [0 ])
    effective_taint =_effective_tainted_keys (live_policy ,tainted_keys )
    candidate =copy .deepcopy (bank )
    candidate_by_id ={str (item .get ("id")):item for item in candidate if isinstance (item ,dict )and item .get ("id")is not None }
    plan_by_item_page ={(str (plan ["item_id"]),plan ["page"]):plan for plan in plans }
    payloads =[]
    applied =0 
    role ="answer_context"if side =="answer"else "question_context"
    for suspect in suspects :
        item_id =str (suspect .get ("id"))
        item =candidate_by_id .get (item_id )
        if item is None :
            continue 
        pages =list (suspect .get ("visual_pages")or ())
        if not pages :
            batch_warnings .append ("%sapply_skip_no_pages: %s"%("answer_"if side =="answer"else "",item_id ))
            continue 
        fallback =(item .get ("answer_source_file")or item .get ("source_file")if side =="answer"else item .get ("source_file"))
        source_file ,pdf =_resolve_apply_pdf (materials ,suspect .get ("source_file")or fallback ,item_id ,batch_warnings ,)
        if pdf is None :
            continue 
        item_plans =[]
        for page in pages :
            plan =plan_by_item_page .get ((item_id ,page ))
            if plan is None :
                _die ("--apply deterministic target plan drifted for %s p.%s"%(item_id ,page ))
            if is_student_attempt_tainted (plan ["path"],effective_taint ):
                batch_warnings .append ("%sapply_skip_student_attempt_path: %s"%("answer_"if side =="answer"else "",item_id ))
                item_plans =[]
                break 
            item_plans .append (plan )
        if not item_plans :
            continue 
        rendered =[]
        complete =True 
        for page ,plan in zip (pages ,item_plans ):
            try :
                payload =backend .render_page_png (pdf ,page -1 )
            except Exception as exc :
                batch_warnings .append ("%sapply_skip_render_failed: %s p.%d (%s)"%("answer_"if side =="answer"else "",item_id ,page ,exc ))
                complete =False 
                break 
            if not payload :
                batch_warnings .append ("%sapply_skip_render_failed: %s p.%d"%("answer_"if side =="answer"else "",item_id ,page ))
                complete =False 
                break 
            payload =_validated_png_payload (payload ,"--apply %s %s p.%d"%(side ,item_id ,page ))
            rendered .append ((page ,plan ,payload ))
        if not complete :
            continue 
        current_assets =item .get ("assets")if isinstance (item .get ("assets"),list )else []
        kept ,pruned =[],[]
        for asset in current_assets :
            answer_asset =(isinstance (asset ,dict )and asset .get ("role")in ("answer_context","worked_solution"))
            keep =(isinstance (asset ,dict )and _usable_asset (ws ,asset )if side =="prompt"else not answer_asset or _usable_asset (ws ,asset ))
            if keep :
                kept .append (asset )
            else :
                pruned .append ("%sapply_pruned_stale_asset: %s (%r)"%("answer_"if side =="answer"else "",item_id ,asset .get ("path")if isinstance (asset ,dict )else asset ))
        updated_assets =list (kept )
        for page ,plan ,payload in rendered :
            declaration ={"path":plan ["path"],"role":role ,"type":"page_image","sha256":hashlib .sha256 (payload ).hexdigest (),"generated_by":_REPAIR_WRITER_ID ,"source_layer":str (suspect .get ("source_layer")or "quiz_bank"),"source_file":source_file ,"source_page":page ,"side":side ,"caption":"Rendered source page %s p.%d (%s side)"%(source_file ,page ,side ),}
            replaced =False 
            for index ,current in enumerate (updated_assets ):
                if (isinstance (current ,dict )and physical_asset_key (current .get ("path"))==plan ["key"]and current .get ("role")==role ):
                    updated_assets [index ]=declaration 
                    replaced =True 
                    break 
            if not replaced :
                updated_assets .append (declaration )
            payloads .append ((plan ["full_path"],payload ))
        item ["assets"]=updated_assets 
        if side =="prompt":
            item ["maybe_requires_assets"]=True 
        batch_warnings .extend (pruned )
        applied +=1 
    try :
        _publish_bytes_transactionally (payloads )
    except OSError as exc :
        _die ("--apply transactional asset publication failed: %s"%exc )
    if applied :
        _replace_list_records_in_place (bank ,candidate )
    warnings .extend (batch_warnings )
    return applied 
def apply_suspects (ws ,materials ,bank ,suspects ,backend ,asset_root ,warnings ,tainted_keys =None ,policy_rows =None ,preflight_done =False ):
    ''
    return _apply_page_suspects (ws ,materials ,bank ,suspects ,backend ,asset_root ,warnings ,"prompt",tainted_keys =tainted_keys ,policy_rows =policy_rows ,preflight_done =preflight_done )
def apply_answer_suspects (ws ,materials ,bank ,suspects ,backend ,asset_root ,warnings ,tainted_keys =None ,policy_rows =None ,preflight_done =False ):
    ''
    return _apply_page_suspects (ws ,materials ,bank ,suspects ,backend ,asset_root ,warnings ,"answer",tainted_keys =tainted_keys ,policy_rows =policy_rows ,preflight_done =preflight_done )
def _merge_per_chapter (*rollups ):
    merged ={}
    for rollup in rollups :
        for chapter ,counts in (rollup or {}).items ():
            row =merged .setdefault (chapter ,{})
            for key ,value in counts .items ():
                row [key ]=row .get (key ,0 )+value 
    return merged 
def _write_json_with_backup (path ,value ):
    ''
    with open (path ,"rb")as src :
        original =src .read ()
    backup =path +".bak"
    _atomic_write_bytes (backup ,original )
    payload =(json .dumps (value ,ensure_ascii =False ,indent =2 )+"\n").encode ("utf-8")
    _atomic_write_bytes (path ,payload )
def _apply_repair_run_transaction (ws ,materials ,backend ,asset_root ,warnings ,bank ,teaching ,bank_path ,teaching_path ,bank_prompt_suspects ,bank_answer_suspects ,teaching_prompt_suspects ,teaching_answer_suspects ,tainted_keys ,policy_rows ,plans ):
    ''
    watched =[plan ["full_path"]for plan in plans ]
    watched .extend ((bank_path ,bank_path +".bak",teaching_path ,teaching_path +".bak"))
    try :
        states =_snapshot_file_states (watched )
    except OSError as exc :
        _die ("--apply transaction preflight failed: %s"%exc )
    original_bank =copy .deepcopy (bank )
    original_teaching =copy .deepcopy (teaching )
    warning_count =len (warnings )
    counts =[0 ,0 ,0 ,0 ]
    try :
        if bank_prompt_suspects :
            counts [0 ]=apply_suspects (ws ,materials ,bank ,bank_prompt_suspects ,backend ,asset_root ,warnings ,tainted_keys =tainted_keys ,policy_rows =policy_rows ,preflight_done =True ,)
        if bank_answer_suspects :
            counts [1 ]=apply_answer_suspects (ws ,materials ,bank ,bank_answer_suspects ,backend ,asset_root ,warnings ,tainted_keys =tainted_keys ,policy_rows =policy_rows ,preflight_done =True ,)
        if teaching_prompt_suspects :
            counts [2 ]=apply_suspects (ws ,materials ,teaching ,teaching_prompt_suspects ,backend ,asset_root ,warnings ,tainted_keys =tainted_keys ,policy_rows =policy_rows ,preflight_done =True ,)
        if teaching_answer_suspects :
            counts [3 ]=apply_answer_suspects (ws ,materials ,teaching ,teaching_answer_suspects ,backend ,asset_root ,warnings ,tainted_keys =tainted_keys ,policy_rows =policy_rows ,preflight_done =True ,)
        if counts [0 ]or counts [1 ]:
            _write_json_with_backup (bank_path ,bank )
        if counts [2 ]or counts [3 ]:
            _write_json_with_backup (teaching_path ,teaching )
    except BaseException :
        _replace_list_records_in_place (bank ,original_bank )
        _replace_list_records_in_place (teaching ,original_teaching )
        del warnings [warning_count :]
        try :
            _restore_file_states (states )
        except OSError as rollback_exc :
            raise RuntimeError ("--apply rollback failed: %s"%rollback_exc )
        raise 
    return tuple (counts )
_WIKI_PAGE_RE =re .compile (r"<!--(?!\s*wiki-visual-index:)\s*(.*?)\s+p\.(\d+)\s*-->")
_MD_IMAGE_RE =re .compile (r"!\[([^\]]*)\]\(([^)]+)\)")
_OLD_GALLERY_ALT_RE =re .compile (r"^(.*?)\s+第\s*(\d+)\s*页图示\s*$")
_INDEX_ALT_RE =re .compile (r"^原页图示\s+(.*?)\s+p\.(\d+)\s*$")
_WIKI_MARKER_RE =re .compile (r"<!--\s*wiki-visual-index:\s*(.*?)\s+p\.(\d+)\s*-->",re .S )
_WIKI_MARKED_IMAGE_RE =re .compile (r"<!--\s*wiki-visual-index:\s*(.*?)\s+p\.(\d+)\s*-->\s*"  r"!\[([^\]]*)\]\(([^)]+)\)",re .S )
def _wiki_generated_asset_rel (source_file ,page ):
    digest =hashlib .sha1 (source_file .encode ("utf-8")).hexdigest ()[:10 ]
    return "references/assets/wiki_%s_p%04d.png"%(digest ,page )
def _wiki_marker_matches (source_token ,page_token ,source_file ,page ):
    token =str (source_token or "").strip ().replace ("\\","/")
    return (int (page_token )==int (page )and (token ==source_file or ("/"not in token and os .path .basename (source_file )==token )))
def _validated_owned_wiki_block (text ,source_file ,page ):
    ''
    markers =[match for match in _WIKI_MARKER_RE .finditer (text )if _wiki_marker_matches (match .group (1 ),match .group (2 ),source_file ,page )]
    blocks =[match for match in _WIKI_MARKED_IMAGE_RE .finditer (text )if _wiki_marker_matches (match .group (1 ),match .group (2 ),source_file ,page )]
    if len (markers )>1 or len (blocks )>1 :
        raise ValueError ("duplicate wiki-visual-index markers for %s p.%d"%(source_file ,page ))
    if markers and len (blocks )!=1 :
        raise ValueError ("wiki-visual-index marker for %s p.%d is marker-only or has malformed image markup"%(source_file ,page ))
    return blocks [0 ]if blocks else None 
def _validate_wiki_marker_contracts (text ,fig_files ):
    ''
    markers =list (_WIKI_MARKER_RE .finditer (text ))
    blocks =list (_WIKI_MARKED_IMAGE_RE .finditer (text ))
    block_starts ={match .start ()for match in blocks }
    if any (marker .start ()not in block_starts for marker in markers ):
        raise ValueError ("wiki-visual-index marker is marker-only or has malformed image markup")
    if len (blocks )!=len (markers ):
        raise ValueError ("wiki-visual-index marker/image cardinality is inconsistent")
    seen =set ()
    for marker in markers :
        token =str (marker .group (1 )or "").strip ().replace ("\\","/")
        source =_resolve_fig_file (fig_files or {},token )or token 
        key =(source ,int (marker .group (2 )))
        if key in seen :
            raise ValueError ("duplicate wiki-visual-index markers for %s p.%d"%key )
        seen .add (key )
def _resolve_fig_file (fig_files ,source_file ):
    ''
    sf =str (source_file or "").strip ().replace ("\\","/")
    if sf in fig_files :
        return sf 
    if "/"in sf :
        return None 
    hits =[rel for rel in fig_files if os .path .basename (rel )==sf ]
    return hits [0 ]if len (hits )==1 else None 
def _resolve_fig_files (fig_files ,source_file ):
    ('')
    sf =str (source_file or "").strip ().replace ("\\","/")
    if sf in fig_files :
        return [sf ]
    if not sf or "/"in sf :
        return []
    return sorted (rel for rel in fig_files if os .path .basename (rel )==sf )
def _resolved_page_pairs (fig_files ,source_file ,pages ):
    ''
    rels =_resolve_fig_files (fig_files ,source_file )
    if not rels :
        unresolved =str (source_file or "").strip ().replace ("\\","/")
        rels =[unresolved ]if unresolved else []
    return {(rel ,page )for rel in rels for page in (pages or [])if type (page )is int and page >=1 }
def derive_item_page_sides (fig_files ,*item_layers ):
    ('')
    prompt_pages ,answer_pages =set (),set ()
    for layer in item_layers :
        for item in layer or []:
            if not isinstance (item ,dict ):
                continue 
            prompt_pages .update (_resolved_page_pairs (fig_files ,item .get ("source_file"),item .get ("source_pages")))
            answer_source =item .get ("answer_source_file")or item .get ("source_file")
            answer_pages .update (_resolved_page_pairs (fig_files ,answer_source ,item .get ("answer_source_pages")))
    return prompt_pages ,answer_pages 
def _wiki_asset_record (ws ,wiki_path ,raw_link ,origin =None ,tainted_keys =None ,asset_policy =None ):
    ''
    link =str (raw_link or "").strip ()
    if link .startswith ("<")and link .endswith (">"):
        link =link [1 :-1 ].strip ()
    norm =link .replace ("\\","/")
    if not norm or "://"in norm or norm .startswith (("/","\\"))or re .match (r"^[A-Za-z]:",norm ):
        return {"markdown_path":link ,"workspace_path":None ,"usable":False ,"unsafe":True ,"origin":origin }
    lexical_full =os .path .abspath (os .path .join (os .path .dirname (wiki_path ),*norm .split ("/")))
    full =os .path .realpath (lexical_full )
    ws_real =os .path .realpath (ws )
    try :
        inside =os .path .commonpath ([os .path .normcase (full ),os .path .normcase (ws_real )])==os .path .normcase (ws_real )
    except ValueError :
        inside =False 
    rel =_rel_posix (ws_real ,full )if inside else None 
    tainted =bool (rel and is_student_attempt_tainted (rel ,tainted_keys or ()))
    policy_problem =None 
    if rel and asset_policy is not None :
        try :
            tainted =tainted or workspace_asset_is_student_attempt (rel ,ws ,asset_policy )
        except ValueError as exc :
            policy_problem =str (exc )
    linked =bool (_path_has_link_or_reparse_component (ws ,lexical_full ))
    usable =bool (inside and not tainted and not linked and not policy_problem and os .path .isfile (full )and os .access (full ,os .R_OK ))
    png_valid =None 
    if usable and str (full ).lower ().endswith (".png"):
        png_valid =_is_structurally_valid_png_file (full )
        usable =usable and png_valid 
    elif usable and origin =="generated":
        png_valid =False 
        usable =False 
    return {"markdown_path":link ,"workspace_path":rel ,"origin":origin ,"usable":usable ,"unsafe":bool (not inside or linked or policy_problem ),"student_attempt":tainted ,"png_valid":png_valid ,"link_or_reparse":linked ,"asset_policy_error":policy_problem }
def _wiki_inventory (ws ,fig_files ,warnings ,tainted_keys =None ):
    ('')
    asset_policy =_live_visual_asset_policy (ws )
    tainted_keys =_effective_tainted_keys (asset_policy ,tainted_keys )
    wiki_dir =os .path .join (ws ,"references","wiki")
    anchors ,assets ,manual_block_assets ,claims ={},{},{},{}
    if not os .path .isdir (wiki_dir ):
        warnings .append ("wiki_visual_no_wiki_dir: references/wiki 不存在，无法核对视觉覆盖")
        return anchors ,assets ,manual_block_assets ,claims 
    if _path_has_link_or_reparse_component (ws ,wiki_dir ):
        warnings .append ("wiki_visual_unsafe_wiki_dir: references/wiki 含符号链接父级，拒绝把外部内容计入覆盖")
        return anchors ,assets ,manual_block_assets ,claims 
    for fn in sorted (os .listdir (wiki_dir )):
        path =os .path .join (wiki_dir ,fn )
        if (not fn .lower ().endswith (".md")or not os .path .isfile (path )or is_link_or_reparse (path )):
            continue 
        try :
            with open (path ,encoding ="utf-8")as f :
                text0 =f .read ()
        except (OSError ,UnicodeDecodeError )as e :
            warnings .append ("wiki_visual_read_failed: %s (%s)"%(fn ,e ))
            continue 
        marks =list (_WIKI_PAGE_RE .finditer (text0 ))
        for i ,mark in enumerate (marks ):
            rel =_resolve_fig_file (fig_files ,mark .group (1 ))
            if rel is None :
                continue 
            page =int (mark .group (2 ))
            key =(fn ,rel ,page )
            anchors [key ]=True 
            claims .setdefault (rel ,{}).setdefault (fn ,set ()).add (page )
            block =text0 [mark .end ():(marks [i +1 ].start ()if i +1 <len (marks )else len (text0 ))]
            claimed_spans =[]
            for marked in _WIKI_MARKED_IMAGE_RE .finditer (block ):
                exp_rel =_resolve_fig_file (fig_files ,marked .group (1 ))
                if exp_rel is None :
                    continue 
                target =(fn ,exp_rel ,int (marked .group (2 )))
                asset =_wiki_asset_record (ws ,path ,marked .group (4 ).strip (),"generated",tainted_keys ,asset_policy )
                expected =_wiki_generated_asset_rel (exp_rel ,int (marked .group (2 )))
                asset ["expected_workspace_path"]=expected 
                asset ["writer_target_match"]=(physical_asset_key (asset .get ("workspace_path"))==physical_asset_key (expected ))
                if not asset ["writer_target_match"]:
                    asset ["usable"]=False 
                assets .setdefault (target ,[]).append (asset )
                claimed_spans .append (marked .span ())
            for image in _MD_IMAGE_RE .finditer (block ):
                if any (start <=image .start ()and image .end ()<=end for start ,end in claimed_spans ):
                    continue 
                alt ,raw_link =image .group (1 ).strip (),image .group (2 ).strip ()
                manual =_wiki_asset_record (ws ,path ,raw_link ,"manual",tainted_keys ,asset_policy )
                manual_block_assets .setdefault (key ,[]).append (manual )
                explicit =_OLD_GALLERY_ALT_RE .match (alt )
                if not explicit :
                    continue 
                exp_rel =_resolve_fig_file (fig_files ,explicit .group (1 ))
                if exp_rel is None :
                    continue 
                target =(fn ,exp_rel ,int (explicit .group (2 )))
                assets .setdefault (target ,[]).append (manual )
    return anchors ,assets ,manual_block_assets ,claims 
def _visual_wiki_keys (source_file ,page ,anchors ,claims ):
    ''
    exact =sorted (k for k in anchors if k [1 ]==source_file and k [2 ]==page )
    if exact :
        return [(key ,False )for key in exact ]
    candidates =claims .get (source_file )or {}
    if not candidates :
        return [((None ,source_file ,page ),True )]
    ranked =[]
    for wiki_file ,known_pages in candidates .items ():
        distance =min (abs (page -known )for known in known_pages )
        ranked .append ((distance ,wiki_file ))
    _distance ,chosen =min (ranked )
    return [((chosen ,source_file ,page ),True )]
def _inventory_wiki_keys (source_file ,page ,anchors ,assets ,manual_block_assets ):
    ''
    inventory =set (anchors )|set (assets )|set (manual_block_assets )
    return sorted (key for key in inventory if key [1 ]==source_file and key [2 ]==page )
def build_wiki_visual_coverage (ws ,fig_files ,warnings =None ,missing_reasons =None ,emit_warnings =True ,prompt_pages =None ,answer_pages =None ,shared_blocker_pages =None ,tainted_keys =None ):
    ('')
    live_policy =_live_visual_asset_policy (ws )
    tainted_keys =_effective_tainted_keys (live_policy ,tainted_keys )
    local_warnings =[]
    anchors ,assets ,manual_block_assets ,claims =_wiki_inventory (ws ,fig_files ,local_warnings ,tainted_keys =tainted_keys )
    reasons =missing_reasons or {}
    prompt_pages =set (prompt_pages or ())
    answer_pages =set (answer_pages or ())
    shared_pages =prompt_pages &answer_pages 
    shared_blocker_pages =set (shared_blocker_pages or ())
    pages =[]
    def refs (records ,usable_only =False ):
        values =set ()
        for asset in records :
            if usable_only and not asset .get ("usable"):
                continue 
            value =asset .get ("workspace_path")or asset .get ("markdown_path")
            if value :
                values .add (value )
        return sorted (values )
    visual_pairs ={(source_file ,page )for source_file ,info in fig_files .items ()for page in (info .get ("visual")or {})}
    candidates =[]
    for source_file ,info in sorted (fig_files .items ()):
        for page ,cls in sorted ((info .get ("visual")or {}).items ()):
            for key ,inferred in _visual_wiki_keys (source_file ,page ,anchors ,claims ):
                candidates .append ((key ,inferred ,cls ,False ))
    for source_file ,page in sorted (answer_pages ):
        if (source_file ,page )in visual_pairs :
            continue 
        inventory_keys =_inventory_wiki_keys (source_file ,page ,anchors ,assets ,manual_block_assets )
        if not inventory_keys and (source_file ,page )in shared_pages :
            inventory_keys =[(None ,source_file ,page )]
        for key in inventory_keys :
            candidates .append ((key ,False ,{},True ))
    seen =set ()
    for (wiki_file ,source_file ,page ),inferred ,cls ,inventory_only in candidates :
        key =(wiki_file ,source_file ,page )
        if key in seen :
            continue 
        seen .add (key )
        declared =assets .get (key ,[])
        usable =refs (declared ,usable_only =True )
        rec ={"wiki_file":wiki_file ,"source_file":source_file ,"page":page ,"visual_kinds":cls .get ("visual_kinds")or [],"signals":cls .get ("signals")or {},"visual_candidate":not inventory_only ,"inventory_only":inventory_only ,"anchor_inferred":inferred ,"asset_paths":usable ,"declared_assets":refs (declared )}
        if (source_file ,page )in answer_pages :
            generated =[a for a in declared if a .get ("origin")=="generated"]
            manual =[a for a in declared if a .get ("origin")!="generated"]
            manual +=manual_block_assets .get (key ,[])
            is_shared =(source_file ,page )in shared_pages 
            rec .update ({"status":"shared_prompt_answer"if is_shared else "deferred_answer","reason":("shared_prompt_answer_page_deferred_from_wiki"if is_shared else "answer_only_page_deferred_from_wiki"),"generated_assets":refs (generated ),"manual_assets":refs (manual ),"manual_usable_assets":refs (manual ,usable_only =True ),})
            issues =[]
            if is_shared and (source_file ,page )in shared_blocker_pages :
                rec ["blocker"]="audited_question_side_crop_required"
                issues .append ("shared_prompt_answer_page")
            if rec ["manual_assets"]:
                rec ["coverage_issue"]="manual_answer_exposure"
                issues .append ("manual_answer_exposure")
            if issues :
                rec ["coverage_issues"]=issues 
        else :
            rec ["status"]="embedded"if usable else "missing"
            if not usable :
                default_reason ="wiki_source_unmapped"if wiki_file is None else "source_page_anchor_missing"if inferred else "not_embedded"
                rec ["reason"]=reasons .get (key ,default_reason )
        pages .append (rec )
    deferred =[p for p in pages if p ["status"]=="deferred_answer"]
    shared =[p for p in pages if p ["status"]=="shared_prompt_answer"]
    eligible =[p for p in pages if p ["status"]in ("embedded","missing")]
    missing =[p for p in eligible if p ["status"]=="missing"]
    embedded =[p for p in eligible if p ["status"]=="embedded"]
    manual_exposures =[p for p in deferred +shared if p .get ("coverage_issue")=="manual_answer_exposure"]
    shared_blockers =[p for p in shared if p .get ("blocker")]
    per_chapter ={}
    for p in pages :
        chapter_key =p ["wiki_file"]if p ["wiki_file"]is not None else "__unmapped__"
        c =per_chapter .setdefault (chapter_key ,{"detected":0 ,"embedded":0 ,"missing":0 ,"deferred_answer":0 ,"shared_prompt_answer":0 ,"total_visual_pages":0 })
        c ["total_visual_pages"]+=1 
        if p ["status"]=="deferred_answer":
            c ["deferred_answer"]+=1 
        elif p ["status"]=="shared_prompt_answer":
            c ["shared_prompt_answer"]+=1 
        else :
            c ["detected"]+=1 
            c [p ["status"]]+=1 
    if emit_warnings :
        for fn ,counts in sorted (per_chapter .items ()):
            if counts ["missing"]:
                target_fn =None if fn =="__unmapped__"else fn 
                refs0 =["%s p.%d"%(p ["source_file"],p ["page"])for p in missing if p ["wiki_file"]==target_fn ]
                local_warnings .append ("wiki_visual_missing: %s 有 %d/%d 个已检测视觉页未嵌入：%s"%(fn ,counts ["missing"],counts ["detected"],"、".join (refs0 )))
        for rec in manual_exposures :
            local_warnings .append ("wiki_answer_manual_exposure: %s %s p.%d 含手工/旧式图片 %s；解答相关页不会计入 "  "wiki missing，且 --apply-wiki 不会静默删除，请人工移除后重跑"%(rec .get ("wiki_file")or "__unmapped__",rec ["source_file"],rec ["page"],"、".join (rec .get ("manual_assets")or ["(unknown)"])))
        for rec in shared :
            local_warnings .append ("%s: %s %s p.%d 同时是题面页和答案页；整页不会回挂 wiki%s"%("shared_prompt_answer_page"if rec .get ("blocker")else "wiki_shared_prompt_answer_deferred",rec .get ("wiki_file")or "__unmapped__",rec ["source_file"],rec ["page"],"，须提供经审核的独立题面裁剪图"if rec .get ("blocker")else ""))
    coverage ={"detected":len (eligible ),"embedded":len (embedded ),"missing":len (missing ),"total_visual_pages":len (pages ),"deferred_answer_count":len (deferred ),"deferred_answer_pages":deferred ,"shared_prompt_answer_count":len (shared ),"shared_prompt_answer_pages":shared ,"shared_prompt_answer_blocker_count":len (shared_blockers ),"shared_prompt_answer_blocker_pages":shared_blockers ,"inventory_only_answer_page_count":sum (int (p .get ("inventory_only"))for p in deferred +shared ),"manual_answer_exposure_count":len (manual_exposures ),"manual_answer_exposure_pages":manual_exposures ,"per_chapter":per_chapter ,"pages":pages ,"missing_pages":missing ,"warnings":local_warnings ,}
    if warnings is not None :
        warnings .extend (local_warnings )
    return coverage 
def _material_pdf (materials ,source_file ,warnings ,label ):
    ''
    sf =str (source_file or "").replace ("\\","/")
    if os .path .isabs (sf )or re .match (r"^[A-Za-z]:",sf )or "://"in sf or ".."in sf .split ("/"):
        warnings .append ("wiki_apply_unsafe_source: %s (%s)"%(label ,sf ))
        return None 
    exact =os .path .join (materials ,*sf .split ("/"))
    if os .path .isfile (exact ):
        candidate =exact 
    elif "/"not in sf :
        candidates =[]
        for base ,dirs ,files in os .walk (materials ):
            for d in list (dirs ):
                full =os .path .join (base ,d )
                if d in ALWAYS_PRUNE or _is_leftover_workspace (full ,d )or _is_workspace_root (full ):
                    dirs .remove (d )
            if sf in files :
                candidates .append (os .path .join (base ,sf ))
        if len (candidates )!=1 :
            warnings .append ("wiki_apply_%s_source: %s (%s)"%("ambiguous"if candidates else "missing",label ,sf ))
            return None 
        candidate =candidates [0 ]
    else :
        warnings .append ("wiki_apply_missing_source: %s (%s)"%(label ,sf ))
        return None 
    mat_real ,real =os .path .realpath (materials ),os .path .realpath (candidate )
    try :
        inside =os .path .commonpath ([os .path .normcase (real ),os .path .normcase (mat_real )])==os .path .normcase (mat_real )
    except ValueError :
        inside =False 
    if not inside :
        warnings .append ("wiki_apply_outside_materials: %s (%s)"%(label ,sf ))
        return None 
    return candidate 
def _insert_wiki_visual (wiki_path ,source_file ,page ,asset_full ):
    ''
    with open (wiki_path ,encoding ="utf-8")as f :
        text0 =f .read ()
    marker ="<!-- wiki-visual-index: %s p.%d -->"%(source_file ,page )
    if marker in text0 :
        return False 
    marks =list (_WIKI_PAGE_RE .finditer (text0 ))
    chosen =None 
    same_source =[]
    for mark in marks :
        sf =mark .group (1 ).strip ().replace ("\\","/")
        matches_source =sf ==source_file or ("/"not in sf and os .path .basename (source_file )==sf )
        if matches_source :
            same_source .append (mark )
        if int (mark .group (2 ))==page and matches_source :
            chosen =mark 
            break 
    if chosen is None and not same_source :
        return False 
    alt_source =source_file .replace ("]","_").replace ("\n"," ").replace ("\r"," ")
    link =_canonical_rel_posix (os .path .dirname (wiki_path ),asset_full )
    image_block ="%s\n![原页图示 %s p.%d](%s)"%(marker ,alt_source ,page ,link )
    if chosen is not None :
        insertion =chosen .end ()
        addition ="\n\n%s\n"%image_block 
    else :
        later =[m for m in same_source if int (m .group (2 ))>page ]
        if later :
            insertion =min (later ,key =lambda m :int (m .group (2 ))).start ()
        else :
            last =max (same_source ,key =lambda m :m .start ())
            following =[m for m in marks if m .start ()>last .start ()]
            insertion =min (following ,key =lambda m :m .start ()).start ()if following else len (text0 )
        source_anchor ="<!-- %s p.%d -->"%(alt_source ,page )
        addition ="\n\n%s\n%s\n\n"%(source_anchor ,image_block )
    text1 =text0 [:insertion ]+addition +text0 [insertion :]
    _atomic_write_bytes (wiki_path ,text1 .encode ("utf-8"))
    return True 
def _remove_generated_answer_visuals (ws ,fig_files ,solution_sensitive_pages ,warnings ):
    ('')
    wiki_dir =os .path .join (ws ,"references","wiki")
    if not os .path .isdir (wiki_dir )or not solution_sensitive_pages :
        return 0 
    plans ,removed =[],[]
    for fn in sorted (name for name in os .listdir (wiki_dir )if name .lower ().endswith (".md")):
        path ,error =_safe_wiki_file (ws ,fn )
        if error :
            _die ("--apply-wiki 拒绝不安全的 references/wiki/%s：%s"%(fn ,error ))
        try :
            with open (path ,encoding ="utf-8")as source :
                text0 =source .read ()
        except (OSError ,UnicodeDecodeError )as exc :
            _die ("--apply-wiki 无法读取 references/wiki/%s：%s"%(fn ,exc ))
        def replace (match ):
            resolved =_resolve_fig_file (fig_files ,match .group (1 ))
            page =int (match .group (2 ))
            if resolved is not None and (resolved ,page )in solution_sensitive_pages :
                removed .append ((fn ,resolved ,page ))
                return ""
            return match .group (0 )
        text1 =_WIKI_MARKED_IMAGE_RE .sub (replace ,text0 )
        if text1 !=text0 :
            plans .append ((path ,text1 ))
    for path ,text in plans :
        _atomic_write_bytes (path ,text .encode ("utf-8"))
    if removed :
        refs =["%s %s p.%d"%row for row in removed ]
        warnings .append ("wiki_answer_generated_removed: 已移除 %d 个答案专属页自动回挂块：%s"%(len (removed ),"、".join (refs )))
    return len (removed )
def _selected_wiki_repairs (coverage ,per_chapter_cap ):
    ''
    by_chapter ={}
    for record in coverage .get ("missing_pages")or ():
        by_chapter .setdefault (record .get ("wiki_file"),[]).append (record )
    selected ={}
    for wiki_file ,records in by_chapter .items ():
        if wiki_file is None :
            selected [wiki_file ]=[]
            continue 
        embedded =(coverage .get ("per_chapter",{}).get (wiki_file ,{}).get ("embedded")or 0 )
        budget =max (0 ,int (per_chapter_cap )-int (embedded ))
        selected [wiki_file ]=sorted (records ,key =lambda row :(row ["source_file"],row ["page"]))[:budget ]
    return selected 
def _wiki_generated_ownership (ws ,wiki_dir ,fig_files ,target_plans ):
    ''
    ownership =set ()
    if not any (os .path .lexists (plan ["full_path"])for plan in target_plans ):
        return ownership 
    for filename in sorted (name for name in os .listdir (wiki_dir )if name .lower ().endswith (".md")):
        wiki_path ,error =_safe_wiki_file (ws ,filename )
        if error :
            _die ("--apply-wiki 拒绝不安全的 references/wiki/%s：%s"%(filename ,error ))
        try :
            with open (wiki_path ,encoding ="utf-8")as stream :
                text =stream .read ()
        except (OSError ,UnicodeDecodeError )as exc :
            _die ("--apply-wiki 无法读取 references/wiki/%s：%s"%(filename ,exc ))
        for match in _WIKI_MARKED_IMAGE_RE .finditer (text ):
            marker_source =_resolve_fig_file (fig_files or {},match .group (1 ))
            if marker_source is None :
                marker_source =str (match .group (1 )or "").strip ().replace ("\\","/")
            marker_page =int (match .group (2 ))
            for plan in target_plans :
                if (marker_source ==plan ["source_file"]and marker_page ==plan ["page"]):
                    ownership .add (plan ["key"])
    return ownership 
def _preflight_wiki_asset_targets (ws ,wiki_dir ,root_real ,selected_by_wiki ,fig_files ,policy_rows ):
    ''
    plans =[]
    by_key ={}
    ws_real =os .path .realpath (ws )
    for wiki_file ,records in selected_by_wiki .items ():
        if wiki_file is None :
            continue 
        for record in records :
            relative_target =_wiki_generated_asset_rel (record ["source_file"],record ["page"])
            full_path =os .path .join (ws_real ,*relative_target .split ("/"))
            if os .path .normcase (os .path .normpath (os .path .dirname (full_path )))!=os .path .normcase (os .path .normpath (root_real )):
                _die ("--apply-wiki deterministic target escaped the canonical asset root")
            relative_path =_rel_posix (ws_real ,full_path )
            key =physical_asset_key (relative_path )
            if key is None :
                _die ("--apply-wiki deterministic target is not a safe workspace path: %r"%relative_path )
            plan ={"wiki_file":wiki_file ,"source_file":record ["source_file"],"page":record ["page"],"full_path":full_path ,"path":relative_path ,"key":key ,}
            previous =by_key .get (key )
            if previous is not None and (previous ["source_file"],previous ["page"])!=(plan ["source_file"],plan ["page"]):
                _die ("--apply-wiki deterministic target collision: %s"%relative_path )
            by_key [key ]=plan 
            plans .append (plan )
    if policy_rows is not None :
        for layer in ("quiz_rows","teaching_rows","content_units"):
            for path ,role in iter_asset_declarations (policy_rows .get (layer )or ()):
                key =physical_asset_key (path )
                if key in by_key :
                    _die ("--apply-wiki target %s is already owned by structured evidence "  "role=%r path=%r"%(by_key [key ]["path"],role ,path ))
    validated_wikis ={}
    if not os .path .isdir (wiki_dir ):
        if plans :
            _die ("--apply-wiki selected repairs but references/wiki is missing")
        return plans 
    for wiki_file in sorted (name for name in os .listdir (wiki_dir )if name .lower ().endswith (".md")):
        wiki_path ,error =_safe_wiki_file (ws ,wiki_file )
        if error :
            _die ("--apply-wiki rejects references/wiki/%s: %s"%(wiki_file ,error ))
        try :
            with open (wiki_path ,encoding ="utf-8")as stream :
                validated_wikis [wiki_file ]=stream .read ()
            _validate_wiki_marker_contracts (validated_wikis [wiki_file ],fig_files or {})
        except (OSError ,UnicodeDecodeError )as exc :
            _die ("--apply-wiki cannot read references/wiki/%s: %s"%(wiki_file ,exc ))
        except ValueError as exc :
            _die ("--apply-wiki invalid generated marker ownership: %s"%exc )
    for plan in plans :
        wiki_file =plan ["wiki_file"]
        if wiki_file not in validated_wikis :
            _die ("--apply-wiki selected a missing wiki file: %s"%wiki_file )
        try :
            _validated_owned_wiki_block (validated_wikis [wiki_file ],plan ["source_file"],plan ["page"])
        except ValueError as exc :
            _die ("--apply-wiki invalid generated marker ownership: %s"%exc )
    ownership =_wiki_generated_ownership (ws ,wiki_dir ,fig_files or {},list (by_key .values ()))
    for key ,plan in by_key .items ():
        if not os .path .lexists (plan ["full_path"]):
            continue 
        if (is_link_or_reparse (plan ["full_path"])or not os .path .isfile (plan ["full_path"])):
            _die ("--apply-wiki target is non-regular or link-backed: %s"%plan ["path"])
        if key not in ownership :
            _die ("--apply-wiki target already exists without current same-source/page "  "wiki-writer ownership: %s"%plan ["path"])
    return plans 
def _apply_wiki_visuals_legacy (ws ,materials ,coverage ,backend ,asset_root ,warnings ,per_chapter_cap =30 ,fig_files =None ,solution_sensitive_pages =None ,tainted_keys =None ,policy_rows =None ):
    ('')
    return apply_wiki_visuals (ws ,materials ,coverage ,backend ,asset_root ,warnings ,per_chapter_cap =per_chapter_cap ,fig_files =fig_files ,solution_sensitive_pages =solution_sensitive_pages ,tainted_keys =tainted_keys ,policy_rows =policy_rows ,)
def _insert_wiki_visual_text (text0 ,wiki_path ,source_file ,page ,asset_full ):
    ''
    marker ="<!-- wiki-visual-index: %s p.%d -->"%(source_file ,page )
    owned =_validated_owned_wiki_block (text0 ,source_file ,page )
    alt_source =source_file .replace ("]","_").replace ("\n"," ").replace ("\r"," ")
    link =_canonical_rel_posix (os .path .dirname (wiki_path ),asset_full )
    image_block ="%s\n![Source page %s p.%d](%s)"%(marker ,alt_source ,page ,link )
    if owned is not None :
        updated =text0 [:owned .start ()]+image_block +text0 [owned .end ():]
        return updated ,updated !=text0 
    marks =list (_WIKI_PAGE_RE .finditer (text0 ))
    chosen ,same_source =None ,[]
    for mark in marks :
        marked_source =mark .group (1 ).strip ().replace ("\\","/")
        matches =(marked_source ==source_file or ("/"not in marked_source and os .path .basename (source_file )==marked_source ))
        if matches :
            same_source .append (mark )
        if matches and int (mark .group (2 ))==page :
            chosen =mark 
            break 
    if chosen is None and not same_source :
        return text0 ,False 
    if chosen is not None :
        insertion =chosen .end ()
        addition ="\n\n%s\n"%image_block 
    else :
        later =[mark for mark in same_source if int (mark .group (2 ))>page ]
        if later :
            insertion =min (later ,key =lambda mark :int (mark .group (2 ))).start ()
        else :
            last =max (same_source ,key =lambda mark :mark .start ())
            following =[mark for mark in marks if mark .start ()>last .start ()]
            insertion =(min (following ,key =lambda mark :mark .start ()).start ()if following else len (text0 ))
        source_anchor ="<!-- %s p.%d -->"%(alt_source ,page )
        addition ="\n\n%s\n%s\n\n"%(source_anchor ,image_block )
    return text0 [:insertion ]+addition +text0 [insertion :],True 
def apply_wiki_visuals (ws ,materials ,coverage ,backend ,asset_root ,warnings ,per_chapter_cap =30 ,fig_files =None ,solution_sensitive_pages =None ,tainted_keys =None ,policy_rows =None ):
    ''
    live_policy =_live_visual_asset_policy (ws )
    effective_taint =_effective_tainted_keys (live_policy ,tainted_keys )
    policy_rows =_merged_policy_owners (live_policy ,policy_rows )
    wiki_dir =os .path .join (ws ,"references","wiki")
    if _path_has_link_or_reparse_component (ws ,wiki_dir ):
        _die ("--apply-wiki rejects a link/reparse-backed references/wiki directory")
    if os .path .isdir (wiki_dir ):
        linked =[name for name in os .listdir (wiki_dir )if name .lower ().endswith (".md")and is_link_or_reparse (os .path .join (wiki_dir ,name ))]
        if linked :
            _die ("--apply-wiki rejects linked wiki files: %s"%", ".join (sorted (linked )))
    missing =list (coverage .get ("missing_pages")or ())
    if missing and not backend .can_render ():
        _die ("--apply-wiki requires a PDF page rendering backend",3 )
    root_real =_require_standard_visual_asset_root (ws ,asset_root ,"--apply-wiki --asset-root")
    selected_by_wiki =_selected_wiki_repairs (coverage ,per_chapter_cap )
    plans =_preflight_wiki_asset_targets (ws ,wiki_dir ,root_real ,selected_by_wiki ,fig_files or {},policy_rows ,)
    plan_by_key ={(plan ["wiki_file"],plan ["source_file"],plan ["page"]):plan for plan in plans }
    wiki_paths ={}
    if os .path .isdir (wiki_dir ):
        for name in sorted (item for item in os .listdir (wiki_dir )if item .lower ().endswith (".md")):
            path ,error =_safe_wiki_file (ws ,name )
            if error :
                _die ("--apply-wiki rejects references/wiki/%s: %s"%(name ,error ))
            wiki_paths [name ]=path 
    texts ,original_texts ={},{}
    for name ,path in wiki_paths .items ():
        try :
            with open (path ,encoding ="utf-8")as stream :
                texts [name ]=stream .read ()
        except (OSError ,UnicodeDecodeError )as exc :
            _die ("--apply-wiki cannot read references/wiki/%s: %s"%(name ,exc ))
        original_texts [name ]=texts [name ]
    batch_warnings =[]
    removed =[]
    sensitive =set (solution_sensitive_pages or ())
    if sensitive :
        for name ,text0 in list (texts .items ()):
            def remove_sensitive (match ):
                resolved =_resolve_fig_file (fig_files or {},match .group (1 ))
                page =int (match .group (2 ))
                if resolved is not None and (resolved ,page )in sensitive :
                    removed .append ((name ,resolved ,page ))
                    return ""
                return match .group (0 )
            texts [name ]=_WIKI_MARKED_IMAGE_RE .sub (remove_sensitive ,text0 )
    reasons ,inserted ={},0 
    payloads =[]
    selected_keys ={(wiki_file ,record ["source_file"],record ["page"])for wiki_file ,records in selected_by_wiki .items ()for record in records }
    for record in missing :
        key =(record .get ("wiki_file"),record ["source_file"],record ["page"])
        if record .get ("wiki_file")is None :
            reasons [key ]="wiki_source_unmapped"
        elif key not in selected_keys :
            reasons [key ]="chapter_cap"
    unmapped_count =sum (1 for key in reasons if key [0 ]is None )
    if unmapped_count :
        batch_warnings .append ("wiki_apply_unmapped: %d visual pages have no wiki source declaration"%unmapped_count )
    capped_by_wiki ={}
    for key ,reason in reasons .items ():
        if reason =="chapter_cap"and key [0 ]is not None :
            capped_by_wiki .setdefault (key [0 ],[]).append ("%s p.%d"%(key [1 ],key [2 ]))
    for wiki_file ,refs in sorted (capped_by_wiki .items ()):
        batch_warnings .append ("wiki_visual_cap: %s reached cap %d; not attached: %s"%(wiki_file ,per_chapter_cap ,", ".join (refs )))
    for wiki_file in sorted (selected_by_wiki ,key =lambda value :str (value or "")):
        if wiki_file is None :
            continue 
        wiki_path =wiki_paths .get (wiki_file )
        if wiki_path is None :
            _die ("--apply-wiki selected a missing wiki file: %s"%wiki_file )
        for record in selected_by_wiki [wiki_file ]:
            key =(wiki_file ,record ["source_file"],record ["page"])
            label ="%s %s p.%d"%key 
            plan =plan_by_key .get (key )
            if plan is None :
                _die ("--apply-wiki deterministic target plan drifted for %s"%label )
            if is_student_attempt_tainted (plan ["path"],effective_taint ):
                reasons [key ]="student_attempt_tainted_path"
                batch_warnings .append ("wiki_apply_skip_student_attempt_path: %s"%label )
                continue 
            pdf =_material_pdf (materials ,record ["source_file"],batch_warnings ,label )
            if pdf is None :
                reasons [key ]="source_unavailable"
                continue 
            try :
                payload =backend .render_page_png (pdf ,record ["page"]-1 )
            except Exception as exc :
                batch_warnings .append ("wiki_apply_render_failed: %s (%s)"%(label ,exc ))
                reasons [key ]="render_failed"
                continue 
            if not payload :
                reasons [key ]="render_failed"
                continue 
            payload =_validated_png_payload (payload ,"--apply-wiki %s"%label )
            candidate ,changed =_insert_wiki_visual_text (texts [wiki_file ],wiki_path ,record ["source_file"],record ["page"],plan ["full_path"],)
            if not changed :
                marker ="<!-- wiki-visual-index: %s p.%d -->"%(record ["source_file"],record ["page"])
                if marker not in texts [wiki_file ]:
                    reasons [key ]="wiki_anchor_unavailable"
                    continue 
            else :
                texts [wiki_file ]=candidate 
                inserted +=1 
            payloads .append ((plan ["full_path"],payload ))
    if removed :
        batch_warnings .append ("wiki_answer_generated_removed: removed %d generated solution-page blocks"%len (removed ))
    for name ,path in wiki_paths .items ():
        if texts [name ]!=original_texts [name ]:
            payloads .append ((path ,texts [name ].encode ("utf-8")))
    try :
        _publish_bytes_transactionally (payloads )
    except OSError as exc :
        _die ("--apply-wiki transactional publication failed: %s"%exc )
    warnings .extend (batch_warnings )
    return inserted ,reasons ,len (removed )
def run (argv =None ,backend =None ,_state_locked =False ):
    ap =argparse .ArgumentParser (description ="Build the generic dual visual index (recall-first; pure stdlib + optional PDF backend; no LLM/network).")
    ap .add_argument ("--workspace",required =True ,help ="cram workspace (contains references/quiz_bank.json)")
    ap .add_argument ("--materials",default =None ,help ="course materials folder (scan PDFs to build figure_page_index)")
    ap .add_argument ("--out-dir",default =None ,help ="index output dir (default <workspace>/references/)")
    ap .add_argument ("--apply",action ="store_true",help ="repair prompt suspects as question_context and answer suspects as answer_context")
    ap .add_argument ("--apply-wiki",action ="store_true",help ="idempotently render detected visual pages and insert them at matching wiki page anchors")
    ap .add_argument ("--wiki-page-cap",type =int ,default =30 ,help ="maximum embedded visual pages per wiki chapter for --apply-wiki (default 30)")
    ap .add_argument ("--asset-root",default =None ,help ="screenshot dir for --apply/--apply-wiki (default <workspace>/references/assets)")
    args =ap .parse_args (argv )
    if args .wiki_page_cap <1 :
        _die ("--wiki-page-cap 必须是 >=1 的整数")
    ws =os .path .abspath (args .workspace )
    if not os .path .isdir (ws )or is_link_or_reparse (ws ):
        _die ("--workspace 必须是现有的非符号链接目录: %s"%ws )
    try :
        exam_start .require_full_processing (ws ,materials =args .materials ,purpose ="full visual-index scanning/publication",)
    except exam_start .FullProcessingRequired as exc :
        _die (str (exc ))
    if not _state_locked :
        with workspace_publication_lock (ws ):
            return run (argv ,backend =backend ,_state_locked =True )
    references_dir =_safe_workspace_dir (ws ,os .path .join (ws ,"references"),"references",create =False )
    asset_root =args .asset_root or os .path .join (references_dir ,"assets")
    if args .apply or args .apply_wiki :
        _require_standard_visual_asset_root (ws ,asset_root ,"--asset-root")
    bank_path =_safe_workspace_file (ws ,os .path .join (references_dir ,"quiz_bank.json"),"quiz_bank.json")
    bank =_read_json (bank_path ,"quiz_bank.json")
    if not isinstance (bank ,list ):
        _die ("quiz_bank.json 必须是数组")
    teaching_path =os .path .join (references_dir ,"teaching_examples.json")
    teaching =[]
    teaching_exists =os .path .lexists (teaching_path )
    if teaching_exists :
        _safe_workspace_file (ws ,teaching_path ,"teaching_examples.json")
        teaching =_read_json (teaching_path ,"teaching_examples.json")
        if not isinstance (teaching ,list ):
            _die ("teaching_examples.json 必须是数组")
    try :
        asset_policy =workspace_asset_policy_snapshot (ws )
    except ValueError as exc :
        _die ("无法建立完整 student-attempt 资产策略快照: %s"%exc )
    if asset_policy ["unsafe_paths"]:
        _die ("student-attempt 资产策略含不安全路径: %s"%asset_policy ["unsafe_paths"][0 ])
    if asset_policy ["conflicts"]:
        _die ("student-attempt/题面/答案资产角色冲突: %s"%asset_policy ["conflicts"][0 ])
    tainted_asset_keys =asset_policy ["tainted_keys"]
    supplied_out_dir =os .path .abspath (args .out_dir or references_dir )
    canonical_out_dir =os .path .abspath (references_dir )
    if os .path .normpath (supplied_out_dir )!=os .path .normpath (canonical_out_dir ):
        _die ("--out-dir must be exactly <workspace>/references using its canonical spelling")
    out_dir =_safe_workspace_dir (ws ,supplied_out_dir ,"--out-dir",create =False )
    index_targets =[os .path .join (out_dir ,"figure_page_index.json"),os .path .join (out_dir ,"image_question_index.json"),]
    try :
        _snapshot_file_states (index_targets )
    except OSError as exc :
        _die ("index output target preflight failed: %s"%exc )
    warnings =[]
    backend =backend or RealBackend ()
    fig_files ={}
    if args .materials :
        if not os .path .isdir (args .materials ):
            _die ("找不到材料目录: %s"%args .materials )
        fig_files =scan_materials (args .materials ,backend ,warnings )
    else :
        warnings .append ("no_materials: 未给 --materials——只建题目索引，无法交叉核对疑漏（召回网关闭）")
    prompt_pages ,answer_pages =derive_item_page_sides (fig_files ,bank ,teaching )
    shared_pages =prompt_pages &answer_pages 
    questions ,per_chapter ,bank_prompt_suspects ,bank_answer_suspects =build_question_index (ws ,bank ,fig_files ,warnings ,"quiz_bank",shared_pages )
    teaching_questions ,teaching_per_chapter ,teaching_prompt_suspects ,teaching_answer_suspects =build_question_index (ws ,teaching ,fig_files ,warnings ,"teaching_examples",shared_pages )
    prompt_suspects =bank_prompt_suspects +teaching_prompt_suspects 
    answer_suspects =bank_answer_suspects +teaching_answer_suspects 
    shared_blockers =[s for s in prompt_suspects if s .get ("blocker")=="shared_prompt_answer_page"]
    shared_blocker_pages ={(row ["source_file"],row ["page"])for suspect in shared_blockers for row in (suspect .get ("shared_prompt_answer_pages")or [])if isinstance (row ,dict )and row .get ("source_file")and type (row .get ("page"))is int }
    coverage =build_wiki_visual_coverage (ws ,fig_files ,emit_warnings =False ,prompt_pages =prompt_pages ,answer_pages =answer_pages ,shared_blocker_pages =shared_blocker_pages ,tainted_keys =tainted_asset_keys )
    if args .apply or args .apply_wiki :
        asset_root =_safe_workspace_dir (ws ,asset_root ,"--asset-root",create =True )
    bank_prompt_applied =bank_answer_applied =0 
    teaching_prompt_applied =teaching_answer_applied =0 
    if args .apply and (prompt_suspects or answer_suspects ):
        try :
            repair_plans =_preflight_repair_assets (ws ,asset_root ,((bank ,bank_prompt_suspects ,"prompt"),(bank ,bank_answer_suspects ,"answer"),(teaching ,teaching_prompt_suspects ,"prompt"),(teaching ,teaching_answer_suspects ,"answer"),),asset_policy ,)
        except ValueError as exc :
            _die ("--apply candidate asset policy could not be built: %s"%exc )
        (bank_prompt_applied ,bank_answer_applied ,teaching_prompt_applied ,teaching_answer_applied )=_apply_repair_run_transaction (ws ,args .materials or "",backend ,asset_root ,warnings ,bank ,teaching ,bank_path ,teaching_path ,bank_prompt_suspects ,bank_answer_suspects ,teaching_prompt_suspects ,teaching_answer_suspects ,tainted_asset_keys ,asset_policy ,repair_plans ,)
        if (bank_prompt_applied or bank_answer_applied or teaching_prompt_applied or teaching_answer_applied ):
            questions ,per_chapter ,bank_prompt_suspects ,bank_answer_suspects =build_question_index (ws ,bank ,fig_files ,source_layer ="quiz_bank",shared_prompt_answer_pages =shared_pages )
            teaching_questions ,teaching_per_chapter ,teaching_prompt_suspects ,teaching_answer_suspects =build_question_index (ws ,teaching ,fig_files ,source_layer ="teaching_examples",shared_prompt_answer_pages =shared_pages )
            prompt_suspects =bank_prompt_suspects +teaching_prompt_suspects 
            answer_suspects =bank_answer_suspects +teaching_answer_suspects 
    shared_blockers =[s for s in prompt_suspects if s .get ("blocker")=="shared_prompt_answer_page"]
    shared_blocker_pages ={(row ["source_file"],row ["page"])for suspect in shared_blockers for row in (suspect .get ("shared_prompt_answer_pages")or [])if isinstance (row ,dict )and row .get ("source_file")and type (row .get ("page"))is int }
    prompt_applied =bank_prompt_applied +teaching_prompt_applied 
    answer_applied =bank_answer_applied +teaching_answer_applied 
    wiki_applied ,wiki_deferred_removed ,wiki_reasons ,wiki_apply_warnings =0 ,0 ,{},[]
    if args .apply_wiki :
        if not args .materials :
            _die ("--apply-wiki 必须同时给 --materials，才能从已索引原 PDF 渲染页面")
        start =len (warnings )
        wiki_applied ,wiki_reasons ,wiki_deferred_removed =apply_wiki_visuals (ws ,args .materials ,coverage ,backend ,asset_root ,warnings ,args .wiki_page_cap ,fig_files =fig_files ,solution_sensitive_pages =answer_pages ,tainted_keys =tainted_asset_keys ,policy_rows =asset_policy )
        wiki_apply_warnings =warnings [start :]
    coverage =build_wiki_visual_coverage (ws ,fig_files ,warnings =warnings ,missing_reasons =wiki_reasons ,emit_warnings =True ,prompt_pages =prompt_pages ,answer_pages =answer_pages ,shared_blocker_pages =shared_blocker_pages ,tainted_keys =tainted_asset_keys )
    coverage ["removed_deferred_answer_blocks"]=wiki_deferred_removed 
    if wiki_apply_warnings :
        coverage ["warnings"]=wiki_apply_warnings +coverage ["warnings"]
    integrity =_integrity_snapshot (ws ,args ,backend ,warnings ,item_layers =(bank ,teaching ),coverage =coverage ,fig_files =fig_files )
    fig_index ={"generated_by":"build_visual_index.py","media_signals":backend .can_media (),"note":"确定性启发式（结构/排版/词面分层，召回优先）；不是语义判定，AI 识图为未来 opt-in","files":{rel :{"pages":info ["pages"],"visual_pages":[{"page":p ,**cls }for p ,cls in sorted (info ["visual"].items ())]}for rel ,info in sorted (fig_files .items ())},"wiki_visual_coverage":coverage ,"shared_prompt_answer_count":coverage ["shared_prompt_answer_count"],"shared_prompt_answer_blocker_count":coverage ["shared_prompt_answer_blocker_count"],"manual_answer_exposure_count":coverage ["manual_answer_exposure_count"],"warnings":warnings ,}
    shared_page_rows =[{"source_file":source ,"page":page }for source ,page in sorted (shared_pages )]
    q_index ={"generated_by":"build_visual_index.py","questions":questions ,"per_chapter":per_chapter ,"teaching_questions":teaching_questions ,"teaching_per_chapter":teaching_per_chapter ,"combined_per_chapter":_merge_per_chapter (per_chapter ,teaching_per_chapter ),"suspects":prompt_suspects ,"prompt_suspects":prompt_suspects ,"answer_suspects":answer_suspects ,"applied":bank_prompt_applied ,"prompt_applied":prompt_applied ,"answer_applied":answer_applied ,"bank_prompt_applied":bank_prompt_applied ,"bank_answer_applied":bank_answer_applied ,"teaching_prompt_applied":teaching_prompt_applied ,"teaching_answer_applied":teaching_answer_applied ,"wiki_applied":wiki_applied ,"wiki_deferred_answer_blocks_removed":wiki_deferred_removed ,"shared_prompt_answer_pages":shared_page_rows ,"shared_prompt_answer_count":len (shared_page_rows ),"shared_prompt_answer_blockers":shared_blockers ,"shared_prompt_answer_blocker_count":len (shared_blockers ),"manual_answer_exposure_count":coverage ["manual_answer_exposure_count"],"warnings":warnings ,}
    integrity ["outputs"]={"figure_page_index.json":{"sha256":_manifest_result_sha256 (fig_index )},"image_question_index.json":{"sha256":_manifest_result_sha256 (q_index )},}
    fig_index ["integrity"]=integrity 
    q_index ["integrity"]=integrity 
    try :
        _publish_bytes_transactionally ([(index_targets [0 ],(json .dumps (fig_index ,ensure_ascii =False ,indent =2 )+"\n").encode ("utf-8")),(index_targets [1 ],(json .dumps (q_index ,ensure_ascii =False ,indent =2 )+"\n").encode ("utf-8")),])
    except OSError as exc :
        _die ("transactional index publication failed: %s"%exc )
    n_vis =sum (len (i ["visual"])for i in fig_files .values ())
    print ("[+] figure_page_index: %d 个文件 / %d 个视觉页 / wiki %d/%d + deferred-answer %d"  " + shared-prompt-answer %d；"  "image_question_index: "  "%d 题 / 题面疑漏 %d / 答案疑漏 %d / 回写 %d+%d"%(len (fig_files ),n_vis ,coverage ["embedded"],coverage ["detected"],coverage ["deferred_answer_count"],coverage ["shared_prompt_answer_count"],len (questions )+len (teaching_questions ),len (prompt_suspects ),len (answer_suspects ),prompt_applied ,answer_applied ))
    for w in warnings :
        print ("[!] "+w )
    if prompt_suspects and not args .apply :
        print ("[!] 有 %d 道疑似漏标的图依赖题（详见 image_question_index.json 的 suspects）；"  "用 --apply 渲染原页并标 maybe_requires_assets"%len (prompt_suspects ))
    if answer_suspects and not args .apply :
        print ("[!] 有 %d 道答案侧视觉疑漏（详见 answer_suspects）；用 --apply 追加 answer_context"%len (answer_suspects ))
    if coverage ["missing"]and not args .apply_wiki :
        print ("[!] wiki 有 %d/%d 个已检测视觉页未嵌入；用 --apply-wiki 回挂原页图"%(coverage ["missing"],coverage ["detected"]))
    if coverage ["manual_answer_exposure_count"]:
        print ("[!] wiki 检出 %d 个解答相关页手工图片暴露；已保留原文并写入 coverage issue，"  "本次 fail-closed 返回 2"%coverage ["manual_answer_exposure_count"])
        return 2 
    if shared_blockers :
        print ("[!] 有 %d 道题的题面页与答案页重合，未找到经审核的独立题面裁剪图；"  "已阻止整页自动回写，本次 fail-closed 返回 2"%len (shared_blockers ))
        return 2 
    return 0 
if __name__ =="__main__":
    sys .exit (run ())
