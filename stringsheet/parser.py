import os

from lxml import etree


def _is_root_valid(root):
    if root.tag != 'resources':
        return False
    return root.get('translatable', 'true').lower() == 'true'


def _is_string_valid(element):
    if element.tag != 'string':
        return False
    if 'name' not in element.attrib:
        return False
    return element.get('translatable', 'true').lower() == 'true'


def parse_file(source):
    """Parse the specified source and extract all found strings as a ``dict``.

    Args:
        source: The source object to parse. Can be any of the following:

            - a file name/path
            - a file object
            - a file-like object
            - a URL using the HTTP or FTP protocol

    Returns:
        dict: A dictionary with all the parsed strings mapped as 'id': 'text'.
    """
    tree = etree.parse(source)
    root = tree.getroot()

    if not _is_root_valid(root):
        return {}
    return {
        element.get('name'): element.text
        for element in root
        if _is_string_valid(element)
    }


def _is_file_valid(file):
    return file.endswith('.xml') and file != 'donottranslate.xml'


def parse_directory(directory):
    """Parse XML files located under the specified directory as strings dict.

    The directory argument usually should point to one of the 'values-lang'
    directories located under res directory of an Android project.

    Args:
        directory (str): The path to directory with XML files to parse.

    Returns:
        dict: A dictionary with all the parsed strings mapped as 'id': 'text'.
    """
    files = os.listdir(directory)
    xml_files = [file for file in files if _is_file_valid(file)]

    strings = {}
    for file in xml_files:
        file_name = directory + '/' + file
        strings.update(parse_file(file_name))
    return strings


def _is_language_valid(language):
    if language == 'default':
        # Special case for identifying strings in primary language
        return True

    # Language code might contain a country separator
    language, sep, country = language.partition('-r')

    if sep and (not country or len(country) != 2):
        # If there was a separator there also must be a country with a length
        # of 2 letters.
        return False

    # All language codes must be 2 letters long
    return len(language) == 2


def parse_resources(directory):
    """Parse all string resources located under the specified `directory``.

    This function assumes that the passed ``directory`` corresponds to the "res"
    directory of an Android project containing "values" directories with strings
    for each language.

    Args:
        directory (str): The path to res directory of an Android project
            containing values directories with strings for each language.

    Returns:
        dict: A dictionary of strings mapped by language and then by string id.
    """
    strings = {}
    for child_dir in os.listdir(directory):
        if not child_dir.startswith('values'):
            continue

        if child_dir == 'values':
            language = 'default'
        else:
            _, _, language = child_dir.partition('-')

        if not _is_language_valid(language):
            continue

        language_strings = parse_directory(directory + '/' + child_dir)
        if language_strings:
            strings[language] = language_strings

    return strings


def get_languages(strings):
    return sorted([it for it in strings.keys() if it != 'default'])


def create_language_sheet_values(strings, language):
    column_names = ['id', 'comment', 'default', language]
    result = [column_names]

    default_strings = strings['default']
    for string_id in sorted(default_strings):
        row = [string_id, None, default_strings[string_id]]
        language_strings = strings[language]
        if string_id in language_strings:
            row.append(language_strings[string_id])
        else:
            row.append(None)
        result.append(row)

    return result


def create_spreadsheet_values(strings):
    """Create strings array that can be used to execute API calls.

    Args:
        strings (dict): A dictionary with strings parsed from Android XML
            strings files.

    Returns:
        list: List of spreadsheet rows and columns.
    """
    languages = get_languages(strings)
    column_names = ['id', 'comment', 'default'] + languages
    result = [column_names]

    default_strings = strings['default']
    for string_id in sorted(default_strings):
        column = [string_id, None, default_strings[string_id]]
        for language in languages:
            language_strings = strings[language]
            if string_id in language_strings:
                column.append(language_strings[string_id])
            else:
                column.append(None)
        result.append(column)

    return result


def parse_spreadsheet_values(values):
    """Parse the result returned by Google Spreadsheets API call.

    Args:
        values (dict): The json values data returned by Google Spreadsheets API.

    Returns:
        dict: A dictionary of strings mapped by language and then by string id.
    """
    title_row = values[0]

    strings_by_language = {}

    for lang_index in range(2, len(title_row)):
        language = title_row[lang_index]

        language_strings = {}
        for row in values[1:]:
            column_count = len(row)
            if column_count < 3:
                # Actual strings shouldn't be separated by an empty row.
                break

            translation = row[lang_index] if column_count > lang_index else ''
            string_id = row[0]
            default_text = row[2]

            if not string_id or not default_text:
                # All strings must have id and a default text.
                break

            if ' ' in string_id:
                # String ids can't contain whitespace characters.
                # TODO: Check for more invalid characters
                break

            language_strings[string_id] = translation

        strings_by_language[language] = language_strings

    return strings_by_language
