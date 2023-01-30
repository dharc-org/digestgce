from SPARQLWrapper import SPARQLWrapper, POST, DIGEST , JSON
import re

def get_values():
    sparql = SPARQLWrapper("https://projects.dharc.unibo.it/digestgel/sparql")
    sparql.setQuery("""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?entity ?label
        WHERE {
        ?entity rdfs:label ?label .
        FILTER CONTAINS(?label, '; ;')
        }
    """)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    entity_label = []
    for result in results["results"]["bindings"]:
        entity_label.append((result["entity"]["value"], result["label"]["value"]))
    return entity_label

def replace_values(entity_label):
    clean_label = []
    for entity, label in entity_label:
        label = re.sub('((;\s*)+;)','', label)
        clean_label.append((entity,label))
        print(entity, label,'\n')
    return clean_label

def update_label(entity, label):
    sparql = SPARQLWrapper("http://127.0.0.1:3000/bigdata/sparql")
    sparql.setHTTPAuth(DIGEST)
    sparql.setMethod(POST)
    q = """
    WITH <"""+entity+""">
    DELETE
    {   <"""+entity+"""> rdfs:label ?label .
        <"""+entity[:-1]+"""> <http://purl.org/spar/biro/isReferencedBy> ?label .

    }
    INSERT {
      <"""+entity+"""> rdfs:label \""""+label+"""\" .
      <"""+entity[:-1]+"""> <http://purl.org/spar/biro/isReferencedBy> \""""+label+"""\" .
    }
    WHERE {
        <"""+entity+"""> rdfs:label ?label .
        <"""+entity[:-1]+"""> <http://purl.org/spar/biro/isReferencedBy> ?label .
    }
    """
    sparql.setQuery(q)
    print(q)
    results = sparql.query()
    print(results.response.read())

# get uri/labels with mistakes
entity_label = get_values()

# replace labels
clean_label = replace_values(entity_label)

# update sparql
for entity, label in clean_label:
    update_label(entity, label)
