#!/usr/bin/env python
# -*- coding: utf-8 -*-
('')
import json 
import os 
MODES =("from_scratch","shore_up","fill_gaps")
TIERS =("le1d","d1_3","d3_7","gt7d")
LANGS =("zh","en","bilingual")
ARTIFACT_MODES =("chat","visual")
PROCESSING_MODES =("lightweight","full")
ANSWER_EXPLANATION_MODES =("ordinary","isolated")
INTERACTION_STYLES =("batch","step_by_step")
WINDOW_STATUSES =("in_window","out_window","verified")
ROW_STATUSES =("to_review","to_revisit","corrected","reviewed","revisited","resolved")
MISTAKE_RESOLVED =frozenset (("corrected","reviewed","resolved"))
CONFUSION_RESOLVED =frozenset (("revisited","resolved"))
_ZH ={"mode.from_scratch":"零基础从头讲","mode.shore_up":"某章起步补弱","mode.fill_gaps":"查缺补漏","tier.le1d":"≤1天","tier.d1_3":"1-3天","tier.d3_7":"3-7天","tier.gt7d":">7天","lang.zh":"中文","lang.en":"English","lang.bilingual":"双语","artifact.chat":"对话省额","artifact.visual":"视觉教材","window.in_window":"在窗口","window.out_window":"窗口外","window.verified":"已实测","row.to_review":"待复盘","row.to_revisit":"待回顾","row.corrected":"已订正","row.reviewed":"已复盘","row.revisited":"已回顾","row.resolved":"已解决","notebook_type.walkthrough":"精讲","notebook_type.feedback":"判分","notebook_type.confusion":"疑难","notebook_type.review":"复盘","notebook.index_title":"# 📒 学习笔记目录","notebook.chapter_heading":"第 %(num)s 章","mistakes.index_title":"# ❌ 错题本目录","mistakes.status_suffix":"｜ 状态：%(status)s",}
_EN ={"mode.from_scratch":"teach from scratch","mode.shore_up":"start mid-course, shore up weak spots","mode.fill_gaps":"fill the gaps","tier.le1d":"≤1 day","tier.d1_3":"1-3 days","tier.d3_7":"3-7 days","tier.gt7d":">7 days","lang.zh":"Chinese","lang.en":"English","lang.bilingual":"Bilingual","artifact.chat":"chat-only","artifact.visual":"visual study guide","window.in_window":"in window","window.out_window":"out of window","window.verified":"verified by quiz","row.to_review":"to review","row.to_revisit":"to revisit","row.corrected":"corrected","row.reviewed":"reviewed","row.revisited":"revisited","row.resolved":"resolved","notebook_type.walkthrough":"Walkthrough","notebook_type.feedback":"Feedback","notebook_type.confusion":"Confusion","notebook_type.review":"Review","notebook.index_title":"# 📒 Notebook index","notebook.chapter_heading":"Chapter %(num)s","mistakes.index_title":"# ❌ Mistake-notebook index","mistakes.status_suffix":"| Status: %(status)s",}
_ZH .update ({"processing.lightweight":"轻量按需（推荐）","processing.full":"完整建库",})
_EN .update ({"processing.lightweight":"lightweight on-demand (recommended)","processing.full":"full knowledge-base build",})
_ZH .update ({"answer_explanation.ordinary":"普通逐题详解","answer_explanation.isolated":"隔离逐题详解（延展功能）",})
_EN .update ({"answer_explanation.ordinary":"ordinary per-item explanation","answer_explanation.isolated":"isolated per-item explanation (extended)",})
_EMBEDDED ={"zh":_ZH ,"en":_EN }
_MODE_IN ={c :c for c in MODES }
_MODE_IN .update ({_ZH ["mode."+c ]:c for c in MODES })
_MODE_IN .update ({_EN ["mode."+c ].lower ():c for c in MODES })
_MODE_IN .update ({"from scratch":"from_scratch","teach-from-scratch":"from_scratch","shore up":"shore_up","shore up weak spots":"shore_up","start mid-course":"shore_up","mid-course":"shore_up","fill gaps":"fill_gaps","fill-the-gaps":"fill_gaps","gap filling":"fill_gaps",})
MODE_MIGRATION ={"panic":("from_scratch","le1d"),"sprint":("fill_gaps","d1_3"),"normal":("fill_gaps",None ),"mock":("fill_gaps",None ),}
_TIER_IN ={c :c for c in TIERS }
_TIER_IN .update ({_ZH ["tier."+c ]:c for c in TIERS })
_TIER_IN .update ({"<=1天":"le1d","1天":"le1d","当天":"le1d","今天":"le1d","一天":"le1d","考前一天":"le1d","明天考":"le1d","1—3天":"d1_3","1~3天":"d1_3","2-3天":"d1_3","几天":"d1_3","3—7天":"d3_7","3~7天":"d3_7","一周":"d3_7","一周内":"d3_7","＞7天":"gt7d","7天以上":"gt7d","一周以上":"gt7d","还早":"gt7d","时间充裕":"gt7d","1 day":"le1d","1-3 days":"d1_3","3-7 days":"d3_7",">7 days":"gt7d",})
_TIER_IN .update ({_EN ["tier."+c ].lower ():c for c in TIERS })
_LANG_IN ={c :c for c in LANGS }
_LANG_IN .update ({_ZH ["lang."+c ]:c for c in LANGS })
_LANG_IN .update ({"zh-cn":"zh","chinese":"zh","简体中文":"zh","汉语":"zh","中":"zh","english":"en","英文":"en","英语":"en","bi":"bilingual","zh+en":"bilingual","中英":"bilingual","中英双语":"bilingual",})
_ARTIFACT_IN ={c :c for c in ARTIFACT_MODES }
_ARTIFACT_IN .update ({_ZH ["artifact."+c ]:c for c in ARTIFACT_MODES })
_ARTIFACT_IN .update ({_EN ["artifact."+c ].lower ():c for c in ARTIFACT_MODES })
_ARTIFACT_IN .update ({"对话模式":"chat","只在对话教学":"chat","仅对话":"chat","聊天教学":"chat","省额度":"chat","省token":"chat","低token":"chat","v3":"chat","chat only":"chat","conversation only":"chat","low-token":"chat","save tokens":"chat","打印pdf":"visual","生成pdf":"visual","pdf":"visual","可打印教材":"visual","完整教材":"visual","不在乎token":"visual","不在乎 token":"visual","token不敏感":"visual","token 不敏感":"visual","study guide":"visual","printable":"visual","token-insensitive":"visual","print pdf":"visual","visual":"visual",})
_PROCESSING_IN ={c :c for c in PROCESSING_MODES }
_PROCESSING_IN .update ({_ZH ["processing."+c ]:c for c in PROCESSING_MODES })
_PROCESSING_IN .update ({_EN ["processing."+c ].lower ():c for c in PROCESSING_MODES })
_PROCESSING_IN .update ({"light":"lightweight","lite":"lightweight","on-demand":"lightweight","on demand":"lightweight","lazy":"lightweight","default":"lightweight","轻量":"lightweight","轻量模式":"lightweight","按需":"lightweight","按需处理":"lightweight","默认":"lightweight","complete":"full","heavy":"full","knowledge base":"full","full ingestion":"full","完整":"full","完整模式":"full","全量":"full","完整建库":"full","全量建库":"full",})
_WINDOW_IN ={c :c for c in WINDOW_STATUSES }
_WINDOW_IN .update ({_ZH ["window."+c ]:c for c in WINDOW_STATUSES })
_WINDOW_IN .update ({_EN ["window."+c ]:c for c in WINDOW_STATUSES })
_ROW_IN ={c :c for c in ROW_STATUSES }
_ROW_IN .update ({_ZH ["row."+c ]:c for c in ROW_STATUSES })
_ROW_IN .update ({_EN ["row."+c ]:c for c in ROW_STATUSES })
def canon_mode (v ):
    ('')
    v =(v or "").strip ()
    if v in _MODE_IN :
        return _MODE_IN [v ],None ,None 
    if v .lower ()in _MODE_IN :
        return _MODE_IN [v .lower ()],None ,None 
    if v in MODE_MIGRATION :
        code ,tier =MODE_MIGRATION [v ]
        return code ,tier ,("旧模式「%s」已废弃，迁移为「%s」%s（新模式仅 %s）"%(v ,display ("mode",code ),("＋时间宽裕度「%s」"%display ("tier",tier ))if tier else "","/".join (display ("mode",c )for c in MODES )))
    return v ,None ,("非标准学习模式「%s」——canonical 仅 %s；已按原值保留，请确认是否规范化"%(v ,"/".join (display ("mode",c )for c in MODES )))
