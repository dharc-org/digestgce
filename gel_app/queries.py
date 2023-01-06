# -*- coding: utf-8 -*-
import conf , os , operator , pprint , ssl , rdflib , json , re
from SPARQLWrapper import SPARQLWrapper, JSON , CSV
from collections import defaultdict
from rdflib import URIRef , XSD, Namespace , Literal
from rdflib.namespace import OWL, DC , DCTERMS, RDF , RDFS
from rdflib.plugins.sparql import prepareQuery
from pymantic import sparql
import utils as u

u.reload_config()

ssl._create_default_https_context = ssl._create_unverified_context
server = sparql.SPARQLServer(conf.myEndpoint)
dir_path = os.path.dirname(os.path.realpath(__file__))

def hello_blazegraph(q):
	sparql = SPARQLWrapper(conf.myEndpoint)
	sparql.setQuery(q)
	sparql.setReturnFormat(JSON)
	results = sparql.query().convert()
	return results


# LIST OF RECORDS IN THE BACKEND


def getRecords(res_class=None):
	""" get all the records created by users to list them in the backend welcome page """
	class_restriction = "" if res_class is None else "?s a <"+res_class+"> ."

	queryRecords = """
		PREFIX prov: <http://www.w3.org/ns/prov#>
		PREFIX base: <"""+conf.base+""">
		PREFIX dbpedia: <http://dbpedia.org/ontology/>
		SELECT DISTINCT ?g ?title ?userLabel ?modifierLabel ?date ?stage ?class
		WHERE
		{ GRAPH ?g {
			?s ?p ?o . ?s a ?class .
			""" +class_restriction+ """
			OPTIONAL { ?g rdfs:label ?title; prov:wasAttributedTo ?user; prov:generatedAtTime ?date ; dbpedia:currentStatus ?stage. ?user rdfs:label ?userLabel .
				OPTIONAL {?g prov:wasInfluencedBy ?modifier. ?modifier rdfs:label ?modifierLabel .} }
			OPTIONAL {?g rdfs:label ?title; prov:generatedAtTime ?date ; dbpedia:currentStatus ?stage . }

			BIND(COALESCE(?date, '-') AS ?date ).
			BIND(COALESCE(?stage, '-') AS ?stage ).
			BIND(COALESCE(?userLabel, '-') AS ?userLabel ).
			BIND(COALESCE(?modifierLabel, '-') AS ?modifierLabel ).
			BIND(COALESCE(?title, 'none', '-') AS ?title ).
			filter not exists {
			  ?g prov:generatedAtTime ?date2
			  filter (?date2 > ?date)
			}

		  }
		  FILTER( str(?g) != '"""+conf.base+"""vocabularies/' )
		}
		"""

	records = set()
	sparql = SPARQLWrapper(conf.myEndpoint)
	sparql.setQuery(queryRecords)
	sparql.setReturnFormat(JSON)
	results = sparql.query().convert()

	for result in results["results"]["bindings"]:
		records.add( (result["g"]["value"], result["title"]["value"], result["userLabel"]["value"], result["modifierLabel"]["value"], result["date"]["value"], result["stage"]["value"], result["class"]["value"] ))
	return records


