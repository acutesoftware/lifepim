#!/usr/bin/python3
# coding: utf-8
# index.py

"""
indexing reads files and produces
1. list of all keywords
2. list of headings
3. index file with keywords , files weightings
4. lookup file - unique list of words (minus stopwords) 

searching for a keyword
a) find the word ID in keywords file
b) find all matches in index file for that keyword
c) return search results based on file rankings from index results
"""

import os
import shutil
import glob
import config as mod_cfg
import aikif.lib.cls_filelist as mod_fl

filelist = os.path.join(mod_cfg.index_folder, 'filelist.csv')
heading_file = os.path.join(mod_cfg.index_folder, 'headings.csv')
keyword_file = os.path.join(mod_cfg.index_folder, 'keywords.csv')
index_file = os.path.join(mod_cfg.index_folder, 'index.dat')

stopwords = [
"-", "=", "[", "]", "\\", "/", ".", ",", "<", ">","|", "{", "}", "=", "-", "`",
"~", "!",  "@", "#",  "$", "%",  "^", "&",  "*", "(",")","_","+",  
"0o", "0s", "3a", "3b", "3d", "6b", "6o", "a", 
"A", "a1", "a2", "a3", "a4", "ab", "able", "about", "above", "abst", "ac", "accordance", "according", "accordingly", "across", "act", "actually", "ad", "added", "adj", "ae", "af", "affected", "affecting", "after", "afterwards", "ag", "again", "against", "ah", "ain", "aj", "al", "all", "allow", "allows", "almost", "alone", "along", "already", "also", "although", "always", "am", "among", "amongst", "amoungst", "amount", "an", "and", "announce", "another", "any", "anybody", "anyhow", "anymore", "anyone", "anyway", "anyways", "anywhere", "ao", "ap", "apart", "apparently", "appreciate", "approximately", "ar", "are", "aren", "arent", "arise", "around", "as", "aside", "ask", "asking", "at", "au", "auth", "av", "available", "aw", "away", "awfully", "ax", "ay", "az", 
"b", "B", "b1", "b2", "b3", "ba", "back", "bc", "bd", "be", "became", "been", "before", "beforehand", "beginnings", "behind", "below", "beside", "besides", "best", "between", "beyond", "bi", "bill", "biol", "bj", "bk", "bl", "bn", "both", "bottom", "bp", "br", "brief", "briefly", "bs", "bt", "bu", "but", "bx", "by", 
"c", "C", "c1", "c2", "c3", "ca", "call", "came", "can", "cannot", "cant", "cc", "cd", "ce", "certain", "certainly", "cf", "cg", "ch", "ci", "cit", "cj", "cl", "clearly", "cm", "cn", "co", "com", "come", "comes", "con", "concerning", "consequently", "consider", "considering", "could", "couldn", "couldnt", "course", "cp", "cq", "cr", "cry", "cs", "ct", "cu", "cv", "cx", "cy", "cz", 
"d", "D", "d2", "da", "date", "dc", "dd", "de", "definitely", "describe", "described", "despite", "detail", "df", "di", "did", "didn", "dj", "dk", "dl", "do", "does", "doesn", "doing", "don", "done", "down", "downwards", "dp", "dr", "ds", "dt", "du", "due", "during", "dx", "dy", 
"e", "E", "e2", "e3", "ea", "each", "ec", "ed", "edu", "ee", "ef", "eg", "ei", "eight", "eighty", "either", "ej", "el", "eleven", "else", "elsewhere", "em", "en", "end", "ending", "enough", "entirely", "eo", "ep", "eq", "er", "es", "especially", "est", "et", "et-al", "etc", "eu", "ev", "even", "ever", "every", "everybody", "everyone", "everything", "everywhere", "ex", "exactly", "example", "except", "ey", 
"f", "F", "f2", "fa", "far", "fc", "few", "ff", "fi", "fifteen", "fifth", "fify", "fill", "find", "fire", "five", "fix", "fj", "fl", "fn", "fo", "followed", "following", "follows", "for", "former", "formerly", "forth", "forty", "found", "four", "fr", "from", "front", "fs", "ft", "fu", "full", "further", "furthermore", "fy", 
"g", "G", "ga", "gave", "ge", "get", "gets", "getting", "gi", "give", "given", "gives", "giving", "gj", "gl", "go", "goes", "going", "gone", "got", "gotten", "gr", "greetings", "gs", "gy", "h", "H", "h2", "h3", "had", "hadn", "happens", "hardly", "has", "hasn", "hasnt", "have", "haven", "having", "he", "hed", "hello", "help", "hence", "here", "hereafter", "hereby", "herein", "heres", "hereupon", "hes", "hh", "hi", "hid", "hither", "hj", "ho", "hopefully", "how", "howbeit", "however", "hr", "hs", "http", "hu", "hundred", "hy", "i2", "i3", "i4", "i6", "i7", "i8", "ia", "ib", "ibid", "ic", "id", "ie", "if", "ig", "ignored", "ih", "ii", "ij", "il", "im", "immediately", "in", "inasmuch", "inc", "indeed", "index", "indicate", "indicated", "indicates", "information", "inner", "insofar", "instead", "interest", "into", "inward", "io", "ip", "iq", "ir", "is", "isn", "it", "itd", "its", "iv", "ix", "iy", "iz", "j", "J", "jj", "jr", "js", "jt", "ju", "just", "k", "K", "ke", "keep", "keeps", "kept", "kg", "kj", "km", "ko", "l", "L", "l2", "la", "largely", "last", "lately", "later", "latter", "latterly", "lb", "lc", "le", "least", "les", "less", "lest", "let", "lets", "lf", "like", "liked", "likely", "line", "little", "lj", "ll", "ln", "lo", "look", "looking", "looks", "los", "lr", "ls", "lt", "ltd", "m", "M", "m2", "ma", "made", "mainly", "make", "makes", "many", "may", "maybe", "me", "meantime", "meanwhile", "merely", "mg", "might", "mightn", "mill", "million", "mine", "miss", "ml", "mn", "mo", "more", "moreover", "most", "mostly", "move", "mr", "mrs", "ms", "mt", "mu", "much", "mug", "must", "mustn", "my", "n", "N", "n2", "na", "name", "namely", "nay", "nc", "nd", "ne", "near", "nearly", "necessarily", "neither", "nevertheless", "new", "next", "ng", "ni", "nine", "ninety", "nj", "nl", "nn", "no", "nobody", "non", "none", "nonetheless", "noone", "nor", "normally", "nos", "not", "noted", "novel", "now", "nowhere", "nr", "ns", "nt", "ny", "o", "O", "oa", "ob", "obtain", "obtained", "obviously", "oc", "od", "of", "off", "often", "og", "oh", "oi", "oj", "ok", "okay", "ol", "old", "om", "omitted", "on", "once", "one", "ones", "only", "onto", "oo", "op", "oq", "or", "ord", "os", "ot", "otherwise", "ou", "ought", "our", "out", "outside", "over", "overall", "ow", "owing", "own", "ox", "oz", "p", "P", "p1", "p2", "p3", "page", "pagecount", "pages", "par", "part", "particular", "particularly", "pas", "past", "pc", "pd", "pe", "per", "perhaps", "pf", "ph", "pi", "pj", "pk", "pl", "placed", "please", "plus", "pm", "pn", "po", "poorly", "pp", "pq", "pr", "predominantly", "presumably", "previously", "primarily", "probably", "promptly", "proud", "provides", "ps", "pt", "pu", "put", "py", "q", "Q", "qj", "qu", "que", "quickly", "quite", "qv", "r", "R", "r2", "ra", "ran", "rather", "rc", "rd", "re", "readily", "really", "reasonably", "recent", "recently", "ref", "refs", "regarding", "regardless", "regards", "related", "relatively", "research-articl", "respectively", "resulted", "resulting", "results", "rf", "rh", "ri", "right", "rj", "rl", "rm", "rn", "ro", "rq", "rr", "rs", "rt", "ru", "run", "rv", "ry", "s", "S", "s2", "sa", "said", "saw", "say", "saying", "says", "sc", "sd", "se", "sec", "second", "secondly", "section", "seem", "seemed", "seeming", "seems", "seen", "sent", "seven", "several", "sf", "shall", "shan", "shed", "shes", "show", "showed", "shown", "showns", "shows", "si", "side", "since", "sincere", "six", "sixty", "sj", "sl", "slightly", "sm", "sn", "so", "some", "somehow", "somethan", "sometime", "sometimes", "somewhat", "somewhere", "soon", "sorry", "sp", "specifically", "specified", "specify", "specifying", "sq", "sr", "ss", "st", "still", "stop", "strongly", "sub", "substantially", "successfully", "such", "sufficiently", "suggest", "sup", "sure", "sy", "sz", "t", "T", "t1", "t2", "t3", "take", "taken", "taking", "tb", "tc", "td", "te", "tell", "ten", "tends", "tf", "th", "than", "thank", "thanks", "thanx", "that", "thats", "the", "their", "theirs", "them", "themselves", "then", "thence", "there", "thereafter", "thereby", "thered", "therefore", "therein", "thereof", "therere", "theres", "thereto", "thereupon", "these", "they", "theyd", "theyre", "thickv", "thin", "think", "third", "this", "thorough", "thoroughly", "those", "thou", "though", "thoughh", "thousand", "three", "throug", "through", "throughout", "thru", "thus", "ti", "til", "tip", "tj", "tl", "tm", "tn", "to", "together", "too", "took", "top", "toward", "towards", "tp", "tq", "tr", "tried", "tries", "truly", "try", "trying", "ts", "tt", "tv", "twelve", "twenty", "twice", "two", "tx", "u", "U", "u201d", "ue", "ui", "uj", "uk", "um", "un", "under", "unfortunately", "unless", "unlike", "unlikely", "until", "unto", "uo", "up", "upon", "ups", "ur", "us", "used", "useful", "usefully", "usefulness", "using", "usually", "ut", "v", "V", "va", "various", "vd", "ve", "very", "via", "viz", "vj", "vo", "vol", "vols", "volumtype", "vq", "vs", "vt", "vu", "w", "W", "wa", "was", "wasn", "wasnt", "way", "we", "wed", "welcome", "well", "well-b", "went", "were", "weren", "werent", "what", "whatever", "whats", "when", "whence", "whenever", "where", "whereafter", "whereas", "whereby", "wherein", "wheres", "whereupon", "wherever", "whether", "which", "while", "whim", "whither", "who", "whod", "whoever", "whole", "whom", "whomever", "whos", "whose", "why", "wi", "widely", "with", "within", "without", "wo", "won", "wonder", "wont", "would", "wouldn", "wouldnt", "www", "x", "X", "x1", "x2", "x3", "xf", "xi", "xj", "xk", "xl", "xn", "xo", "xs", "xt", "xv", "xx", "y", "Y", "y2", "yes", "yet", "yj", "yl", "you", "youd", "your", "youre", "yours", "yr", "ys", "yt", 
"z", "Z", "zero", "zi", "zz"]




