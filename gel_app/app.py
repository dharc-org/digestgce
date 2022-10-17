# -*- coding: utf-8 -*-
import os
import json
import datetime
import time
import sys
import re
import logging
import cgi
from importlib import reload
from urllib.parse import parse_qs
import requests
import web
from web import form
import spacy
from spacy import displacy
import csv
from io import StringIO
import forms, mapping, conf, queries , vocabs  , github_sync
import utils as u
#import threading

web.config.debug = False

# VARS

WIKIDATA_SPARQL = "https://query.wikidata.org/bigdata/namespace/wdq/sparql"
DEFAULT_FORM_JSON = conf.myform
DEFAULT_ENDPOINT = "http://127.0.0.1:3000/blazegraph/sparql"
IP_LOGS = "ip_logs.log"
RESOURCE_TEMPLATES = 'resource_templates/'
TEMPLATE_LIST = RESOURCE_TEMPLATES+"template_list.json"
ASK_CLASS = RESOURCE_TEMPLATES+"ask_class.json"
NER = spacy.load("en_core_web_sm")
FIELD_MAPPINGS = u.keys2name()

# ROUTING

prefix = ''
prefixLocal = prefix # REPLACE IF IN SUBFOLDER
urls = (
	prefix + '/', 'Login',
	prefix + '/setup', 'Setup',
	prefix + '/template-(.+)', 'Template',
	prefix + '/logout', 'Logout',
	prefix + '/gitauth', 'Gitauth',
	prefix + '/oauth-callback', 'Oauthcallback',
	prefix + '/welcome-(.+)','Index',
	prefix + '/record-(.+)', 'Record',
	prefix + '/modify-(.+)', 'Modify',
	prefix + '/review-(.+)', 'Review',
	prefix + '/documentation', 'Documentation',
	prefix + '/records', 'Records',
	prefix + '/charts', 'Charts',
	prefix + '/search', 'Search',
	prefix + '/model', 'DataModel',
	prefix + '/view-(.+)', 'View',
	prefix + '/term-(.+)', 'Term',
	prefix + '/(sparql)','sparql',
	prefix + '/savetheweb-(.+)','Savetheweb',
	prefix + '/nlp','Nlp',
	prefix + '/login_mask', 'Login_mask',
	prefix + '/export', 'Export',
	prefix + '/api/(.+)', 'Results'
)

app = web.application(urls, globals())
wsgiapp = app.wsgifunc()

# SESSIONS

store, session, session_data = u.initialize_session(app)

# TEMPLATING

render = web.template.render('templates/', base="layout", cache=False,
								globals={'session':session,'time_now':u.get_timestamp,
								'isinstance':isinstance,'str':str, 'next':next,
								'upper':u.upper, 'toid':u.toid,'isnumeric':u.isnum,
								'get_type':web.form.Checkbox.get_type, 'type':type,
								'Checkbox':web.form.Checkbox,
								'Dropdown':web.form.Dropdown})


# LOAD CONFIG AND CONTROLLED VOCABULARIES
u.reload_config()
u.init_js_config(conf)
try:
	vocabs.import_vocabs()
except Exception as e:
	print(e)
is_git_auth = github_sync.is_git_auth()

# ERROR HANDLER

def notfound():
	return web.notfound(render.notfound(user=session['username'],
		is_git_auth=is_git_auth,project=conf.myProject))

def internalerror():
	return web.internalerror(render.internalerror(user=session['username'],
		is_git_auth=is_git_auth,project=conf.myProject))

class Notfound:
	def GET(self):
		raise web.notfound()

app.notfound = notfound
app.internalerror = internalerror

# UTILS

def create_record(data):
	""" POST method in static pages. The only accepted request are
	Create a new record and Create a new template.

	Parameters
	----------
	data: dict
		Dictionary of user input -- web.input().
	"""
	if data and 'action' in data and data.action.startswith('createRecord'):
		record = data.action.split("createRecord",1)[1]
		u.log_output('START NEW RECORD', session['logged_in'], session['username'])
		raise web.seeother(prefixLocal+'record-'+record)
	else:
		u.log_output('ELSE', session['logged_in'], session['username'])
		return internalerror()


# GITHUB AUTHENTICATION

class Gitauth:
	def GET(self):
		""" When the user clicks on Member area
		s/he is redirected to github authentication interface"""

		github_auth = "https://github.com/login/oauth/authorize"
		clientId = conf.gitClientID
		scope = "&scope=repo read:user"

		return web.seeother(github_auth+"?client_id="+clientId+scope)

class Oauthcallback:
	def GET(self):
		""" Redirect from class Gitauth.
		After the user authenticates, get profile information (ask_user_permission).
		Check the user is a collaborator of the repository (get_github_users)
		"""

		data = web.input()
		code = data.code
		res = github_sync.ask_user_permission(code)

		if res:
			userlogin, usermail, bearer_token = github_sync.get_user_login(res)
			is_valid_user = github_sync.get_github_users(userlogin)
			if is_valid_user == True:
				session['logged_in'] = 'True'
				session['username'] = usermail
				session['gituser'] = userlogin
				session['ip_address'] = str(web.ctx['ip'])
				session['bearer_token'] = bearer_token
				# store the token in session
				u.log_output('LOGIN VIA GITHUB', session['logged_in'], session['username'])
				raise web.seeother(prefixLocal+'welcome-1')
		else:
			print("bad request to github oauth")
			return internalerror()