def getRecordsPagination(page, filterRecords=''):
	""" get all the records created by users to list them in the backend welcome page """
	newpage = int(page)-1
	offset = str(0) if int(page) == 1 \
		else str(( int(conf.pagination) *newpage))
	queryRecordsPagination = """
		PREFIX prov: <http://www.w3.org/ns/prov#>
		PREFIX base: <"""+conf.base+""">
		PREFIX dbpedia: <http://dbpedia.org/ontology/>
		SELECT DISTINCT ?g ?title ?userLabel ?modifierLabel ?date ?stage ?class
		WHERE
		{ GRAPH ?g {
			?s ?p ?o ; a ?class .
			OPTIONAL { ?g rdfs:label ?title; prov:wasAttributedTo ?user; prov:generatedAtTime ?date ; dbpedia:currentStatus ?stage. ?user rdfs:label ?userLabel .
				OPTIONAL {?g prov:wasInfluencedBy ?modifier. ?modifier rdfs:label ?modifierLabel .} }
			OPTIONAL {?g rdfs:label ?title; prov:generatedAtTime ?date ; dbpedia:currentStatus ?stage . }

			BIND(COALESCE(?date, '-') AS ?date ).
			BIND(COALESCE(?stage, '-') AS ?stage ).
			BIND(COALESCE(?userLabel, '-') AS ?userLabel ).
			BIND(COALESCE(?modifierLabel, '-') AS ?modifierLabel ).
			BIND(COALESCE(?title, 'none', '-') AS ?title ).
			filter not exists {
			  ?g prov:generatedAtTime ?date2
			  filter (?date2 > ?date)
			}

		  }
		  """+filterRecords+"""
		  FILTER( str(?g) != '"""+conf.base+"""vocabularies/' )

		}
		ORDER BY DESC(?date)
		LIMIT """+conf.pagination+"""
		OFFSET  """+offset+"""
		"""

	records = list()
	sparql = SPARQLWrapper(conf.myEndpoint)
	sparql.setQuery(queryRecordsPagination)
	sparql.setReturnFormat(JSON)
	results = sparql.query().convert()
	for result in results["results"]["bindings"]:
		records.append( (result["g"]["value"], result["title"]["value"], result["userLabel"]["value"], result["modifierLabel"]["value"], result["date"]["value"], result["stage"]["value"] , result["class"]["value"] ))

	return records


def getCountings(filterRecords=''):
	countRecords = """
		PREFIX prov: <http://www.w3.org/ns/prov#>
		PREFIX base: <"""+conf.base+""">
		PREFIX dbpedia: <http://dbpedia.org/ontology/>
		SELECT (COUNT(DISTINCT ?g) AS ?count) ?stage
		WHERE
		{ GRAPH ?g { ?s ?p ?o .
			}
			?g dbpedia:currentStatus ?stage .
			"""+filterRecords+"""
			FILTER( str(?g) != '"""+conf.base+"""vocabularies/' ) .

		}
		GROUP BY ?stage
		"""
	sparql = SPARQLWrapper(conf.myEndpoint)
	sparql.setQuery(countRecords)
	sparql.setReturnFormat(JSON)
	results = sparql.query().convert()
	all, notreviewed, underreview, published = 0,0,0,0
	for result in results["results"]["bindings"]:
		notreviewed = int(result["count"]["value"]) if result["stage"]["value"] == "not modified" else notreviewed
		underreview = int(result["count"]["value"]) if result["stage"]["value"] == "modified" else underreview
		published = int(result["count"]["value"]) if result["stage"]["value"] == "published" else published
		all = notreviewed + underreview + published
	return all, notreviewed, underreview, published


def countAll(res_class=None, exclude_unpublished=False):
	class_restriction = "" if res_class is None else "?s a <"+res_class+"> ."
	exclude = "" if exclude_unpublished is False \
		else "?g dbpedia:currentStatus ?anyValue . FILTER (isLiteral(?anyValue) && lcase(str(?anyValue))= 'published') ."
	countall = """
		PREFIX prov: <http://www.w3.org/ns/prov#>
		PREFIX base: <"""+conf.base+""">
		PREFIX dbpedia: <http://dbpedia.org/ontology/>
		SELECT (COUNT(DISTINCT ?g) AS ?count)
		WHERE
		{ GRAPH ?g { ?s ?p ?o .
			"""+class_restriction+"""
		}
		"""+exclude+"""
			FILTER( str(?g) != '"""+conf.base+"""vocabularies/' ) .
		}
		"""
	sparql = SPARQLWrapper(conf.myEndpoint)
	sparql.setQuery(countall)
	sparql.setReturnFormat(JSON)
	results = sparql.query().convert()
	alll = results["results"]["bindings"][0]['count']['value']
	return alll


def getRecordCreator(graph_name):
	""" get the label of the creator of a record """
	creatorIRI, creatorLabel = None, None
	queryRecordCreator = """
		PREFIX prov: <http://www.w3.org/ns/prov#>
		PREFIX dbpedia: <http://dbpedia.org/ontology/>
		SELECT DISTINCT ?creatorIRI ?creatorLabel
		WHERE { <"""+graph_name+"""> prov:wasAttributedTo ?creatorIRI .
		?creatorIRI rdfs:label ?creatorLabel . }"""

	sparql = SPARQLWrapper(conf.myEndpoint)
	sparql.setQuery(queryRecordCreator)
	sparql.setReturnFormat(JSON)
	results = sparql.query().convert()
	for result in results["results"]["bindings"]:
		creatorIRI, creatorLabel = result["creatorIRI"]["value"],result["creatorLabel"]["value"]
	return creatorIRI, creatorLabel


