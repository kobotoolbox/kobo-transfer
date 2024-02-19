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

def nested_group_element(_uid, group, cell_value):
    group_name = group.split("/")
    parent_group = _uid
    group_element = None
    for group in group_name: 
        group_element = _uid.find(".//" + group)
        if (group_element == None):
            group_element = ET.SubElement(parent_group, group)

        if (group == group_name[-1]):
            group_element.text = str(cell_value)
        
        parent_group = group_element
        group_element = None
    return _uid


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
            if submission_uid == uuid:
                element = ET.SubElement(submission_xml, sheet_name)
            for col_num, cell_value in enumerate(row, start=1):
                col_name = str(headers[col_num - 1])
                group_arr = col_name.split("/")

                if cell_value is None or cell_value == "none" or cell_value == "None":
                    cell_value = ""

                if len(group_arr) == 2 and sheet_name in col_name:
                    if submission_uid == uuid:
                        group_element = ET.SubElement(element, group_arr[1])
                        group_element.text = str(cell_value)
    
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
        _uid = nested_group_element(_uid, str(col_name), str(cell_value))
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
        # Iterate through cells in the row and create corresponding XML elements
        for col_num, cell_value in enumerate(row, start=1):
            col_name = headers[col_num - 1]
            if col_name == "":
                continue
            all_empty, formatted_uuid = single_submission_xml(
                gtransfer, _uid, col_name, cell_value, all_empty, formatted_uuid
            )

        if all_empty:
            print(
                "Warning: Data may include one or more blank responses where no questions were answered."
            )

        # iterate through other sheets to create repeat groups, and append to xml
        repeat_elements = repeat_groups(_uid, formatted_uuid, workbook)
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

    workbook.close()
    
    return root
