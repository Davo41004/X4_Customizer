'''
Change Log:
 * 0.9
  - Initial version, after a long evening of adapting X3_Customizer for X4.
  - Added first transform, Adjust_Job_Count.
'''
# Note: changes moved here for organization, and to make them easier to
# break out during documentation generation.

def Get_Version():
    '''
    Returns the highest version number in the change log,
    as a string, eg. '3.4.1'.
    '''
    # Traverse the docstring, looking for ' *' lines, and keep recording
    #  strings as they are seen.
    version = ''
    for line in __doc__.splitlines():
        if not line.startswith(' *'):
            continue
        version = line.split('*')[1].strip()
    return version