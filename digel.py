import hashlib
import re
import requests , urllib.parse
from collections import defaultdict
from datetime import datetime

import pandas as pd
import numpy as np

import sparql_dataframe
from rdflib import Graph, Literal, RDF, URIRef, ConjunctiveGraph, Namespace
from rdflib.namespace import XSD, OWL, RDF , RDFS, DCTERMS
from SPARQLWrapper import SPARQLWrapper, JSON
from google.colab import files

base = 'https://w3id.org/digestgel/'
vocab = 'https://w3id.org/digestgel/vocab/'
schema = "http://schema.org/"


BASE = Namespace(base)
VOCAB = Namespace(vocab)
SCHEMA = Namespace(schema)
BIRO = Namespace("http://purl.org/spar/biro/") #isReferencedBy
FABIO = Namespace("http://purl.org/spar/fabio/")
FRBR = Namespace("http://purl.org/vocab/frbr/core#")
PRISM = Namespace("http://prismstandard.org/namespaces/basic/2.0/")
PROV = Namespace("http://www.w3.org/ns/prov#")

# controlled vocabularies
vocab_graph = URIRef(BASE+'vocabularies/')

ENDPOINT = "https://projects.dharc.unibo.it/digestgel/sparql"
Q_PEOPLE = """
  SELECT DISTINCT ?authorURI ?author
  WHERE {
	VALUES ?p { <https://w3id.org/digestgel/firstAuthor> <https://w3id.org/digestgel/secondAuthor>
	<https://w3id.org/digestgel/thirdAuthor> <https://w3id.org/digestgel/fourthAuthor>
	<https://w3id.org/digestgel/fifthAuthor>  <https://w3id.org/digestgel/sixthAuthor>
	<https://w3id.org/digestgel/seventhAuthor> <https://w3id.org/digestgel/eighthAuthor>
	<https://w3id.org/digestgel/ninthAuthor> <https://w3id.org/digestgel/tenthAuthor>
	<https://w3id.org/digestgel/firstEditor> <https://w3id.org/digestgel/secondEditor> <https://w3id.org/digestgel/thirdEditor> <https://w3id.org/digestgel/fourthEditor> <https://w3id.org/digestgel/fifthEditor>  <https://w3id.org/digestgel/sixthEditor> <https://w3id.org/digestgel/seventhEditor> <https://w3id.org/digestgel/eighthEditor> <https://w3id.org/digestgel/ninthEditor> <https://w3id.org/digestgel/tenthEditor> }
	?s ?p ?authorURI . ?authorURI rdfs:label ?author
  }
  """

Q_JOURNALS = """
  SELECT DISTINCT ?journalURI ?journal WHERE {
	?journalURI ^<http://purl.org/vocab/frbr/core#partOf> ?article .
	?article a <http://purl.org/spar/fabio/JournalArticle> .
	?journalURI rdfs:label ?journal .
  }
  """

Q_PUBLISHERS = """
  SELECT DISTINCT ?publisherURI ?publisher WHERE {
	?any <http://purl.org/dc/terms/publisher> ?publisherURI .
	?publisherURI rdfs:label ?publisher .
  }
"""

Q_BOOKS = """
  SELECT DISTINCT ?bookURI ?book WHERE {
	?chapter a <http://purl.org/spar/fabio/BookChapter> ;
		<http://purl.org/vocab/frbr/core#partOf> ?bookURI .
	?bookURI rdfs:label ?book .
  }
"""

# vocabularies

COLUMNS = [ "reference (apa)", "publication type",
		   "title",
		   "author_1", "author_2", "author_3", "author_4", "author_5", "author_6", "author_7",
		   "author_8", "author_9", "author_10", "journal", "volume", "issue", "pages", "year",
		   "main_theme", "secondary_theme", "lang", "link", "doi", "booktitle", "publisher",
		   "editor_1", "editor_2", "editor_3", "editor_4", "editor_5", "editor_6", "editor_7",
		   "editor_8", "editor_9", "editor_10"]

# "Reports"
PUBLICATION_TYPES = ['Article',
 'Journal Issue',
 'Report',
 'Book chapter',
 'Book',
 'Doctoral Thesis', 'Doctoral thesis', 'Grey Literature']

LANGUAGES = ["Polish", "Spanish", "Portuguese", "Italian", "Dutch", "German", "French", "English","Finnish","Slovak"]

LANGUAGES_MAPPING = {"https://w3id.org/digestgel/vocabularies/polish": "Polish",
"https://w3id.org/digestgel/vocabularies/spanish": "Spanish",
"https://w3id.org/digestgel/vocabularies/portuguese": "Portuguese",
"https://w3id.org/digestgel/vocabularies/italian": "Italian",
"https://w3id.org/digestgel/vocabularies/dutch": "Dutch",
"https://w3id.org/digestgel/vocabularies/german": "German",
"https://w3id.org/digestgel/vocabularies/french": "French",
"https://w3id.org/digestgel/vocabularies/english": "English",
"https://w3id.org/digestgel/vocabularies/finnish": "Finnish",
"https://w3id.org/digestgel/vocabularies/slovak": "Slovak"}

