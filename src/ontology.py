#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ontology.py
#
# Utilities to check the upper ontology for both game information
# and real world data

import os
import sys
from interfaces.web import web_data as web
import config

# this reads in the list and builds a single sorted file
file_ontology_export = config.ontology_file #os.path.join(os.getcwd(), '..', 'SAMPLE_DATA', 'configuration', 'ontology.csv')

# folder contains user editied lists of ontology files
folder_ontology = config.ontology_folder

def ont_list():
    o = Ontology(folder_ontology, file_ontology_export)
    #print(o)


def ont_find(txt):
    o = Ontology(folder_ontology, file_ontology_export)
    res = o.find(txt)
    for line in res:
        print(line)
    print('Found ' + str(len(res)) + ' ontology nodes')


class OntologyItem (object):
    """
    graph_depth,sort_order,node_id,parent_id,node_name,detail,reference_info
    """
    def __init__(self, csv_line):
        self.graph_depth	= int(csv_line[0])
        self.sort_order	= int(csv_line[1])
        self.node_id	= csv_line[2]
        self.parent_id = csv_line[3]
        self.node_name = csv_line[4]
        self.detail = csv_line[5]
        self.full_path = ''
        self.prefix_for_child_nodes = self.node_id + '_'
        self.reference_info = csv_line[6]

    def __str__(self):
        res = ''
        res += self.parent_id + ' - '
        res += self.node_id + ' ['
        res += self.detail + '] full_path = '
        res += self.full_path
        return res

class Ontology (object):
    def __init__(self, folder_csv_import, export_csv_file):
        self.dat = []
        self.export_csv_file = export_csv_file
        self.folder_csv_import = folder_csv_import

        self.raw_ontology = self.load_ontology_files()

        # save the export file now
        #print(self.raw_ontology)
        print('total raw lines = ' + str(len(self.raw_ontology)))

        for row in self.raw_ontology:
            if row != []:
                self.dat.append(OntologyItem(row))
        self.num_nodes = len(self.dat)

    def __str__(self):
        op = 'Ontology from - ' + self.folder_csv_import + '\n'
        for o in self.dat:
            op += str(o) + '\n'
        op += 'Total nodes = ' + str(self.num_nodes)
        return op

    def load_ontology_files(self):
        """
        reads the full list of ontology*.csv files from the folder
        specified in config and builds a single ontology list
        (To allow simpler editing of specific sets of data)
        """
        import glob
        all_ont_files = glob.glob(self.folder_csv_import + os.sep + '*.csv') 
        curr_data = []  # holds the current raw CSV from current file
        
        # start off with the root node added manually
        #all_data = [['1','1','root','','Root','Main root node','root','','root','']]
        all_data = []


        # append each CSV file in ontology folder
        for cur_file in all_ont_files:
            curr_data = web.read_csv_to_list2(cur_file)
            print(len(curr_data))
            all_data.extend(curr_data)
            print('loaded ' + cur_file)

        pprint_raw(all_data)

        return all_data

    def find(self, txt):
        res = []
        for ont_item in self.dat:
            #print('checking line ' + str(ont_item) + ' for string ' + txt)
            if txt in str(ont_item).upper():
                #print(ont_item)
                res.append(ont_item)
        return res

    def tree_view(self):
        print('show as tree..')
        #sorted_ont = self.dat.sort(key=lambda x:str(x[1]))
        
        for node in self.dat:
            spaces = ' ' * node.graph_depth * 8
            
            print(spaces + node.node_name + ' ' + node.detail)
            #print('-' + node.node_name.rjust(spaces))

def pprint_raw(lst):
    """
    pretty print the raw list
    """
    for row in lst:
        print(str(row))
    print('pprint_raw Total raw lines = ' + str(len(row)))



def ont_help():
    print('\n\nontology.py - utilies for ontology file')
    print('parameters : ')
    print(' -t = show as tree ')
    print(' -c = checks for mismatched entries ')
    print(' -f [txt] = lists entries containing "txt" ')
    

    

if __name__ == '__main__':
    if len(sys.argv) == 1:
        ont_list()
        ont_help()
        exit(0)
    if sys.argv[1] == '-c':
        print('checking file...')
    if sys.argv[1] == '-f':
        #print('finding ' + sys.argv[2])
        ont_find(sys.argv[2].upper())
    if sys.argv[1] == '-t':
        o = Ontology(folder_ontology, file_ontology_export)
        o.tree_view()

