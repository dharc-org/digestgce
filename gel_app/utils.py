import os
import re
import time
import datetime
import json
from dotenv import load_dotenv
import web
import requests
import conf
from collections import defaultdict,OrderedDict
from importlib import reload
from json.decoder import JSONDecodeError


RESOURCE_TEMPLATES = 'resource_templates/'
TEMPLATE_LIST = RESOURCE_TEMPLATES+"template_list.json"
ASK_CLASS = RESOURCE_TEMPLATES+"ask_class.json"

# WEBPY STUFF

def reload_config():
	"""Reload the config from conf.py and overrides the blazegraph endpoint
	   if the env variable is specified.
	"""
	load_dotenv()
	reload(conf)
	myEndpoint = os.getenv('BLAZEGRAPH_ENDPOINT', conf.myEndpoint)
	myPublicEndpoint = os.getenv('PUBLIC_BLAZEGRAPH_ENDPOINT', conf.myPublicEndpoint)

	conf.myEndpoint = myEndpoint
	conf.myPublicEndpoint = myPublicEndpoint


def initialize_session(app):
	""" initialize user session.
	Sessions are pickled in folder /sessions"""
	if web.config.get('_session') is None:
		store = web.session.DiskStore('sessions')
		session = web.session.Session(app, store, initializer={'logged_in': 'False', 'username': 'anonymous', 'gituser': 'None', 'bearer_token': 'None', 'ip_address': 'None'})
		web.config._session = session
		session_data = session._initializer
	else:
		session = web.config._session
		session_data = session._initializer

	web.config.session_parameters['timeout'] = 86400
	return store, session, session_data


def log_output(action, logged_in, user, recordID=None):
	""" log information in console """
	message = '*** '+str(datetime.datetime.now())+' | '+action
	if recordID:
		message += ': <'+recordID+'>'
	message += ' | LOGGED IN: '+str(logged_in)+' | USER: '+user
	print(message)

# LIMIT REQUESTS BY IP ADDRESSES

def write_ip(timestamp, ip_add, request):
	""" write IP addresses in a log file"""
	logs = open(conf.log_file, 'a+')
	logs.write( str(timestamp)+' --- '+ ip_add + ' --- '+ request+'\n')
	logs.close()

def check_ip(ip_add, current_time):
	"""read log file with IP addresses
	limit user POST requests to XX a day"""

	is_user_blocked = False
	limit = int(conf.limit_requests)
	today = current_time.split()[0]
	data = open(conf.log_file, 'r').readlines()
	user_requests = [(line.split(' --- ')[0].split()[0], line.split(' --- ')[1]) for line in data if ip_add in line.split(' --- ')[1] and line.split(' --- ')[0].split()[0] == today ]
	if len(user_requests) > limit:
		is_user_blocked = True
	return is_user_blocked, limit


# METHODS FOR TEMPLATING

def get_dropdowns(fields):
	""" retrieve Dropdowns ids to render them properly
	in Modify and Review form"""
	ids_dropdown= [field['id'] for field in fields if field['type'] == 'Dropdown']
	return ids_dropdown

def get_timestamp():
	""" return timestamp when creating a new record """
	return str(time.time()).replace('.','-')

def upper(s):
	return s.upper()

# METHODS FOR DATA MODEL

def camel_case_split(identifier):
	matches = re.finditer('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', identifier)
	return " ".join([m.group(0) for m in matches])

def split_uri(term):
	last_term = term.rsplit("/",1)[1]
	last_term = last_term.split("#")[1] if '#' in last_term else last_term
	return camel_case_split(last_term)

def get_LOV_labels(term, term_type=None):
	""" get class/ property labels from the form"""
	term, label = term, split_uri(term)
	lov_api = "https://lov.linkeddata.es/dataset/lov/api/v2/term/search?q="
	t = "&type="+term_type if term_type else ''
	label_en = "http://www.w3.org/2000/01/rdf-schema#label@en"
	req = requests.get(lov_api+term+t)

	if req.status_code == 200:
		res = req.json()
		for result in res["results"]:
			if result["uri"][0] in [term, term.replace("https","http")]:
				label = result["highlight"][label_en][0] \
					if label_en in result["highlight"] \
					else result["highlight"][label_en.replace("@en","")][0]\
					if label_en not in result["highlight"]  \
					and label_en.replace("@en","") in result["highlight"]\
					else split_uri(term)

	return term, label

