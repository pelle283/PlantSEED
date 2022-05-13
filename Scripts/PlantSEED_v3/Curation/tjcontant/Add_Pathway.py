#!/usr/bin/env python
import os,sys,json

if(len(sys.argv)<2 or os.path.isfile(sys.argv[1]) is False):
    print("Takes one argument, the path to and including pathway file")
    sys.exit()

pwy_file = sys.argv[1]

with open("../../../../Data/PlantSEED_v3/PlantSEED_Roles.json") as subsystem_file:
    roles_list = json.load(subsystem_file)

roles_dict=dict()
spontaneous_reactions=list()
for entry in roles_list:
    roles_dict[entry['role']]=entry
    if(entry['role'] == 'Spontaneous Reaction'):
        for reaction in entry['reactions']:
            if(reaction not in spontaneous_reactions):
                spontaneous_reactions.append(reaction)

with open(pwy_file) as pwy_file_handle:
    for line in pwy_file_handle.readlines():
        line=line.strip('\r\n')
        #print(line.split('\t'))
        (rxn,role,ftr,pub,ss,cls,pwy,loc)=line.split('\t')

        new_role = False
        if(role not in roles_dict):
            new_role = True
        elif(role == 'Spontaneous Reaction'):
            if(rxn not in spontaneous_reactions):
                new_role = True

        if(new_role is True):
            new_role = {'role':'',
                        'include':True,
                        'subsystems':[],
                        'classes':{},
                        'features':[],
                        'reactions':[],
                        'localization':{},
                        'publications':[]}

            ####################################
            # Add function
            new_role['role']=role

            ####################################
            # Add subsystem and class
            class_dict=dict()
            for entry in ss.split('||'):
                new_role['subsystems'].append(entry)
                class_dict[entry]=[]

                # If MetaCyc Pathway defined
                if(pwy != ""):
                    # One pathway for all classes
                    if (len(pwy.split('||')) == 1):
                        class_dict[entry].append(pwy)
                    # Pathway for each class
                    else:
                        # Check if each pathway defined for each class
                        if(pwy.split('||')[ss.split('||').index(entry)] != ""):
                            class_dict[entry].append(pwy.split('||')[ss.split('||').index(entry)])

            new_role['classes'][cls]=class_dict

            ####################################
            # Add reaction
            new_role['reactions'].append(rxn)

            ####################################
            # Add genes
            if(ftr != ""):
                new_role['features'].append(ftr)

            ####################################
            # Add publications
            if(pub != ""):
                new_role['publications'].append(pub)

            ####################################
            # Add localization
            for entry in loc.split('||'):
                loc_dict=dict()
                #if protein localization data used
                if(':' in entry):
                    (cpt,sources)=entry.split(':')
                    loc_dict[ftr]=sources.split('|')
                #assumed reaction compartment
                else:
                    cpt=entry
                    loc_dict[rxn]=[]

                new_role['localization'][cpt]=loc_dict

            roles_list.append(new_role)
            roles_dict[role] = line

with open('../../../../Data/PlantSEED_v3/PlantSEED_Roles.json','w') as new_subsystem_file:
    json.dump(roles_list,new_subsystem_file,indent=4)
#print(json.dumps(roles_list,indent=4))