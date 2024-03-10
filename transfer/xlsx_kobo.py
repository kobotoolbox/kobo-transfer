import re
import string

import openpyxl
from xml.etree import ElementTree as ET

from helpers.config import Config
from transfer.xml import get_src_submissions_xml
from .media import rename_media_folder
from .xml import generate_new_instance_id

def find_n(xml, n, element_name):
    """
    finds nth occurence of tag in xml and returns the element
    used to append data to correct repeat group 
    """
    occurrences = 0
    for element in xml.iter(element_name):
        occurrences += 1
        if occurrences == int(n):
            return element
    return None

"""def check_for_group(_uid, group_name):
    parent_group = _uid
    group_element = None
    for group in group_name: 

        group_element = _uid.find(".//" + group)

        if (group_element == None):
            group_element = ET.SubElement(parent_group, group)
        
        parent_group = group_element
        group_element = None
    
    return _uid"""


def create_group(group_name, cell_value, parent_group = None):
    """
    Creates and returns an xml element of nested groups.

    :param group_name Header containing group split by ('/'). Example of xlsx header that would be split is [pets/pet/name_of_pet]
    :param cell_value: value stored in the cell for a particular submission, under the group_name column. 
    :param parent_group: None when the first string in group_name is the root. 
    """
    if parent_group is None:
        initial = create_xml_element_and_tag(None, group_name[0], None)
        parent_group = initial
        print("not nested1")
    else:
        initial = parent_group
        print("nested1")
    
    group_element = None
    for group in group_name: 
        if parent_group.tag == group:
            continue
    
        group_element = parent_group.find(".//" + group)

        if (group_element == None):
            group_element = create_xml_element_and_tag(parent_group, group, None)

        if (group == group_name[-1]) and cell_value: #last element in group_name is the question
            group_element.text = str(cell_value)
        
        parent_group = group_element
        group_element = None

    return initial

