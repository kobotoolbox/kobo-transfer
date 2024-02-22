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

"""
def nested_group_element(_uid, group, cell_value):
    group_name = group.split("/")
    parent_group = _uid
    group_element = None
    for group in group_name: 
        group_element = _uid.find(".//" + group)

        if (group_element == None):
            group_element = ET.SubElement(parent_group, group)
        
        if (group == group_name[-1]): #last element in group_name is the question
            group_element.text = str(cell_value)
        
        parent_group = group_element
        group_element = None
    return _uid
"""


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

        if (group_element is None):
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
        if (group_element is None):
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
                    if mini_group is None: 
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
                   # first = ET.ElementTree(submission_xml)
                    #first.write("trace.xml") #first sheet, first xml, no S subgroup

                    element.append(mini_group)

                if row == sheet.max_row:
                    original_indexes = new_indexes

        return submission_xml


"""
def group_element(_uid, group, cell_value):
#creates logical groups in xml for kobo
    group_name = group.split("/")
    element = _uid.find(".//" + group_name[0])
    if element == None:
        element = ET.SubElement(_uid, group_name[0])

    if group_name[0] != group_name[1]:
        group_element = ET.SubElement(element, group_name[1])
        group_element.text = str(cell_value)

    return _uid
"""






def kobo_xls_match_warnings(xls_questions, submission_data):
    config_src = Config().src
    xml_url = config_src["xml_url"] + f"?limit={30000}"
    kobo_form_xml = get_src_submissions_xml(xml_url)
    uid = submission_data["asset_uid"]
    uid_element = kobo_form_xml.find(f".//{uid}")

    kobo_form_questions = []
    lowercase_no_punctuation_koboq = []

    for subelement in uid_element:
        kobo_form_questions.append(subelement.tag)
        lower_no_punct_k = subelement.tag.lower()
        lower_no_punct_k = "".join(
            char for char in lower_no_punct_k if char not in string.punctuation
        )
        lower_no_punct_k = lower_no_punct_k.replace(" ", "")
        lowercase_no_punctuation_koboq.append(lower_no_punct_k)

    xls_questions = [
        element for element in xls_questions if not element.startswith("_")
    ]
    lowercase_no_punctuation_xlsq = []
    for question in xls_questions:
        lower_no_punct_q = question.lower()
        lower_no_punct_q = "".join(
            char for char in lower_no_punct_q if char not in string.punctuation
        )
        lower_no_punct_q = lower_no_punct_q.replace(" ", "")
        lowercase_no_punctuation_xlsq.append(lower_no_punct_q.lower())

    elements_to_remove = [
        "formhub",
        "__version__",
        "version",
        "meta",
        "start",
        "end",
        "Timestamp",
    ]
    for element in elements_to_remove:
        if element in kobo_form_questions:
            kobo_form_questions.remove(element)
        if element in lowercase_no_punctuation_koboq:
            lowercase_no_punctuation_koboq.remove(element)
        if element in xls_questions:
            xls_questions.remove(element)
        if element in lowercase_no_punctuation_xlsq:
            lowercase_no_punctuation_xlsq.remove(element)

    # check if number of questions in kobo form, and number of questions in xls match
    if len(kobo_form_questions) != len(xls_questions):
        print(
            "Warning: number of questions in kobo form might not match number of questions in xls"
        )
    elif kobo_form_questions != xls_questions:
        # if standardised is same, but original is different
        if lowercase_no_punctuation_koboq != lowercase_no_punctuation_xlsq:
            print(
                "Warning: Question labels in kobo and XLS form have slight differences. Check if capitalisation, punctuation, and spacing are consistent."
            )
        else:
            # same number of questions but different labels
            print(
                "Warning: question labels in kobo form do not match xls labels exactly"
            )


def repeat_groups(submission_xml, uuid, workbook):
    """method is called when there are multiple sheets in xlsx, because it is assumed to be repeat groups"""
    uuid = uuid[len("uuid:") :]
    sheet_names = workbook.sheetnames 
    sheet_names = sheet_names[1:]
    for sheet_name in sheet_names:
        sheet = workbook[sheet_name]
        headers = [cell.value for cell in sheet[1]] 
        try:
            submission_uid_header = headers.index("_submission__uuid")
        except Exception:
            print(
                "Error: if xlsx file has multiple tabs, data in extra sheets must be in expected repeating group format"
            )
            raise
        for row in sheet.iter_rows(min_row=2, values_only=True):
            submission_uid = str(row[submission_uid_header])
            #if submission_uid == uuid:
             #   ET.SubElement(submission_xml, sheet_name) #creates parent_group xml element 
            for col_num, cell_value in enumerate(row, start=1):
                col_name = str(headers[col_num - 1])
                group_arr = col_name.split("/")

                if cell_value is None or cell_value == "none" or cell_value == "None":
                    cell_value = ""
        
                if len(group_arr) >= 2 and sheet_name in col_name: #these are the columns that contain questions 
                    if submission_uid == uuid:
                        nested_group_element(submission_xml, group_arr, cell_value)
    
    return submission_xml



def initial_repeat(_uid, col_arr, cell_value):
    """When xlsx data doesn't have a uuid (initial transfer to kobo), repeating group responses created with this method.
    All questions in repeat group should have an equal number of responses, even if a response is blank. If question 1 in repeating group responses are {a, b, c},
    question 2 responses need to have same number so indices match {1,,3}
    expected label to indicate repeat group: repeat/{group_name}/{question}
    """
    # repeat/group_name/question
    group_name = col_arr[1]
    responses = cell_value.split(",")
    elements = _uid.findall(".//" + group_name)
    if not elements:
        # when initial group doesn't exist, create element with group name, and subelement with question label and response
        for response in responses:
            element = ET.SubElement(_uid, group_name)
            subelement = ET.SubElement(element, col_arr[2])
            subelement.text = response
    else:
        if len(elements) != len(responses):
            raise Exception(
                "Repeat group transfer failed. They should be saved in order with commas seperating each repeat response. No response should have a comma within it."
            )
        for group_el, response in zip(elements, responses):
            subelement = ET.SubElement(group_el, col_arr[2])
            subelement.text = response

    return _uid


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


def single_submission_xml(
    gtransfer, _uid, col_name, cell_value, all_empty, formatted_uuid
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


def general_xls_to_xml(
    excel_file_path, submission_data, gtransfer=False, warnings=False
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

    if warnings:
        kobo_xls_match_warnings(headers, submission_data)

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
            all_empty, formatted_uuid = single_submission_xml(
                gtransfer, _uid, col_name, cell_value, all_empty, formatted_uuid
            )

        if all_empty:
            print(
                "Warning: Data may include one or more blank responses where no questions were answered."
            )
      #  _uid = ET.ElementTree(_uid)
      # _uid.write("uid.xml")

        # iterate through other sheets to create repeat groups, and append to xml
        repeat_elements = new_repeat(_uid, formatted_uuid, workbook, index)
#        _repeat = ET.ElementTree(repeat_elements)
 #       _repeat.write("xm.xml")

        if repeat_elements is not None:
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
    #root.write("./um.xml")
    workbook.close()
    
    return root