class Setup:
	def GET(self):
		""" /setup webpage. Modify config.py and reload the module
		"""

		u.log_output("SETUP:GET",session['logged_in'], session['username'])
		is_git_auth = github_sync.is_git_auth()
		u.reload_config() # reload conf
		f = forms.get_form('setup.json') # get the form template
		data = u.get_vars_from_module('conf') # fill in the form with conf values
		return render.setup(f=f,user=session['username'],
							data=data, is_git_auth=is_git_auth,project=conf.myProject)

	def POST(self):
		""" Modify config.py and static/js/conf.json and reload the module
		"""

		data = web.input()
		if 'action' in data:
			create_record(data)
		else:
			u.log_output("SETUP:POST",session['logged_in'], session['username'])
			original_status=conf.status

			# override the module conf and conf.json
			file = open('conf.py', 'w')
			file.writelines('# -*- coding: utf-8 -*-\n')
			file.writelines('status= "modified"\n')
			file.writelines('main_entity = "https://schema.org/CreativeWork"\n')
			file.writelines('myform = "'+DEFAULT_FORM_JSON+'"\n')
			file.writelines('myEndpoint = "'+DEFAULT_ENDPOINT+'"\n')
			file.writelines('log_file = "'+IP_LOGS+'"\n')
			file.writelines('wikidataEndpoint = "'+WIKIDATA_SPARQL+'"\n')
			file.writelines('resource_templates = "'+RESOURCE_TEMPLATES+'"\n')
			file.writelines('template_list = "'+TEMPLATE_LIST+'"\n')
			file.writelines('ask_form = "'+RESOURCE_TEMPLATES+'ask_class.json"\n')
			# ONLY GCE
			file.writelines('loginUsers = "True"\n')
			data = u.validate_setup(data)

			for k,v in data.items():
				file.writelines(k+''' = "'''+v+'''"\n''')

			# write the json config file for javascript
			u.init_js_config(data)
			u.reload_config()

			raise web.seeother(prefixLocal+'/welcome-1')


class Template:
	def GET(self, res_name):
		""" Modify the form template for data entry

		Parameters
		----------
		res_name: str
			the name assigned to the template / class
		"""

		is_git_auth = github_sync.is_git_auth()

		with open(TEMPLATE_LIST,'r') as tpl_file:
			tpl_list = json.load(tpl_file)

		res_type = [i['type'] for i in tpl_list if i["short_name"] == res_name][0]
		res_full_name = [i['name'] for i in tpl_list if i["short_name"] == res_name][0]

		# if does not exist create the template json file
		template_path = RESOURCE_TEMPLATES+'template-'+res_name+'.json'
		if not os.path.isfile(template_path):
			f = open(template_path, "w")
			json.dump([],f)
			fields = None
		else: # load template form
			with open(template_path,'r') as tpl_file:
				fields = json.load(tpl_file)

		return render.template(f=fields,user=session['username'],
								res_type=res_type,res_name=res_full_name,
								is_git_auth=is_git_auth,project=conf.myProject)

	def POST(self, res_name):
		""" Save the form template for data entry and reload config files
		"""

		data = web.input()
		if 'action' in data and 'updateTemplate' not in data.action and 'deleteTemplate' not in data.action:
			create_record(data)
		else:
			template_path = RESOURCE_TEMPLATES+'template-'+res_name+'.json'
			if 'action' in data and 'deleteTemplate' in data.action:
				#os.remove(template_path) # remove json file
				u.updateTemplateList(res_name,None,remove=True) # update tpl list
				u.update_ask_class(template_path, res_name,remove=True) # update ask_class
				raise web.seeother(prefixLocal+'/welcome-1')
			else:
				u.fields_to_json(data, template_path) # save the json template
				u.reload_config()
				vocabs.import_vocabs()
				u.update_ask_class(template_path, res_name) # modify ask_class json
				raise web.seeother(prefixLocal+'/welcome-1')

# LOGIN : Homepage

class Login:
	def GET(self):
		""" Homepage """

		is_git_auth = github_sync.is_git_auth()
		# REPLACE ONLY GCE
		#github_repo_name = conf.repo_name if is_git_auth == True else None
		github_repo_name = conf.repo_name if (is_git_auth == True and conf.loginUsers != 'True') else None

		if session.username != 'anonymous':
			u.log_output('HOMEPAGE LOGGED IN', session['logged_in'], session['username'])
			raise web.seeother(prefixLocal+'welcome-1')
		else:
			u.log_output('HOMEPAGE ANONYMOUS', session['logged_in'], session['username'])
			return render.login(user='anonymous',is_git_auth=is_git_auth,project=conf.myProject,payoff=conf.myPayoff,github_repo_name=github_repo_name)

	def POST(self):
		data = web.input()
		create_record(data)


class Logout:
	def GET(self):
		"""Logout"""
		u.log_output('LOGOUT', session['logged_in'], session['username'])
		session['logged_in'] = 'False'
		session['username'] = 'anonymous'
		session['ip_address'] = str(web.ctx['ip'])
		session['bearer_token'] = 'None'
		session['gituser'] = 'None'
		raise web.seeother(prefixLocal+'/')

	def POST(self):
		data = web.input()
		create_record(data)

# LOGIN MASK -- GCE ONLY
class Login_mask:
	def GET(self):
		""" login mask instead of github auth """
		return render.login_mask(user='anonymous',is_git_auth="True",project=conf.myProject,alert=None)

	def POST(self):
		""" check password """
		data = web.input()
		username = data["username"] if 'username' in data else None
		pw = data["password"] if 'password' in data else None
		is_member = github_sync.verify_password(username, pw)
		if is_member:
			session['logged_in'] = 'True'
			session['username'] = data["username"]
			session['ip_address'] = str(web.ctx['ip'])
			raise web.seeother(prefixLocal+'welcome-1')
		else:
			return render.login_mask(user='anonymous',is_git_auth="True",project=conf.myProject,alert="Wrong username or password")
# BACKEND Index: show list or records (only logged users)