# CONFIG STUFF

def get_vars_from_module(module_name):
	""" get all variables from a python module, e.g. conf"""
	module = globals().get(module_name, None)
	book = {}
	if module:
		book = {key: value for key, value in module.__dict__.items() if not (key.startswith('__') or key.startswith('_'))}
	return book

def toid(s):
	s = s.lower()
	s = s.replace(" ", "_")
	return s

def fields_to_json(data, json_file):
	""" setup/update the json file with the form template
	as modified via the web page *template* """

	list_dicts = defaultdict(dict)
	list_ids = sorted([k.split("__")[0] for k in data.keys()])

	for k,v in data.items():
		if k != 'action':
			# group k,v by number in the k to preserve the order
			# e.g. '4__type__scope': 'Checkbox'
			idx, json_key , field_id = k.split("__")
			list_dicts[int(idx)]["id"] = field_id
			list_dicts[int(idx)][json_key] = v
	list_dicts = dict(list_dicts)
	for n,d in list_dicts.items():
		# cleanup existing k,v
		if 'values' in d:
			values_pairs = d['values'].replace('\r','').strip().split('\n')
			d["value"] = "URI"
			d['values'] = { pair.split(",")[0].strip():pair.split(",")[1].strip() for pair in values_pairs }
		d["disambiguate"] = "True" if 'disambiguate' in d else "False"
		d["browse"] = "True" if 'browse' in d else "False"
		# default if missing
		if d["type"] == "None":
			d["type"] = "Textbox" if "values" not in d else "Dropdown"
		# textarea value
		if d["type"] == "Textarea":
			d["value"] = "Literal"
		if len(d["label"]) == 0:
			d["label"] = "no label"
		if len(d["property"]) == 0:
			d["property"] = "http://example.org/"+d["id"]
		# add default values
		d['searchWikidata'] = "True" if d['type'] == 'Textbox' and d['value'] == 'URI' else "False"
		d['searchGeonames'] = "True" if d['type'] == 'Textbox' and d['value'] == 'Place' else "False"
		d["disabled"] = "False"
		d["class"]= "col-md-11"
		d["cache_autocomplete"] ="off"
	# add a default disambiguate if none is selected
	is_any_disambiguate = ["yes" for n,d in list_dicts.items() if d['disambiguate'] == 'True']
	if len(is_any_disambiguate) == 0:
		ids_disamb = [[n, d["disambiguate"]] for n,d in list_dicts.items() if d['type'] == 'Textbox' and d['value'] == 'URI']
		if len(ids_disamb) > 0:
			list_dicts[ids_disamb[0][0]]["disambiguate"] = "True"

	ordict = OrderedDict(sorted(list_dicts.items()))
	ordlist = [d for k,d in ordict.items()]
	# store the dict as json file
	with open(json_file, 'w') as fout:
		fout.write(json.dumps(ordlist, indent=1))

def validate_setup(data):
	""" Validate user input in setup page and check errors / missing values"""

	data["myEndpoint"] = data["myEndpoint"] if "myEndpoint" in data and data["myEndpoint"].startswith("http") else "http://127.0.0.1:3000/blazegraph/sparql"
	data["myPublicEndpoint"] = data["myPublicEndpoint"] if data["myPublicEndpoint"].startswith("http") else "http://127.0.0.1:3000/blazegraph/sparql"
	data["base"] = data["base"] if data["base"].startswith("http") else "http://example.org/base/"
	# data["main_entity"] = data["main_entity"] if data["main_entity"].startswith("http") else "http://example.org/entity/"
	data["limit_requests"] = data["limit_requests"] if isinstance(int(data["limit_requests"]), int) else "50"
	data["pagination"] = data["pagination"] if isinstance(int(data["pagination"]), int) else "10"
	data["github_backup"] = data["github_backup"] if data["github_backup"] in ["True", "False"] else "False"
	# github backup
	if data["github_backup"] == "True" \
		and (len(data["repo_name"]) > 1 and len(data["owner"]) > 1 and len(data["author_email"]) > 1 and len(data["token"]) > 1):
		data["github_backup"] = "True"
	else:
		data["github_backup"] = "False"

	return data

