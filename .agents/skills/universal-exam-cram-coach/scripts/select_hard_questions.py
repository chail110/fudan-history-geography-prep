#!/usr/bin/env python
# -*- coding: utf-8 -*-
('')
import argparse 
import json 
import os 
import re 
import sys 
sys .path .insert (0 ,os .path .dirname (os .path .abspath (__file__ )))
import score_difficulty as sd 
from asset_policy import canonical_chapter_key 
from select_questions import (SOURCE_TYPES ,load_runtime_bank ,)
from update_progress import _normalize_mode ,parse_md as _parse_md ,MD_NAME 
for _s in ("stdout","stderr"):
    try :
        getattr (sys ,_s ).reconfigure (encoding ="utf-8")
    except Exception :
        pass 
STATE_NAME ="study_state.json"
import i18n 
LEARNING_MODES =i18n .MODES 
_MIXED_SCOPES ={None ,"","混合题池","mixed","混合"}
_MIXED_OVERRIDE ={"all","mixed","*","混合","全部"}
_MISTAKE_RESOLVED =i18n .MISTAKE_RESOLVED 
_CONFUSION_RESOLVED =i18n .CONFUSION_RESOLVED 
def _die (msg ,code =2 ):
    sys .stderr .write ("select_hard_questions: "+msg +"\n")
    raise SystemExit (code )
def _parse_source_types (raw ):
    ('')
    vals =[v .strip ()for v in raw .split (",")if v .strip ()]
    if not vals :
        _die ("--source-type 不能为空（'' 或 ','）——显式空过滤视为用法错误，"  "不写就是混合池，别用空串静默清空（与 A2 select_questions 一致）")
    bad =[v for v in vals if v not in SOURCE_TYPES ]
    if bad :
        _die ("非法 source_type: %s（应为 %s）"%(", ".join (bad ),sorted (SOURCE_TYPES )))
    return set (vals )
def _scope_to_source_types (scope ):
    ('')
    if scope is not None and not isinstance (scope ,str ):
        _die ("study_state 记录的范围偏好不是字符串（%r）——state 疑被手改/损坏；"  "请修复 study_state.json 的 scope 字段，或显式传 --source-type 覆盖"%(scope ,))
    if scope in _MIXED_SCOPES :
        return None 
    norm =str (scope ).strip ().lower ()
    for suf in ("-only","_only"," only","-仅","仅"):
        if norm .endswith (suf ):
            norm =norm [:-len (suf )].strip ()
    if norm in SOURCE_TYPES :
        return {norm }
    _die ("study_state 记录了范围偏好「%s」，但无法自动映射到 source_type；"  "请显式传 --source-type <%s>，或先解除范围偏好——避免静默越界（A2 范围契约）"%(scope ,"/".join (sorted (SOURCE_TYPES ))))
def _assert_contained (ws ,path ,name ):
    ws_real =os .path .normcase (os .path .realpath (ws ))
    real =os .path .normcase (os .path .realpath (path ))
    if real !=ws_real and not real .startswith (ws_real +os .sep ):
        _die ("%s 经符号链接 / 父目录逃出工作区——拒绝读取（realpath 归属校验失败）"%name )
def load_state (ws ):
    ('')
    path =os .path .join (ws ,STATE_NAME )
    if os .path .islink (path ):
        _die ("study_state.json 不得为符号链接（A4 事实源，可能指向工作区外）——拒绝读取")
    if os .path .isfile (path ):
        _assert_contained (ws ,path ,"study_state.json")
        try :
            with open (path ,"r",encoding ="utf-8")as f :
                st =json .load (f )
        except ValueError as e :
            _die ("study_state.json 不是合法 JSON: %s"%e )
        if not isinstance (st ,dict ):
            _die ("study_state.json 顶层必须是对象")
        return st 
    md =os .path .join (ws ,MD_NAME )
    if os .path .islink (md ):
        _die ("study_progress.md 不得为符号链接（可能指向工作区外）——拒绝读取")
    if not os .path .isfile (md ):
        return None 
    _assert_contained (ws ,md ,"study_progress.md")
    with open (md ,"r",encoding ="utf-8")as f :
        phase ,mistakes ,confusions ,_checklist ,window ,prefs =_parse_md (f .read ())
    return {"mode":prefs .get ("mode"),"scope":prefs .get ("scope"),"current_phase":phase ,"mistake_archive":mistakes ,"confusion_log":confusions ,"knowledge_window":window }