class Index:
	def GET(self, page):
		""" Member area

		Parameters
		----------
		page: str
			pagination of records in the backend (1= first page)
		"""

		web.header("Content-Type","text/html; charset=utf-8")
		web.header('Access-Control-Allow-Origin', '*')
		web.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

		is_git_auth = github_sync.is_git_auth()
		session['ip_address'] = str(web.ctx['ip'])
		filterRecords = ''
		userID = session['username'].replace('@','-at-').replace('.','-dot-')
		alll = queries.countAll()
		all, notreviewed, underreview, published = queries.getCountings()
		results = queries.getRecordsPagination(page)

		records = list(reversed(sorted(results, key=lambda tup: u.key(tup[4][:-5]) ))) if len(results) > 0 else []

		with open(TEMPLATE_LIST,'r') as tpl_file:
			tpl_list = json.load(tpl_file)

		session_data['logged_in'] = 'True' if (session['username'] != 'anonymous') else 'False'

		# if logged in or no login is provided at all : GCE addition
		if (session['username'] != 'anonymous'):
			u.log_output('WELCOME PAGE', session['logged_in'], session['username'])

			return render.index(wikilist=records, user=session['username'],
				varIDpage=str(time.time()).replace('.','-'), alll=alll, all=all,
				notreviewed=notreviewed,underreview=underreview,
				published=published, page=page,pagination=int(conf.pagination),
				filter=filterRecords, filterName = 'filterAll',is_git_auth=is_git_auth,
				project=conf.myProject,templates=tpl_list)
		else:
			if conf.gitClientID == '' and conf.loginUsers != 'True':
				session['logged_in'] = 'False'
				return render.index(wikilist=records, user=session['username'],
					varIDpage=str(time.time()).replace('.','-'), alll=alll, all=all,
					notreviewed=notreviewed,underreview=underreview,
					published=published, page=page,pagination=int(conf.pagination),
					filter=filterRecords, filterName = 'filterAll',is_git_auth=is_git_auth,
					project=conf.myProject,templates=tpl_list)
			else:
				session['logged_in'] = 'False'
				u.log_output('WELCOME PAGE NOT LOGGED IN', session['logged_in'], session['username'])
				raise web.seeother(prefixLocal+'/')

	def POST(self, page):
		""" Member area

		Parameters
		----------
		page: str
			pagination of records in the backend (1= first page)
		"""

		web.header("Content-Type","text/html; charset=utf-8")
		web.header('Access-Control-Allow-Origin', '*')
		web.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

		actions = web.input()
		session['ip_address'] = str(web.ctx['ip'])
		is_git_auth = github_sync.is_git_auth()

		with open(TEMPLATE_LIST,'r') as tpl_file:
			tpl_list = json.load(tpl_file)

		pub_stage = "?g dbpedia:currentStatus ?anyValue . "
		filter = "isLiteral(?anyValue) && lcase(str(?anyValue))"
		# filters on the list of records
		filter_values = {
			"filterNew": pub_stage+"FILTER ("+filter+" = 'not modified') .",
			"filterReviewed": pub_stage+"FILTER ("+filter+" = 'modified') .",
			"filterPublished": pub_stage+ "FILTER ("+filter+" = 'published') .",
			"filterAll": "none"
		}

		# filter records
		if actions.action.startswith('filter'):
			#print(actions.action)
			filterRecords = filter_values[actions.action]
			filterRecords = filterRecords if filterRecords not in ['none',None] else ''
			filterName = actions.action
			page = 1
			results = queries.getRecordsPagination(page, filterRecords)
			records = list(reversed(sorted(results, key=lambda tup: u.key(tup[4][:-5]) ))) if len(results) > 0 else []
			alll = queries.countAll()
			all, notreviewed, underreview, published = queries.getCountings()
			filterRecords = filterRecords if filterRecords != '' else 'none'

			return render.index(wikilist=records, user=session['username'],
				varIDpage=str(time.time()).replace('.','-'),
				alll=alll, all=all, notreviewed=notreviewed,
				underreview=underreview, published=published,
				page=page, pagination=int(conf.pagination),
				filter= filterRecords, filterName = filterName, is_git_auth=is_git_auth,
				project=conf.myProject,templates=tpl_list)

		# create a new record
		elif actions.action.startswith('createRecord'):
			record = actions.action.split("createRecord",1)[1]
			u.log_output('START NEW RECORD (LOGGED IN)', session['logged_in'], session['username'], record )
			raise web.seeother(prefixLocal+'record-'+record)

		# delete a record (but not the dump in /records folder)
		elif actions.action.startswith('deleteRecord'):
			graph = actions.action.split("deleteRecord",1)[1].split(' __')[0]
			filterRecords = actions.action.split('deleteRecord',1)[1].split(' __')[1]
			queries.deleteRecord(graph)
			userID = session['username'].replace('@','-at-').replace('.','-dot-')
			if conf.github_backup == "True": # path hardcoded, to be improved
				file_path = "records/"+graph.split(conf.base)[1].rsplit('/',1)[0]+".ttl"
				github_sync.delete_file(file_path,"main", session['gituser'],
										session['username'], session['bearer_token'])
			u.log_output('DELETE RECORD', session['logged_in'], session['username'], graph )
			if filterRecords in ['none',None]:
				raise web.seeother(prefixLocal+'welcome-'+page)
			else:
				filterName = [k if v == filterRecords else 'filterName' for k,v in filter_values.items()][0]
				results = queries.getRecordsPagination(page,filterRecords)
				records = list(reversed(sorted(results, key=lambda tup: u.key(tup[4][:-5]) ))) if len(results) > 0 else []
				alll = queries.countAll()
				all, notreviewed, underreview, published = queries.getCountings(filterRecords)

				return render.index(wikilist=records, user=session['username'],
					varIDpage=str(time.time()).replace('.','-'),
					alll=alll, all=all, notreviewed=notreviewed,
					underreview=underreview, published=published,
					page=page, pagination=int(conf.pagination),
					filter= filterRecords, filterName = filterName, is_git_auth=is_git_auth,
					project=conf.myProject,templates=tpl_list)

		# modify a record
		elif actions.action.startswith('modify'):
			record = actions.action.split(conf.base,1)[1].replace('/','')
			u.log_output('MODIFY RECORD', session['logged_in'], session['username'], record )
			raise web.seeother(prefixLocal+'modify-'+record)

		# start review of a record
		elif actions.action.startswith('review'):
			record = actions.action.split(conf.base,1)[1].replace('/','')
			u.log_output('REVIEW RECORD', session['logged_in'], session['username'], record )
			raise web.seeother(prefixLocal+'review-'+record)

		# change page
		elif actions.action.startswith('changepage'):
			pag = actions.action.split('changepage-',1)[1].split(' __')[0]
			filterRecords = actions.action.split('changepage-',1)[1].split(' __')[1]
			if filterRecords in ['none',None]:
				raise web.seeother(prefixLocal+'welcome-'+pag)
			else:
				filterName = [k if v == filterRecords else '' for k,v in filter_values.items()][0]
				results = queries.getRecordsPagination(pag, filterRecords)
				records = list(reversed(sorted(results, key=lambda tup: u.key(tup[4][:-5]) )))
				alll = queries.countAll()
				all, notreviewed, underreview, published = queries.getCountings(filterRecords)

				return render.index( wikilist=records, user=session['username'],
					varIDpage=str(time.time()).replace('.','-'),
					alll=alll, all=all, notreviewed=notreviewed,
					underreview=underreview, published=published,
					page=page, pagination=int(conf.pagination),
					filter= filterRecords, filterName = filterName, is_git_auth=is_git_auth,
					project=conf.myProject,templates=tpl_list)

		# create a new template
		elif actions.action.startswith('createTemplate'):
			#print('create template')
			is_git_auth = github_sync.is_git_auth()
			res_type = actions.class_uri.strip() if "class_uri" in actions else conf.main_entity
			res_name = actions.class_name.replace(' ','_').lower() if "class_name" in actions else "not provided"

			with open(TEMPLATE_LIST,'r') as tpl_file:
				templates = json.load(tpl_file)

			names = [t['short_name'] for t in templates]
			types = [t['type'] for t in templates]
			now_time = str(time.time()).replace('.','-')
			# check for duplicates
			res_n = actions.class_name if (res_type not in types and res_name not in names) else class_name+'_'+now_time
			u.updateTemplateList(res_n,res_type)
			raise web.seeother(prefixLocal+'template-'+res_name)

		# login or create a new record
		else:
			create_record(actions)