def init_js_config(data):
	"""Initializes the JS config by the given data

	Parameters
	----------
	data: dict
		Dictionary that is either the initial config or the given data record.
	"""
	with open('static/js/conf.js', 'w') as jsfile:
		jsfile.writelines('var myPublicEndpoint = "'+data.myPublicEndpoint+'";\n')
		jsfile.writelines('var base = "'+ data.base +'";\n')
		# TODO, support for data served in a single graph
		jsfile.writelines('var graph = "";\n')

def updateTemplateList(res_name=None,res_type=None,remove=False):
	"""Update the list of resource templates.
	If the list has not been created yet, it creates the file.

	Parameters
	----------
	res_name: str
		Name of the class associated to the template. Becomes dictionary key
	res_type: str
		URI of the class associated to the template. Becomes dictionary value
	"""

	# create the template list for the first time
	if not os.path.isfile(TEMPLATE_LIST):
		f = open(TEMPLATE_LIST, "w")

	# add a new template
	if res_name and res_type and remove==False:
		try:
			with open(TEMPLATE_LIST,'r') as tpl_file:
				data = json.load(tpl_file)
		except JSONDecodeError:
			data = []

		res = {}
		res["name"] = res_name
		res["short_name"] = res_name.replace(' ','_').lower()
		res["type"] = res_type
		res["template"] = RESOURCE_TEMPLATES+'template-'+res_name.replace(' ','_').lower()+'.json'
		data.append(res)

		with open(TEMPLATE_LIST,'w') as tpl_file:
			json.dump(data, tpl_file)

	# remove a template
	if res_name and remove==True:
		with open(TEMPLATE_LIST,'r') as tpl_file:
			data = json.load(tpl_file)

		for i in range(len(data)):
			if data[i]['short_name'] == res_name:
				#del data[i]
				#break
				data[i]["status"] = "deleted"

		with open(TEMPLATE_LIST,'w') as tpl_file:
			json.dump(data, tpl_file)

def get_template_from_class(res_type):
	#print("###res_type",res_type)
	""" Return the tempalte file path given the URI of the OWL class

	Parameters
	----------
	res_type: str
		URI of the class associated to the template. Becomes dictionary value
	"""

	with open(TEMPLATE_LIST,'r') as tpl_file:
		data = json.load(tpl_file)

	res_template = [t["template"] for t in data if t["type"] == res_type][0]
	return res_template

def update_ask_class(template_path,res_name,remove=False):
	""" Update the list of existing templates in ask_class.json.
	The form is shown when creating a new record and let the user
	decide the template.

	Parameters
	----------
	res_name: str
		Name of the class associated to the template. Becomes dictionary key
	template_path: str
		The local path of the template form (json file)

	"""
	#print(template_path,res_name)
	with open(ASK_CLASS,'r') as tpl_file:
		ask_tpl = json.load(tpl_file)

	if remove:
		ask_tpl[0]["values"].pop(template_path,None)
	else:
		ask_tpl[0]["values"][template_path] = res_name

	# get list of templates
	# with open(TEMPLATE_LIST,'r') as tpl_file:
	# 	tpl_list = json.load(tpl_file)
	#tpl_names = [t["short_name"] for t in tpl_list]
	#tpl_names = [t["name"] for t in tpl_list]

	# check if any template has been removed manually
	# in case, remove it from the ask template
	# for tpl_file,tpl_name in ask_tpl[0]['values'].items():
	# 	if tpl_name not in tpl_names:
	# 		ask_tpl[0]["values"].pop(tpl_file,None)

	with open(ASK_CLASS,'w') as tpl_file:
		json.dump(ask_tpl, tpl_file)

def check_ask_class():
	""" check if any template has been removed manually,
	before loading the new record template.
	In case, remove the template name from the ask template """
	with open(ASK_CLASS,'r') as tpl_file:
		ask_tpl = json.load(tpl_file)

	with open(TEMPLATE_LIST,'r') as tpl_file:
		tpl_list = json.load(tpl_file)
	tpl_names = [t["short_name"] for t in tpl_list]
	remove_tpls = []
	for tpl_file,tpl_name in ask_tpl[0]['values'].items():
		if tpl_name not in tpl_names:
			remove_tpls.append(tpl_file)
	for tpl_file in remove_tpls:
		ask_tpl[0]["values"].pop(tpl_file,None)

	with open(ASK_CLASS,'w') as tpl_file:
		json.dump(ask_tpl, tpl_file)

