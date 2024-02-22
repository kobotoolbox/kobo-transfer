import string
from datetime import datetime
from xml.etree import ElementTree as ET
import openpyxl
import pandas as pd
from dateutil import parser
import requests
from helpers.config import Config
from transfer.xml import get_src_submissions_xml
from .media import rename_media_folder
from .xml import generate_new_instance_id


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


def formhub_element(uid, NSMAP, formhub_uuid):
    """creates formhub element with nested uuid"""
    _uid = ET.Element(uid, NSMAP)
    fhub_el = ET.SubElement(_uid, "formhub")
    uuid_el = ET.SubElement(fhub_el, "uuid")
    uuid_el.text = formhub_uuid
    return _uid


def meta_element(_uid, formatted_uuid):
    """meta tag
          <meta>
                <instanceID>uuid:a0ea37ef-ac71-434b-93b6-1713ef4c367f</instanceID>
                <deprecatedID>
            </meta>
    }"""
    meta = ET.Element("meta")
    if formatted_uuid == "uuid:":
        formatted_uuid = generate_new_instance_id()[1]
    instanceId = ET.SubElement(meta, "instanceID")
    deprecatedId = ET.SubElement(meta, "deprecatedID")
    instanceId.text = formatted_uuid
    deprecatedId.text = formatted_uuid
    _uid.append(meta)
    return formatted_uuid


def single_submission_xml(_uid, col_name, cell_value, all_empty, formatted_uuid
):

    if cell_value is None or cell_value == "none" or cell_value == "None":
        cell_value = ""
    else:
        all_empty = False

    # if xlsx data is downloaded from kobo, it will contain this column
    if col_name == "_uuid":
        if cell_value == "":  # if there is no uuid specified, new one will be generated
            formatted_uuid = formatted_uuid + generate_new_instance_id()[1]
        else:
            formatted_uuid = formatted_uuid + str(cell_value)

    # column headers that include / indicate {group_name}/{question}
    group_arr = col_name.split("/")
    if len(group_arr) >= 2: #TODO MAKE SURE IT DEALS W NESTED GROUPS
       # _uid = group_element(_uid, str(col_name), str(cell_value))
        _uid = nested_group_element(_uid, group_arr, str(cell_value))
        return all_empty, formatted_uuid

    if not (
        col_name.startswith("_")
    ):  # columns automatically generated with kobo (this is after data has been downloaded from kobo)
        cell_element = ET.SubElement(_uid, col_name)
        if col_name == "end" or col_name == "start":
            if cell_value != "":
                cell_value = cell_value.isoformat()
        cell_element.text = str(cell_value)

    return all_empty, formatted_uuid


def t_general_xls_to_xml(excel_file_path, submission_data, gtransfer=False, warnings=False
):
    workbook = open_xlsx(excel_file_path)
    sheet = workbook.worksheets[
        0
    ]  # first sheet should have all data, if xlsx contains other sheets, they must be for repeat groups

    uid = submission_data["asset_uid"]
    formhub_uuid = submission_data["formhub_uuid"]
    v = submission_data["version"]
    __version__ = submission_data["__version__"]

    root = ET.Element("root")
    results = ET.Element("results")
    headers = [cell.value for cell in sheet[1]]

    num_results = 0
    NSMAP = {
        "xmlns:jr": "http://openrosa.org/javarosa",
        "xmlns:orx": "http://openrosa.org/xforms",
        "id": str(uid),
        "version": str(v),
    }
    

    for row_num, row in enumerate(
        sheet.iter_rows(
            min_row=2,
            values_only=True,
        ),
        start=2,
    ):
        _uid = formhub_element(uid, NSMAP, formhub_uuid)

        all_empty = True
        formatted_uuid = "uuid:"

        index = None
        # Iterate through cells in the row and create corresponding XML elements
        for col_num, cell_value in enumerate(row, start=1):
            col_name = headers[col_num - 1]
            if col_name == '_index': 
                index = str(cell_value)
            if col_name == "":
                continue
            all_empty, formatted_uuid= single_submission_xml(
                _uid, col_name, cell_value, all_empty, formatted_uuid
            ) 

        # iterate through other sheets to create repeat groups, and append to xml
        print(index)
        repeat_elements = new_repeat(_uid, formatted_uuid, workbook, index)
        #_repeat = ET.ElementTree(repeat_elements)
        #_repeat.write("xm.xml")

        if repeat_elements != None:
            _uid = repeat_elements

        version = ET.Element("__version__")
        version.text = __version__
        _uid.append(version)

        formatted_uuid = meta_element(_uid, formatted_uuid)

        # for initial transfer (without uuids), attachments are saved with row numbers
        # row number folder is renamed to uuid to complete transfer to kobo and associate attachment to specific response
       # rename_media_folder(submission_data, formatted_uuid[len("uuid:") :], row_num)
        results.append(_uid)
        num_results += 1

    count = ET.SubElement(root, "count")
    count.text = str(num_results)
    next = ET.SubElement(root, "next")
    next.text = None
    previous = ET.SubElement(root, "previous")
    previous.text = None
    root.append(results)

    root = ET.ElementTree(root)
    root.write("./fullsubmission.xml")
    workbook.close()
    
    return root