# EXPORT
class Export():
	def GET(self):
		results = queries.export_data()
		bindings = results['results']['bindings']
		sparqlVars = ['article', 'cit']
		metaAttribute = 'value'
		f = 'results'
		# with open(f, 'w', newline='') as csvfile :
		# 	writer = csv.DictWriter(csvfile, fieldnames=sparqlVars)
		# 	writer.writeheader()
		# 	for b in bindings :
		# 		writer.writerow({var:b[var][metaAttribute] for var in sparqlVars})
		# 	web.header('Content-Type','text/csv')
		# 	web.header('Content-disposition', 'attachment; filename='+f)
		# 	print("".join(f))
		#return
		csv_file = StringIO()
		csv_writer = csv.writer(csv_file)
		csv_writer.writerow(['article_id', 'type', 'citation','title','author1', 'author2',  'author3', 'author4',
		'author5', 'author6', 'author7', 'author8', 'author9', 'author10', 'editor1', 'editor2',  'editor3', 'editor4',
		'editor5', 'editor6', 'editor7', 'editor8', 'editor9', 'editor10', 'journal_or_booktitle', 'volume',
		'issue', 'pages', 'year', 'publisher', 'language' , 'link' , 'doi' ])

		for b in bindings:
			csv_writer.writerow([b['article']['value'],b['type']['value'], b['cit']['value'],b['title']['value'],
			b['author1']['value'], b['author2']['value'], b['author3']['value'], b['author4']['value'],
			b['author5']['value'], b['author6']['value'], b['author7']['value'], b['author8']['value'],
			b['author9']['value'], b['author10']['value'], b['editor1']['value'], b['editor2']['value'], b['editor3']['value'], b['editor4']['value'],
			b['editor5']['value'], b['editor6']['value'], b['editor7']['value'], b['editor8']['value'],
			b['editor9']['value'], b['editor10']['value'], b['journal']['value'], b['volume']['value'],
			b['issue']['value'], b['pages']['value'], b['year']['value'], b['publisher']['value'], b['language']['value'].lower() , b['link']['value'] , b['doi']['value']  ])
		web.header('Content-Type','text/csv')
		web.header('Content-disposition', 'attachment; filename=digest.csv')
		returnval = csv_file.getvalue()
		csv_file.close()
		return returnval


# FORM: create a new record (both logged in and anonymous users)

