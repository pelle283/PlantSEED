#!/usr/bin/env python

#Setting up environment
#from Workspace.WorkspaceClient import Workspace as Workspace
import biokbase.workspace.baseclient as baseclient
from biokbase.workspace.client import Workspace

import os, json, sys, time
Workspace_URL = 'https://kbase.us/services/ws'
Token = os.environ['KB_AUTH_TOKEN']
WSClient = Workspace(url = Workspace_URL, token = Token)
#############################################
print('WS Client instantiated: Version '+WSClient.ver())

Result_List = WSClient.list_workspace_info({})

for result in Result_List:
	print(result[0:4])