def _chapter_key (q ):
    ''
    for k in ("chapter","phase"):
        v =q .get (k )
        if v is not None :
            return str (v )
    return None 
def _chapter_keys (q ):
    ''
    return {canonical_chapter_key (q .get (k ),allow_phase =True )for k in ("chapter","phase","chapter_id")if q .get (k )is not None }-{None }
def _numeric_chapters (q ):
    ('')
    out =set ()
    for k in ("chapter","phase"):
        v =q .get (k )
        if v is not None :
            m =re .search (r"\d+",str (v ))
            if m :
                out .add (int (m .group (0 )))
    return out 
def _item_points (q ):
    kps =q .get ("knowledge_points")
    return [str (k ).strip ()for k in kps if str (k ).strip ()]if isinstance (kps ,list )else []
def build_mastery (state ):
    ('')
    idx ={"mistake_ids":set (),"trouble_ch":set (),"weak_pt":set (),"strong_pt":set ()}
    if not state :
        return idx 
    for m in state .get ("mistake_archive")or []:
        if isinstance (m ,dict )and i18n .canon_row_status (m .get ("status")or "")not in _MISTAKE_RESOLVED :
            if m .get ("id"):
                idx ["mistake_ids"].add (str (m ["id"]))
            if m .get ("chapter")is not None :
                idx ["trouble_ch"].add (str (m ["chapter"]))
    for c in state .get ("confusion_log")or []:
        if (isinstance (c ,dict )and c .get ("chapter")is not None and i18n .canon_row_status (c .get ("status")or "")not in _CONFUSION_RESOLVED ):
            idx ["trouble_ch"].add (str (c ["chapter"]))
    for w in state .get ("knowledge_window")or []:
        if not isinstance (w ,dict ):
            continue 
        pt =str (w ["point"]).strip ()if w .get ("point")else None 
        if not pt :
            continue 
        raw =w .get ("status")or "in_window"
        status =i18n .canon_window_status (raw )if isinstance (raw ,str )else raw 
        if status =="out_window":
            idx ["weak_pt"].add (pt )
        elif status in ("in_window","verified"):
            idx ["strong_pt"].add (pt )
    return idx 
def _pt_hit (item_pts ,pt_set ):
    ''
    for ip in item_pts :
        for wp in pt_set :
            if ip and wp and (ip in wp or wp in ip ):
                return True 
    return False 
def classify (q ,idx ):
    ''
    qid =str (q .get ("id"))
    chs =_chapter_keys (q )
    pts =_item_points (q )
    if qid in idx ["mistake_ids"]:
        return "weak","错题"
    if chs &idx ["trouble_ch"]:
        return "weak","本章有错题/疑难"
    if _pt_hit (pts ,idx ["weak_pt"]):
        return "weak","窗口外(点)"
    if _pt_hit (pts ,idx ["strong_pt"]):
        return "mastered","在窗口/已实测"
    return "neutral","常规"
_CLASS_RANK ={"weak":0 ,"neutral":1 ,"mastered":2 }
_CLASS_REASON ={"weak":"薄弱巩固·先易后难","mastered":"已掌握·挑战(先难)","neutral":"常规",}
def order_items (scored ,mode ):
    ''
    def key (it ):
        rank =_CLASS_RANK [it ["cls"]]
        if mode =="from_scratch":
            return (it ["difficulty"],rank ,it ["orig_idx"])
        d =it ["difficulty"]if it ["cls"]=="weak"else -it ["difficulty"]
        return (rank ,d ,it ["orig_idx"])
    return sorted (scored ,key =key )