class Record(object):
	def GET(self, name):
		""" Create a new record

		Parameters
		----------
		name: str
			the record ID (a timestamp)
		"""

		web.header("Cache-Control", "no-cache, max-age=0, must-revalidate, no-store")
		web.header("Content-Type","text/html; charset=utf-8")
		web.header('Access-Control-Allow-Origin', '*')
		web.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
		u.log_output('GET RECORD FORM', session['logged_in'], session['username'])

		is_git_auth = github_sync.is_git_auth()
		session['ip_address'] = str(web.ctx['ip'])
		user = session['username']
		logged_in = True if user != 'anonymous' else False
		block_user, limit = u.check_ip(str(web.ctx['ip']), str(datetime.datetime.now()) )
		u.check_ask_class()
		ask_form = u.change_template_names()
		f = forms.get_form(ask_form,True)

		return render.record(record_form=f, pageID=name, user=user,
							alert=block_user, limit=limit,
							is_git_auth=is_git_auth,invalid=False,
							project=conf.myProject, template=None)

	def POST(self, name):
		""" Submit a new record

		Parameters
		----------
		name: str
			the record ID (a timestamp)
		"""

		web.header("Content-Type","text/html; charset=utf-8")
		web.header('Access-Control-Allow-Origin', '*')
		web.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

		is_git_auth = github_sync.is_git_auth()
		f = forms.get_form(conf.ask_form)
		user = session['username']
		session['ip_address'] = str(web.ctx['ip'])
		u.write_ip(str(datetime.datetime.now()), str(web.ctx['ip']), 'POST')
		block_user, limit = u.check_ip(str(web.ctx['ip']), str(datetime.datetime.now()) )
		whereto = prefixLocal+'/' if user == 'anonymous' else prefixLocal+'welcome-1'

		# form validation (ask_class)
		if not f.validates():
			u.log_output('SUBMIT INVALID FORM', session['logged_in'], session['username'],name)
			return render.record(record_form=f, pageID=name, user=user, alert=block_user,
								limit=limit, is_git_auth=is_git_auth,invalid=True,
								project=conf.myProject,template=None)
		else:
			recordData = web.input()

			# load the template selected by the user
			if 'res_name' in recordData:
				if recordData.res_name != 'None':
					f = forms.get_form(recordData.res_name)
					return render.record(record_form=f, pageID=name, user=user, alert=block_user,
									limit=limit, is_git_auth=is_git_auth,invalid=False,
									project=conf.myProject,template=recordData.res_name)
				else:
					raise web.seeother(prefixLocal+'record-'+name)

			if 'action' in recordData:
				create_record(recordData)

			recordID = recordData.recordID if 'recordID' in recordData else None
			templateID = recordData.templateID if 'templateID' in recordData else None
			u.log_output('CREATED RECORD', session['logged_in'], session['username'],recordID)

			if recordID:
				userID = user.replace('@','-at-').replace('.','-dot-')
				file_path = mapping.inputToRDF(recordData, userID, 'not modified',tpl_form=templateID)
				if conf.github_backup == "True":
					try:
						github_sync.push(file_path,"main", session['gituser'], session['username'], session['bearer_token'])
					except Exception as e:
						print(e)

				raise web.seeother(whereto)
			else:
				create_record(recordData)

# FORM: modify a record (only logged in users)

class Modify(object):
	def GET(self, name):
		""" Modify an existing record

		Parameters
		----------
		name: str
			the record ID (a timestamp)
		"""

		web.header("Cache-Control", "no-cache, max-age=0, must-revalidate, no-store")
		web.header("Content-Type","text/html; charset=utf-8")
		web.header('Access-Control-Allow-Origin', '*')
		web.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

		is_git_auth = github_sync.is_git_auth()
		session['ip_address'] = str(web.ctx['ip'])
		# CHANGE GCE ONLY
		session_data['logged_in'] = 'True' if (session['username'] != 'anonymous') else False
		#session_data['logged_in'] = 'True' if (session['username'] != 'anonymous') or \
		#					(conf.gitClientID == '' and session['username'] == 'anonymous') else 'False'

		# if (session['username'] != 'anonymous') or \
		# 	(conf.gitClientID == '' and session['username'] == 'anonymous'):
		if (session['username'] != 'anonymous'):
			graphToRebuild = conf.base+name+'/'
			recordID = name
			res_class = queries.getClass(conf.base+name)
			res_template = u.get_template_from_class(res_class)
			data = queries.getData(graphToRebuild, res_template)
			u.log_output('START MODIFY RECORD', session['logged_in'], session['username'], recordID )

			f = forms.get_form(res_template)

			with open(res_template) as tpl_form:
				fields = json.load(tpl_form)
			ids_dropdown = u.get_dropdowns(fields)

			return render.modify(graphdata=data, pageID=recordID, record_form=f,
							user=session['username'],ids_dropdown=ids_dropdown,
							is_git_auth=is_git_auth,invalid=False,
							project=conf.myProject,template=res_template)
		else:
			session['logged_in'] = 'False'
			raise web.seeother(prefixLocal+'view-'+name)

	def POST(self, name):
		""" Modify an existing record

		Parameters
		----------
		name: str
			the record ID (a timestamp)
		"""

		web.header("Content-Type","text/html; charset=utf-8")
		web.header('Access-Control-Allow-Origin', '*')
		web.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

		recordData = web.input()
		session['ip_address'] = str(web.ctx['ip'])
		is_git_auth = github_sync.is_git_auth()
		templateID = recordData.templateID if 'templateID' in recordData else None
		res_class = queries.getClass(conf.base+name)
		res_template = u.get_template_from_class(res_class)

		if 'action' in recordData:
			create_record(recordData)
		else:
			f = forms.get_form(templateID)
			if not f.validates():
				graphToRebuild = conf.base+name+'/'
				recordID = name
				data = queries.getData(graphToRebuild,templateID)
				u.log_output('INVALID MODIFY RECORD', session['logged_in'], session['username'], recordID )
				f = forms.get_form(templateID)

				with open(templateID) as tpl_form:
					fields = json.load(tpl_form)
				ids_dropdown = u.get_dropdowns(fields)

				return render.modify(graphdata=data, pageID=recordID, record_form=f,
								user=session['username'],ids_dropdown=ids_dropdown,
								is_git_auth=is_git_auth,invalid=True,
								project=conf.myProject,template=res_template)
			else:
				#print(recordData)
				recordID = recordData.recordID
				userID = session['username'].replace('@','-at-').replace('.','-dot-')
				graphToClear = conf.base+name+'/'
				file_path = mapping.inputToRDF(recordData, userID, 'modified', graphToClear,tpl_form=templateID)
				if conf.github_backup == "True":
					try:
						github_sync.push(file_path,"main", session['gituser'],
									session['username'], session['bearer_token'], '(modified)')
					except Exception as e:
						print(e)
				u.log_output('MODIFIED RECORD', session['logged_in'], session['username'], recordID )
				raise web.seeother(prefixLocal+'welcome-1')