def refresh_indexes_if_needed():
    """
    top level function called from server. 
    """
    if is_index_dirty():
        build_indexes()

def is_index_dirty():
    """
    Checks file dates against index dates and refreshes when needed.
    For sample data, always refresh on server start.
    """
    return True


def build_indexes():
    print('rebuilding indexes in ', mod_cfg.index_folder)
    print('scanning ', mod_cfg.data_folder)
    aikif_fl = mod_fl.FileList([mod_cfg.data_folder], ['*.*'], [], filelist )
    aikif_fl.save_filelist(filelist, ["name", "path", "size", "date"])
    index_headings(aikif_fl)


def index_headings(fl):
    all_headings = []  # list of lists [fname, heading_text]
    tot_lines_all_files = 0
    keywords_all_files = []  # list of [fname, keyword, count]
    hashtags_all_files = []  # list of [fname, keyword, count]
    #print(fl.get_list())
    #return

    for fname in fl.get_list():
        if is_text_file(fname):
            print('indexing ' + fname)
            tot_lines, headings, keywords, hashtags = scan_file(fname)
            all_headings.extend(headings)
            tot_lines_all_files += tot_lines
            keywords_all_files.extend(keywords)
            hashtags_all_files.extend(hashtags)
    #print('headers = ', all_headings)        
    print('Total Files = ', len(fl.get_list()))        
    print('Total headings = ', len(all_headings))        
    print('Total Hashtags = ', len(hashtags_all_files))        
    print('Total lines = ', tot_lines_all_files)        
    print('Total keywords = ', keywords_all_files)

    print('Hashtags = ', print_hashtags(hashtags_all_files))        

    save_list(keywords_all_files, keyword_file)
    save_list(all_headings, heading_file)