def new_repeat(submission_xml, workbook, submission_index):
        """method is called when there are multiple sheets in xlsx, because it is assumed to be repeat groups"""
        sheet_names = workbook.sheetnames 
        original_indexes = [] #cleared every time its a new sheet. 
        for sheet_name in sheet_names[1:]:
            new_indexes = []
            sheet = workbook[sheet_name]
            headers = [cell.value for cell in sheet[1]] 
            try:
                index_header = headers.index("_index")
                parent_index_header = headers.index('_parent_index')
                parent_table_header = headers.index('_parent_table_name')
            except Exception:
                print(
                    "Error: if xlsx file has multiple tabs, data in extra sheets must be in expected repeating group format"
                )
                raise

            question_headers = [item for item in headers if not item.startswith('_')] 

            #loop through the question headers and make sure that none of them start with a non-repeating group
            #if they do start with a non-repeating group, make sure that its in the submission_uid already
            non_repeat_groups = []
            
            for column in question_headers:
                parts = column.split('/')
                for part in parts:
                    if part in sheet_names:
                        break
                    else:
                        non_repeat_groups.append(part)
                        break
            
            
            #TODO what if its double nested? what if there are two non-repeat groups, adn then the repeat starts... 

            #for each of the elements in non_repeat_groups, make sure it is in submission_uid
            #if it is, do nothing
            #if it is not, edit submission_uid and add the group
            #create the element in submission_uid if it does not already exist.. 
            for normal_group in non_repeat_groups:
                create_group(normal_group.split('/'), None, submission_xml)


            for row in sheet.iter_rows(min_row=2, values_only=True):
                mini_group = None
                #submission_uid = str(row[submission_uid_header])
                index = str(row[index_header]) #this is the current value
                parent_index = str(row[parent_index_header]) #this is row's parent value
                parent_table = str(row[parent_table_header])
                #group_to_appendto = None
                
                if parent_table == str(sheet_names[0]): #if the parent_table is the main sheet (the first one)

                    #only look at rows with same value as this submission (passed in as parameter)
                    if parent_index != submission_index: 
                        continue
                    else:
                        #populate original_indexes with index of the rows that haave parent_group == passed in value from first sheet
                        original_indexes.append(index) #first sheet, makes sure this is not empty.. 
                     
                else: #if the parent_table a different sheet (not the first one)
                    print(original_indexes)
                    if parent_index not in original_indexes:  #you have to see if its part of the original indexes
                        continue
                    else: 
                        new_indexes.append(index)

                        #TODO
                        #so you know parent_table is repeat1
                        #original indexes holds the index of the submissions you want to look at
                        #so what happens when multiple repeat groups have the same parent_table

            

                for col_name in question_headers: 
                    col_num = headers.index(col_name)
                    cell_value = str(row[col_num])

                    if cell_value in [None, 'None', 'none']:
                        cell_value = ""

                    group_names = col_name.split('/') 

                    #now there is an array of the header
                    #you start the repeat stuff from when repeat sheet name is mentioned!
                    index_of_sheet_group = group_names.index(str(sheet_name)) 
                    
                    #when there is group within a repeat group, this is ok, since can still start the elements from the sheetname
                    #HOWEVER, need different condition when the repeat group is nested in a group

                    if mini_group is None: #this is for first column of the sheet, creates all elements in header starting from spreadsheet name
                        #TODO so what if the second column of the sheet has a different path?? what if it has an extra group in there somewhere. 
                        mini_group = create_group(group_names[index_of_sheet_group:], str(cell_value)) #this is from the top

                    else: #following columns of the sheet (nest the elements, or append to the elements created from first column)
                        mini_group = create_group(group_names[index_of_sheet_group:], str(cell_value), mini_group)


                #group_names is going to be the last column of the current sheet
                #group_names[0] would be the first parent group (the group it starts with) of the last q in the sheet
                #i think this is done w the assumption that all in a sheet are going to start with the same group?? IDK THO
                if question_headers != []:
                    #print(question_headers)
                    #if (str(sheet_name) == group_names[0]): #when initial parent repeat group (the one it starts with) is same as sheet. 
                    #all repeat groups in single sheet have to be nested in same way
                     #   submission_xml.append(mini_group)
                    
                    if parent_table == str(sheet_names[0]): #append to xml if parent_table for this sheet is the initial one. 
    
                        #if repeat_group is nested, must be nested within a non-repeating group
                        #find the previous element and append to that (which is what next condition will do.
                        #otherwise just append to overall xml. 
                        if (index_of_sheet_group == 0):                        
                           submission_xml.append(mini_group)
                        else:
                            parent_of_sheet_group = group_names[index_of_sheet_group - 1]
                            group_to_append_to = submission_xml.find(".//" + str(parent_of_sheet_group))
                            group_to_append_to.append(mini_group)


                     #if its not the first sheet/first parent element
                    else:

                        #TODO this should just be an else condition
                        #when the parent_table is something else
            
                        #print(sheet_name)

                        #look at the parent_table.... 
                        #that should be um value
                        #TODO the only reason this might not work.. and you need to test
                        #if the parent_table is different from the group right before the sheet starts
                        #this would happen when theres a normal group right before it... so the repeat group would need to be nested within a group. and this nested group and all would need to h
                        #have a parent_table that is another repat group 

            
                        um = question_headers[0].split('/')

                            #ok so when you do um[index_of_sheet_group-1], you are assuming that the parent group is a repeating group

                            #you are finding the one right before your current sheet index (like where in the header ur current sheet is found)
                            #pass in submission to append to, the nth mention of parent to find, parent group of the element created 
                    
                        element = find_n(submission_xml, original_indexes.index(parent_index) + 1, um[index_of_sheet_group-1])
                        print(original_indexes.index(parent_index) + 1)
                        print("UM")
                        print(um[index_of_sheet_group-1])

                        element.append(mini_group)

                    if row == sheet.max_row:
                        original_indexes = new_indexes

        return submission_xml

def open_xlsx(excel_file_path):
    """opens xlsx, and returns workbook"""
    try:
        workbook = openpyxl.load_workbook(excel_file_path, read_only=True)
    except FileNotFoundError as e:
        print(f"⚠️ Error: Excel file not found at path '{excel_file_path}'.")
        raise (e)
    except openpyxl.utils.exceptions.InvalidFileException:
        print(f"⚠️ Error: Invalid file format for '{excel_file_path}'")
        raise (e)
    except TypeError as e:
        if "NoneType" in str(e):
            print(f"⚠️ Error: File path is None. Specify xls file path with flag -ef")
            raise (e)
    except Exception as e:
        print(f"⚠️ Something went wrong when reading xlsx file: {e}")
        raise (e)
    return workbook