PRIMARY_SUBJECTS = ["community work",
					"conceptual publications",
					"educational partnerships",
					"formal education",
					"higher education research",
					"informal education including youth work",
					"international volunteering",
					"media",
					"non-formal education",
					"policy related research",
					"study visits",
					"teacher education",
					"theoretical & conceptual publications",
					"training of trainers",
					"teaching material"]

# missing  "theoretical & conceptual publications"
PRIMARY_MAPPING = {
	"https://w3id.org/digestgel/vocabularies/community-work": "community work",
	"https://w3id.org/digestgel/vocabularies/conceptual-publications": "conceptual publications",
	"https://w3id.org/digestgel/vocabularies/educational-partnerships": "educational partnerships",
	"https://w3id.org/digestgel/vocabularies/formal-education": "formal education",
	"https://w3id.org/digestgel/vocabularies/higher-education-research": "higher education research",
	"https://w3id.org/digestgel/vocabularies/informal-education-including-youth-work": "informal education including youth work",
	"https://w3id.org/digestgel/vocabularies/international-volunteering": "international volunteering",
	"https://w3id.org/digestgel/vocabularies/media": "media",
	"https://w3id.org/digestgel/vocabularies/non-formal-education": "non-formal education",
	"https://w3id.org/digestgel/vocabularies/policy-related-research": "policy related research",
	"https://w3id.org/digestgel/vocabularies/study-visits": "study visits",
	"https://w3id.org/digestgel/vocabularies/teacher-education": "teacher education",
	"https://w3id.org/digestgel/vocabularies/theoretical": "theoretical",
	"https://w3id.org/digestgel/vocabularies/training-of-trainers": "training of trainers",
	"https://w3id.org/digestgel/vocabularies/teaching-material": "teaching material"
}

SECONDARY_SUBJECTS = ["community work",
					"conceptual publications",
					"educational partnerships",
					"formal education",
					"higher education research",
					"informal education including youth work",
					"international volunteering",
					"media",
					"non-formal education",
					"policy related research",
					"study visits",
					"teacher education",
					"theoretical",
					"theoretical & conceptual publications",
					"training of trainers"]

# missing  "theoretical & conceptual publications"
SECONDARY_MAPPING = {
	"https://w3id.org/digestgel/vocabularies/community-work": "community work",
	"https://w3id.org/digestgel/vocabularies/conceptual-publications": "conceptual publications",
	"https://w3id.org/digestgel/vocabularies/educational-partnerships": "educational partnerships",
	"https://w3id.org/digestgel/vocabularies/formal-education": "formal education",
	"https://w3id.org/digestgel/vocabularies/higher-education-research": "higher education research",
	"https://w3id.org/digestgel/vocabularies/informal-education-including-youth-work": "informal education including youth work",
	"https://w3id.org/digestgel/vocabularies/international-volunteering": "international volunteering",
	"https://w3id.org/digestgel/vocabularies/media": "media",
	"https://w3id.org/digestgel/vocabularies/non-formal-education": "non-formal education",
	"https://w3id.org/digestgel/vocabularies/policy-related-research": "policy related research",
	"https://w3id.org/digestgel/vocabularies/study-visits": "study visits",
	"https://w3id.org/digestgel/vocabularies/teacher-education": "teacher education",
	"https://w3id.org/digestgel/vocabularies/theoretical": "theoretical",
	"https://w3id.org/digestgel/vocabularies/training-of-trainers": "training of trainers"
}


def check_duplicates(df):
    "Controlla se nella tabella ci sono dei record già online e li rimuove temporaneamente"
    ENDPOINT = "https://projects.dharc.unibo.it/digestgel/sparql"
    sparql = SPARQLWrapper(ENDPOINT)
    sparql.setReturnFormat(JSON)
    c = 0
    for index, row in df.iterrows():
        first_author = str(row["author_1"]).strip().replace("\n"," ")
        title = str(row["title"]).strip().replace("\"",'').replace("\n"," ")
        year = str(row["year"]).strip().replace('(','').replace(')','')
        if year:
            year = str(int(float(year)))

        q = """
        SELECT ?entity
        WHERE {
            ?person rdfs:label \""""+first_author+"""\" .
            ?entity <https://w3id.org/digestgel/firstAuthor> ?person ;
                rdfs:label \""""+title+"""\"; <http://prismstandard.org/namespaces/basic/2.0/publicationDate><https://w3id.org/digestgel/vocabularies/"""+year+"""> .}
        """
        sparql.setQuery(q)
        res = sparql.queryAndConvert()
        if len(res["results"]["bindings"]) > 0:
          c +=1
          print(c,"duplicate")
          print("riga",index, "+2, title:", df.loc[[index]]['title'])
          df = df.drop(index)
    return df