# TRIPLE PATTERNS FROM THE FORM



# REBUILD GRAPH TO MODIFY/REVIEW RECORD
def getClass(res_uri):
	""" get the class of a resource given the URI"""

	q = """ SELECT DISTINCT ?class WHERE {<"""+res_uri+"""> a ?class}"""
	res_class = []
	results = hello_blazegraph(q)
	for result in results["results"]["bindings"]:
		res_class.append(result["class"]["value"])
	return res_class[0] if len(res_class) > 0 else ""

def getData(graph,res_template,addValues=''):
	""" get a named graph and rebuild results for modifying the record"""
	with open(res_template) as config_form:
		fields = json.load(config_form)

	res_class = getClass(graph[:-1])

	patterns = [ 'OPTIONAL {?subject <'+field['property']+'> ?'+field['id']+'.}. '  if field['value'] == 'Literal' else 'OPTIONAL {?subject <'+field['property']+'> ?'+field['id']+'. ?'+field['id']+' rdfs:label ?'+field['id']+'_label .} .' for field in fields]
	patterns_string = ''.join(patterns)
	#print("\npatterns_string\n",patterns_string)
	queryNGraph = '''
			PREFIX base: <'''+conf.base+'''>
			PREFIX schema: <https://schema.org/>
			PREFIX dbpedia: <http://dbpedia.org/ontology/>
			SELECT DISTINCT *
			WHERE { '''+addValues+'''
				<'''+graph+'''> rdfs:label ?graph_title ;
									dbpedia:currentStatus ?stage
					GRAPH <'''+graph+'''>
					{	?subject a <'''+res_class+'''> .
						'''+patterns_string+'''
						OPTIONAL {?subject schema:keywords ?keywords . ?keywords rdfs:label ?keywords_label . } }
			}
			'''
	sparql = SPARQLWrapper(conf.myEndpoint)
	sparql.setQuery(queryNGraph)
	sparql.setReturnFormat(JSON)
	results = sparql.query().convert()

	def compare_sublists(l, lol):
		for sublist in lol:
			temp = [i for i in sublist if i in l]
			if sorted(temp) == sorted(l):
				return True
		return False

	data = defaultdict(list)
	for result in results["results"]["bindings"]:
		result.pop('subject',None)
		result.pop('graph_title',None)
		for k,v in result.items():
			if '_label' not in k and v['type'] == 'literal': # string values
				if v['value'] not in data[k]: # unique values
					data[k].append(v['value'])
			elif v['type'] == 'uri': # uri values

				if k+'_label' in result:
					# conf.base in v['value'] or
					if  'wikidata' in v['value'] or 'geonames' in v['value']:
						uri = v['value'].rsplit('/', 1)[-1]
					else:
						uri = v['value']
					label = [value['value'] for key,value in result.items() if key == k+'_label'][0]
				else:
					uri = v['value']
					label = uri
					#label = [value['value'] if key == k+'_label' else v['value'] for key,value in result.items()][0]

				if compare_sublists([uri,label], data[k]) == False:
					data[k].append([uri,label])
	#print("############ data",res_template,data)
	return data


# BROWSE ENTITY (VOCAB TERMS; NEW ENTITIES MENTIONED IN RECORDS)


def describeTerm(name):
	""" ask if the resource exists, then describe it."""
	ask = """ASK { ?s ?p <""" +conf.base+name+ """> .}"""
	results = hello_blazegraph(ask)
	if results["boolean"] == True: # new entity
		describe = """DESCRIBE <"""+conf.base+name+ """>"""
		return hello_blazegraph(describe)
	else: # vocab term
		ask = """ASK { ?s ?p ?o .
				filter( regex( str(?o), '"""+name+"""$' ) )
				}"""
		results = hello_blazegraph(ask)
		if results["boolean"] == True:
			describe = """DESCRIBE ?o
				WHERE { ?s ?p ?o .
				filter( regex( str(?o), '/"""+name+"""$' ) ) .
				filter( regex( str(?o), '^"""+conf.base+"""' ) ) . }"""

			return hello_blazegraph(describe)
		else:
			return None