def canon_tier (v ):
    ''
    v =(v or "").strip ()
    if v in _TIER_IN :
        return _TIER_IN [v ],None 
    if v .lower ()in _TIER_IN :
        return _TIER_IN [v .lower ()],None 
    return v ,("非标准时间宽裕度「%s」——canonical 仅 %s；已按原值保留，请确认是否规范化"%(v ,"/".join (display ("tier",c )for c in TIERS )))
def canon_language (v ):
    ''
    v =(v or "").strip ()
    if v in _LANG_IN :
        return _LANG_IN [v ],None 
    key =v .lower ()
    if key in _LANG_IN :
        return _LANG_IN [key ],None 
    return v ,("非标准语言偏好「%s」——canonical 仅 %s；已按原值保留，请确认是否规范化"%(v ,"/".join (LANGS )))
def canon_artifact_mode (v ):
    ('')
    v =(v or "").strip ()
    if v in _ARTIFACT_IN :
        return _ARTIFACT_IN [v ],None 
    key =v .lower ()
    if key in _ARTIFACT_IN :
        return _ARTIFACT_IN [key ],None 
    return v ,("非标准输出资源模式「%s」——canonical 仅 %s；已按原值保留，运行时回退为 chat"%(v ,"/".join (ARTIFACT_MODES )))