# auxiliary functions
def check_columns(user_columns, stable_columns, lowercase):
	"Controlla se i nomi delle colonne sono conformi a quelli concordati"
	errors = []
	for v in user_columns:
		v = v.lower() if lowercase else v
		if v not in stable_columns:
			errors.append("1")
			raise TypeError("ERRORE - Il nome della colonna "+v+" non è corretto. Sostituisci e ricarica il file")
	if len(errors) == 0:
		print("OK -- i nomi delle colonne sono corretti")

def check_vocabulary(user_vocab, stable_vocab, column_name, lowercase=None,removechars=None):
	"Controlla se i vocabolari nella tabella sono conformi ai vocabolari concordati"
	errors = []
	for v in user_vocab:
		v = v.lower() if lowercase else v
		v = v.replace('-',' ') if removechars else v
	if v not in stable_vocab:
		errors.append("1")
		raise TypeError("ERRORE - Il valore "+v+" nella colonna "+column_name+" non è corretto. Sostituisci e ricarica il file")
	if len(errors) == 0:
		print("OK -- il dizionario nella colonna "+column_name+" è corretto")

def check_omonyms(cols):
    "Prende valori dalle colonne e ritorna una lista di valori unici per review"
    unique_values = set()
    cols = [x.dropna().unique().tolist() for x in cols]
    for col in cols:
        for coll in col:
            unique_values.add(coll.strip())
    unique_values = sorted(unique_values)
    for v in unique_values:
        print(v)
    return unique_values

def get_entities(what):
    "interroga digest online e ritorna una tabella con nomi e URL delle persone"
    q = Q_PEOPLE if what == 'people' else Q_JOURNALS if what == 'journals' else Q_PUBLISHERS if what == 'publishers' else Q_BOOKS if what == 'books' else Q_PEOPLE
    sparql = SPARQLWrapper(ENDPOINT)
    sparql.setReturnFormat(JSON)
    sparql.setQuery(q)
    result = sparql.queryAndConvert()
    df = pd.DataFrame(result['results']['bindings'])
    df.applymap(lambda x: x['value'])
    #df = sparql_dataframe.get(ENDPOINT, q, post=True)
    return df


def match_entities(user_values, labels, uris):
    "compara la lista di nuovi nomi con i nomi delle entità presenti nel digest online"
    labels = labels.tolist()
    uris = uris.tolist()
    matches = defaultdict(list)
    for user_val in user_values:
        # perfect match
        if user_val in labels:
            pos = labels.index(user_val)
            uri = uris[pos]
            matches[user_val].append(uri)
            print("MATCH -- "+ user_val + " : https://projects.dharc.unibo.it/digestgel/term-"+ uri.rsplit('/',1)[1])
        else:
            print("NEW -- "+user_val )
    return matches

def ts():
    "timestamp per uri"
    now = datetime.now()
    timestamp = datetime.timestamp(now)
    return str(timestamp).replace('.','-')

def label_to_vocab_uri(base,label):
    "ritorna un uri per i termini dei vocabolari controllati"
    if "theoretical & conceptual publications" in label.lower():
        res = URIRef(base+'vocabularies/theoretical')
    else:
        res = URIRef(base+'vocabularies/'+label.lower().replace(' ', '-'))
    return res