def nested_group_element(_uid, group_name, cell_value):
    parent_group = _uid
    #if (_uid == None):
     #   parent_group = ET.Element(group_name[0]) 
      #  group_name = group_name[1:]
    group_element = None
    for group in group_name: 
        if parent_group.tag == group:
            continue
    
        group_element = _uid.find(".//" + group)

        if (group_element == None):
            group_element = ET.SubElement(parent_group, group)

        if (group == group_name[-1]): #last element in group_name is the question
            group_element.text = str(cell_value)
        
        parent_group = group_element
        group_element = None
    
    return _uid



def group_section(group_name, cell_value):
    #group_name = group.split("/")
    initial = ET.Element(group_name[0]) 
    group_name = group_name[1:] #root is initial, search for elements after it when you use .find//
    #alternatively you can do the cnotinue thing... that you did in nested
    
    parent_group = initial
    group_element = None
    for group in group_name: 
        #if group == group_name[0]: #this is parent group
         #   parent_group = ET.Element(group)
        group_element = parent_group.find(".//" + group) 
        if (group_element == None):
            group_element = ET.SubElement(parent_group, group)
        
        if (group == group_name[-1]): #last element in group_name is the question
            group_element.text = str(cell_value)
        
        parent_group = group_element
        group_element = None

    return initial

def find_n(xml, n, element_name):
    occurrences = 0
    for element in xml.iter(element_name):
        occurrences += 1
        if occurrences == int(n):
            return element
    return None

