#!/usr/bin/env python
import datetime
import time
from urllib.request import urlopen
import pickle
import copy
import sys
import os
import json
import string

#bioObj_ref = "/chenry/public/modelsupport/biochemistry/plantdefault.biochem" #PMS reference
biochem_ref = "48/1/5" #AppDev reference NB: doesn't work in production!

############################
## Load Additional Curation
############################

# A) Load Reaction Curation
# List of reactions for which their direction should be fixed as
# It differs from the biochemistry
curated_reactions_dict=dict()
with open("../../../Data/PlantSEED_v3/Curated_Reaction_Directions_MSDv1.1.1.txt") as rxn_fh:
	for line in rxn_fh.readlines():
		line=line.rstrip('\r\n')
		array=line.split('\t')
		curated_reactions_dict[array[0]]=array[1]

# B) Load Gapfilling Curation
# This is a list of reactions in PlantSEED that are commonly
# made reversible as part of a gapfilling solution when they shouldn't be
# This is not necessary as part of a re-compilation, but if we ever need to use
# gapfilling to fix a new pathway, then we need this.
limited_gf_reactions_list=list()
with open("../../../Data/PlantSEED_v3/Restricted_PlantSEED_Gapfilling_MSDv1.1.1.txt") as gf_rxn_fh:
	for line in gf_rxn_fh.readlines():
		line=line.rstrip('\r\n')
		limited_gf_reactions_list.append(line)

# C) Load Asymmetric transport
# The asymmetric transport is now encoded in the PlantSEED roles file.
# I'm leaving this note as it's an important distinction that may be lost.

# D) Load unbalanced reactions to include
# The update to the biochemistry meant that a few reactions *became* unbalanced when
# they shouldn't have been.
# As of 12/01/20, there are two problematic compounds: THF and Stearoyl-ACP that need investigating
excepted_reactions_list=list()
with open("Unbalanced_Reactions_to_Fix.txt") as exc_rxn_fh:
	for line in exc_rxn_fh.readlines():
		line=line.rstrip('\r\n')
		excepted_reactions_list.append(line)
print("Including unbalanced reactions: "+", ".join(excepted_reactions_list))