# create a graph for each row
def create_graphs(articles_df,
	authors_uri={}, journals_uri={}, publishers_uri={}, books_uri={},
	api_key="",
	match_people={}, match_journals={}, match_publishers={}, match_books={}):

    # create ids for every resource (for interlinking)
    articles_df = articles_df.applymap(str)
    ids = {}
    for index, row in articles_df.iterrows():
        ids[index] = ts()
    for index, row in articles_df.iterrows():
        g = ConjunctiveGraph()
        g.bind("gce", BASE)
        g.bind("schema", SCHEMA)
        g.bind("biro", BIRO)
        g.bind("fabio", FABIO)
        g.bind("frbr", FRBR)
        g.bind("prism", PRISM)
        g.bind("prov", PROV)

        loc_id = ids[index]
        res = URIRef(base+loc_id)
        g_name = res+'/'

        if row["title"] != 'nan' and len(row["title"]) > 1:
            ###########
            # URI: type
            if 'article' in row["publication type"].lower():
                g.add(( res , RDF.type , FABIO.JournalArticle , g_name ))
            if 'thesis' in row["publication type"].lower():
                g.add(( res , RDF.type , FABIO.DoctoralThesis , g_name ))
            if 'book chapter' in row["publication type"].lower():
                g.add(( res , RDF.type , FABIO.BookChapter , g_name ))
            if 'book' in row["publication type"].lower() and 'chapter' not in row["publication type"].lower():
                g.add(( res , RDF.type , FABIO.Book , g_name ))
            if 'issue' in row["publication type"].lower():
                g.add(( res , RDF.type , FABIO.JournalIssue , g_name ))
            if 'report' in row["publication type"].lower():
                g.add(( res , RDF.type , FABIO.ReportDocument , g_name ))
            if 'grey literature' in row["publication type"].lower():
                g.add(( res , RDF.type , FABIO.Work , g_name ))

            # STR: citation
            rec_title = ''
            add_year = str(int(float(row["year"]))) if (row["year"] != 'nan' and len(row["year"])) > 1 else ''
            # if "author_5" in row and row["author_5"] and row["author_5"] != 'nan' and len(row["author_5"]) > 1:
            #     rec_title += row["author_1"].strip()+" et al. ("+add_year+')' if row["author_1"].strip() != 'nan' \
            #       else "No authors ("+add_year+').'
            # else:
            if "author_1" in row and row["author_1"].strip() != 'nan':
                rec_title += row["author_1"].strip() if row["author_1"].strip() != 'nan' else ''
                rec_title += "; "+row["author_2"].strip() if row["author_2"] != 'nan' else ''
                rec_title += "; "+row["author_3"].strip() if row["author_3"] != 'nan' else ''
                rec_title += "; "+row["author_4"].strip() if row["author_4"] != 'nan' else ''
                rec_title += "; "+row["author_5"].strip() if row["author_5"] != 'nan' else ''
                rec_title += "; "+row["author_6"].strip() if row["author_6"] != 'nan' else ''
                rec_title += "; "+row["author_7"].strip() if row["author_7"] != 'nan' else ''
                rec_title += "; "+row["author_8"].strip() if row["author_8"] != 'nan' else ''
                rec_title += "; "+row["author_9"].strip() if row["author_9"] != 'nan' else ''
                rec_title += "; "+row["author_10"].strip() if row["author_10"] != 'nan' else ''
                rec_title += " ("+ add_year+').'
            else:
                if 'book' in row["publication type"].lower():
                    rec_title += row["editor_1"].strip() if row["editor_1"].strip() != 'nan' else ''
                    if "editor_2" in row and row["editor_2"].strip() != 'nan':
                        rec_title += "; "+row["editor_2"].strip() if row["editor_2"] != 'nan' else ''
                        rec_title += "; "+row["editor_3"].strip() if row["editor_3"] != 'nan' else ''
                        rec_title += "; "+row["editor_4"].strip() if row["editor_4"] != 'nan' else ''
                        rec_title += "; "+row["editor_5"].strip() if row["editor_5"] != 'nan' else ''
                        rec_title += "; "+row["editor_6"].strip() if row["editor_6"] != 'nan' else ''
                        rec_title += "; "+row["editor_7"].strip() if row["editor_7"] != 'nan' else ''
                        rec_title += "; "+row["editor_8"].strip() if row["editor_8"] != 'nan' else ''
                        rec_title += "; "+row["editor_9"].strip() if row["editor_9"] != 'nan' else ''
                        rec_title += "; "+row["editor_10"].strip() if row["editor_10"] != 'nan' else ''
                        rec_title += ' (eds)'
                    else:
                        rec_title += ' (ed)'
                    rec_title += " ("+ add_year+').'
                else:
                    rec_title += "No author ("+ add_year+').'
            ###########
            # STR: title
            res_title = row["title"].strip().replace("\"",'')
            rec_title += ' '+res_title+'.'
            g.add(( res , DCTERMS.title , Literal(res_title) , g_name ))
            g.add(( res , RDFS.label , Literal(res_title) , g_name ))

            ###########
            # VOCAB: year
            if row["year"] != 'nan' and len(row["year"]) > 1:
                year = row["year"].strip().replace('(','').replace(')','')
                year = str(int(float(year)))
                g.add(( res , PRISM.publicationDate , URIRef(base+'vocabularies/'+year) , g_name ))
                g.add(( URIRef(base+'vocabularies/'+year) , RDFS.label , Literal(year) , g_name ))

            ###########
            # VOCAB: theme
            if row["main_theme"] != 'nan' and len(row["main_theme"]) > 1:
                themes = row["main_theme"].strip('][').split(', ')
                if len(themes) > 0 and len(themes[0]) > 0:
                    for theme in themes:
                        theme = theme.replace('\'','')
                        theme_uri = label_to_vocab_uri(base,theme)
                        theme_label = "theoretical" if "theoretical & conceptual publications" in theme.lower() else theme.lower()
                        g.add(( res , FABIO.hasPrimarySubjectTerm , theme_uri , g_name ))
                        g.add(( theme_uri , RDFS.label , Literal(theme_label) , g_name ))

            ###########
            # VOCAB: secondary theme
            if row["secondary_theme"] != 'nan' and len(row["secondary_theme"]) > 1:
                themes = row["secondary_theme"].strip('][').split(', ')
                if len(themes) > 0 and len(themes[0]) > 0:
                    for theme in themes:
                        theme = theme.replace('\'','')
                        theme_uri = label_to_vocab_uri(base,theme)
                        theme_label = "theoretical" if "theoretical & conceptual publications" in theme.lower() else theme.lower()
                        g.add(( res , FABIO.hasSubjectTerm , theme_uri , g_name ))
                        g.add(( theme_uri , RDFS.label , Literal(theme_label) , g_name ))

            ###########
            # VOCAB: lang
            if row["lang"] != 'nan' and len(row["lang"]) > 1:
                lang = row["lang"].strip()
                lang_uri = label_to_vocab_uri(base,lang)
                g.add(( res , DCTERMS.language , lang_uri , g_name ))
                g.add(( lang_uri , RDFS.label , Literal(lang.lower()) , g_name ))

            ###########
            # STR: Link
            if row["link"] != 'nan' and 'not found' not in row["link"].lower() and len(row["link"]) > 1:
                link = row["link"].strip()
                g.add(( res , FABIO.hasURL , Literal(link) , g_name ))

            ###########
            # STR: DOI
            if row["doi"] != 'nan' and 'not ' not in row["doi"].lower() and len(row["doi"]) > 1:
                doi = row["doi"].strip().lower().replace('https://doi.org/','').replace('http://dx.doi.org/','').replace('doi:','').replace('doi','').strip()
                g.add(( res , PRISM.doi , Literal(doi.lower()) , g_name ))

            ###########
            # URI: authors
            if 'issue' not in row["publication type"].lower():
                # URI: first author
                if row["author_1"] != 'nan' and len(row["author_1"]) > 1:
                    first_author = match_people[row["author_1"]][0] if row["author_1"] in match_people else authors_uri[row["author_1"].strip()]
                    g.add(( res , BASE.firstAuthor , URIRef(first_author) , g_name ))
                    g.add(( URIRef(first_author) , RDFS.label , Literal(row["author_1"].strip()) , g_name ))

                # URI: second author
                if row["author_2"] != 'nan' and len(row["author_2"]) > 1:
                    second_author = match_people[row["author_2"]][0] if row["author_2"] in match_people else authors_uri[row["author_2"].strip()]
                    g.add(( res , BASE.secondAuthor , URIRef(second_author) , g_name ))
                    g.add(( URIRef(second_author) , RDFS.label , Literal(row["author_2"].strip()) , g_name ))

                # URI: third author
                if row["author_3"] != 'nan' and len(row["author_3"]) > 1:
                    third_author = match_people[row["author_3"]][0] if row["author_3"] in match_people else authors_uri[row["author_3"].strip()]
                    g.add(( res , BASE.thirdAuthor , URIRef(third_author) , g_name ))
                    g.add(( URIRef(third_author) , RDFS.label , Literal(row["author_3"].strip()) , g_name ))

                # URI: fourth author
                if row["author_4"] != 'nan' and len(row["author_4"]) > 1:
                    fourth_author = match_people[row["author_4"]][0] if row["author_4"] in match_people else authors_uri[row["author_4"].strip()]
                    g.add(( res , BASE.fourthAuthor , URIRef(fourth_author) , g_name ))
                    g.add(( URIRef(fourth_author) , RDFS.label , Literal(row["author_4"].strip()) , g_name ))

                # URI: fifth author
                if row["author_5"] != 'nan' and len(row["author_5"]) > 1:
                    fifth_author = match_people[row["author_5"]][0] if row["author_5"] in match_people else authors_uri[row["author_5"].strip()]
                    g.add(( res , BASE.fifthAuthor , URIRef(fifth_author) , g_name ))
                    g.add(( URIRef(fifth_author) , RDFS.label , Literal(row["author_5"].strip()) , g_name ))

                # URI: sixth author
                if row["author_6"] != 'nan' and len(row["author_6"]) > 1:
                    sixth_author = match_people[row["author_6"]][0] if row["author_6"] in match_people else authors_uri[row["author_6"].strip()]
                    g.add(( res , BASE.sixthAuthor , URIRef(sixth_author) , g_name ))
                    g.add(( URIRef(sixth_author) , RDFS.label , Literal(row["author_6"].strip()) , g_name ))

                # URI: seventh author
                if row["author_7"] != 'nan' and len(row["author_7"]) > 1:
                    seventh_author = match_people[row["author_7"]][0] if row["author_7"] in match_people else authors_uri[row["author_7"].strip()]
                    g.add(( res , BASE.seventhAuthor , URIRef(seventh_author) , g_name ))
                    g.add(( URIRef(seventh_author) , RDFS.label , Literal(row["author_7"].strip()) , g_name ))

                # URI: eighth author
                if row["author_8"] != 'nan' and len(row["author_8"]) > 1:
                    eighth_author = match_people[row["author_8"]][0] if row["author_8"] in match_people else authors_uri[row["author_8"].strip()]
                    g.add(( res , BASE.eighthAuthor , URIRef(eighth_author) , g_name ))
                    g.add(( URIRef(eighth_author) , RDFS.label , Literal(row["author_8"].strip()) , g_name ))

                # URI: ninth author
                if row["author_9"] != 'nan' and len(row["author_9"]) > 1:
                    ninth_author = match_people[row["author_9"]][0] if row["author_9"] in match_people else authors_uri[row["author_9"].strip()]
                    g.add(( res , BASE.ninthAuthor , URIRef(ninth_author) , g_name ))
                    g.add(( URIRef(ninth_author) , RDFS.label , Literal(row["author_9"].strip()) , g_name ))

                # URI: tenth author
                if row["author_10"] != 'nan' and len(row["author_10"]) > 1:
                    tenth_author = match_people[row["author_10"]][0] if row["author_10"] in match_people else authors_uri[row["author_10"].strip()]
                    g.add(( res , BASE.tenthAuthor , URIRef(tenth_author) , g_name ))
                    g.add(( URIRef(tenth_author) , RDFS.label , Literal(row["author_10"].strip()) , g_name ))

                # URI: et al.
                if row["author_5"] != 'nan' and len(row["author_5"]) > 1:
                    g.add(( res , BASE.otherAuthors , URIRef(base+'et-al') , g_name ))
                    g.add(( URIRef(base+'et-al') , RDFS.label , Literal('et al.') , g_name ))

            ###########
            # STR: volume and issue
            if 'issue' in row["publication type"].lower() or 'article' in row["publication type"].lower():
                # URI: journal
                if row["journal"] != 'nan' and len(row["journal"]) > 1:
                    journal = row["journal"].strip()
                    journal_uri = match_journals[row["journal"]][0] if row["journal"] in match_journals else journals_uri[row["journal"].strip()]
                    #journal_uri = journals_uri[journal.strip()]
                    g.add(( res , FRBR.partOf , URIRef(journal_uri) , g_name ))
                    g.add(( URIRef(journal_uri) , RDFS.label , Literal(journal) , g_name ))
                    rec_title += ' '+journal
                # STR: volume
                if row["volume"] != 'nan' and len(row["volume"]) > 1:
                    vol = row["volume"].strip().replace('(','').replace(')','')
                    g.add(( res , PRISM.volume , Literal(vol) , g_name ))
                    rec_title += ', '+vol
                # STR: issue
                if row["issue"] != 'nan' and len(row["issue"]) > 1:
                    issue = row["issue"].strip().replace('(','').replace(')','')
                    g.add(( res , PRISM.issueIdentifier , Literal(issue) , g_name ))
                    if row["volume"] != 'nan' and len(row["volume"]) > 1:
                        rec_title += '('+issue+')'
                    else:
                        rec_title += ', '+issue

            ###########
            # URI: publisher editors and book title
            if 'issue' not in row["publication type"].lower() and 'article' not in row["publication type"].lower():

                # URI: book editors
                if 'book' in row["publication type"].lower() or ('incollection' in row["publication type"].lower() and row["journal"] == 'nan') or 'misc' in row["publication type"].lower():
                    editors_uri = authors_uri
                    if "editor_1" in row and row["editor_1"] != 'nan':
                        # URI: first editor
                        if "editor_1" in row and row["editor_1"] != 'nan' and len(row["editor_1"]) > 1:
                            first_editor = match_people[row["editor_1"]][0] if row["editor_1"] in match_people else editors_uri[row["editor_1"].strip()]
                            g.add(( res , BASE.firstEditor , URIRef(first_editor) , g_name ))
                            g.add(( URIRef(first_editor) , RDFS.label , Literal(row["editor_1"].strip()) , g_name ))

                        # URI: second editor
                        if "editor_2" in row and row["editor_2"] != 'nan' and len(row["editor_2"]) > 1:
                            second_editor = match_people[row["editor_2"]][0] if row["editor_2"] in match_people else editors_uri[row["editor_2"].strip()]
                            g.add(( res , BASE.secondEditor , URIRef(second_editor) , g_name ))
                            g.add(( URIRef(second_editor) , RDFS.label , Literal(row["editor_2"].strip()) , g_name ))

                        # URI: third editor
                        if "editor_3" in row and row["editor_3"] != 'nan' and len(row["editor_3"]) > 1:
                            third_editor = match_people[row["editor_3"]][0] if row["editor_3"] in match_people else editors_uri[row["editor_3"].strip()]
                            g.add(( res , BASE.thirdEditor , URIRef(third_editor) , g_name ))
                            g.add(( URIRef(third_editor) , RDFS.label , Literal(row["editor_3"].strip()) , g_name ))

                        # URI: fourth editor
                        if "editor_4" in row and row["editor_4"] != 'nan' and len(row["editor_4"]) > 1:
                            fourth_editor = match_people[row["editor_4"]][0] if row["editor_4"] in match_people else editors_uri[row["editor_4"].strip()]
                            g.add(( res , BASE.fourthEditor , URIRef(fourth_editor) , g_name ))
                            g.add(( URIRef(fourth_editor) , RDFS.label , Literal(row["editor_4"].strip()) , g_name ))

                        # URI: fifth editor
                        if "editor_5" in row and row["editor_5"] != 'nan' and len(row["editor_5"]) > 1:
                            fifth_editor = match_people[row["editor_5"]][0] if row["editor_5"] in match_people else editors_uri[row["editor_5"].strip()]
                            g.add(( res , BASE.fifthEditor , URIRef(fifth_editor) , g_name ))
                            g.add(( URIRef(fifth_editor) , RDFS.label , Literal(row["editor_5"].strip()) , g_name ))

                        # URI: sixth editor
                        if "editor_6" in row and row["editor_6"] != 'nan' and len(row["editor_6"]) > 1:
                            sixth_editor = match_people[row["editor_6"]][0] if row["editor_6"] in match_people else editors_uri[row["editor_6"].strip()]
                            g.add(( res , BASE.sixthEditor , URIRef(sixth_editor) , g_name ))
                            g.add(( URIRef(sixth_editor) , RDFS.label , Literal(row["editor_6"].strip()) , g_name ))

                        # URI: seventh editor
                        if "editor_7" in row and row["editor_7"] != 'nan' and len(row["editor_7"]) > 1:
                            seventh_editor = match_people[row["editor_7"]][0] if row["editor_7"] in match_people else editors_uri[row["editor_7"].strip()]
                            g.add(( res , BASE.seventhEditor , URIRef(seventh_editor) , g_name ))
                            g.add(( URIRef(seventh_editor) , RDFS.label , Literal(row["editor_7"].strip()) , g_name ))

                        # URI: eighth editor
                        if "editor_8" in row and row["editor_8"] != 'nan' and len(row["editor_8"]) > 1:
                            eighth_editor = match_people[row["editor_8"]][0] if row["editor_8"] in match_people else editors_uri[row["editor_8"].strip()]
                            g.add(( res , BASE.eighthEditor , URIRef(eighth_editor) , g_name ))
                            g.add(( URIRef(eighth_editor) , RDFS.label , Literal(row["editor_8"].strip()) , g_name ))

                        # URI: ninth editor
                        if "editor_9" in row and row["editor_9"] != 'nan' and len(row["editor_9"]) > 1:
                            ninth_editor = match_people[row["editor_9"]][0] if row["editor_9"] in match_people else editors_uri[row["editor_9"].strip()]
                            g.add(( res , BASE.ninthEditor , URIRef(ninth_editor) , g_name ))
                            g.add(( URIRef(ninth_editor) , RDFS.label , Literal(row["editor_9"].strip()) , g_name ))

                        # URI: tenth editor
                        if "editor_10" in row and row["editor_10"] != 'nan' and len(row["editor_10"]) > 1:
                            tenth_editor = match_people[row["editor_10"]][0] if row["editor_10"] in match_people else editors_uri[row["editor_10"].strip()]
                            g.add(( res , BASE.tenthEditor , URIRef(tenth_editor) , g_name ))
                            g.add(( URIRef(tenth_editor) , RDFS.label , Literal(row["editor_10"].strip()) , g_name ))

                    # URI: et al.
                    # if "editor_5" in row and row["editor_5"] != 'nan' and len(row["editor_5"]) > 1:
                    #     g.add(( res , BASE.otherEditors , URIRef(base+'et-al') , g_name ))
                    #     g.add(( URIRef(base+'et-al') , RDFS.label , Literal('et al.') , g_name ))

                    # if "editor_5" in row and row["editor_5"] != 'nan' and len(row["editor_5"]) > 1:
                    #     rec_title += ' In ' + row["editor_1"].strip()+" et al. (eds.) " if "editor_1" in row and row["editor_1"] != 'nan' \
                    #         else " In"
                    # else:
                    if len(row["author_1"].strip()) < 1:
                        rec_title += ' In ' + row["editor_1"].strip()
                        if "editor_2" in row and row["editor_2"] != 'nan':
                            rec_title += "; "+row["editor_2"].strip()
                            rec_title += "; "+row["editor_3"].strip() if "editor_3" in row and row["editor_3"] != 'nan' else ''
                            rec_title += "; "+row["editor_4"].strip() if "editor_4" in row and row["editor_4"] != 'nan' else ''
                            rec_title += "; "+row["editor_5"].strip() if "editor_5" in row and row["editor_5"] != 'nan' else ''
                            rec_title += "; "+row["editor_6"].strip() if "editor_6" in row and row["editor_6"] != 'nan' else ''
                            rec_title += "; "+row["editor_7"].strip() if "editor_7" in row and row["editor_7"] != 'nan' else ''
                            rec_title += "; "+row["editor_8"].strip() if "editor_8" in row and row["editor_8"] != 'nan' else ''
                            rec_title += "; "+row["editor_9"].strip() if "editor_9" in row and row["editor_9"] != 'nan' else ''
                            rec_title += "; "+row["editor_10"].strip() if "editor_10" in row and row["editor_10"] != 'nan' else ''
                            rec_title += " (eds), "
                        else:
                            rec_title += " (ed), "
                if 'book chapter' in row["publication type"].lower() or ('incollection' in row["publication type"].lower() and row["journal"] == 'nan') or 'misc' in row["publication type"].lower():
                    # URI: book title
                    if "booktitle" in row:
                        if row["booktitle"] != 'nan' and len(row["booktitle"]) > 1:
                            book_uri = match_books[row["booktitle"]][0] if row["booktitle"] in match_books else books_uri[row["booktitle"].strip()]
                            g.add(( res , FRBR.partOf , URIRef(book_uri) , g_name ))
                            g.add(( URIRef(book_uri) , RDFS.label , Literal(row["booktitle"].strip()) , g_name ))
                            rec_title += row["booktitle"].strip()+'.'
                # if 'thesis' in row["publication type"].lower() or 'doctoral theses' in row["publication type"].lower() \
                #     or 'book chapter' in row["publication type"].lower() or ('incollection' in row["publication type"].lower() and row["journal"] == 'nan') or 'misc' in row["publication type"].lower() \
                #     or 'report' in row["publication type"].lower():

                # URI: publisher
                if "publisher" in row:
                    if row["publisher"] != 'nan' and len(row["publisher"]) > 1:
                        publisher = row["publisher"].strip()
                        publisher_uri = match_publishers[row["publisher"]][0] if row["publisher"] in match_publishers \
                            else publishers_uri[row["publisher"].strip()] if row["publisher"].strip() in publishers_uri \
                            else None
                        if publisher_uri:
                            g.add(( res , DCTERMS.publisher , URIRef(publisher_uri) , g_name ))
                            g.add(( URIRef(publisher_uri) , RDFS.label , Literal(publisher) , g_name ))
                            rec_title += ' '+publisher

            ###########
            # STR: pages
            if 'pages' in row and row["pages"] != 'nan' and len(row["pages"]) > 1:
                pages = row["pages"].strip().replace('(','').replace(')','')
                g.add(( res , PRISM.pageRange , Literal(pages) , g_name ))
                rec_title += ', '+pages

            ###########
            # STR: citation
            g.add(( res , BIRO.isReferencedBy , Literal(rec_title.strip()) , g_name ))

            # graph name
            g.add(( g_name , RDFS.label , Literal(rec_title.strip()) , g_name ))

            # URI: creator
            res_creator = 'marilena.daquino2@unibo.it'
            res_creator_uri = URIRef(BASE+res_creator.replace('.','-dot-').replace('@', '-at-'))
            g.add(( g_name, PROV.wasAttributedTo , res_creator_uri, g_name ))
            g.add(( res_creator_uri, RDFS.label , Literal(res_creator), g_name ))

            # STR: date
            date = Literal(datetime.now(),datatype=XSD.dateTime)
            g.add(( g_name, PROV.generatedAtTime , date, g_name ))

            # STR: publication stage
            g.add(( g_name, URIRef("http://dbpedia.org/ontology/currentStatus") , Literal("published"), g_name ))

            # serialize ttl
            graph_data = g.serialize(format='ttl' , encoding='utf-8' )
            import_to_digest(graph_data, loc_id,api_key)
    g.serialize(format='trig',destination='data.trig',  encoding='utf-8' )

    # download
    files.download('data.trig')

def import_to_digest(graph_data, graph_name,api_key):
    "importa i dati online"
    api_url = 'https://projects.dharc.unibo.it/digestgel/import'
    headers = { 'Content-type': 'application/x-turtle',}
    params = {'graph_name': graph_name, 'api_key': api_key, 'data': graph_data}
    print("sending request for "+graph_name)
    print("API URL:", api_url)
    response = requests.post(api_url, headers=headers, params=params)
    print("request sent "+graph_name, graph_data)
    print(response.status_code)

def prepare_uris(user_people, user_journals, user_publishers=None, user_books=None):
    "prepara uri di default per le nuove entità da creare"
    # MISSING editors
    authors_uri = { a: base+ts() for a in user_people } if user_people else {}
    journals_uri = { a.strip(): base+ts() for a in user_journals } if user_journals else {}

    publishers_uri = { a.strip(): base+ts() for a in user_publishers } if user_publishers else {}
    books_uri = { str(a).strip(): base+ts() for a in user_books } if user_books else {}
    return authors_uri, journals_uri, publishers_uri, books_uri