# FORM: review a record for publication (only logged in users)

class Review(object):
	def GET(self, name):
		""" Review and publish an existing record

		Parameters
		----------
		name: str
			the record ID (a timestamp)
		"""

		web.header("Cache-Control", "no-cache, max-age=0, must-revalidate, no-store")
		web.header("Content-Type","text/html; charset=utf-8")
		web.header('Access-Control-Allow-Origin', '*')
		web.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

		is_git_auth = github_sync.is_git_auth()
		session_data['logged_in'] = 'True' if (session['username'] != 'anonymous') or \
							(conf.gitClientID == '' and session['username'] == 'anonymous') else 'False'

		# anonymous or authenticated user
		if (session['username'] != 'anonymous') or \
			(conf.gitClientID == '' and session['username'] == 'anonymous'):
			graphToRebuild = conf.base+name+'/'
			recordID = name
			res_class = queries.getClass(conf.base+name)
			res_template = u.get_template_from_class(res_class)
			data = queries.getData(graphToRebuild,res_template)
			session['ip_address'] = str(web.ctx['ip'])
			u.log_output('START REVIEW RECORD', session['logged_in'], session['username'], recordID )

			f = forms.get_form(res_template)

			with open(res_template) as tpl_form:
				fields = json.load(tpl_form)
			ids_dropdown = u.get_dropdowns(fields) # TODO CHANGE
			return render.review(graphdata=data, pageID=recordID, record_form=f,
								graph=graphToRebuild, user=session['username'],
								ids_dropdown=ids_dropdown,is_git_auth=is_git_auth,
								invalid=False,project=conf.myProject,template=res_template)
		else:
			session['logged_in'] = 'False'
			raise web.seeother(prefixLocal+'/')

	def POST(self, name):
		""" Review and publish an existing record

		Parameters
		----------
		name: str
			the record ID (a timestamp)
		"""

		web.header("Content-Type","text/html; charset=utf-8")
		web.header('Access-Control-Allow-Origin', '*')
		web.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

		actions = web.input()
		session['ip_address'] = str(web.ctx['ip'])
		templateID = actions.templateID if 'templateID' in actions else None
		f = forms.get_form(templateID)

		# save the new record for future publication
		if actions.action.startswith('save'):
			if not f.validates():
				graphToRebuild = conf.base+name+'/'
				recordID = name
				data = queries.getData(graphToRebuild,templateID)
				session['ip_address'] = str(web.ctx['ip'])
				u.log_output('INVALID REVIEW RECORD', session['logged_in'], session['username'], recordID )
				#f = forms.get_form(conf.myform)
				with open(templateID) as tpl_form:
					fields = json.load(tpl_form)
				ids_dropdown = u.get_dropdowns(fields) # TODO CHANGE
				return render.review(graphdata=data, pageID=recordID, record_form=f,
									graph=graphToRebuild, user=session['username'],
									ids_dropdown=ids_dropdown,is_git_auth=is_git_auth,
									invalid=True,project=conf.myProject,template=templateID)
			else:
				recordData = web.input()
				recordID = recordData.recordID
				userID = session['username'].replace('@','-at-').replace('.','-dot-')
				graphToClear = conf.base+name+'/'
				file_path = mapping.inputToRDF(recordData, userID, 'modified',graphToClear,templateID)
				if conf.github_backup == "True":
					try:
						github_sync.push(file_path,"main", session['gituser'],
									session['username'], session['bearer_token'], '(reviewed)')
					except Exception as e:
						print(e)
				u.log_output('REVIEWED (NOT PUBLISHED) RECORD', session['logged_in'], session['username'], recordID )
				raise web.seeother(prefixLocal+'welcome-1')

		# publish the record
		elif actions.action.startswith('publish'):
			if not f.validates():
				graphToRebuild = conf.base+name+'/'
				recordID = name
				data = queries.getData(graphToRebuild,templateID)
				session['ip_address'] = str(web.ctx['ip'])
				u.log_output('INVALID REVIEW RECORD', session['logged_in'], session['username'], recordID )
				f = forms.get_form(templateID)
				with open(templateID) as tpl_form:
					fields = json.load(tpl_form)
				ids_dropdown = u.get_dropdowns(fields)
				return render.review(graphdata=data, pageID=recordID, record_form=f,
									graph=graphToRebuild, user=session['username'],
									ids_dropdown=ids_dropdown,is_git_auth=is_git_auth,
									invalid=True,project=conf.myProject,template=templateID)
			else:
				recordData = web.input()
				userID = session['username'].replace('@','-at-').replace('.','-dot-')
				graphToClear = conf.base+name+'/'
				file_path= mapping.inputToRDF(recordData, userID, 'published',graphToClear,templateID)
				if conf.github_backup == "True":
					try:
						github_sync.push(file_path,"main", session['gituser'],
								session['username'], session['bearer_token'], '(published)')
					except Exception as e:
						print(e)


				u.log_output('PUBLISHED RECORD', session['logged_in'], session['username'], name )
				raise web.seeother(prefixLocal+'welcome-1')

		# login or create new record
		else:
			create_record(actions)

# FORM: view documentation

class Documentation:
	def GET(self):
		""" Editorial guidelines"""
		web.header("Cache-Control", "no-cache, max-age=0, must-revalidate, no-store")
		is_git_auth = github_sync.is_git_auth()
		return render.documentation(user=session['username'],
									is_git_auth=is_git_auth,project=conf.myProject)

	def POST(self):
		""" Editorial guidelines"""

		data = web.input()
		if 'action' in data:
			create_record(data)

# VIEW : lists of types of records of the catalogue

