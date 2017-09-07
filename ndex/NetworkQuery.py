__author__ = 'aarongary'

import ndex
import ijson
import sys
import pysolr
import requests
from pysolr import SolrError
from ndex import solr_url
from model.NiceCXNetwork import NiceCXNetwork
from model.cx.aspects.NodesElement import NodesElement
from model.cx.aspects.EdgesElement import EdgesElement
from model.cx.aspects.NetworkAttributesElement import NetworkAttributesElement
from model.cx.aspects.NodeAttributesElement import NodeAttributesElement
from model.cx.aspects.EdgeAttributesElement import EdgeAttributesElement
from model.cx.aspects.CitationElement import CitationElement
from model.metadata.MetaDataElement import MetaDataElement
from model.cx.aspects.SupportElement import SupportElement
from model.cx.aspects import ATTRIBUTE_DATA_TYPE
from model.cx.aspects.SimpleNode import SimpleNode
from model.cx import CX_CONSTANTS
from model.cx import known_aspects
import time

if sys.version_info.major == 3:
    from urllib.request import urlopen
else:
    from urllib import urlopen


class NetworkQuery():
    def __init__(self):
        self.query = ''

    def query_network1(self, uuid, search_string, max_edges):
        niceCx = NiceCXNetwork()
        #uuid = '7246d8cf-c644-11e6-b48c-0660b7976219'
        search_terms_dict = {k:1 for k in search_string.split(',')}
        edge_keepers = set([])
        node_keepers = set([])

        solr = pysolr.Solr(solr_url + uuid + '/', timeout=10)

        try:
            results = solr.search(search_string, rows=10000)
            #search_terms_array = [int(n['id']) for n in results.docs]
            search_terms_array = {int(n['id']):1 for n in results.docs}
            search_terms_set = set([int(n['id']) for n in results.docs])
            if(not search_terms_array):
                return {'message': 'No nodes found'}

            print('starting nodes 1')
            #===================
            # METADATA
            #===================
            available_aspects = []
            for ae in (o for o in self.streamAspect(uuid, 'metaData')):
                available_aspects.append(ae.get(CX_CONSTANTS.METADATA_NAME))
                mde = MetaDataElement(json_obj=ae)
                niceCx.addMetadata(mde)

            opaque_aspects = set(available_aspects).difference(known_aspects)

            print(opaque_aspects)

            #===================
            # EDGES
            #===================
            edge_count = 0
            added_edges = 0
            edges = []
            edge_found = False
            edge_id = -1
            edge_s = None
            edge_t = None
            edge_i = None
            e_count = 0

            start_time = time.time()
            parser = self.streamAspectRaw(uuid, 'edges')

            for prefix, event, value in parser:
                if(event == 'end_map'):
                    e_count += 1
                    if e_count % 5000 == 0:
                        print(e_count)
                    if edge_found:
                        edge_keepers.add(edge_id)
                        node_keepers.update([edge_s, edge_t])
                        edges.append(EdgesElement(id=edge_id, edge_source=edge_s, edge_target=edge_t, edge_interaction=edge_i))

                    edge_id = -1
                    edge_s = None
                    edge_t = None
                    edge_i = None
                    edge_found = False

                if (prefix) == ('item.s'):
                    if value in search_terms_set:
                        edge_found = True
                    edge_s = value

                elif (prefix) == ('item.t'):
                    if value in search_terms_set:
                        edge_found = True
                    edge_t = value

                elif (prefix) == ('item.i'):
                    if edge_found:
                        edge_i = value

                elif (prefix) == ('item.@id'):
                    edge_id = value

            print('Response time (Edge search): ' + str(time.time() - start_time))
            print(node_keepers)
            print(edge_keepers)

            '''
            if 'edges' in available_aspects:
                for ae in (o for o in self.streamAspect(uuid, 'edges')):
                    if ae.get(CX_CONSTANTS.EDGE_SOURCE_NODE_ID) in search_terms_set or ae.get(CX_CONSTANTS.EDGE_TARGET_NODE_ID) in search_terms_set:
                        edge_keepers.add(ae.get(CX_CONSTANTS.ID))
                        node_keepers.update([ae.get(CX_CONSTANTS.EDGE_SOURCE_NODE_ID), ae.get(CX_CONSTANTS.EDGE_TARGET_NODE_ID)])

                    if edge_count % 5000 == 0:
                        print(edge_count)

                    if added_edges > max_edges:
                        raise StopIteration('Max edges reached')

                    edge_count += 1
            else:
                raise Exception('Network does not contain any nodes.  Cannot query')
            '''

        except SolrError as se:
            if('404' in se.message):
                ndex.get_logger('SOLR').warning('Network not found ' + self.uuid + ' on ' + solr_url + ' server.')
                raise Exception("Network not found (SOLR)")
            else:
                ndex.get_logger('SOLR').warning('Network error ' + self.uuid + ' on ' + solr_url + ' server. ' + se.message)
                raise Exception(se.message)
        except StopIteration as si:
                ndex.get_logger('QUERY').warning("Found more than max edges.  Raising exception")
                raise StopIteration(si.message)


    def query_network(self, uuid, search_string, max_edges):
        myConst = CX_CONSTANTS

        niceCx = NiceCXNetwork()
        #uuid = '7246d8cf-c644-11e6-b48c-0660b7976219'
        search_terms_dict = {k:1 for k in search_string.split(',')}

        solr = pysolr.Solr(solr_url + uuid + '/', timeout=10)

        try:
            results = solr.search(search_string, rows=10000)
            #search_terms_array = [int(n['id']) for n in results.docs]
            search_terms_array = {int(n['id']):1 for n in results.docs}
            if(not search_terms_array):
                return {'message': 'No nodes found'}

            print('starting nodes 1')
            #===================
            # METADATA
            #===================
            available_aspects = []
            for ae in (o for o in self.streamAspect(uuid, 'metaData')):
                available_aspects.append(ae.get(CX_CONSTANTS.METADATA_NAME))
                mde = MetaDataElement(json_obj=ae)
                niceCx.addMetadata(mde)

            available_aspects = ['edges', 'nodes'] # TODO - remove this
            opaque_aspects = set(available_aspects).difference(known_aspects)

            print(opaque_aspects)

            #===================
            # NODES
            #===================
            if 'nodes' in available_aspects:
                for ae in (o for o in self.streamAspect(uuid, 'nodes')):
                    if search_terms_array.get(ae.get(CX_CONSTANTS.ID)):
                        add_this_node = NodesElement(json_obj=ae)
                        niceCx.addNode(add_this_node)
            else:
                raise Exception('Network does not contain any nodes.  Cannot query')

            print('starting edges 1')
            #===================
            # EDGES
            #===================
            edge_count = 0
            added_edges = 0
            start_time = time.time()
            if 'edges' in available_aspects:
                for ae in (o for o in self.streamAspect(uuid, 'edges')):
                    if niceCx.nodes.get(ae.get(CX_CONSTANTS.EDGE_SOURCE_NODE_ID)) is not None or niceCx.nodes.get(ae.get(CX_CONSTANTS.EDGE_TARGET_NODE_ID)) is not None:
                        add_this_edge = EdgesElement(json_obj=ae)
                        niceCx.addEdge(add_this_edge)
                        added_edges += 1
                    if edge_count % 5000 == 0:
                        print(edge_count)

                    #if edge_count > 30000:
                    #    break

                    if added_edges > max_edges:
                        raise StopIteration('Max edges reached')
                    edge_count += 1
            else:
                raise Exception('Network does not contain any nodes.  Cannot query')

            print('Response time (Edge search): ' + str(time.time() - start_time))
            print('starting nodes 2')
            #===================
            # NODES
            #===================
            for ae in (o for o in self.streamAspect(uuid, 'nodes')):
                if niceCx.getMissingNodes().get(ae.get(CX_CONSTANTS.ID)):
                    add_this_node = NodesElement(json_obj=ae)
                    niceCx.addNode(add_this_node)

            #====================
            # NETWORK ATTRIBUTES
            #====================
            if 'networkAttributes' in available_aspects:
                for ae in (o for o in self.streamAspect(uuid, 'networkAttributes')):
                    add_this_network_attribute = NetworkAttributesElement(json_obj=ae)
                    niceCx.addNetworkAttribute(add_this_network_attribute)

            #===================
            # NODE ATTRIBUTES
            #===================
            if 'nodeAttributes' in available_aspects:
                for ae in (o for o in self.streamAspect(uuid, 'nodeAttributes')):
                    if niceCx.nodes.get(ae.get(CX_CONSTANTS.PROPERTY_OF)):
                        add_this_node_att = NodeAttributesElement(json_obj=ae)
                        niceCx.addNodeAttribute(add_this_node_att)

            #===================
            # EDGE ATTRIBUTES
            #===================
            if 'edgeAttributes' in available_aspects:
                for ae in (o for o in self.streamAspect(uuid, 'edgeAttributes')):
                    if niceCx.edges.get(ae.get(CX_CONSTANTS.PROPERTY_OF)):
                        add_this_edge_att = EdgeAttributesElement(json_obj=ae)
                        niceCx.addEdgeAttribute(add_this_edge_att)

            #===================
            # NODE CITATIONS
            #===================
            if 'nodeCitations' in available_aspects:
                for ae in (o for o in self.streamAspect(uuid, 'nodeCitations')):
                    for e_po in ae.get(CX_CONSTANTS.PROPERTY_OF):
                        if niceCx.getNodes().get(e_po) is not None:
                            niceCx.addNodeCitationsFromCX(ae)

            #===================
            # EDGE CITATIONS
            #===================
            ec_count = 0
            if 'edgeCitations' in available_aspects:
                for ae in (o for o in self.streamAspect(uuid, 'edgeCitations')):
                    for e_po in ae.get(CX_CONSTANTS.PROPERTY_OF):
                        if niceCx.getEdges().get(e_po) is not None:
                            niceCx.addEdgeCitationsFromCX(ae)
                    ec_count += 1
                    if ec_count % 500 == 0:
                        print(ec_count)

            #===================
            # CITATIONS
            #===================
            if 'citations' in available_aspects:
                #======================================================
                # FILTER CITATIONS IF THERE ARE EDGE OR NODE CITATIONS
                # OTHERWISE ADD THEM ALL (NO-FILTER) -- TODO
                #======================================================
                for ae in (o for o in self.streamAspect(uuid, 'citations')):
                    add_this_citation = CitationElement(json_obj=ae)
                    niceCx.addCitation(add_this_citation)

        except SolrError as se:
            if('404' in se.message):
                ndex.get_logger('SOLR').warning('Network not found ' + self.uuid + ' on ' + solr_url + ' server.')
                raise Exception("Network not found (SOLR)")
            else:
                ndex.get_logger('SOLR').warning('Network error ' + self.uuid + ' on ' + solr_url + ' server. ' + se.message)
                raise Exception(se.message)
        except StopIteration as si:
                ndex.get_logger('QUERY').warning("Found more than max edges.  Raising exception")
                raise StopIteration(si.message)


        #nice_cx_json = niceCx.to_json()

        return niceCx

    def streamAspect(self, uuid, aspect_name):
        if aspect_name == 'metaData':
            print('http://dev2.ndexbio.org/v2/network/' + uuid + '/aspect')
            md_response = requests.get('http://dev2.ndexbio.org/v2/network/' + uuid + '/aspect')
            json_respone = md_response.json()
            return json_respone.get('metaData')
        else:
            return ijson.items(urlopen('http://dev2.ndexbio.org/v2/network/' + uuid + '/aspect/' + aspect_name), 'item')

    def streamAspectRaw(self, uuid, aspect_name):
        return ijson.parse(urlopen('http://dev2.ndexbio.org/v2/network/' + uuid + '/aspect/' + aspect_name))