def add_formhub_element(nsmap_dict, formhub_uuid):
    """
    creates and returns initial element for the submission )example of the format is <aDVansdqUpnpUhGxy8 id="aDVansdqUpnpUhGxy8" version="3 (2022-03-08 10:33:24)">)
    and the formhub element nested within it. 

    :param nsmap_dict: dictionary containing uid and version
    """ 
    uid = nsmap_dict["id"]
    _uid = create_xml_element_and_tag(None, uid, None, nsmap_dict)
    fhub_element = create_xml_element_and_tag(_uid, 'formhub', None)
    create_xml_element_and_tag(fhub_element, 'uuid', str(formhub_uuid))
    return _uid


def add_meta_element(_uid, formatted_uuid):
    """creates element in xml with meta tag. Meta contains instanceId and deprecatedId elements and appears at end of each submission. 
    Format is as follows:
          <meta>
                <instanceID>uuid:a0io37ef-ac71-434b-93b6-1243ef4c123f</instanceID>
                <deprecatedID>
            </meta>
    once meta element is created, it is appended to the xml of whole submission, and then returned. 

    :param _uid is the xml representing a single submission. it is built upon and starts with the inital nsmaplement
    :param formatted_uuid is unique instance id of the submission
    :param edited is a boolean that is true when submission was modified, and false when unchanged

    """

    #if its #edited, you will create a new one, and move the old one to the deprecated
    #if there is no uuid or uuid is blank, this means it's an initial submission. you will not create the deprecated element. just create a new uuid. 
    meta = create_xml_element_and_tag(None, 'meta', None)
    instanceId = create_xml_element_and_tag(meta, 'instanceID', None)

    if formatted_uuid is None: #uuid will be generated here when xlsx doesn't contain header _uuid
        formatted_uuid = generate_new_instance_id()[0]
        instanceId.text = formatted_uuid
    else:
        create_xml_element_and_tag(meta, 'deprecatedID', str(formatted_uuid))
        instanceId.text = str(generate_new_instance_id()[1])
        formatted_uuid = instanceId.text

    _uid.append(meta)

    return formatted_uuid


def extract_uuid(cell_value):
    """
    if uuid is not present in xlsx, it generates a uuid for the submission
    othrerwise, it extracts uuid from cell and returns it
    """
    formatted_uuid = None
 #   if not cell_value:  # if there is no uuid specified, new one will be generated
  #      formatted_uuid = generate_new_instance_id()[0] 
   # else:
    if cell_value:
        formatted_uuid = 'uuid:' + str(cell_value) #TODO CHANGED HERE
    return formatted_uuid


def create_xml_element_and_tag(parent, tag, text, namespace=None):
    if tag is None:
        raise Exception("Somethign went wrong.")
    
    if parent is None and text is None: 
        if namespace is None:
            new_element = ET.Element(tag) 
        else:
            new_element = ET.Element(tag, namespace) #only called for the nsmap dictionary
    elif parent is None: 
        new_element = ET.Element(tag)
        new_element.text = text
    elif text is None: 
        new_element = ET.SubElement(parent, tag)
    else:
        new_element = ET.SubElement(parent, tag)
        new_element.text = text

    return new_element



def process_data_in_columns( _uid, col_name, cell_value
):
    """
    creates the xml for a single submission which is represented in a single row in the xlsx

    :param _uid is the root element for the single submission that will be appended to as rows are parsed
    :param col_name is the header/label of the column in xlsx 
    :param cell_value i

    returns: 
    all_empty is a boolean that is true when the submission is blank and all questions have not been responded to
    formatted_uuid is the unique uuid for the submission
    """
    all_empty = None
    formatted_uuid = None
    if cell_value in [None, 'None', 'none']:
        cell_value = ""
    else:
        all_empty = False
    
    # if xlsx data is downloaded from kobo, it will contain this column
    if col_name == "_uuid":
        formatted_uuid = extract_uuid(cell_value)
    
    # column headers that include / indicate {group_name}/{question}
    elif len(col_name.split('/')) >= 2: 
        _uid = create_group(col_name.split('/'), str(cell_value), _uid)
    else: 
        if col_name in ['end', 'start']:
            #if cell_value:
                cell_value = cell_value.isoformat() if cell_value else ""

        create_xml_element_and_tag(_uid, col_name, str(cell_value)) 

    return all_empty, formatted_uuid


def is_geopoint_header(recent_question, col_name):
    """
    returns false if column header should be treated should be treated as a question and
    returns true if column header should be ignored since it is part of geopoint/geoline type
    used to filter out headers that follow pattern of _<question_name>_latitude etc. 
    """
    geopoint_patterns = r"_" + re.escape(recent_question) + r"_(latitude|longitude|altitude|precision)"
    return re.match(geopoint_patterns, col_name) is not None