# EXPLORE METHODS

def getBrowsingFilters(res_template_path):
	with open(res_template_path) as config_form:
		fields = json.load(config_form)
	props = [(f["property"], f["label"], f["type"], f["value"]) for f in fields if ("browse" in f and f["browse"] == "True") or ("disambiguate" in f and f["disambiguate"] == "True")]
	return props


# GRAPH methods

def deleteRecord(graph):
	""" delete a named graph and related record """
	if graph:
		clearGraph = ' CLEAR GRAPH <'+graph+'> '
		deleteGraph = ' DROP GRAPH <'+graph+'> '
		sparql = SPARQLWrapper(conf.myEndpoint)
		sparql.setQuery(clearGraph)
		sparql.method = 'POST'
		sparql.query()
		sparql.setQuery(deleteGraph)
		sparql.method = 'POST'
		sparql.query()


def clearGraph(graph):
	if graph:
		clearGraph = ' CLEAR GRAPH <'+graph+'> '
		sparql = SPARQLWrapper(conf.myEndpoint)
		sparql.setQuery(clearGraph)
		sparql.method = 'POST'
		sparql.query()

# GCE CHARTS
def counter_authors():
	""" """

	q = """
		PREFIX base: <"""+conf.base+""">
		PREFIX dbpedia: <http://dbpedia.org/ontology/>
		SELECT (COUNT(DISTINCT ?person) as ?count)
		WHERE {
			VALUES ?p {base:firstAuthor base:secondAuthor base:thirdAuthor base:fourthAuthor base:fifthAuthor base:sixthAuthor base:seventhAuthor base:eighthAuthor base:ninthAuthor base:tenthAuthor}
			?pub ?p ?person . }
		"""
	count = []
	results = hello_blazegraph(q)
	for result in results["results"]["bindings"]:
		count.append(result["count"]["value"])
	return int(count[0]) if len(count) > 0 else 0

def counter_pubs():
	""" """

	q = """
		PREFIX base: <"""+conf.base+""">
		PREFIX dbpedia: <http://dbpedia.org/ontology/>
		SELECT (COUNT(DISTINCT ?pub) as ?count)
		WHERE { ?pub a ?class . }
		"""
	count = []
	results = hello_blazegraph(q)
	for result in results["results"]["bindings"]:
		count.append(result["count"]["value"])
	return int(count[0]) if len(count) > 0 else 0

def counter_langs():
	""" """

	q = """
		PREFIX base: <"""+conf.base+""">
		PREFIX dcterms: <http://purl.org/dc/terms/>
		PREFIX dbpedia: <http://dbpedia.org/ontology/>
		SELECT (COUNT(DISTINCT ?l) as ?count)
		WHERE { ?pub dcterms:language ?l . }
		"""
	count = []
	results = hello_blazegraph(q)
	for result in results["results"]["bindings"]:
		count.append(result["count"]["value"])
	return int(count[0]) if len(count) > 0 else 0

def counter_publishers():
	""" """

	q = """
		PREFIX base: <"""+conf.base+""">
		PREFIX dcterms: <http://purl.org/dc/terms/>
		PREFIX dbpedia: <http://dbpedia.org/ontology/>
		SELECT (COUNT(DISTINCT ?l) as ?count)
		WHERE { ?pub dcterms:publisher ?l . }
		"""
	count = []
	results = hello_blazegraph(q)
	for result in results["results"]["bindings"]:
		count.append(result["count"]["value"])
	return int(count[0]) if len(count) > 0 else 0

def counter_journals():
	""" """

	q = """
		PREFIX base: <"""+conf.base+""">
		PREFIX dcterms: <http://purl.org/dc/terms/>
		PREFIX frbr: <http://purl.org/vocab/frbr/core#>
		PREFIX fabio: <http://purl.org/spar/fabio/>
		PREFIX dbpedia: <http://dbpedia.org/ontology/>
		SELECT (COUNT(DISTINCT ?l) as ?count)
		WHERE { ?pub a fabio:JournalArticle ; frbr:partOf ?l . }
		"""
	count = []
	results = hello_blazegraph(q)
	for result in results["results"]["bindings"]:
		count.append(result["count"]["value"])
	return int(count[0]) if len(count) > 0 else 0

