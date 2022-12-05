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

def get_ontology():
    """
    called by LifePIM Desktop this sets up the class and 
    loads the ontology without the parent needing to know
    where the data file lives. May or may not be a good idea
    """
    o = Ontology(folder_ontology, file_ontology_export)
    return o

class OntologyItem (object):
    """
    graph_depth,sort_order,node_id,parent_id,node_name,detail,reference_info
    """
    def __init__(self, csv_line):
        try:
            self.graph_depth	= int(csv_line[0])
            self.sort_order	= float(csv_line[1])
            self.node_id	= csv_line[2]
            self.parent_id = csv_line[3]
            self.node_name = csv_line[4]
            self.detail = csv_line[5]
            self.full_path = ''
            self.prefix_for_child_nodes = self.node_id + '_'
            self.reference_info = csv_line[6]
        except Exception as ex:
            print("Problem parsing ontology raw data - " + str(csv_line))
            print("ERROR = " + str(ex))
            sys.exit()

    def __str__(self):
        res = ''
        res += str(self.graph_depth) + ' - '
        res += str(self.sort_order) + ' - '
        res += self.parent_id + ' - '
        res += self.node_id + ' ['
        res += self.detail + ']'
        res += self.reference_info
        return res

    def get_node_details_as_list(self):
        """
        returns a list containing the columns of the original export
        (which may have been fixed in some other process)
        """
        return [
            self.graph_depth, 
            self.sort_order, 
            self.node_id, 
            self.parent_id, 
            self.node_name, 
            self.detail, 
            self.reference_info            
        ]

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
        
        all_data = []


        # append each CSV file in ontology folder
        for cur_file in all_ont_files:
            curr_data = web.read_csv_to_list2(cur_file)
            print('loaded ' + str(len(curr_data)) + ' rows from ' + cur_file)
            all_data.extend(curr_data)
            

        #pprint_raw(all_data)

        clean_data = []
        for row in all_data:
            if row != []:
                clean_data.append(row)

        import operator
        srt_list = sorted(clean_data, key = operator.itemgetter(1,0))
        #pprint_raw(srt_list)
        return srt_list


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
            spaces = ' ' * node.graph_depth * 4
            
            print(str(node.sort_order) + spaces + node.node_name + ' ' + node.detail)
            #print('-' + node.node_name.rjust(spaces))

    def verify(self):
        print("Verifying ontology...")
        tot_errors = 0
        for test_node in self.dat:
            num_node_id = 0
            num_sort_order = 0
            has_parent = 'N'
            node_id_parts = test_node.node_id.split('_')
            node_id_base = node_id_parts[0:len(node_id_parts)-1]
            calc_parent= '_'.join(n for n in node_id_base)
            if calc_parent != test_node.parent_id and test_node.graph_depth > 3:
                print("ERROR - node ID does not match parent [" + calc_parent + "] if calculated - " + str(test_node))
                tot_errors += 1
            #print("Checking node " + str(test_node))
            for inner_node in self.dat:

                # check for unique sort order (sounds a bit manual but leave for now)
                if test_node.sort_order == inner_node.sort_order:
                    num_sort_order += 1

                # check for unique node id
                if test_node.node_id == inner_node.node_id:
                    num_node_id += 1

                # Check that all nodes have a parent (and ignore root)                    
                if test_node.parent_id == inner_node.node_id:
                    has_parent = 'Y'

                if test_node.node_id == 'root':
                    has_parent = 'Y'


            if num_sort_order != 1:
                print("Error - duplicate sort order in " + str(test_node))
                tot_errors += 1

            if num_node_id != 1:
                print("Error - duplicate node_id in " + str(test_node))
                tot_errors += 1

            if has_parent != 'Y':
                print("Error - node_id has no parent " + str(test_node))
                tot_errors += 1

        if tot_errors > 0:
            print("FAILED VERIFCATION - " + str(tot_errors) + " errors")
            return False
        else:
            print("Success - Ontology is good")
            return True
 
    def write_export(self):
        """
        output the ontology into 1 large CSV file for quick loading by Desktop
        """
        import csv
        
        print("writing export file to " + self.export_csv_file)
        with open(self.export_csv_file, 'w', newline='') as csvfile:
            csvop = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for new_sort_order, node in enumerate(self.dat):
                cur_node_details = node.get_node_details_as_list()
                cur_node_details[0] = new_sort_order
                csvop.writerow(cur_node_details)
        generate_tags_from_ids(self.dat)                



def generate_tags_from_ids(node_list):
    """
    takes the ontology file and creates a tag list as follows
    - each part of the id (minus the start o_, e_ etc)
    - each node_name
    - removes garbage words
    - saves to tags.txt as starting point for tages
    """
    #from collections import Counter

    tag_file = os.path.join(config.user_folder, 'configuration', 'exported_tags.csv')

    all_words = []
    tags = []
    stop_words = ['', '/', '-', 'a', 'or', ',', ';', ':']
    
    print('about to extract tags from ' + str(len(node_list)) + ' nodes')

    for node in node_list:
        cur_node = node.get_node_details_as_list()
        id_parts = cur_node[2].split('_')[1:]
        all_words.extend(id_parts)

        # Option 1 - add the node name if it is one word
        #if ' ' not in cur_node[4]:
        #    all_words.append(cur_node[4].lower().translate({ord(ch): None for ch in '0123456789'}))


        # Option 2 - add the node name split into words
        name_parts = cur_node[4].split(' ')
        for prt in name_parts:
            clean_word = get_clean_tag(prt)
            if clean_word not in stop_words:
                all_words.append(clean_word)



    #print(all_words)

    for wrd in all_words:
        clean_word = get_clean_tag(wrd)
        if clean_word not in tags:
            if clean_word != '':
                tags.append(clean_word)

    tags.sort()

    print(tags)
    print('extracted ' + str(len(all_words)) + ' tags')
    print('summary ' + str(len(tags)) + ' tags')
    
    #counts = Counter(all_words)
    #print(counts)
    with open(tag_file, 'w') as fop:
        for tag in tags:
            fop.write(tag + '\n')


def get_clean_tag(txt):
    """
    removes numbers and parenthisis from a word to get a clean name
    """
    return txt.lower().translate({ord(ch): None for ch in '0123456789(),"''/'})



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
        o = Ontology(folder_ontology, file_ontology_export)
        if o.verify():
            o.write_export()

    if sys.argv[1] == '-f':
        #print('finding ' + sys.argv[2])
        ont_find(sys.argv[2].upper())
    if sys.argv[1] == '-t':
        if len(sys.argv) > 2:
            fltr = sys.argv[2].upper()
            print("TODO - filter tree on this = " + fltr)
        o = Ontology(folder_ontology, file_ontology_export)
        o.tree_view()