def change_template_names():
	""" open the ASK FORM and change the template short_names with full name
	to be shown when creating a new record """
	with open(ASK_CLASS,'r') as tpl_file:
		ask_tpl = json.load(tpl_file)

	with open(TEMPLATE_LIST,'r') as tpl_file:
		tpl_list = json.load(tpl_file)

	for tpl_file,tpl_name in ask_tpl[0]['values'].items():
		full_name = [tpl["name"] for tpl in tpl_list if tpl["short_name"] == tpl_name][0]
		ask_tpl[0]['values'][tpl_file] = full_name

	return ask_tpl

# UTILS

def key(s):
	"""Return a datetime from a timestamp

	Parameters
	----------
	s: str
		A string representing a timestamp
	"""
	fmt = "%Y-%m-%dT%H:%M:%S"
	cleandate = datetime.datetime.strptime(s, fmt) if s else '-'
	return cleandate

def isnum(s):
	return s.isnumeric()

def camel_case_split(identifier):
    matches = re.finditer('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', identifier)
    return [m.group(0) for m in matches]

def keys2name():
	""" Returns a mapping of fields RDF properties and IDs for each template"""
	# get the list of templates urls
	templates_list = []
	mapping_id_label = {}
	with open(TEMPLATE_LIST,'r') as tpl_file:
		data = json.load(tpl_file)
		for tpl in data:
			if "example" not in tpl:
				templates_list.append(tpl["template"])
	# open each single template and create a Dictionary
	# { template : {  id: label, id:label },
	#  template2 : { id: label, ...} }
	for tpl in templates_list:
		tpl_mapping = {}
		with open(tpl) as config_form:
			fields = json.load(config_form)
			for field in fields:
				tpl_mapping[field["property"]] = field["id"]
		mapping_id_label[tpl] = tpl_mapping
	return mapping_id_label