def counter_topics():
	""" """

	q = """
		PREFIX base: <"""+conf.base+""">
		PREFIX dcterms: <http://purl.org/dc/terms/>
		PREFIX frbr: <http://purl.org/vocab/frbr/core#>
		PREFIX fabio: <http://purl.org/spar/fabio/>
		PREFIX dbpedia: <http://dbpedia.org/ontology/>
		SELECT (COUNT(DISTINCT ?l) as ?count)
		WHERE {
		VALUES ?p {fabio:hasPrimarySubjectTerm fabio:hasSubjectTerm }
		?pub ?p ?l . }
		"""
	count = []
	results = hello_blazegraph(q)
	for result in results["results"]["bindings"]:
		count.append(result["count"]["value"])
	return int(count[0]) if len(count) > 0 else 0

def authors_over_years():
	""" """
	q = """
	PREFIX base: <"""+conf.base+""">
	PREFIX prism: <http://prismstandard.org/namespaces/basic/2.0/>
	PREFIX dbpedia: <http://dbpedia.org/ontology/>
	SELECT (SAMPLE(?yearlabel) as ?yearl) (COUNT(DISTINCT ?person) as ?count)
	WHERE {
		VALUES ?p {base:firstAuthor base:secondAuthor base:thirdAuthor base:fourthAuthor base:fifthAuthor base:sixthAuthor base:seventhAuthor base:eighthAuthor base:ninthAuthor base:tenthAuthor}
		?pub ?p ?person ; prism:publicationDate ?year . ?year rdfs:label ?yearlabel

	} GROUP BY ?year ?yearl ORDER by ?yearl
	"""
	count = []
	results = hello_blazegraph(q)
	for result in results["results"]["bindings"]:
		i = {}
		i["year"] = result["yearl"]["value"]
		i["count"] = int(result["count"]["value"])
		count.append(i)
	newlist = sorted(count, key=lambda d: d['year'])
	return newlist

def publication_over_years():
	""" """
	q = """
	PREFIX base: <"""+conf.base+""">
	PREFIX prism: <http://prismstandard.org/namespaces/basic/2.0/>
	PREFIX dbpedia: <http://dbpedia.org/ontology/>
	SELECT (SAMPLE(?yearlabel) as ?yearl) (COUNT(DISTINCT ?pub) as ?count)
	WHERE {
		?pub prism:publicationDate ?year . ?year rdfs:label ?yearlabel
	} GROUP BY ?year ?yearl ORDER by ?yearl
	"""
	count = []
	results = hello_blazegraph(q)
	for result in results["results"]["bindings"]:
		i = {}
		i["year"] = result["yearl"]["value"]
		i["count"] = int(result["count"]["value"])
		count.append(i)
	newlist = sorted(count, key=lambda d: d['year'])
	return newlist

def language_over_years():
	""" """
	q = """
	PREFIX base: <"""+conf.base+""">
	PREFIX dcterms: <http://purl.org/dc/terms/>
	PREFIX prism: <http://prismstandard.org/namespaces/basic/2.0/>
	PREFIX dbpedia: <http://dbpedia.org/ontology/>
	SELECT (SAMPLE(?yearlabel) as ?yearl) (SAMPLE(?langlabel) as ?langlabel)  (COUNT(DISTINCT ?pub) as ?count)
	WHERE {
		?pub prism:publicationDate ?year ; dcterms:language ?lang .
		?lang rdfs:label ?langlabel .
		?year rdfs:label ?yearlabel .
	} GROUP BY ?year ?yearl ?lang ORDER by ?yearl
	"""
	count = []
	results = hello_blazegraph(q)
	for result in results["results"]["bindings"]:
		i = {}
		i["year"] = int(result["yearl"]["value"])
		i["lang"] = result["langlabel"]["value"].lower()
		i["count"] = int(result["count"]["value"])
		count.append(i)

	final = []
	years = list({d['year'] for d in count})
	for year in years:
		final_d = {}
		final_d["year"] = str(year)
		for i in count:
			if i["year"] == year:
				final_d[i["lang"]] = i["count"]
		final.append(final_d)

	final = sorted(final, key=lambda d: d['year'])

	return final

