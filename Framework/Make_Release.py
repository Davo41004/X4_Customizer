'''
Creates a zip file with all necessary contents for a release.
Included should be documentation, binaries, and necessary game
files.
'''
import os
from pathlib import Path # TODO: switch over from os.
import sys
import zipfile
import argparse

import Make_Documentation
import Make_Executable
#import Make_Patches

parent_dir = Path(__file__).resolve().parent.parent
if str(parent_dir) not in sys.path:
    sys.path.append(str(parent_dir))
import Framework

This_dir = os.path.join(os.path.dirname(__file__))
Top_dir = os.path.normpath(os.path.join(This_dir, '..'))

def Make(*args):    
    # Set up command line arguments.
    argparser = argparse.ArgumentParser(
        description='Prepare a release of this project, zipping the'
                    ' necessary files.',
        )
            
    argparser.add_argument(
        '-refresh', 
        action='store_true',
        help = 'Automatically call Make_Documentation and Make_Executable.')
    
    argparser.add_argument(
        '-uncompress', 
        action='store_true',
        help = 'Leaves the output zip file uncompressed.')

    #argparser.add_argument(
    #    '-doc_refresh', 
    #    action='store_true',
    #    help = 'Regenerates documentation files before release.')
    #
    #argparser.add_argument(
    #    '-exe_refresh', 
    #    action='store_true',
    #    help = 'Regenerates executable and support files before release.')
    
    #argparser.add_argument(
    #    '-patch_refresh', 
    #    action='store_true',
    #    help = 'Regenerates patch files before release. This should be'
    #           ' rarely needed.')
        
    # Run the parser on the input args.
    # Split off the remainder, mostly to make it easy to run this
    # in VS when its default args are still set for Main.
    parsed_args, remainder = argparser.parse_known_args(args)


    # Update the documentation and binary and patches.
    if parsed_args.refresh:
        print('Refreshing documentation.')
        Make_Documentation.Make()
        print('Refreshing executable.')
        Make_Executable.Make()

    #if parsed_args.patch_refresh:
    #    print('Refreshing patches.')
    #    Make_Patches.Make()

    # Get a list of all file paths to add to the release.
    # These will be absolute paths.
    file_paths = []

    # Check the top dir.
    wanted_top_names = (
        'Cat_Pack.bat',
        'Cat_Unpack.bat',
        'Check_Extensions.bat',
        'Clean_Script.bat',
        'Run_Script.bat',
        'Start_Gui.bat',
        'Documentation.md',
        'README.md',
        'License.txt',
        )
    wanted_script_names = (
        'Authors_Transforms.py',
        'Cat_Pack.py',
        'Cat_Unpack.py',
        'Check_Extensions.py',
        'Example_Transforms.py',
        'Default_Script_template.py',
        )
    for file_name in os.listdir(Top_dir):
        if file_name in wanted_top_names:
            file_paths.append(os.path.join(Top_dir, file_name))

    # Grab everything in bin, game_files, and patches.
    # TODO: look into parsing the git index to know which files are
    #  part of the actual repository, and not leftover work files (like
    #  modified scripts).
    # For now, some hand selected filters will be used.
    for folder in ['bin', 'Scripts', 'Plugins']: #,'game_files','patches'
        for dir_path, _, file_names in os.walk(os.path.join(Top_dir, folder)):

            # Skip the pycache folders.
            if 'pycache' in dir_path:
                continue

            # Check each file name individually.
            for file_name in file_names:

                ## Skip patches that don't end in .patch.
                #if folder == 'patches' and not file_name.endswith('.patch'):
                #    continue
                #
                ## Skip game files that end in .bak, leftovers from
                ##  the script editor.
                #if folder == 'game_files' and file_name.endswith('.bak'):
                #    continue

                # Skip anything in scripts or plugins that isn't .py or .ui.
                if (folder in ['Scripts','Plugins'] 
                and not file_name.endswith('.py')
                and not file_name.endswith('.ui')):
                    continue

                # Pick scripts to include.
                if folder == 'Scripts' and file_name not in wanted_script_names:
                    continue

                file_paths.append(os.path.join(folder, dir_path, file_name))
                
                
    # Create a new zip file.
    # Put this in the top level directory.
    version_name = 'X4_Customizer_v{}'.format(Framework.Change_Log.Get_Version())
    zip_path = os.path.normpath(os.path.join(This_dir, '..', version_name + '.zip'))
    # Optionally open it with compression.
    if parsed_args.uncompress:
        zip_file = zipfile.ZipFile(zip_path, 'w')
    else:
        zip_file = zipfile.ZipFile(
            zip_path, 'w',
            # Can try out different zip algorithms, though from a really
            # brief search it seems lzma is the newest and strongest.
            # Result: seems to work well, dropping the ~90M qt version
            # down to ~25M.
            # Note: LZMA is the 7-zip format, not native to windows.
            #compression = zipfile.ZIP_LZMA,
            # Deflate is the most commonly supported format.
            # With max compression, this is ~36M, so still kinda okay.
            compression = zipfile.ZIP_DEFLATED,
            # Compression level only matters for bzip2 and deflated.
            compresslevel = 9 # 9 is max for deflated
            )

    # Add all files to the zip, with an extra nesting folder to
    # that the files don't sprawl out when unpacked.
    for path in file_paths:
        zip_file.write(
            # Give a full path.
            path,
            # Give an alternate internal path and name.
            # This will be relative to the top dir.
            # Note: relpath seems to bugger up if the directories match,
            #  returning a blank instead of the file name.
            arcname = os.path.join(version_name, os.path.relpath(path, Top_dir))
            )

    # Close the zip; this needs to be explicit, according to the
    #  documenation.
    zip_file.close()

    print('Release written to {}'.format(zip_path))

if __name__ == '__main__':
    # Feed all args except the first (which is the file name).
    Make(*sys.argv[1:])