def json2ris(data,res_template,FIELD_MAPPINGS):
	""" Transforms the results of getData() into a .ris file (export in search)"""
	print("FIELD_MAPPINGS",FIELD_MAPPINGS)
	print("\n\n\ndata",data)
	type_vocab = {
		"resource_templates/template-article.json": "JOUR",
		"resource_templates/template-book_chapter.json":"CHAP",
		"resource_templates/template-book.json": "BOOK",
		"resource_templates/template-doctoral_thesis.json": "THES",
		"resource_templates/template-example_template.json":"JOUR",
		"resource_templates/template-journal_issue.json":"SER",
		"resource_templates/template-report.json":"RPRT"
	}
	ris_text = ""

	# TY
	res_type = type_vocab[res_template] if res_template in type_vocab else "JOUR"
	ris_text += "TY - "+ res_type + "\n"

	auth1,auth2,auth3,auth4,auth5,auth6,auth7,auth8,auth9,auth10 = None,None,None,None,None,None,None,None,None,None
	year,doi,issue,vol,pub,journal,lang,link,title = None,None,None,None,None,None,None,None,None
	# AU
	if "https://w3id.org/digestgel/firstAuthor" in FIELD_MAPPINGS[res_template]:
		auth1 = find_field("https://w3id.org/digestgel/firstAuthor",FIELD_MAPPINGS[res_template])
	if "https://w3id.org/digestgel/secondAuthor" in FIELD_MAPPINGS[res_template]:
		auth2 = find_field("https://w3id.org/digestgel/secondAuthor",FIELD_MAPPINGS[res_template])
	if "https://w3id.org/digestgel/thirdAuthor" in FIELD_MAPPINGS[res_template]:
		auth3 = find_field("https://w3id.org/digestgel/thirdAuthor",FIELD_MAPPINGS[res_template])
	if "https://w3id.org/digestgel/fourthAuthor" in FIELD_MAPPINGS[res_template]:
		auth4 = find_field("https://w3id.org/digestgel/fourthAuthor",FIELD_MAPPINGS[res_template])
	if "https://w3id.org/digestgel/fifthAuthor" in FIELD_MAPPINGS[res_template]:
		auth5 = find_field("https://w3id.org/digestgel/fifthAuthor",FIELD_MAPPINGS[res_template])
	if "https://w3id.org/digestgel/sixthAuthor" in FIELD_MAPPINGS[res_template]:
		auth6 = find_field("https://w3id.org/digestgel/sixthAuthor",FIELD_MAPPINGS[res_template])
	if "https://w3id.org/digestgel/seventhAuthor" in FIELD_MAPPINGS[res_template]:
		auth7 = find_field("https://w3id.org/digestgel/seventhAuthor",FIELD_MAPPINGS[res_template])
	if "https://w3id.org/digestgel/eighthAuthor" in FIELD_MAPPINGS[res_template]:
		auth8 = find_field("https://w3id.org/digestgel/eighthAuthor",FIELD_MAPPINGS[res_template])
	if "https://w3id.org/digestgel/ninthAuthor" in FIELD_MAPPINGS[res_template]:
		auth9 = find_field("https://w3id.org/digestgel/ninthAuthor",FIELD_MAPPINGS[res_template])
	if "https://w3id.org/digestgel/tenthAuthor" in FIELD_MAPPINGS[res_template]:
		auth10 = find_field("https://w3id.org/digestgel/tenthAuthor",FIELD_MAPPINGS[res_template])

	if auth1 and auth1 in data:
		ris_text += "AU - "+ data[auth1][0][1] + "\n"
	if auth2 and auth2 in data:
		ris_text += "AU - "+ data[auth2][0][1] + "\n"
	if auth3 and auth3 in data:
		ris_text += "AU - "+ data[auth3][0][1] + "\n"
	if auth4 and auth4 in data:
		ris_text += "AU - "+ data[auth4][0][1] + "\n"
	if auth5 and auth5 in data:
		ris_text += "AU - "+ data[auth5][0][1] + "\n"
	if auth6 and auth6 in data:
		ris_text += "AU - "+ data[auth6][0][1] + "\n"
	if auth7 and auth7 in data:
		ris_text += "AU - "+ data[auth7][0][1] + "\n"
	if auth8 and auth8 in data:
		ris_text += "AU - "+ data[auth8][0][1] + "\n"
	if auth9 and auth9 in data:
		ris_text += "AU - "+ data[auth9][0][1] + "\n"
	if auth10 and auth10 in data:
		ris_text += "AU - "+ data[auth10][0][1] + "\n"

	# PY
	year = find_field("http://prismstandard.org/namespaces/basic/2.0/publicationDate",FIELD_MAPPINGS[res_template])
	if year and year in data:
		ris_text += "PY - "+ data[year][0][1] + "\n"

	# DO
	doi = find_field("http://prismstandard.org/namespaces/basic/2.0/doi", FIELD_MAPPINGS[res_template])
	if doi and doi in data:
		ris_text += "DO - "+ data[doi][0] + "\n"

	# IS
	issue = find_field("http://prismstandard.org/namespaces/basic/2.0/issueIdentifier", FIELD_MAPPINGS[res_template])
	if issue and issue in data:
		ris_text += "IS - "+ data[issue][0] + "\n"

	# TI
	title = find_field("http://purl.org/dc/terms/title", FIELD_MAPPINGS[res_template])
	if title and title in data:
		ris_text += "TI - "+ data[title][0] + "\n"

	# JO
	journal = find_field("http://purl.org/vocab/frbr/core#partOf", FIELD_MAPPINGS[res_template])
	if journal and journal in data:
		if res_type == "CHAP":
			ris_text += "J2 - "+ data[journal][0][1] + "\n"
		else:
			ris_text += "JO - "+ data[journal][0][1] + "\n"

	# VL
	vol = find_field("http://prismstandard.org/namespaces/basic/2.0/volume", FIELD_MAPPINGS[res_template])
	if vol and vol in data:
		ris_text += "VL - "+ data[vol][0] + "\n"

	# PB
	pub = find_field("http://purl.org/dc/terms/publisher", FIELD_MAPPINGS[res_template])
	if pub and pub in data:
		ris_text += "PB - "+ data[pub][0][1] + "\n"

	# LA
	lang = find_field("http://purl.org/dc/terms/language", FIELD_MAPPINGS[res_template])
	if lang and lang in data:
		ris_text += "LA - "+ data[lang][0][1] + "\n"

	# L2
	link = find_field("http://purl.org/spar/fabio/hasURL", FIELD_MAPPINGS[res_template])
	if link and link in data:
		ris_text += "L2 - "+ data[link][0] + "\n"

	ris_text += "DP - Digest Global Education and Learning\n"
	ris_text += "ER  - \n"
	return ris_text

def find_field(f,d):
	return d[f] if f in d else None