def get_results(data):
	""" get results from advanced search"""
	# {'search_author': 'tarozzi', 'search_subject-1': 'https://w3id.org/digestgce/vocabularies/conceptual-publications,conceptual publications', 'search_journal': '', 'search_year-19': 'https://w3id.org/digestgce/vocabularies/2021,2021', 'search_year-17': 'https://w3id.org/digestgce/vocabularies/2019,2019', 'search_publisher': '', 'search_language-3': 'https://w3id.org/digestgce/vocabularies/italian,Italian', 'search_title': 'education', 'search_year-18': 'https://w3id.org/digestgce/vocabularies/2020,2020', 'search_language-7': 'https://w3id.org/digestgce/vocabularies/english,English'}
	results = []
	# prepare the query
	q = """SELECT DISTINCT * WHERE { """
	with open('advancedSearch.json') as config_form:
		fields = json.load(config_form)
	recap = defaultdict(list)
	checkboxes = defaultdict(list)
	for k,v in data.items():
		# checkbox, textbox
		field_type = [ field["type"] for field in fields if field["id"] in k ][0]
		# URI, Literal
		field_value = [ field["value"] for field in fields if field["id"] in k ][0]
		# single or multiple properties
		field_property = [ field["property"] for field in fields if field["id"] in k ][0]
		field_name = [ field["label"] for field in fields if field["id"] in k ][0]

		if len(v) > 0 and field_type == "Textbox":
			if field_value == "Literal":
				# bds:minRelevance '0.5'^^xsd:double ;
				q += "?"+k+" bds:search \""+v+"*\" . ?"+k+"  bds:matchAllTerms 'true' . "
				q += "?work <"+field_property+"> ?"+k+" . " if "|" not in field_property else "?work "+field_property+" ?"+k+" . "
			if field_value == "URI":
				q += "?"+k+" bds:search \""+v+"\" . ?"+k+" bds:minRelevance '0.5'^^xsd:double ; bds:matchAllTerms 'true'. "
				q += "?"+k+"URI rdfs:label ?"+k+" . ?work <"+field_property+"> ?"+k+"URI . " if "|" not in field_property else "?"+k+"URI rdfs:label ?"+k+" . ?work "+field_property+" ?"+k+"URI . "
			recap[field_name].append(v)
		if len(v) > 0 and field_type == "Checkbox":
			# group values for the same checkbox
			field_id = [ field["id"] for field in fields if field["id"] in k ][0]
			uri,label = v.split(',',1)
			checkboxes[field_id].append( uri )
			recap[field_name].append(label)
			# checkboxes as union
			# q += "?"+k+" bds:search \""+v+"*\" . ?"+k+" bds:minRelevance '0.3'^^xsd:double . "
			# q += "?"+k+"URI rdfs:label ?"+k+" . ?work <"+field_property+"> ?"+k+"URI . " if "|" not in field_property else "?"+k+"URI rdfs:label ?"+k+" . ?work "+field_property+" ?"+k+"URI . "

	if len(checkboxes) > 0:
		for k,v in checkboxes.items():
			q += " VALUES ?"+k+" {"
			for uri in v:
				q+= "<"+uri+">"
			field_property = [ field["property"] for field in fields if field["id"] in k ][0]
			q += "} . ?work <"+field_property+"> ?"+k+". "
	# sort by year and type
	# hardcoded for GCE
	q += " ?work a ?worktype ; <http://purl.org/spar/biro/isReferencedBy> ?citation ; \
			<http://prismstandard.org/namespaces/basic/2.0/publicationDate> ?date \
			OPTIONAL { ?work <http://prismstandard.org/namespaces/basic/2.0/doi> ?doi }.} \
			ORDER BY ?date ?citation ?worktype"
	print(q)
	sparql_results = hello_blazegraph(q)
	for result in sparql_results["results"]["bindings"]:
		r = {}
		r["worktype"] = " ".join(u.camel_case_split(result["worktype"]["value"].rsplit('/', 1)[-1]))
		r["citation"] = result["citation"]["value"]
		r["year"] = result["date"]["value"].rsplit('/', 1)[-1]
		r["workid"] = result["work"]["value"].rsplit('/', 1)[-1]
		r["doi"] = result["doi"]["value"] if "doi" in result else ""
		results.append(r)
	#print(q, recap)
	return results , recap

