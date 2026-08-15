''
import json 
class StrictJSONError (ValueError ):
    ''
def _object_without_duplicates (pairs ):
    result ={}
    for key ,value in pairs :
        if key in result :
            raise StrictJSONError ("duplicate JSON key: %s"%key )
        result [key ]=value 
    return result 
def _reject_constant (value ):
    raise StrictJSONError ("non-finite JSON constant is not allowed: %s"%value )
def load (stream ):
    return json .load (stream ,object_pairs_hook =_object_without_duplicates ,parse_constant =_reject_constant ,)
def loads (text ):
    return json .loads (text ,object_pairs_hook =_object_without_duplicates ,parse_constant =_reject_constant ,)
def load_file (path ):
    with open (path ,"r",encoding ="utf-8")as stream :
        return load (stream )