def extract_submission_data(submission_data):
    formhub_uuid = submission_data["formhub_uuid"]
    __version__ = submission_data["__version__"]
    return formhub_uuid, __version__


def create_nsmap_dict(submission_data): 
    """ extracts version and asset uid from submission_data to create 
    dictionary containing them. this dictionary (nsmap_dict) will be used to create the first parent xml element 
    for a single submission """
    v = submission_data["version"]
    uid = submission_data["asset_uid"]
    nsmap_dict = {
        "id": str(uid),
        "version": str(v),
    }
    return nsmap_dict

# Iterate through cells in the row and create corresponding XML elements
def process_single_row(row, headers, added_on_headers_during_export, _uid):
    all_empty = True
    index = None
    recent_question = None
    #edited = False
    for col_num, cell_value in enumerate(row, start=1):
        col_name = headers[col_num - 1]
        if col_name == '_index': 
            index = str(cell_value)
       # if col_name == '$edited': 
        #    if cell_value: 
         #       edited = eval(str(cell_value)) #must be true or false
        if not col_name:
            continue
        geopoint = is_geopoint_header(str(recent_question), col_name)
        if geopoint or col_name in added_on_headers_during_export: 
            continue
        recent_question = col_name
        all_empty, formatted_uuid = process_data_in_columns(
            _uid, col_name, cell_value
        )
        if not all_empty: #all_empty should only be true when all cell values are blank
            all_empty = False 
        
    return index, formatted_uuid, all_empty

def initialize_elements():
    """
    creates and returns initial parent xml elements for data.
    root and results will be appended to as xlsx is parsed.
    """
    root = create_xml_element_and_tag(None, 'root', None)
    results = create_xml_element_and_tag(None, 'results', None)
    return root, results

def general_xls_to_xml(
    excel_file_path, submission_data, warnings=False
):
    """
    parses entire xlsx and creates xml from it
    returns root of the xml that can be used to transfer to kobo project
    """
    workbook = open_xlsx(excel_file_path)
    sheet = workbook.worksheets[
        0
    ]  # first sheet should have all data, if xlsx contains other sheets, they must be for repeat groups

    formhub_uuid, __version__= extract_submission_data(submission_data)
    nsmap_dict = create_nsmap_dict(submission_data)
    root, results = initialize_elements()
    headers = [cell.value for cell in sheet[1]]
    # columns automatically generated with kobo (this is after data has been downloaded from kobo)
    added_on_headers_during_export = ['_id', '_submission_time', '_validation_status', '_notes',	'_status',	'__version__', '_submitted_by', '_tags', '_index', '$edited']

#    if warnings:
#        kobo_xls_match_warnings(headers, submission_data)
    
    for  row in sheet.iter_rows(
            min_row=2,
            values_only=True,
        ):
        _uid = add_formhub_element(nsmap_dict, formhub_uuid)
        
        #check if submission xml needs to be created
        if not eval(str(row[headers.index('$edited')])): #currently all false or blank $edited submissions are being skipped
            continue 

        index, formatted_uuid, all_empty = process_single_row(row, headers, added_on_headers_during_export, _uid)        
        if all_empty:
            print(
                "Warning: Data may include one or more blank responses where no questions were answered."
            )
        # iterate through other sheets to create repeat groups, and append to xml
        _uid = new_repeat(_uid, workbook, index)
        formatted_uuid = add_version_and_meta_element(_uid, formatted_uuid, __version__)

        # for initial transfer (without uuids), each submission associated with index
        # index folder is renamed to uuid to complete transfer to kobo and associate attachment to specific response
        rename_media_folder(submission_data, formatted_uuid, index) 
        results.append(_uid)

    root =  add_prev_next(root)
    root.append(results)
    
    test_by_writing(root)
    workbook.close()
    return root

def test_by_writing(root):
    root = ET.ElementTree(root)
    root.write("./um.xml")

def add_version_and_meta_element(_uid, formatted_uuid, __version__):
    """
    creates xml elements at the end of submission stating version number and meta data
    """
    version_element = create_xml_element_and_tag(None, '__version__', __version__) 
    _uid.append(version_element)
    formatted_uuid = add_meta_element(_uid, formatted_uuid)
    return formatted_uuid

def add_prev_next(root):
    """
    creates xml elements that appear prior to the results data (count, next, previous) and appends it
    """
    create_xml_element_and_tag(root, 'next', None)
    create_xml_element_and_tag(root, 'previous', None)
    return root