def canon_processing_mode (v ):
    ('')
    v =(v or "").strip ()
    if v in _PROCESSING_IN :
        return _PROCESSING_IN [v ],None 
    key =v .lower ()
    if key in _PROCESSING_IN :
        return _PROCESSING_IN [key ],None 
    return v ,("non-standard processing mode %r; canonical values are %s; "  "the effective runtime falls back to lightweight"%(v ,"/".join (PROCESSING_MODES )))
def canon_answer_explanation_mode (v ):
    ('')
    if not isinstance (v ,str ):
        return "ordinary",("missing or non-string answer explanation mode; using ordinary"if v is not None else None )
    if v in ANSWER_EXPLANATION_MODES :
        return v ,None 
    return "ordinary",("unknown or non-canonical answer explanation mode %r; using ordinary"%v )
def canon_window_status (v ):
    ''
    v =(v or "").strip ()
    return _WINDOW_IN .get (v ,v )
def canon_row_status (v ):
    ''
    v =(v or "").strip ()
    return _ROW_IN .get (v ,v )
_REPO_ROOT =os .path .dirname (os .path .dirname (os .path .abspath (__file__ )))
_catalog_cache ={}
def catalog (lang ):
    ('')
    lang =lang if lang in _EMBEDDED else "zh"
    if lang in _catalog_cache :
        return _catalog_cache [lang ]
    cat =dict (_EMBEDDED [lang ])
    path =os .path .join (_REPO_ROOT ,"locales",lang ,"messages.json")
    if os .path .isfile (path ):
        try :
            with open (path ,"r",encoding ="utf-8")as f :
                overlay =json .load (f )
            if isinstance (overlay ,dict ):
                cat .update ({k :v for k ,v in overlay .items ()if isinstance (v ,str )})
        except (OSError ,ValueError ):
            pass 
    _catalog_cache [lang ]=cat 
    return cat 
def display (kind ,code ,lang ="zh"):
    ('')
    if code is None :
        return code 
    return catalog (lang ).get ("%s.%s"%(kind ,code ),code )
def msg (msgid ,lang ="zh",**fmt ):
    ('')
    s =catalog (lang ).get (msgid )
    if s is None :
        return None 
    return s %fmt if fmt else s 
def workspace_language (state ):
    ('')
    v =(state or {}).get ("language")if isinstance (state ,dict )else state 
    code ,_w =canon_language (v or "")
    return code if code in LANGS else "zh"
def workspace_artifact_mode (state ):
    ('')
    v =(state or {}).get ("artifact_mode")if isinstance (state ,dict )else state 
    if not isinstance (v ,str ):
        return "chat"
    code ,_w =canon_artifact_mode (v )
    return code if code in ARTIFACT_MODES else "chat"
def workspace_effective_artifact_mode (state ):
    ('')
    if workspace_processing_mode (state )!="full":
        return "chat"
    return workspace_artifact_mode (state )
def workspace_artifact_mode_dormant (state ):
    ''
    return (workspace_artifact_mode (state )=="visual"and workspace_effective_artifact_mode (state )=="chat")
def workspace_processing_mode (state ):
    ('')
    v =(state or {}).get ("processing_mode")if isinstance (state ,dict )else state 
    if not isinstance (v ,str ):
        return "lightweight"
    code ,_w =canon_processing_mode (v )
    return code if code in PROCESSING_MODES else "lightweight"
def workspace_answer_explanation_mode (state ):
    ('')
    v =((state or {}).get ("answer_explanation_mode")if isinstance (state ,dict )else state )
    return "isolated"if v =="isolated"else "ordinary"
def workspace_no_questions (state ):
    ''
    if not isinstance (state ,dict ):
        return False 
    preferences =state .get ("preferences")
    if not isinstance (preferences ,dict ):
        return False 
    for key in ("no_questions","no-questions","不要出题","不要问我"):
        if key not in preferences :
            continue 
        value =preferences .get (key )
        if value is True :
            return True 
        if isinstance (value ,str )and value .strip ().lower ()in ("1","true","yes","on","是","不出题","不要问"):
            return True 
    return False 
def workspace_interaction_style_preference (state ):
    ''
    preferences =state .get ("preferences")if isinstance (state ,dict )else None 
    if not isinstance (preferences ,dict ):
        return "batch"
    value =preferences .get ("interaction_style","batch")
    return value if value in INTERACTION_STYLES else "batch"
def workspace_effective_interaction_style (state ):
    ''
    preference =workspace_interaction_style_preference (state )
    if (preference =="step_by_step"and workspace_processing_mode (state )=="full"and not workspace_no_questions (state )):
        return "step_by_step"
    return "batch"
def workspace_interaction_style_dormant (state ):
    return (workspace_interaction_style_preference (state )=="step_by_step"and workspace_effective_interaction_style (state )=="batch")