def main (argv =None ):
    ap =argparse .ArgumentParser (description ="Select questions by difficulty x mastery x A6 mode (A7)")
    ap .add_argument ("--workspace",required =True )
    ap .add_argument ("-n","--num",type =int ,default =10 ,help ="number of questions (default 10)")
    ap .add_argument ("--mode",default =None ,help ="learning mode: from_scratch/shore_up/fill_gaps (zh display words and legacy "  "normal/sprint/panic/mock also accepted); defaults to study_state.mode, else fill_gaps")
    ap .add_argument ("--chapter",default =None ,help ="only this chapter (exact chapter-or-phase match)")
    ap .add_argument ("--from-chapter",type =int ,default =None ,help ="only numeric chapter numbers >= N (for 某章起步补弱); never guessed from current_phase - unset means no such filter")
    ap .add_argument ("--source-type",default =None ,help ="filter by source type (comma-separated, A2-consistent); defaults to study_state.scope, untagged items always excluded; "  "pass all/mixed/* to explicitly override to the mixed pool (this turn; announce the A2 boundary override first)")
    ap .add_argument ("--json",action ="store_true")
    args =ap .parse_args (argv )
    items ,runtime =load_runtime_bank (args .workspace ,chapter =args .chapter )
    state =load_state (args .workspace )
    raw_mode =args .mode or (state or {}).get ("mode")
    mode =_normalize_mode (raw_mode )[0 ]if raw_mode else "fill_gaps"
    if mode not in LEARNING_MODES :
        mode ="fill_gaps"
    idx =build_mastery (state )
    late =sd ._late_chapter_cutoff (items )
    notes =[]
    if runtime ["exclusion_counts"]:
        notes .append ("runtime 安全门禁排除：%s"%", ".join ("%s=%d"%pair for pair in sorted (runtime ["exclusion_counts"].items ())))
    if args .source_type is not None :
        if args .source_type .strip ().lower ()in _MIXED_OVERRIDE :
            source_types =None 
            sc =(state or {}).get ("scope")
            if not isinstance (sc ,(str ,type (None )))or sc not in _MIXED_SCOPES :
                notes .append ("已按显式 --source-type %s 覆盖存档范围为混合池（本轮；A2 越界覆盖须先向学生声明）"%args .source_type .strip ())
        else :
            source_types =_parse_source_types (args .source_type )
    else :
        source_types =_scope_to_source_types ((state or {}).get ("scope"))
        if source_types :
            notes .append ("已按存档范围 scope→source_type=%s（未标签项排除）"%"/".join (sorted (source_types )))
    from_chapter =args .from_chapter 
    if mode =="shore_up"and from_chapter is None and args .chapter is None :
        _die ("某章起步补弱 需要显式章范围：传 --chapter <N> 或 --from-chapter <N>。不从 current_phase 猜——"  "阶段号未必等于章号（study_plan 可把阶段映到别的章），猜会漏选/错选章节")
    scored =[]
    untagged_excluded =0 
    for i ,q in enumerate (items ):
        if (args .chapter is not None and canonical_chapter_key (args .chapter ,allow_phase =True )not in _chapter_keys (q )):
            continue 
        if from_chapter is not None :
            nums =_numeric_chapters (q )
            if not any (n >=from_chapter for n in nums ):
                continue 
        if source_types is not None and q .get ("source_type")not in source_types :
            if q .get ("source_type")is None :
                untagged_excluded +=1 
            continue 
        d =q .get ("difficulty")
        if not (isinstance (d ,int )and not isinstance (d ,bool )and 1 <=d <=5 ):
            d =sd .score_item (q ,late )[0 ]
        cls ,trig =classify (q ,idx )
        scored .append ({"id":q .get ("id"),"difficulty":d ,"cls":cls ,"trigger":trig ,"chapter":_chapter_key (q ),"orig_idx":i })
    ordered =order_items (scored ,mode )[:max (args .num ,0 )]
    if source_types is not None and untagged_excluded :
        notes .append ("范围过滤排除了 %d 道未标签(source_type 缺失)题——可能是摄取/打标缺口，"  "别当作没有这些题（A2 契约：排除并上报）"%untagged_excluded )
    payload =[{"id":it ["id"],"difficulty":it ["difficulty"],"class":it ["cls"],"chapter":it ["chapter"],"select_reason":"%s（%s）"%(_CLASS_REASON [it ["cls"]],it ["trigger"])}for it in ordered ]
    if args .json :
        print (json .dumps ({"mode":mode ,"count":len (payload ),"state_loaded":state is not None ,"source_types":sorted (source_types )if source_types else None ,"untagged_excluded":untagged_excluded ,"runtime_scoped_items":runtime ["scoped_items"],"runtime_exclusion_counts":runtime ["exclusion_counts"],"bank_binding_id":runtime ["bank_binding"]["binding_id"],"from_chapter":from_chapter ,"notes":notes ,"items":payload },ensure_ascii =False ,indent =2 ))
    else :
        print ("[A7] 模式=%s｜%s｜选出 %d 题（难度×掌握状态启发式排序，非 LLM）"%(i18n .display ("mode",mode ),"已读 study_state"if state is not None else "无 state（全按常规）",len (payload )))
        for note in notes :
            print ("    · "+note )
        for it in payload :
            print ("  %-16s d=%d  %-8s  %s"%(it ["id"],it ["difficulty"],it ["class"],it ["select_reason"]))
    return 0 
if __name__ =="__main__":
    raise SystemExit (main ())
