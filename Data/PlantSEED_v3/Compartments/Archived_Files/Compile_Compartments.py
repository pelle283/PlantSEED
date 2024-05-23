#!/usr/bin/env python
import json

header=1
cpts=dict()
with open('PF_PS_Compartments.tsv') as fh:
	for line in fh.readlines():
		if(header==1):
			header-=1
			continue
		line=line.strip('\r\n')
		(id,id2,name,abbrev,suba,ppdb,aracyc)=line.split('\t')

		cpt={'id':id,'name':name,'abbrev':abbrev,
			'aliases':[]}

		lc_aliases=list()			
		for alias in suba.split(','):
			if(alias==''):
				continue
			if(alias.lower() not in cpt['aliases']):
				cpt['aliases'].append(alias)
		for alias in ppdb.split(','):
			if(alias==''):
				continue
			if(alias.lower() not in cpt['aliases']):
				cpt['aliases'].append(alias)
		for alias in aracyc.split(','):
			if(alias==''):
				continue
			if(alias.lower() not in lc_aliases):
				cpt['aliases'].append(alias)
				lc_aliases.append(alias.lower())

		cpts[id]=cpt

header=1
with open('MST_PS_Compartments.tsv') as fh:
	for line in fh.readlines():
		if(header==1):
			header-=1
			continue
		line=line.strip('\r\n')
		(idx,id,name,hier,ph,aliases)=line.split('\t')
		
		# strip zero
		id=id[0]
		if(id not in cpts):
			cpt={'id':id,'name':name,'abbrev':''.join(name.lower().split(' ')),
				'aliases':[],'ph':ph,'hierarchy':hier}
		else:
			cpt = cpts[id]
			cpt['ph']=ph
			cpt['hierarchy']=hier

		lc_aliases=list()			
		for alias in cpt['aliases']:
			lc_aliases.append(alias.lower())

		for alias in aliases.split(','):
			if(alias.lower() not in lc_aliases):
				cpt['aliases'].append(alias)

		cpts[id]=cpt

header=1
with open('OF_PS_Compartments.tsv') as fh:
	for line in fh.readlines():
		if(header==1):
			header-=1
			continue
		line=line.strip('\r\n')
		(id,abbrev)=line.split('\t')

		cpts[id]['abbrev']=abbrev

with open('PlantSEED_Compartments.json','w') as fh:
	fh.write(json.dumps(cpts,indent=2))