time_string = str(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %Hh %Mm %Ss'))
print("Loading biochemistry "+time_string)
############################
## Load Biochemistry
############################

MSD_git_url = "https://raw.githubusercontent.com/ModelSEED/ModelSEEDDatabase/"
#MSD_commit = "v1.1.1"
MSD_commit = "7063bbffde4b40c01550dcb48b89107f28caa2b1" #adding_nad_transporters

reactions_dict=dict()
if(os.path.isfile('Biochem_Cache/MS_Rxns.pickle')):
	with open('Biochem_Cache/MS_Rxns.pickle', 'rb') as rfh:
		reactions_dict = pickle.load(rfh)

else:
	biochemistry_reactions = json.load(urlopen(MSD_git_url+MSD_commit+"/Biochemistry/reactions.json"))
	for reaction in biochemistry_reactions:
		reactions_dict[reaction['id']]=reaction

	# Its important to use binary mode
	with open('Biochem_Cache/MS_Rxns.pickle', 'ab') as rfh:
		pickle.dump(reactions_dict,rfh)

compounds_dict=dict()
if(os.path.isfile('Biochem_Cache/MS_Cpds.pickle')):
	with open('Biochem_Cache/MS_Cpds.pickle', 'rb') as cfh:
		compounds_dict = pickle.load(cfh)

else:
	biochemistry_compounds = json.load(urlopen(MSD_git_url+MSD_commit+"/Biochemistry/compounds.json"))

	for compound in biochemistry_compounds:

		# fix default values
		for key in ["charge","mass","deltag","deltagerr"]:
			if(compound[key] is None):
				compound[key] = 0.0

		if(compound['formula'] is None):
			compound['formula'] = 'R'

		template_compound_hash = { 'id':compound['id'], 'name':compound["name"],
								   'abbreviation':compound["abbreviation"], 'aliases':[],
								   'formula':compound["formula"], 'isCofactor':0,
								   'defaultCharge':float(compound["charge"]), 'mass':float(compound["mass"]),
								   'deltaG':float(compound["deltag"]), 'deltaGErr':float(compound["deltagerr"]),
								   'compound_ref':biochem_ref+"/compounds/id/"+compound['id'] }

		compounds_dict[compound['id']]=template_compound_hash

	# Its important to use binary mode
	with open('Biochem_Cache/MS_Cpds.pickle', 'ab') as cfh:
		pickle.dump(compounds_dict,cfh)

time_string = str(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %Hh %Mm %Ss'))
print("Biochemistry loaded "+time_string)

#Collect compartments: NB The location will change
compartments = dict()
with open("../../../Data/PlantSEED_v3/Compartments/PlantSEED_Compartments.json") as cpt_fh:
	compartments = json.load(cpt_fh)

############################
## Load PlantSEED
############################

#Load Core Subsystems
#Load PlantSEED Subsystems, Roles, Reactions
with open("../../../Data/PlantSEED_v3/PlantSEED_Roles.json") as subsystem_file:
	roles_list = json.load(subsystem_file)

#Collect Compartmentalized Reactions
reactions_roles=dict()
reactions_cpts=dict()
roles=dict()
roles_ids=dict()
excluded_roles=list()
for entry in roles_list:
	if(entry['include'] is False):
		excluded_roles.append(entry['role'])
		continue

	# Skip vacuolar ATP synthase, for pumping protons into vacuole
	if("rxn08173" in entry["reactions"] and "v" in entry["localization"]):
		print("Skipping vacuolar ATP synthase")
		continue

	# Skip ubiquinol oxidase for now
	# https://en.wikipedia.org/wiki/Alternative_oxidase
	# https://www.annualreviews.org/doi/full/10.1146/annurev-arplant-042110-103857
	# It allows the TCA cycle to continue via succinate dehydrogenase
	# without translocating protons and producing ATP, which causes problems with FBA
	if("rxn12494" in entry["reactions"]):
		print("Skipping alternative ubiquinol oxidase")
		continue

	if('kbase_id' in entry and entry['kbase_id'].startswith('PS_role_')):
		roles_ids[entry['role']]=entry['kbase_id']
	else:
		print("Included role does not have KBase ID:",entry['role'])
		continue
	
	if(entry['role'] not in roles):
		roles[entry['role']]=list()
		
	for rxn in entry['reactions']:
		for cpts in entry['localization']:
			
			# Accordingly, the compartments should all be sorted
			# So a compartment index of 0 matches the first position in the compartment list
			# The order is curated in the PlantSEED database

			reaction_cpt = cpts[0]

			# If its a transporter, need to update the reaction compartment id
			if(len(cpts)==2):

				# The rule is that it is always the non-cytosolic compartment
				if('c' in cpts):
					for cpt in cpts:
						if(cpt != 'c'):
							reaction_cpt = cpt

				# With two main exceptions:
				# 1) whether its an extracellular transporter
				if('e' in cpts):
					for cpt in cpts:
						if(cpt != 'e'):
							reaction_cpt = cpt

				# 2) whether its an intraorganellar transporter
				if('j' in cpts):
					reaction_cpt = 'j'
				if('y' in cpts):
					reaction_cpt = 'y'

			tmpl_rxn = rxn+"_"+reaction_cpt

			# These are stored for compound stoichiometry
			# when generating the reagents below
			reactions_cpts[tmpl_rxn]=cpts

			if(tmpl_rxn not in reactions_roles):
				reactions_roles[tmpl_rxn]=list()
			if(entry['role'] not in reactions_roles[tmpl_rxn]):
				reactions_roles[tmpl_rxn].append(entry['role'])
				
	for ftr in entry['features']:
		if(ftr not in roles[entry['role']]):
			roles[entry['role']].append(ftr)

############################
## Load Complexes
############################
complexes = dict()

# Load Curated Complexes
with open("../../../Data/PlantSEED_v3/Complex/Consolidated_PlantSEED_Complex_Curation.json") as cur_cpx_fh:
	curated_complexes = json.load(cur_cpx_fh)

for rxn_cpx_id in sorted(curated_complexes.keys()):

	# Skip marked complexes
	if("FX" in rxn_cpx_id or "RX" in rxn_cpx_id):
		continue
	
	(reaction,compartment,complex)=rxn_cpx_id.split("_")
	tmpl_rxn = reaction+"_"+compartment

	if(tmpl_rxn not in complexes):
		complexes[tmpl_rxn]=dict()

	if(complex not in complexes[tmpl_rxn]):
		complexes[tmpl_rxn][complex]=list()

	for role_entry in curated_complexes[rxn_cpx_id]['roles']:
		complexes[tmpl_rxn][complex].append(role_entry['role'])

# Load Rest of Complexes
for tmpl_rxn in sorted(reactions_roles):
	if(tmpl_rxn in complexes):
		continue

	sorted_roles = sorted(reactions_roles[tmpl_rxn])
	sorted_letters = list(string.ascii_uppercase)
	for letter_i in string.ascii_uppercase:
		for letter_j in string.ascii_uppercase:
			sorted_letters.append(letter_i+letter_j)

	complexes[tmpl_rxn]=dict()
	for i in range(len(sorted_roles)):
		complexes[tmpl_rxn][sorted_letters[i]]=[sorted_roles[i]]

time_string = str(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %Hh %Mm %Ss'))
print("Generating template"+time_string)

############################
## Begin Template Generation
############################

#Generate Template Roles
template_roles=list()
role_count=1
template_role_file = open("Template_Roles_Record.tmp",'w')
for role in sorted(roles):
	role_hash = { 'id':roles_ids[role], 'name':role, 'source':'PlantSEED',
					'aliases':[], 'features':sorted(roles[role]) }

	template_roles.append(role_hash)
	template_role_file.write(role_hash['id']+"\t"+role+"\n")

#Generate TemplateComplex and TemplateComplexRole
template_complexes=list()
template_reactions_complexes=dict()
complex_count=1
rca_fh = open("Reaction_Complex_Assignments.txt", 'w');
for template_reaction in sorted(complexes.keys()):
	for complex in sorted(complexes[template_reaction].keys()):
		complex_hash = { 'id' : "Cpx."+str(complex_count),
						 'name' : "", 'reference' : "",
						 'source' : "PlantSEED",
						 'confidence' : 1.0,
						 'complexroles' : [] }
		complex_count+=1
		
		for role in sorted(complexes[template_reaction][complex]):
			if(role not in roles_ids):
				print("Complexed role excluded:",role)
				continue
		
			complex_role_hash = { 'templaterole_ref' : "~/roles/id/"+roles_ids[role],
								  'optional_role' : 0,
								  'triggering' : 1 }

			complex_hash['complexroles'].append(complex_role_hash)
			rca_fh.write("\t".join([template_reaction,complex_hash['id'],roles_ids[role],role,"|".join(sorted(roles[role]))])+"\n")
	
		template_complexes.append(complex_hash)

		#Creating lookup for linking reactions to complexes later
		if(template_reaction not in template_reactions_complexes):
			template_reactions_complexes[template_reaction]=list()
		template_reactions_complexes[template_reaction].append(complex_hash['id'])

rca_fh.close()

# Default proton compounds for thylakoid proton motive force
proton_d = {"coefficient": -1.0,
        	"templatecompcompound_ref": "~/compcompounds/id/cpd00067_d"}
proton_y = {"coefficient": -1.0,
        	"templatecompcompound_ref": "~/compcompounds/id/cpd00067_y"}

# Generate TemplateReactions
template_reactions = list()

check_tpl_cpt_dict = dict()
template_compartments = list()

check_tpl_cpd_dict = dict()
template_compounds = list()

check_tpl_cpcpd_dict = dict()
template_compcompounds = list()

excluded_rxns_fh = open("Excluded_Reactions.txt","w")
for template_reaction in sorted(reactions_roles):

	[base_reaction,reaction_cpt]=template_reaction.split('_')

	# Skip unbalanced reactions
	if(base_reaction not in excepted_reactions_list and \
	   (base_reaction not in reactions_dict or 'OK' not in reactions_dict[base_reaction]['status'])):
		excluded_rxns_fh.write("Skipping unbalanced reaction: "+base_reaction+"\n")
		continue

	#determine reaction direction
	direction = "="
	if(reactions_dict[base_reaction]['reversibility'] != "?"):
		direction = reactions_dict[base_reaction]['reversibility']

	if(base_reaction in curated_reactions_dict):
		direction = curated_reactions_dict[base_reaction]

	gapfilling_direction = "="
	if(base_reaction in limited_gf_reactions_list):
		gapfilling_direction = direction

	# NB: I'm using the empty reaction as a default reaction ref as it doesn't really affect anything
	# But I need to double-check how reconstruct_plant_metabolism in plant_fbaImpl.py fetches
	# biochemistry data

	template_reaction_hash = { 'id':template_reaction, 'name':reactions_dict[base_reaction]['name'],
							   'templatecompartment_ref':"~/compartments/id/"+reaction_cpt,
							   'reaction_ref':biochem_ref+"/reactions/id/"+"rxn14003", #base_reaction,
							   'type':"universal",
							   'direction':direction,
							   'GapfillDirection':gapfilling_direction,
							   'maxforflux':0.0, 'maxrevflux':0.0,
							   'templateReactionReagents':[], 'templatecomplex_refs':[] }

	# Add reagents
	for entry in (reactions_dict[base_reaction]['stoichiometry'].split(';')):
		(coefficient,compound,gen_cpt,index,name)=entry.split(":")
		
		# The generic compartment (gen_cpt) is an indice
		# The reaction compartments (reaction_cpts) generally consist of one compartment
		#    so the indice is 0
		# but in the case of a transporter, the reaction can have multiple compartments
		#    so the indice may be 0, 1, or even 2 in rare cases
		rgt_cpt=reactions_cpts[template_reaction][int(gen_cpt)]

		# Check and extend list of template compartments
		if(rgt_cpt not in check_tpl_cpt_dict):
			check_tpl_cpt_dict[rgt_cpt]=1
			template_compartments.append(compartments[rgt_cpt])

		# Check and extend list of template compounds
		if(compound not in check_tpl_cpd_dict):
			check_tpl_cpd_dict[compound]=1
			template_compounds.append(compounds_dict[compound])

		# Check and extend list of template compcompounds
		comp_compound = compound+"_"+rgt_cpt
		if(comp_compound not in check_tpl_cpcpd_dict):
			check_tpl_cpcpd_dict[comp_compound]=1

			comp_compound_hash = { 'id':comp_compound,
								   'charge':compounds_dict[compound]["defaultCharge"], 'maxuptake':0.0,
								   'templatecompound_ref':"~/compounds/id/"+compound,
								   'templatecompartment_ref':"~/compartments/id/"+rgt_cpt };

			template_compcompounds.append(comp_compound_hash)

		rxn_rgt_hash = { 'templatecompcompound_ref' : "~/compcompounds/id/"+comp_compound,
						 'coefficient' : float(coefficient) }
		template_reaction_hash['templateReactionReagents'].append(rxn_rgt_hash)

	# Add complexes
	if(template_reaction in template_reactions_complexes):
		for complex in sorted(template_reactions_complexes[template_reaction]):
			complex_string = "~/complexes/id/"+complex
			template_reaction_hash['templatecomplex_refs'].append(complex_string)

	########################################################################
	# This is for printing the reaction with two distinct protein complexes
	# print(template_reaction_hash['id'])
	if(template_reaction_hash['id'] == "rxn00533_d"):
		for cpx_ref in template_reaction_hash['templatecomplex_refs']:
			cpx_id = cpx_ref.split("/")[-1]
			for complex in template_complexes:
				if(complex['id'] == cpx_id):
					for role_ref in complex['complexroles']:
						role_id = role_ref['templaterole_ref'].split('/')[-1]
						for role in template_roles:
							if(role['id'] == role_id):
								#print(template_reaction_hash['id'],cpx_id,role_id,role['name'],role['features'])
								pass
	########################################################################

	########################################################################
	# This is for modifying the proton pumps in the thylakoid
	# Rather than trying to find or create a new reaction in the biochemistry
	# I'm modifying the reactions here in the template generation
	# PS II
	if(template_reaction_hash['id'] == 'rxn20632_y'):
		proton_in = copy.deepcopy(proton_d)
		proton_in['coefficient'] = -4.0
		template_reaction_hash['templateReactionReagents'].append(proton_in)
		proton_out = copy.deepcopy(proton_y)
		proton_out['coefficient'] = 4.0
		template_reaction_hash['templateReactionReagents'].append(proton_out)

		print(template_reaction_hash['id'],json.dumps(template_reaction_hash['templateReactionReagents'],indent=2))

	# Cytochrome b6f pumps two protons and releases two more protons from plastoquinol
	if(template_reaction_hash['id'] == 'rxn20595_y'):
		for rgt in template_reaction_hash['templateReactionReagents']:
			if(rgt['templatecompcompound_ref'].endswith('cpd00067_d')):
				rgt['coefficient'] = -2.0
		
		proton_out = copy.deepcopy(proton_y)
		proton_out['coefficient'] = 4.0
		template_reaction_hash['templateReactionReagents'].append(proton_out)
		print(template_reaction_hash['id'],json.dumps(template_reaction_hash['templateReactionReagents'],indent=2))

	template_reactions.append(template_reaction_hash)

#Populate model_template dictionary
model_template=dict()
model_template={ 'id' : "Plant",
				'domain' : "Plant",
				'name' : "Plant",
				'type' : "GenomeScale",
				'biochemistry_ref' : biochem_ref,
				
				'compartments' : sorted(template_compartments, key = lambda cpt:cpt['id']),
				'compounds' : sorted(template_compounds, key = lambda cpd:cpd['id']), 
				'compcompounds' : sorted(template_compcompounds, key = lambda ccpd:ccpd['id']),
				
				'reactions' : template_reactions, 
				'roles' : template_roles, 
				'complexes' : template_complexes, 
				
				'biomasses' : [],
				'pathways' : []}

#Save Template
with open("PlantSEED_Neutral_Template.json",'w') as ps_tmpl_fh:
	json.dump(model_template,ps_tmpl_fh,indent=4)
time_string = str(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %Hh %Mm %Ss'))
print("Template generated"+time_string)
