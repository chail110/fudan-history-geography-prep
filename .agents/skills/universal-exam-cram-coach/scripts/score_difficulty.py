#!/usr/bin/env python
# -*- coding: utf-8 -*-
('')
import argparse 
import json 
import os 
import re 
import sys 
try :
    from .ingestion import workspace_publication_lock 
except ImportError :
    from ingestion import workspace_publication_lock 
for _s in ("stdout","stderr"):
    try :
        getattr (sys ,_s ).reconfigure (encoding ="utf-8")
    except Exception :
        pass 
def _die (msg ,code =2 ):
    sys .stderr .write ("score_difficulty: "+msg +"\n")
    raise SystemExit (code )
def bank_path (ws ):
    return os .path .join (ws ,"references","quiz_bank.json")
def load_bank (ws ):
    path =bank_path (ws )
    if not os .path .isfile (path ):
        _die ("找不到题库: %s"%path )
    try :
        with open (path ,"r",encoding ="utf-8")as f :
            bank =json .load (f )
    except ValueError as e :
        _die ("quiz_bank.json 不是合法 JSON: %s"%e )
    if not isinstance (bank ,list ):
        _die ("quiz_bank.json 顶层必须是数组")
    return bank 
_STRUCT_FAMILIES =(("分段",("分段函数","分段","piecewise")),("求和",("求和","累加","Σ","∑","\\sum","sum_{")),("积分",("积分","∫","\\int","integral")),("条件化",("条件概率","条件分布","条件期望","conditional probability","given that")),("变量变换",("换元","代换","变量替换","变量变换","雅可比","jacobian","change of variable")),("证明",("证明","求证","prove that","proof")),("递归归纳",("递归","递推","归纳法","数学归纳","recursion","recurrence","induction")),("极限求导",("求极限","取极限","求导","导数","偏导","微分方程","derivative","differentiate")),("矩阵",("矩阵","行列式","特征值","特征向量","matrix","determinant","eigen")),("优化",("最大化","最小化","最优","拉格朗日","optimal","maximize","minimize","lagrang")),)
_OPEN_TYPES ={"subjective","diagram","code","proof","essay","short_answer"}
def _search_text (q ):
    ''
    parts =[]
    for k in ("question","question_text","explanation","answer","prompt","stem"):
        v =q .get (k )
        if isinstance (v ,str ):
            parts .append (v )
    kw =q .get ("keywords")
    if isinstance (kw ,list ):
        parts .extend (str (x )for x in kw )
    opts =q .get ("options")
    if isinstance (opts ,list ):
        parts .extend (str (x )for x in opts )
    return "\n".join (parts )
def _struct_families (text ):
    low =text .lower ()
    fired =[]
    for name ,cues in _STRUCT_FAMILIES :
        for cue in cues :
            c =cue if not cue .isascii ()else cue .lower ()
            hay =text if not cue .isascii ()else low 
            if c in hay :
                fired .append (name )
                break 
    return fired 
def _kp_count (q ):
    kps =q .get ("knowledge_points")
    if not isinstance (kps ,list ):
        return 0 
    return len ({str (k ).strip ()for k in kps if str (k ).strip ()})
def _multipage (q ):
    ('')
    sp =q .get ("answer_source_pages")
    pages =set ()
    if isinstance (sp ,list ):
        for x in sp :
            try :
                pages .add (int (x ))
            except (ValueError ,TypeError ):
                pass 
    elif isinstance (sp ,str ):
        for tok in re .split (r"[,\s]+",sp .strip ()):
            m =re .match (r"^(\d+)\s*-\s*(\d+)$",tok )
            if m :
                a ,b =int (m .group (1 )),int (m .group (2 ))
                pages .update (range (min (a ,b ),max (a ,b )+1 ))
            elif tok .isdigit ():
                pages .add (int (tok ))
    elif isinstance (sp ,dict ):
        try :
            a ,b =int (sp .get ("start")),int (sp .get ("end"))
            pages .update (range (min (a ,b ),max (a ,b )+1 ))
        except (ValueError ,TypeError ):
            pass 
    return len (pages )>1 
def _numeric_chapter (q ):
    for k in ("chapter","phase"):
        v =q .get (k )
        if v is None :
            continue 
        m =re .search (r"\d+",str (v ))
        if m :
            return int (m .group (0 ))
    return None 
def _late_chapter_cutoff (bank ):
    ''
    nums =sorted ({c for c in (_numeric_chapter (q )for q in bank )if c is not None })
    if len (nums )<3 :
        return None 
    idx =int (len (nums )*2 /3 )
    return nums [min (idx ,len (nums )-1 )]