class Records:
	def GET(self):
		""" EXPLORE page """
		web.header("Cache-Control", "no-cache, max-age=0, must-revalidate, no-store")
		#threading.Thread(target=u.fileWatcher).start()
		is_git_auth = github_sync.is_git_auth()
		# records = queries.getRecords()
		# alll = queries.countAll()
		# filtersBrowse = queries.getBrowsingFilters()

		with open(TEMPLATE_LIST,'r') as tpl_file:
			templates = json.load(tpl_file)

		records_by_template , count_by_template , filters_by_template = {} , {} , {}
		for template in templates:
			res_class=template["type"]
			records = queries.getRecords(res_class)
			records_by_template[template["name"]] = records
			alll = queries.countAll(res_class,True)
			count_by_template[template["name"]] = alll
			filtersBrowse = queries.getBrowsingFilters(template["template"])
			#print(records_by_template)
			filters_by_template[template["name"]] = filtersBrowse
		return render.records(user=session['username'], data=records_by_template,
							title='Latest resources', r_base=conf.base,
							alll=count_by_template, filters=filters_by_template,is_git_auth=is_git_auth,
							project=conf.myProject)

	def POST(self):
		""" EXPLORE page """

		data = web.input()
		if 'action' in data:
			create_record(data)

# VIEW : single record

class View(object):
	def GET(self, name):
		""" Record web page

		Parameters
		----------
		name: str
			the record ID (a timestamp)
		"""
		web.header("Cache-Control", "no-cache, max-age=0, must-revalidate, no-store")
		is_git_auth = github_sync.is_git_auth()
		base = conf.base
		record = base+name
		res_class = queries.getClass(conf.base+name)
		data, stage, title, properties, data_labels = None, None, None, None, {}

		try:
			res_template = u.get_template_from_class(res_class)
			data = dict(queries.getData(record+'/',res_template))
			stage = data['stage'][0] if 'stage' in data else 'draft'

			with open(res_template) as tpl_form:
				fields = json.load(tpl_form)
			try:

				title = [data[k][0] for k,v in data.items() \
					for field in fields if (field['disambiguate'] == "True" \
					and k == field['id'])][0]
			except Exception as e:
				title = "No title"

			properties = {field["label"]:field["property"] for field in fields}
			data_labels = { field['label']:v for k,v in data.items() \
							for field in fields if k == field['id']}
		except Exception as e:
			pass



		return render.view(user=session['username'], graphdata=data_labels,
						graphID=name, title=title, stage=stage, base=base,properties=properties,
						is_git_auth=is_git_auth,project=conf.myProject,res_class=res_class)

	def POST(self,name):
		""" Record web page

		Parameters
		----------
		name: str
			the record ID (a timestamp)
		"""

		data = web.input()
		if 'action' in data:
			create_record(data)

# CHARTS : data visualization [GCE only]

class Charts:
	def GET(self):
		web.header("Cache-Control", "no-cache, max-age=0, must-revalidate, no-store")
		is_git_auth = github_sync.is_git_auth()
		# current status
		authors_count = queries.counter_authors()
		publications_count = queries.counter_pubs()
		language_count = queries.counter_langs()
		publishers_count = queries.counter_publishers()
		journals_count = queries.counter_journals()
		topics_count = queries.counter_topics()
		# evolving data
		authors_over_years = json.dumps(queries.authors_over_years())
		publication_over_years = json.dumps(queries.publication_over_years())
		publishers_over_years = ''
		language_over_years = json.dumps(queries.language_over_years())
		topics_over_years = ''

		return render.charts(user=session['username'],project=conf.myProject, is_git_auth=is_git_auth,
			authors_count=authors_count,publications_count=publications_count,language_count=language_count,
			publishers_count=publishers_count,journals_count=journals_count,topics_count=topics_count,
			authors_over_years=authors_over_years,publication_over_years=publication_over_years,
			language_over_years=language_over_years)

	def POST(self):
		""" Data model page """

		data = web.input()
		if 'action' in data:
			create_record(data)

# ADVANCED SEARCH
class Search:
	def GET(self):
		web.header("Cache-Control", "no-cache, max-age=0, must-revalidate, no-store")
		is_git_auth = github_sync.is_git_auth()
		search_form = forms.get_form("advancedSearch.json")
		return render.search(user=session['username'],project=conf.myProject, is_git_auth=is_git_auth,search_form=search_form,results=None,recap=None,alert="")

	def POST(self):
		data = web.input()
		if 'action' in data:
			create_record(data)
		else:
			is_git_auth = github_sync.is_git_auth()
			search_form = forms.get_form("advancedSearch.json")
			results, recap = queries.get_results(data)
			return render.search(user=session['username'],project=conf.myProject, is_git_auth=is_git_auth,search_form=search_form,results=results,recap=recap,alert="There are no results for your search")

# TERM : vocabulary terms and newly created entities

class Term(object):
	def GET(self, name):
		""" controlled vocabulary term web page

		Parameters
		----------
		name: str
			the ID of the term, generally the last part of the URL
		"""
		web.header("Cache-Control", "no-cache, max-age=0, must-revalidate, no-store")
		data = queries.describeTerm(name)
		is_git_auth = github_sync.is_git_auth()

		count = len([ result["subject"]["value"] \
					for result in data["results"]["bindings"] \
					if (name in result["object"]["value"] and result["object"]["type"] == 'uri') ])

		return render.term(user=session['username'], data=data, count=count,
						is_git_auth=is_git_auth,project=conf.myProject,base=conf.base,name=name)

	def POST(self,name):
		""" controlled vocabulary term web page

		Parameters
		----------
		name: str
			the ID of the term, generally the last part of the URL
		"""

		data = web.input()
		if 'action' in data:
			create_record(data)

# DATA MODEL

