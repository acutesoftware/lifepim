#!/usr/bin/python3
# coding: utf-8
# models.py

CONST_LINEBREAK = '\n'

def SELF_TEST():
    tbl1 = lpModelDataTable('tbl1', ['name', 'address'])
    tbl1.search('any text', '1 = 1')
    print(tbl1)
    #tbl2 = lpModelDataTable('', [])
    #tbl2.search('random', '2=2')
    #print(tbl2)

    fle1 = lpModelTextBlob('Note File')
    fle1.load_data_from_file('lp_models.py')
    print(fle1)

class lpModel(object):
    """
    base class of a model
    _(self, *args, **kwargs):
        super.__init__(self, *args, **kwargs)

    """
    def __init__(self, mdl_name=None):
        if mdl_name:
            self.mdl_name = mdl_name
        else:
            self.mdl_name = 'Unamed Model'
        self.data = [] 
        self.row_count = 0
        self.mdl_type = 'BASE MODEL - DO NOT USE'
        

    def __str__(self):
        res = ''
        res += 'lpModel: ' + self.mdl_type + ' = ' + self.mdl_name + CONST_LINEBREAK
        res += str(self.row_count) + ' rows ' + CONST_LINEBREAK
        
        
        return res

    def search(self, search_term, filters):
        print('searching ' + self.mdl_name + ' for ' + search_term + ' using filters ' + str(filters))
    
    def load_data_from_file(self, file_name):
        print('LOG - loading file')



class lpModelTextBlob(lpModel):
    """
    A large blob of text / UTF chars (eg a Note or logfile)
    """
    def __init__(self, mdl_name):
        super().__init__()
        if mdl_name:
            self.mdl_name = mdl_name
        #self.data = text_blob.split(CONST_LINEBREAK)
        self.row_count = len(self.data)
        self.mdl_type = 'Text'

    def __str__(self):
        res = super().__str__()
        res += ' '
        for i in range(0,3):
            res += str(self.data[i]) + CONST_LINEBREAK
        return res

    def search(self, search_term, filters ):
        # do anything specific for text blobs here
        super().search(search_term, filters)
        print('searcing lines of text ' + str(self.col_list))

    def load_data_from_file(self, file_name):
        super().load_data_from_file(file_name)
        print('reading Text file')
        raw_text = open(file_name, 'r').read()
        self.data = raw_text.split(CONST_LINEBREAK)
        self.row_count = len(self.data)


class lpModelDataTable(lpModel):
    """
    A Data table - rows and columns
    """
    def __init__(self, mdl_name, col_list):
        super().__init__()
        if mdl_name:
            self.mdl_name = mdl_name
        self.col_list = col_list
        self.col_count = len(self.col_list)
        self.mdl_type = 'Data Table'

    def __str__(self):
        res = super().__str__()
        res += ' '
        for i in range(0,3):
            try:
                res += str(self.data[i]) + CONST_LINEBREAK
            except:
                pass
        return res

    def search(self, search_term, filters ):
        # do anything specific for tables here
        super().search(search_term, filters)
        print('searcing columns ' + str(self.col_list))

    def load_data_from_file(self, file_name):
        super().load_data_from_file(file_name)
        print('reading CSV file')

           
if __name__ == '__main__':
    SELF_TEST()        