def new_repeat(submission_xml, uuid, workbook, submission_index):
        """method is called when there are multiple sheets in xlsx, because it is assumed to be repeat groups"""
        uuid = uuid[len("uuid:") :]
        sheet_names = workbook.sheetnames 
        sheet_names = sheet_names[1:]

        original_indexes = [] #cleared every time its a new sheet. 

        for sheet_name in sheet_names:
            new_indexes = []
            sheet = workbook[sheet_name]
            headers = [cell.value for cell in sheet[1]] 
            try:
               # submission_uid_header = headers.index("_submission__uuid")
                index_header = headers.index("_index")
                parent_index_header = headers.index('_parent_index')
            except Exception:
                print(
                    "Error: if xlsx file has multiple tabs, data in extra sheets must be in expected repeating group format"
                )
                raise

            question_headers = [item for item in headers if not item.startswith('_')] #question headers should be the same for a single sheet

            for row in sheet.iter_rows(min_row=2, values_only=True):
                mini_group = None
                #submission_uid = str(row[submission_uid_header])
                index = str(row[index_header])
                parent_index = str(row[parent_index_header]) #this is the current value

                if str(sheet_name) == str(sheet_names[0]): #this is only for the first sheet, because the parent is the uuid submission
                    if parent_index != submission_index: 
                        continue
                    else: 
                        original_indexes.append(index) #first sheet, makes sure this is not empty.. 
    

                else: #if its another sheet, you have to see if its part of the original indexes
                    if parent_index not in original_indexes:
                        continue
                    else: 
                        new_indexes.append(index)
                
                for col_name in question_headers: 
                    col_num = headers.index(col_name)
                    cell_value = str(row[col_num])

                    if cell_value is None or cell_value == "none" or cell_value == "None":
                        cell_value = ""

                    group_names = col_name.split('/')

                    index_of_sheet_group = group_names.index(str(sheet_name))
                    if mini_group == None: 
                        mini_group = group_section(group_names[index_of_sheet_group:], str(cell_value))
                    else:
                        mini_group = nested_group_element(mini_group, group_names[index_of_sheet_group:], str(cell_value))
                
                if (str(sheet_name) == group_names[0]): #if its the first sheet, you will append mini_group. 
                    submission_xml.append(mini_group)


                if (str(sheet_name) != group_names[0]): #if its not the first sheet/first parent element
                    um = question_headers[0].split('/')

                    #TODO
                    #THE TAG U ARE PASISNG IN IS RISKY. WHAT IFONE OF THE REPEAT GROUPS IS UNDER A DIFFERENT PATH... IT COULD BE TBH. 
                    #U SHOULD ACCOUNT FOR IT
                    #WAIT FOR A RESPONSE... 
                    element = find_n(submission_xml, original_indexes.index(parent_index) + 1, um[index_of_sheet_group-1])
                    #print("LAST ONE B4 TRACEBACK")
                    #print(parent_index)
                    first = ET.ElementTree(submission_xml)
                    first.write("trace.xml") #first sheet, first xml, no S subgroup

                    element.append(mini_group)

                if row == sheet.max_row:
                    original_indexes = new_indexes

        return submission_xml




def repeat_sheet(sheet, headers, target_uuid, current_uuid, question_headers): #this is function i made for the firstr sheet lol
    xml_dict = {}

    parent_header = headers.index('_parent_index')
    parent_index = None
    #parent_index = sheet.cell(row = 2, column = parent_header).value #this is the parent index of the first 

    for row in sheet.iter_rows(min_row=2, values_only=True):
        group_section = None

        if target_uuid != current_uuid: 
            continue
        
        if parent_index == None: #this should only be the first time
            parent_index = row[parent_header]
        
        #parent_index will always be the same for the first sheet

        for question in question_headers:
            col_num = headers.index(question)
            cell_value = str(row[col_num])

            if group_section == None: 
                group_section = group_section(question, cell_value) #xml from the top <op5>
            else: #group section will be no longer be none, when uve created the op5 element already. this is for second question in question header
                group_section = nested_group_element(group_section, question, cell_value)
        
        #done with a single row, so you want to put the index in it yk. 
        xml_dict[parent_index] == group_section
    
    return xml_dict    



def find_last_common_element(root1, root2):
    common_element = None
    
    # Get iterators for both XML trees
    iter1 = root1.iter()
    iter2 = root2.iter()
    
    # Iterate through both trees simultaneously
    for elem1, elem2 in zip(iter1, iter2):
        if elem1.tag == elem2.tag:
            common_element = elem1
        else:
            # Elements diverged, break the loop
            break
    
    return common_element