def save_list(lst, fname):
    """
    saves a list to file
    """
    import csv

    with open(fname, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(lst)



def is_text_file(fname):
    print(fname[-3:].upper())
    if fname[-3:].upper() == 'TXT':
        return True
    return False

def print_hashtags(hashtag_list):
    """
    hashtag list has set of [fname, hashtag, line_num]
    """
    res = []
    for ht in hashtag_list:
        res.append(ht[1])
    return res

def scan_file(fname):
    """
    scans a text file and returns lists of 
    headings, words and totals
    """
    tot_lines = 0
    headings = []
    keywords = []
    hashtags = []
    print('indexing ', fname)
    all_text = ''
    with open(fname, 'r') as f:
        for line_num, line in enumerate(f):
            tot_lines += 1
            #print('checking ', line)
            hdr, header_type = extract_header(line)
            if header_type != 'normal':
                headings.append([fname, line_num, header_type, hdr])
                #print('line ' + str(line_num) + ' H' + header_type + ' = ' + hdr)
            all_text += line
    raw_keywords = extract_keywords(all_text)
    for kw in raw_keywords:
        keywords.append([fname, kw[0],kw[1]])
    #print(keywords)

    raw_hashtags = extract_hashtags(all_text)
    for hashtag in raw_hashtags:
        #print('hashtag = ', hashtag)
        hashtags.append([fname, hashtag])



    return tot_lines, headings, keywords, hashtags

def extract_header(txt):
    """
    returns the header text in a line if header, else empty string
    """
    if txt.strip(' ')[0:3] == '###': # sub header
        return txt.strip(' ')[3:].strip('\n'), '2'
    if txt.strip(' ')[0:2] == '##': # header
        return txt.strip(' ')[2:].strip('\n'), '1'
    return '', 'normal'

def extract_keywords(txt):
    """
    returns a list of keywords from a string that are 
    not in the stopwords list
    """
    res = []
    words = txt.split(' ')
    for word in words:
        if word not in stopwords:
            clean_word = word.strip('\n').strip(' ').strip('.').strip(',').strip('"').strip('#')
            if clean_word != '':
                res.append(clean_word)
    """                
    print('txt = ', txt)            
    print('keywords = ', res)
    print('word_freq = ', word_freq(res))  # use this 
    """
    return word_freq(res)

def word_freq(lst):
    wordfreq = [lst.count(wrd) for wrd in lst]
    return list(set(zip(lst,wordfreq))) # wordfreq
    return dict(list(zip(lst,wordfreq)))


def extract_hashtags(txt):
    """
    returns the list of hashtags in text, ignoring
    headers which start with ## or ###
    """
    ht = []
    all_words = txt.replace('\n', ' ').split(' ')
    for wrd in all_words:
        if '#' in wrd:
            #print('word = ', wrd)
            if len(wrd) > 2:
                if wrd[0:1] == '#' and wrd[0:2] != '##':
                    ht.append(wrd[1:])
                    #print(ht)

    return ht



def load_file(fname):
	"""
	read a CSV file to list without worrying about odd characters
	"""
	import csv
	rows_to_load = []
	with open(fname, 'r', encoding='cp1252', errors='ignore') as csvfile:
		csvreader = csv.reader(csvfile, delimiter = ',' )
		reader = csv.reader(csvfile)
		rows_to_load = list(reader)
	return rows_to_load

def search(search_term):
    """
    high level search function called from main route.
    Output should be:
    tbl,res, dte_created, dte_updated, id
    """

    notes_list = search_keywords_in_notes(search_term)
    files_found = search_all_filenames(search_term)

    return notes_list, files_found

def search_keywords_in_notes(search_term):
    res = []
    keywords = load_file(keyword_file)
    #print('keywords = ', keywords[0:2])
    for row in keywords:
        if search_term in row[1]:
            #res.append([col[0], col[1], '', '', ''])
            res.append(row[0])
            
    return list(set(res)) 

def search_all_filenames(search_term):
    """
    searches the files indexed and returns a list of 
    files that contain the search term
    """
    all_indexes = get_list_index_files()
    all_results = []
    for index in all_indexes:
        #print('INDEX FILE = ', index)
        if index[0:1] != '#':
            file_index = read_csv_to_list(index)
            #print('reading index file : ' + index.strip('\n'))
            search_results = search_filenames(file_index, search_term)
            if len(search_results) > 0:
                all_results.extend(search_results)

    print('FINAL SEARCH RESULTS FOR FILES =  ' + str(len(all_results)) + ' files named like ' + search_term)
    #print(all_results[0:3])


    return all_results[0:1000]


def read_csv_to_list(filename):
    """
    reads a CSV file to a list
    """
    import csv

    rows_to_load = []
    with open(filename, 'r',  encoding="utf8", errors='replace') as csvfile:
        reader = csv.reader(csvfile)
        try:
            rows_to_load = list(reader)
        except Exception as ex:
            print('ERROR = problem loading ' + filename)
            print(str(ex))
    return rows_to_load


def search_filenames(lst, txt):
    """
    returns a list of files that contain txt in the name
    """
    res = []
    word_list_to_find = txt.upper().split(' ')
    for line in lst:
        if line[0:1] == '#':
            break
        # make a single uppercase string of all unique content from filelist
        file_details = '|'.join(line).upper()
        if do_all_words_appear_in_text(word_list_to_find, file_details):
            res.append(line)



    # note that this gets called for EACH filelist
    if len(res) > 0:
        print('Found ' + str(len(res)) + ' files named like ' + txt)
    #print(res[0:2])

    return res

def do_all_words_appear_in_text(word_list, txt):
    """
    return true iff all words in word_list are in the string txt
    """
    found = False 
    missing_one = False
    for word in word_list:
        if word in txt:
           found = True
        else:
           missing_one = True  
    if found == True and missing_one == False:
        return True
    else:
        return False
    
def ensure_dir(d):
	try:
		os.makedirs(d, exist_ok=True)
	except Exception as ex:
		pass


def delete_file(f, ignore_errors=False):
	"""
	delete a single file
	"""
	try:
		os.remove(f)
	except Exception as ex:
		if ignore_errors:
			return
		print('ERROR deleting file ' + str(ex))

def delete_files_in_folder(fldr, filespec):
	"""
	delete all files in folder 'fldr'
	"""
	fl = glob.glob(fldr + os.sep + filespec)
	for f in fl:
		delete_file(f, True)
 
def copy_file(src, dest):
	"""
	copy single file
	"""
	try:
		shutil.copy2(src , dest)
	except Exception as ex:
		print('ERROR copying file' + str(ex))
	
def copy_files_to_folder(src, dest, xtn='*.txt'):
	"""
	copies all the files from src to dest folder
	""" 
	
	try:
		all_files = glob.glob(os.path.join(src,xtn))
		for f in all_files:
			copy_file(f, dest)
	except Exception as ex:
		print('ERROR copy_files_to_folder - ' + str(ex))

		
	

def get_list_index_files():

    res_fl = mod_fl.FileList([mod_cfg.index_folder], ['raw_filelist*.csv'], [], 'index_list.txt')
    print('res_fl.get_list() = ', res_fl.get_list())
    return res_fl.get_list()

def get_list_and_names_index_files():
    res = []
    raw_list = get_list_index_files()
    for fname in raw_list:
        # remove the index_folder from start and .csv from end
        
        display_name = mod_cfg.get_path_from_index_filename(fname)
        res.append([fname, display_name])
        print('fname : ', fname, ' display= ', display_name)

    return res

if __name__ == '__main__':
    build_indexes()