class DataModel:
	def GET(self):
		""" Data model page """

		is_git_auth = github_sync.is_git_auth()

		with open(TEMPLATE_LIST,'r') as tpl_file:
			tpl_list = json.load(tpl_file)

		res_data_models = []
		for t in tpl_list:
			if 'status' not in t:
				res_class = t["type"]
				res_name = t["name"]
				with open(t["template"],'r') as tpl_file:
					fields = json.load(tpl_file)
					res_class_label = u.get_LOV_labels(res_class,'class')
					res_data_model = {}
					res_data_model["res_name"] = res_name
					res_data_model["res_class_label"] = res_class_label
					props_labels = [ u.get_LOV_labels(field["property"],'property') for field in fields]
					res_data_model["props_labels"] = props_labels
				res_data_models.append(res_data_model)
		return render.datamodel(user=session['username'], data=res_data_models,is_git_auth=is_git_auth,
								project=conf.myProject)

	def POST(self):
		""" Data model page """

		data = web.input()
		if 'action' in data:
			create_record(data)

# QUERY: endpoint GUI

class sparql:
	def GET(self, active):
		""" SPARQL endpoint GUI and request handler

		Parameters
		----------
		active: str
			Query string or None
			If None, renders the GUI, else parse the query (__run_query_string)
			If the query string includes an update, return error, else sends
			the query to the endpoint (__contact_tp)
		"""
		web.header("Cache-Control", "no-cache, max-age=0, must-revalidate, no-store")
		u.log_output("SPARQL:GET", session['logged_in'], session['username'])
		content_type = web.ctx.env.get('CONTENT_TYPE')
		return self.__run_query_string(active, web.ctx.env.get("QUERY_STRING"), content_type)

	def POST(self, active):
		""" SPARQL endpoint GUI and request handler

		Parameters
		----------
		active: str
			Query string or None
			If None, renders the GUI, else parse the query (__run_query_string)
			If the query string includes an update, return error, else sends
			the query to the endpoint (__contact_tp)
		"""

		u.log_output("SPARQL:POST", session['logged_in'], session['username'])
		content_type = web.ctx.env.get('CONTENT_TYPE')
		web.debug("The content_type value: ")
		web.debug(content_type)

		data = web.input()
		if 'action' in data:
			create_record(data)

		cur_data = web.data()
		if "application/x-www-form-urlencoded" in content_type:
			return self.__run_query_string(active, cur_data, True, content_type)
		elif "application/sparql-query" in content_type:
			return self.__contact_tp(cur_data, True, content_type)
		else:
			raise web.redirect(prefixLocal+"sparql")

	def __contact_tp(self, data, is_post, content_type):
		accept = web.ctx.env.get('HTTP_ACCEPT')
		if accept is None or accept == "*/*" or accept == "":
			accept = "application/sparql-results+xml"
		if is_post: # CHANGE
			req = requests.post(conf.myEndpoint, data=data,
								headers={'content-type': content_type, "accept": accept})
		else: # CHANGE
			req = requests.get("%s?%s" % (conf.myEndpoint, data),
							   headers={'content-type': content_type, "accept": accept})


		if req.status_code == 200:
			web.header('Access-Control-Allow-Origin', '*')
			web.header('Access-Control-Allow-Credentials', 'true')
			web.header('Content-Type', req.headers["content-type"])
			return req.text
		else:
			raise web.HTTPError(
				str(req.status_code), {"Content-Type": req.headers["content-type"]}, req.text)

	def __run_query_string(self, active, query_string, is_post=False,
						   content_type="application/x-www-form-urlencoded"):

		try:
			query_str_decoded = query_string.decode('utf-8')
		except Exception as e:
			query_str_decoded = query_string

		parsed_query = parse_qs(query_str_decoded)

		if query_str_decoded is None or query_str_decoded.strip() == "":
			is_git_auth = github_sync.is_git_auth()
			return render.sparql(active, user=session['username'],
								is_git_auth=is_git_auth,project=conf.myProject)

		if re.search("updates?", query_str_decoded, re.IGNORECASE) is None:
			if "query" in parsed_query:
				return self.__contact_tp(query_string, is_post, content_type)
			else:
				raise web.redirect(conf.myPublicEndpoint)
		else:
			raise web.HTTPError(
				"403", {"Content-Type": "text/plain"}, "SPARQL Update queries are not permitted.")

# RECORD: send request to internet archive

class Savetheweb:
	def GET(self, name):
		# send a request to wayback machine for all URLs
		savetheweb = name.strip()
		try:
			resp = requests.get("http://web.archive.org/save/"+savetheweb,
				headers={"Content-Type": "application/x-www-form-urlencoded"} )

			if resp.status_code == 200:
				print("well done! resource "+savetheweb+" sent to wayback machine")
			else:
				print("mmmm, something wnt wrong with the wayback machine")
			return resp
		except Exception as e:
			print(e)

# perform NER
class Nlp(object):
	def GET(self):
		web.header('Content-Type', 'application/json')
		web.header('Access-Control-Allow-Origin', '*')
		web.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

		query_string = web.input()
		try:
			query_str_decoded = query_string.q.decode('utf-8').strip()
		except Exception as e:
			query_str_decoded = query_string.q.strip()

		# parse string with spacy
		parsed = NER(query_str_decoded)
		entities = {word.text for word in parsed.ents if word.label_ in ['PERSON','ORG','GPE','LOC']}
		# prepare json
		results = []
		for e in list(entities):
			result = {}
			result['result'] = e
			results.append(result)
		return json.dumps(results)

class Results:
	def GET(self, works_id):
		base = conf.base
		works = works_id.split('__')
		text = ""

		for work in works:
			record = base+work
			res_class = queries.getClass(record)
			res_template = u.get_template_from_class(res_class)
			data = dict(queries.getData(record+'/',res_template))
			text += u.json2ris(data,res_template,FIELD_MAPPINGS)

		return json.dumps(text)


if __name__ == "__main__":
	app.run()