def score_item (q ,late_cutoff ):
    ''
    points =0 
    reasons =[]
    kp =_kp_count (q )
    if kp >=3 :
        points +=2 
        reasons .append ("跨%d知识点"%kp )
    elif kp ==2 :
        points +=1 
        reasons .append ("跨2知识点")
    fam =_struct_families (_search_text (q ))
    if fam :
        points +=min (len (fam ),2 )
        reasons .append ("结构:"+"/".join (fam [:3 ]))
    if q .get ("requires_assets")is True :
        points +=1 
        reasons .append ("需读图")
    if _multipage (q ):
        points +=1 
        reasons .append ("多页解答")
    nc =_numeric_chapter (q )
    if late_cutoff is not None and nc is not None and nc >=late_cutoff :
        points +=1 
        reasons .append ("章节靠后(ch%d)"%nc )
    if str (q .get ("type")or "").lower ()in _OPEN_TYPES :
        points +=1 
        reasons .append ("开放题型")
    if points <=0 :
        diff =1 
    elif points ==1 :
        diff =2 
    elif points <=3 :
        diff =3 
    elif points <=5 :
        diff =4 
    else :
        diff =5 
    reason ="启发式下界 d=%d：%s"%(diff ,"、".join (reasons )if reasons else "无高难信号")
    return diff ,reason 
def _assert_within_workspace (ws ,path ):
    ('')
    if os .path .islink (path ):
        _die ("%s 不得为符号链接（可能指向工作区外）——拒绝写入"%path ,1 )
    ws_real =os .path .normcase (os .path .realpath (ws ))
    real =os .path .normcase (os .path .realpath (path ))
    if real !=ws_real and not real .startswith (ws_real +os .sep ):
        _die ("quiz_bank.json 经符号链接 / 父目录逃出工作区——拒绝写入（realpath 归属校验失败）",1 )
def _atomic_write_json (path ,obj ):
    if os .path .lexists (path )and not os .path .islink (path )and not os .path .isfile (path ):
        _die ("%s 已存在但不是常规文件（目录/特殊文件）——拒绝写入，请先手动清理"%path ,1 )
    tmp =path +".tmp"
    if os .path .islink (tmp ):
        _die ("检测到符号链接临时文件 %s——可能指向工作区外，拒绝写入（请手动清理后重试）"%tmp ,1 )
    try :
        if os .path .exists (tmp ):
            os .remove (tmp )
        fd =os .open (tmp ,os .O_CREAT |os .O_EXCL |os .O_WRONLY ,0o666 )
        with os .fdopen (fd ,"w",encoding ="utf-8",newline ="\n")as f :
            f .write (json .dumps (obj ,ensure_ascii =False ,indent =2 ))
            f .write ("\n")
        os .replace (tmp ,path )
    except OSError as e :
        try :
            os .remove (tmp )
        except OSError :
            pass 
        _die ("写入题库失败：%s（未破坏原文件；若为残留 %s 目录请手动清理）"%(e ,tmp ),1 )
def main (argv =None ,_state_locked =False ):
    ap =argparse .ArgumentParser (description ="Deterministic difficulty scoring (A7): writes back difficulty 1-5 + difficulty_reason")
    ap .add_argument ("--workspace",required =True ,help ="workspace root (contains references/quiz_bank.json)")
    ap .add_argument ("--dry-run",action ="store_true",help ="preview the distribution only; no write")
    ap .add_argument ("--force",action ="store_true",help ="rewrite items even when unchanged")
    ap .add_argument ("--json",action ="store_true",help ="print stats as JSON")
    args =ap .parse_args (argv )
    if not args .dry_run and not _state_locked :
        with workspace_publication_lock (args .workspace ):
            return main (argv ,_state_locked =True )
    bank =load_bank (args .workspace )
    items =[q for q in bank if isinstance (q ,dict )and q .get ("id")is not None ]
    late =_late_chapter_cutoff (items )
    changed =0 
    dist ={1 :0 ,2 :0 ,3 :0 ,4 :0 ,5 :0 }
    for q in items :
        diff ,reason =score_item (q ,late )
        dist [diff ]+=1 
        if q .get ("difficulty")!=diff or q .get ("difficulty_reason")!=reason :
            changed +=1 
            if not args .dry_run :
                q ["difficulty"]=diff 
                q ["difficulty_reason"]=reason 
    if not args .dry_run and (changed or args .force ):
        if args .force :
            for q in items :
                diff ,reason =score_item (q ,late )
                q ["difficulty"]=diff 
                q ["difficulty_reason"]=reason 
        _assert_within_workspace (args .workspace ,bank_path (args .workspace ))
        _atomic_write_json (bank_path (args .workspace ),bank )
    stats ={"total_scored":len (items ),"changed":changed ,"distribution":{str (k ):v for k ,v in dist .items ()},"late_chapter_cutoff":late ,"written":(not args .dry_run )and bool (changed or args .force ),}
    if args .json :
        print (json .dumps (stats ,ensure_ascii =False ,indent =2 ))
    else :
        print ("[A7] 已评分 %d 题（%s）；难度分布 1..5 = %s"%(len (items ),"预览未落盘"if args .dry_run else ("已回写 %d 处变动"%changed if (changed or args .force )else "无变动")," / ".join ("%d:%d"%(k ,dist [k ])for k in (1 ,2 ,3 ,4 ,5 ))))
        print ("    诚实口径：这是结构信号的启发式下界，非语义判定；LLM 语义评分为将来 opt-in。")
    return 0 
if __name__ =="__main__":
    raise SystemExit (main ())
