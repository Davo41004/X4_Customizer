
from lxml import etree as ET
from ..Common import Settings, Print

'''
Notes on duplicated extension IDs:
    X4 will load extensions with duplicate ids, but gets buggy on
    how it handles them.
    These IDs are used for two things:
    1) Dependency references will only point to the first (alphabetical folder
       name) extension with an id match.
    2) Changing extension enable state (from default) will only work on
       the first ID match.
       The user content.xml only saves a single element for an ID.
       In game, later extensions cannot have their enable flag flipped
       in the UI.
'''

class Extension_Summary:
    '''
    Class to summarize a found extension, and some picked out details.

    Attributes:
    * content_xml_path
      - Path to the content.xml file for the extension.
    * content_xml
      - XML Element holding the contents of content.xml, used in some
        misc lookup methods.
    * extension_name
      - String, name of the containing folder, lowercase.
      - Should be unique across extensions.
    * ext_id
      - ID of this extension, as found in the content.xml id attribute.
      - May be non-unique across extensions, though in x4 this leads
        to bugs with dependencies (only the last ID match found will
        be considered dependent) and with enabling/disabling mods
        (only the last ID match can be flipped out of its default
        state).
      - Is case sensitive in X4.
    * display_name
      - String, the name to display for the extension.
    * enabled
      - Bool, True if this extensions is enabled, else False.
    * default_enabled
      - Bool, if the extension is enabled by default.
    * is_current_output
      - Bool, True if this extension is the customizer output.
    * soft_dependencies
      - List of ids of other extensions this extension
        has a soft (non-error if missing) dependency on.
    * hard_dependencies
      - As above, but dependencies that will throw an error if missing.
    '''
    def __init__(
            self, 
            ext_id,
            content_xml_path, 
            content_xml,
            enabled, 
            default_enabled,
            is_current_output,
            soft_dependencies,
            hard_dependencies,
        ):
        self.ext_id = ext_id
        self.content_xml_path = content_xml_path
        self.extension_name = content_xml_path.parent.name.lower()
        self.content_xml = content_xml
        self.enabled = enabled
        self.default_enabled = default_enabled
        self.is_current_output = is_current_output
        self.soft_dependencies = soft_dependencies
        self.hard_dependencies = hard_dependencies

        self.display_name = self.Get_Attribute('name')
        return


    def Get_Attribute(self, attribute, default = ''):
        '''
        Return the string value of a given attribute.
        This will search the language node first, then the root node.
        If not found, returns an empty string.
        '''
        node = self.content_xml.find('text[@language="44"][@{}]'.format(attribute))
        if node != None:
            value = node.get(attribute, default)
        else:
            value = self.content_xml.get(attribute, default)
        return value
    

    def Get_Bool_Attribute(self, attribute, default = True):
        '''
        Returns a bool value of a given attribute.
        '''
        attr_str = self.Get_Attribute(attribute, '')
        if not attr_str:
            return default
        # Handle simple integers and bool expressions.
        if attr_str.lower() in ['true','1']:
            return True
        elif attr_str.lower() in ['false','0']:
            return False
        else:
            # As a backup, just return the default.
            # TODO: maybe warn on this case.
            return default


def Find_Extensions():
    '''
    Returns a list of Extension_Summary objects, representing all
    found extensions, enabled or disabled.
    '''    
    ext_summary_list = []

    # Need to figure out which extensions the user has enabled.
    # The user content.xml, if it exists (which it may not), will
    #  hold details on custom extension enable/disable settings.
    # Note: by observation, the content.xml appears to not be a complete
    #  list, and may only record cases where the enable/disable selection
    #  differs from the extension default.
    user_extensions_enabled = {}
    content_xml_path = Settings.Get_User_Content_XML_Path()
    if content_xml_path.exists():
        # (lxml parser needs a string path.)
        content_root = ET.parse(str(content_xml_path)).getroot()
        for extension_node in content_root.xpath('extension'):
            name = extension_node.get('id')
            if extension_node.get('enabled') in ['true','1']:
                user_extensions_enabled[name] = True
            else:
                user_extensions_enabled[name] = False
                

    # Note the path to the target output extension content.xml.
    output_content_path = Settings.Get_Output_Folder() / 'content.xml'

    # Note extension ids found, to detect non-unique cases that
    # can cause problems.
    ext_ids_found = set()

    # Find where these extensions are located, and record details.
    # Could be in documents or x4 directory.
    for base_path in [Settings.Get_X4_Folder(), Settings.Get_User_Folder()]:
        extensions_path = base_path / 'extensions'

        # Skip if there is no extensions folder.
        if not extensions_path.exists():
            continue

        # Use glob to pick out all of the extension content.xml files.
        for content_xml_path in extensions_path.glob('*/content.xml'):

            # Load it and pick out the id.
            content_root = ET.parse(str(content_xml_path)).getroot()
            ext_id = content_root.get('id')
            
            # Warning for multiple same-name extensions.
            if ext_id in ext_ids_found:
                # TODO: what is the best way to signal this?
                # Can just send to Print for now.
                Print(('Warning: duplicate extension id "{}" found, in'
                       ' folder {}').format(ext_id, content_xml_path.parent.name))
            ext_ids_found.add(ext_id)
                            
            # Determine if this is enabled or disabled.
            # If it is in user content.xml, use that flag, else use the
            #  flag in the extension.

            # Apparently a mod can use '1' for this instead of
            # 'true', so try both.
            # TODO: move this into the ext_summary constructor.
            default_enabled =  content_root.get('enabled', 'true').lower() in ['true','1']
            if ext_id in user_extensions_enabled:
                enabled = user_extensions_enabled[ext_id]
            else:
                enabled = default_enabled

                
            # Collect all the names of dependencies.
            # Lowercase these to standardize name checks.
            dependencies = [x.get('id')
                            for x in content_root.xpath('dependency')]
            # Collect optional dependencies.
            soft_dependencies = [x.get('id') 
                            for x in content_root.xpath('dependency[@optional="true"]')]
            # Pick out hard dependencies (those not optional).
            hard_dependencies = [x for x in dependencies
                                    if x not in soft_dependencies ]

            ext_summary_list.append( Extension_Summary(
                ext_id            = ext_id,
                content_xml_path  = content_xml_path, 
                content_xml       = content_root,
                enabled           = enabled, 
                default_enabled   = default_enabled,
                is_current_output = content_xml_path == output_content_path,
                soft_dependencies = soft_dependencies,
                hard_dependencies = hard_dependencies,
                ))
                        
    return ext_summary_list
                