def export_data():
	articles = """
	PREFIX fabio: <http://purl.org/spar/fabio/>
	PREFIX base: <https://w3id.org/digestgel/>
	SELECT DISTINCT ?article ?type (SAMPLE(?cit) AS ?cit) (SAMPLE(?title) AS ?title) (SAMPLE(?author1) AS ?author1) (SAMPLE(?author2) AS ?author2) (SAMPLE(?author3) AS ?author3) (SAMPLE(?author4) AS ?author4) (SAMPLE(?author5) AS ?author5) (SAMPLE(?author6) AS ?author6) (SAMPLE(?author7) AS ?author7) (SAMPLE(?author8) AS ?author8) (SAMPLE(?author9) AS ?author9) (SAMPLE(?author10) AS ?author10) (SAMPLE(?editor1) AS ?editor1) (SAMPLE(?editor2) AS ?editor2) (SAMPLE(?editor3) AS ?editor3) (SAMPLE(?editor4) AS ?editor4) (SAMPLE(?editor5) AS ?editor5) (SAMPLE(?editor6) AS ?editor6) (SAMPLE(?editor7) AS ?editor7) (SAMPLE(?editor8) AS ?editor8) (SAMPLE(?editor9) AS ?editor9) (SAMPLE(?editor10) AS ?editor10) (SAMPLE(?journal) AS ?journal) (SAMPLE(?publisher) AS ?publisher) (SAMPLE(?volume) AS ?volume) (SAMPLE(?issue) AS ?issue) (SAMPLE(?pages) AS ?pages) (SAMPLE(?yearx) AS ?year) (SAMPLE(?lang) AS ?language) ?link ?doi (group_concat(DISTINCT ?ptopic;separator="; ") as ?primary_topics)
	WHERE {
	  ?article <http://purl.org/spar/biro/isReferencedBy> ?cit ; a ?typex.
	  OPTIONAL {?article <http://purl.org/dc/terms/title> ?title}
	  OPTIONAL {?article base:firstAuthor ?author1uri. ?author1uri rdfs:label ?author1}
	  OPTIONAL {?article base:secondAuthor ?author2uri. ?author2uri rdfs:label ?author2}
	  OPTIONAL {?article base:thirdAuthor ?author3uri. ?author3uri rdfs:label ?author3}
	  OPTIONAL {?article base:fourthAuthor ?author4uri. ?author4uri rdfs:label ?author4}
	  OPTIONAL {?article base:fifthAuthor ?author5uri. ?author5uri rdfs:label ?author5}
	  OPTIONAL {?article base:sixthAuthor ?author6uri. ?author6uri rdfs:label ?author6}
	  OPTIONAL {?article base:seventhAuthor ?author7uri. ?author7uri rdfs:label ?author7}
	  OPTIONAL {?article base:eighthAuthor ?author8uri. ?author8uri rdfs:label ?author8}
	  OPTIONAL {?article base:ninthAuthor ?author9uri. ?author9uri rdfs:label ?author9}
	  OPTIONAL {?article base:tenthAuthor ?author10uri. ?author10uri rdfs:label ?author10}
	  OPTIONAL {?article <http://purl.org/vocab/frbr/core#partOf> ?journaluri. ?journaluri rdfs:label ?journal}
	  OPTIONAL {?article <http://prismstandard.org/namespaces/basic/2.0/volume> ?volume }
	  OPTIONAL {?article <http://prismstandard.org/namespaces/basic/2.0/issueIdentifier> ?issue }
	  OPTIONAL {?article <http://prismstandard.org/namespaces/basic/2.0/pageRange> ?pages }
	  OPTIONAL {?article <http://prismstandard.org/namespaces/basic/2.0/publicationDate> ?yearuri. ?yearuri rdfs:label ?yearx }
	  OPTIONAL {?article fabio:hasPrimarySubjectTerm ?ptopicuri. ?ptopicuri rdfs:label ?ptopic }
	  OPTIONAL {?article <http://purl.org/dc/terms/language> ?languri. ?languri rdfs:label ?lang }
	  OPTIONAL {?article <http://purl.org/spar/fabio/hasURL> ?link }
	  OPTIONAL {?article <http://prismstandard.org/namespaces/basic/2.0/doi> ?doi }

	  OPTIONAL {?article base:firstEditor ?editor1uri. ?editor1uri rdfs:label ?editor1}
	  OPTIONAL {?article base:secondEditor ?editor2uri. ?editor2uri rdfs:label ?editor2}
	  OPTIONAL {?article base:thirdEditor ?editor3uri. ?editor3uri rdfs:label ?editor3}
	  OPTIONAL {?article base:fourthEditor ?editor4uri. ?editor4uri rdfs:label ?editor4}
	  OPTIONAL {?article base:fifthEditor ?editor5uri. ?editor5uri rdfs:label ?editor5}
	  OPTIONAL {?article base:sixthEditor ?editor6uri. ?editor6uri rdfs:label ?editor6}
	  OPTIONAL {?article base:seventhEditor ?editor7uri. ?editor7uri rdfs:label ?editor7}
	  OPTIONAL {?article base:eighthEditor ?editor8uri. ?editor8uri rdfs:label ?editor8}
	  OPTIONAL {?article base:ninthEditor ?editor9uri. ?editor9uri rdfs:label ?editor9}
	  OPTIONAL {?article base:tenthEditor ?editor10uri. ?editor10uri rdfs:label ?editor10}
	  OPTIONAL {?article <http://purl.org/dc/terms/publisher> ?publisheruri. ?publisheruri rdfs:label ?publisher}

	  BIND(COALESCE(?title, '-') AS ?title ).
	  BIND(COALESCE(?author1, '-') AS ?author1 ).
	  BIND(COALESCE(?author2, '-') AS ?author2 ).
	  BIND(COALESCE(?author3, '-') AS ?author3 ).
	  BIND(COALESCE(?author4, '-') AS ?author4 ).
	  BIND(COALESCE(?author5, '-') AS ?author5 ).
	  BIND(COALESCE(?author6, '-') AS ?author6 ).
	  BIND(COALESCE(?author7, '-') AS ?author7 ).
	  BIND(COALESCE(?author8, '-') AS ?author8 ).
	  BIND(COALESCE(?author9, '-') AS ?author9 ).
	  BIND(COALESCE(?author10, '-') AS ?author10 ).

	  BIND(COALESCE(?editor1, '-') AS ?editor1 ).
	  BIND(COALESCE(?editor2, '-') AS ?editor2 ).
	  BIND(COALESCE(?editor3, '-') AS ?editor3 ).
	  BIND(COALESCE(?editor4, '-') AS ?editor4 ).
	  BIND(COALESCE(?editor5, '-') AS ?editor5 ).
	  BIND(COALESCE(?editor6, '-') AS ?editor6 ).
	  BIND(COALESCE(?editor7, '-') AS ?editor7 ).
	  BIND(COALESCE(?editor8, '-') AS ?editor8 ).
	  BIND(COALESCE(?editor9, '-') AS ?editor9 ).
	  BIND(COALESCE(?editor10, '-') AS ?editor10 ).
	  BIND(COALESCE(?publisher, '-') AS ?publisher ).

	  BIND(COALESCE(?volume, '-') AS ?volume ).
	  BIND(COALESCE(?issue, '-') AS ?issue ).
	  BIND(COALESCE(?pages, '-') AS ?pages ).
	  BIND(COALESCE(?journal, '-') AS ?journal ).
	  BIND(COALESCE(?year, '-') AS ?year ).
	  BIND(COALESCE(?language, '-') AS ?language ).

	  BIND(COALESCE(?link, '-') AS ?link ).
	  BIND(COALESCE(?doi, '-') AS ?doi ).
	  BIND(REPLACE(str(?typex), str("http://purl.org/spar/fabio/"), "") as ?type)
	}
	GROUP BY ?article ?type ?cit ?title ?author1 ?author2 ?author3 ?author4 ?author5 ?author6 ?author7 ?author8 ?author9 ?author10 ?journal ?volume ?issue ?pages ?year ?language ?link ?doi
	"""

	results = hello_blazegraph(articles)
	return results