"""

def repeat_try(submission_xml, uuid, workbook):
    method is called when there are multiple sheets in xlsx, because it is assumed to be repeat groups
    uuid = uuid[len("uuid:") :]
    sheet_names = workbook.sheetnames 
    sheet_names = sheet_names[1:]

    xml_dict = {}
    
    for sheet_name in sheet_names:
        sheet = workbook[sheet_name]
        headers = [cell.value for cell in sheet[1]] 
        
        try:
            submission_uid_header = headers.index("_submission__uuid")
            index_header = headers.index("_index")
            parent_index_header = headers.index('_parent_index')
        except Exception:
            print(
                "Error: if xlsx file has multiple tabs, data in extra sheets must be in expected repeating group format"
            )
            raise

        question_headers = [item for item in headers if not item.startswith('_')] #question headers should be the same for a single sheet
#       print(question_headers)

        if sheet_name == sheet_names[0]: #if its the first sheet, call another method
            xml_dict = repeat_sheet(sheet, headers, uuid, submission_uid, question_headers)
            continue
            #you have xml_dict with the indexes that you want...

        initial_parent_index = None #lets say we are dealing with 1 first. 
        same_parent = []

        #now you are starting at the second sheet
        for row in sheet.iter_rows(min_row=2, values_only=True):
            submission_uid = str(row[submission_uid_header])
            index = str(row[index_header])
            parent_index = str(row[parent_index_header]) #this is the current value

            if (parent_index not in xml_dict.keys()):
                continue

            if initial_parent_index == None: #this should only be the first time (only happens once)
                initial_parent_index = parent_index 

            xml_group = xml_dict[initial_parent_index] #get the relevant xml_group. this is the 1 index group.. 
            group = None
            if initial_parent_index == parent_index: #this means we are dealing w same xml group, just creating sections, and appending to it, lets say this is 1 for the first row. 
                #this row's parent index is 1
                for col_name in question_headers: 
                    col_num = headers.index(col_name)
                    cell_value = str(row[col_num])
                # "group_op5ep98/group_wm95d90/group_sw2vc60/nested_x_2_within_re_p_this_also_repeats"
                    if group == None: 
                        group = group_section(col_name, cell_value) #this should create it from the top
                    else: 
                        group = nested_group_element(group, col_name, cell_value) #for the columns this works. 
            #you have this rows, thing creatd from the top.... 
            same_parent.append(group)

            #last_common = find_last_common_element(xml_group, group)


            
            else:
                #suddenly we are at parent_index 2... 
                #initial is still index 1, therefore xml group is still index 1
                last_common = find_last_common_element(xml_group, same_parent[0]) #same_parent arbitrarily chosen
                #this last common will be wm>>
                for gr in same_parent: 
                    xml_group = xml_group.find(".//" + last_common).append(gr)

                same_parent = []
                del xml_dict[initial_parent_index]
                xml_dict[]




                    last_common.append(gr)
                
                

                #append it


            

                    #the issue here is
                    #but for the NEXT ROW. we do not want to find the group sw2vc60, we want to create a new sw2
                    # 
                    # 
                    # so lets say for the next group_sw2vc60 row


                    #if sheet_xml_element == None:
                     #   sheet_xml_element = create_section(col_name, cell_value)
                    #else: 
                     #   sheet_xml_element = nested_group_element(sheet_xml_element, col_name, cell_value)

            #now you've created it sheet_xml_element for one row. 
            #you want to append this to the xml_group
            #you want to append S INTO W. 




            #next row, you will get relevent xml_group. 
            

                


            
            if parent_index != initial_parent_index:
                xml_dict[parent_index-1] 
                del xml_group

                #we have moved on... 
                #you are done working with this xml group. 
                #replace it in the xml_dict

            else:
                #

        
            
            parent_group = None
            if sheet_name != sheet_names[0]:
                parent_group = xml_dict.get(str(parent_index)) #initially this is going to be none, because there is nothing in the xml_dict, sheet 1
           
            if parent_group == None:
                print(sheet_name)
                print(parent_index)
            #if (sheet_name == sheet_names[1] and parent_group != None):
             #   first = ET.ElementTree(parent_group)
              #  first.write("help.xml") #first sheet, first xml, no S subgroup
            #next sheet
            #u will get a group based on the parent_index, pass that in and build upon it. 


            for col_name in question_headers: 
                col_num = headers.index(col_name)
                cell_value = str(row[col_num])

                if parent_group == None: #parent_group will be None, create from the TOPPPPPPPP. 
                    #parent_group will be None, for every row in the first sheet. 
                    parent_group = group_section(str(col_name), cell_value) #first sheet, first q going to be created



                else: #when parent group is not None, you have grabbed a parent. this needs to be second sheet onwards. 
                    parent_group = nested_group_element(parent_group, str(col_name), cell_value) #first sheet, second q, going to be assigned to group (THIS WHOLE ROW XML DONE)
        
            if sheet_name != sheet_names[0]:
                if parent_index in xml_dict:
                    del xml_dict[parent_index]
    
            #ok so this was correct
            #problem is that parent_index is the fuckin same for the first sheet. 


            #when you are in hte next sheet... 
            #thats when you need to start changing the values.

            #now you have this new, and edited parent group. 
            #put that in the dictionary with a new index. 

            xml_dict[index] = parent_group


                #first = ET.ElementTree(group)
                #first.write("first.xml") #first sheet, first xml, no S subgroup



            #index of the header, is the enumerated col_num-1

            #but for each row, we need to get the cell_value for the question_headers only

            print(xml_dict)
        #break #so if you bring this break statement back
        #if you only do ONE sheet, the elements under <wm> come back. but as soon as you do more. it gets overwritten. why.... \

            

            
                   for col_num, cell_value in enumerate(row, start=1):
                #only rows looked at will be for this submission
                
                col_name = str(headers[col_num - 1])
                if (col_name.startswith('_')):
                    continue


                #group_arr = col_name.split("/")
                if len(xml_dict) == 0: 
                    group = group_section(str(col_name), cell_value)
                    xml_dict[index] = group

                    
                    first = ET.ElementTree(group)
                    first.write("first.xml") #first sheet, first xml, no S subgroup
                     
                else:
                    print(xml_dict)
                    parent_group = xml_dict.get(parent_index)
                    if (parent_group == None):
                        group = group_section(str(col_name), cell_value)
                        xml_dict[index] = group
                    else:
                        group = nested_group_element(parent_group, str(col_name), cell_value)
                        del xml_dict[parent_index]
                        xml_dict[index] = group
      

    for group_xml in xml_dict.values():
        submission_xml.append(group_xml) 
    
    return submission_xml
        
    """


        #you want to check if there are multiple sheets 
        #go into the next sheet, pass in the index number in question. 
        #if an element has a parent_index of that value, thats what ur workin w (SO PARENT INDEX IS ALL 1 RN LETS SAY)

        #group_op5ep98/group_wm95d90/Enter_a_number_neste_does_not_repeat_tho

        # pass in boolean of new = True
        # pass in _uid lets say 
        #group op doesn't exist, so you create it
        #wm doesnt exist, so you create it, 
        #enter num doesnt exist, so you create it and add the cell value

        #new loop iter
        #pass in _uid, but this time, because its a new row 
        #do the same, create everything u just created

        #NEW SHEET

        #group_op5ep98/group_wm95d90/group_sw2vc60/nested_x_2_within_re_p_this_also_repeats
        #


        #ok how about this
        #create a list
        #you've been passed in an index already from the initial sheet 
        #look for the elements that are parent index, and create this section
        #put the op5 element in a list
        #so for the first row initial (first uuid), ur gonna have TWO elements in it (maybe have it be a dictionary or smth, cuz u want it to be easy lookup)



        #then the next sheet will be opend (next loop) 
        #loop through the vlaues in the 

        #now ur gonna go into the sheet, look for parent index 






"""
      #  _uid = ET.ElementTree(_uid)
      # _uid.write("uid.xml")

        # iterate through other sheets to create repeat groups, and append to xml
        repeat_elements = repeat_groups(_uid, formatted_uuid, workbook)
#        _repeat = ET.ElementTree(repeat_elements)
 #       _repeat.write("xm.xml")

        if repeat_elements != None:
            _uid = repeat_elements

        version = ET.Element("__version__")
        version.text = __version__
        _uid.append(version)

        formatted_uuid = meta_element(_uid, formatted_uuid)

        # for initial transfer (without uuids), attachments are saved with row numbers
        # row number folder is renamed to uuid to complete transfer to kobo and associate attachment to specific response
        rename_media_folder(submission_data, formatted_uuid[len("uuid:") :], row_num)
        results.append(_uid)
        num_results += 1


    count = ET.SubElement(root, "count")
    count.text = str(num_results)
    next = ET.SubElement(root, "next")
    next.text = None
    previous = ET.SubElement(root, "previous")
    previous.text = None
    root.append(results)

    root = ET.ElementTree(root)
    root.write("./um.xml")
    workbook.close()
    
    return root

"""