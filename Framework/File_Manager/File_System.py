
    
from pathlib import Path
import datetime

from .Source_Reader import Source_Reader_class
from .Cat_Writer import Cat_Writer
from .File_Types import Misc_File, XML_File
from ..Common import Settings
from ..Common import File_Missing_Exception
from ..Common import Customizer_Log_class
from ..Common import Change_Log
from ..Common import framework_path
from lxml import etree as ET


class File_System_class:
    '''
    Primary handler for all loaded files, including both read
    and write functionality.

    Attributes:
    * game_file_dict
      - Dict, keyed by virtual path, holding loaded Game_File objects.
    * old_log
      - Customizer_Log_class holding information from the prior
        customizer run.
    * init_complete
      - Bool, set True after the delayed init function has completed.
    * source_reader
      - Source_Reader object.
    '''
    def __init__(self):
        self.game_file_dict = {}
        self.old_log = Customizer_Log_class()
        self.init_complete = False
        self.source_reader = Source_Reader_class()
        return


    def Delayed_Init(self):
        '''
        Initialize the file system and finalize Settings paths.
        '''
        # Skip early if already initialized.
        if self.init_complete:
            return
        self.init_complete = True

        # Make sure the settings are fully initialized at this point.
        # They normally are through a transform call, but may not be
        # if a file was loaded from outside a transform.
        Settings.Delayed_Init()

        # Read any old log file.
        self.old_log.Load(Settings.Get_Customizer_Log_Path())

        # Initialize the source reader, now that paths are set in settings.
        self.source_reader.Init_From_Settings()    
        return


    def Add_File(self, game_file):
        '''
        Record a new a Game_File object, keyed by its virtual path.
        '''
        self.game_file_dict[game_file.virtual_path] = game_file


    def Load_File(self,
                  file_name,
                  # TODO: rename this to be more generic.
                  return_game_file = False, 
                  return_text = False,
                  error_if_not_found = True):
        '''
        Returns a Game_File subclass object for the given file, according
        to its extension.
        If the file has not been loaded yet, reads from the expected
        source file.

        * file_name
          - Name of the file, using the cat_path style (forward slashes,
            no 'addon' folder).
          - For the special text override file to go in the addon/t folder,
            use 'text_override', which will be translated to the correct
            name according to Settings.
        * error_if_not_found
          - Bool, if True and the file is not found, raises an exception,
            else returns None.
        '''
        # Verify Init was called.
        self.Delayed_Init()

        # If the file is not loaded, handle loading.
        if file_name not in self.game_file_dict:

            # Get the file using the source_reader, maybe pulling from
            #  a cat/dat pair.
            # Returns a Game_File object, of some subclass, or None
            #  if not found.
            game_file = self.source_reader.Read(file_name, error_if_not_found = False)

            # Problem if the file isn't found.
            if game_file == None:
                if error_if_not_found:
                    raise File_Missing_Exception(
                        'Could not find file {}, or file was empty'.format(file_name))
                return None
        
            # Store the contents in the game_file_dict.
            self.Add_File(game_file)

        # Return the file contents.
        return self.game_file_dict[file_name]

          
    def Cleanup(self):
        '''
        Handles cleanup of old transform files.
        This is done blindly for now, regardless of it this run intends
         to follow up by applying another renaming and writing new files
         in place of the ones removed.
        This should preceed a call to any call to Write_Files, though can
         be run standalone to do a generic cleaning.
        Preferably do this late in a run, so that files from a prior run
         are not removed if the new run had an error during a transform.
        '''
        # It is possible Init was never run if no transforms were provided.
        # Ensure it gets run here in such cases.
        self.Delayed_Init()

        print('Cleaning up old files')

        # TODO: maybe just completely delete the extension/customizer contents,
        # though that would mess with logs and messages that have been written
        # to up to this point.
        # It is cleaner other than that, though. Maybe manually skip the logs
        # or somesuch.

        # Find all files generated on a prior run, that still appear to be
        #  from that run (eg. were not changed externally), and remove
        #  them.
        for path in self.old_log.Get_File_Paths_From_Last_Run():
            if path.exists():
                path.unlink()            
        return
            

    def Add_Source_Folder_Copies(self):
        '''
        Adds Misc_File objects which copy files from the user source
        folders to the game folders.
        This should only be called after transforms have been completed,
        to avoid adding a copy of a file that was already loaded and
        edited.
        All source folder files, loaded here or earlier, will be flagged
        as modified.
        '''
        # Some loose files may be present in the user source folder which
        #  are intended to be moved into the main folders, whether transformed
        #  or not, in keeping with behavior of older versions of the customizer.
        # These will do direct copies.
        for virtual_path, sys_path in self.source_reader.Get_All_Loose_Source_Files().items():
            # TODO:
            # Skip files which do not match anything in the game cat files,
            #  to avoid copying any misc stuff (backed up files, notes, etc.).
            # This will need a function created to search cat files without
            #  loading from them.

            # Check for files not loaded yet.
            if virtual_path not in self.game_file_dict:
                # Read the binary.
                with open(sys_path, 'rb') as file:
                    binary = file.read()

                # Create the game file.
                self.Add_File(Misc_File(binary = binary, 
                                   virtual_path = virtual_path))

            # Set as modified to force writeout.
            self.game_file_dict['virtual_path'].modified = True
        return

                
    def Write_Files(self):
        '''
        Write output files for all source file content used or
         created by transforms, either to loose files or to a catalog
         depending on settings.
        Existing files which may conflict with the new writes will be renamed,
         including files of the same name as well as their .pck versions.
        '''
        print('Writing output files')# to {}'.format(Settings.Get_Output_Folder()))

        # Add copies of leftover files from the user source folder.
        # Do this before the proper writeout, so it can reuse functionality.
        self.Add_Source_Folder_Copies()

        # TODO: do a pre-pass on all files to do a test write, then if all
        #  look good, do the actual writes and log updates, to weed out
        #  bugs early.
        # Maybe could do it Clang style with gibberish extensions, then once
        #  all files, written, rename then properly.

        # Record the output folder in the log.
        log = Customizer_Log_class()

        # Pick the path to the catalog folder and file.
        cat_path = Settings.Get_Output_Folder() / 'ext_01.cat'

        # Note: this path may be the same as used in a prior run, but
        #  the prior cat file should have been removed by cleanup.
        assert not cat_path.exists()
        cat_writer = Cat_Writer(cat_path)

        # Set up the content.xml file. -Moved to plugin.
        #self.Make_Extension_Content_XML()

        # Loop over the files that were loaded.
        for file_name, file_object in self.game_file_dict.items():

            # Skip if not modified.
            if not file_object.modified:
                continue

            # In case the target directory doesn't exist, such as on a
            #  first run, make it, but only when not sending to a catalog.
            if not Settings.output_to_catalog:
                # Look up the output path.
                file_path = Settings.Get_Output_Folder() / file_object.virtual_path
        
                folder_path = file_path.parent
                if not folder_path.exists():
                    folder_path.mkdir(parents = True)
                
                # Write out the file, using the object's individual method.
                file_object.Write_File(file_path)

                # Add this to the log, post-write for correct hash.
                log.Record_File_Path_Written(file_path)

                # Refresh the log file, in case a crash happens during file
                #  writes, so this last write was captured.
                log.Store()

            else:
                # Add to the catalog writer.
                cat_writer.Add_File(file_object)


        # If anything was added to the cat_writer, do its write.
        if cat_writer.game_files:
            cat_writer.Write()

            # Log both the cat and dat files as written.
            log.Record_File_Path_Written(cat_writer.cat_path)
            log.Record_File_Path_Written(cat_writer.dat_path)

            # Refresh the log file.
            log.Store()

        return

    def Copy_File(
            self,
            source_virtual_path,
            dest_virtual_path = None
        ):
        '''
        Suport function to copy a file from a source folder under this project, 
        to a dest folder. Typically used for scripts, objects, etc.
        Note: this simply creates a Game_File object, and the file write
        will occur during normal output.

        * source_virtual_path
          - Virtual path for the source file, which matches the folder
            structure in the project source folder.
        * dest_virtual_path
          - Virtual path for the dest location.
          - If None, this defaults to match the source_virtual_path.
        '''
        # Normally, the dest will just match the source.
        if dest_virtual_path == None:
            dest_virtual_path = source_virtual_path

        # Get the path for where to find the source file, and load
        #  its binary.
        # Similar to above, but the folder is located in this project.    
        with open(framework_path / '..' / 'game_files' / virtual_path, 'rb') as file:
            source_binary = file.read()

        # Create a generic game object for this, using the dest path.
        self.Add_File( Misc_File(
            virtual_path = dest_virtual_path, 
            binary = source_binary))

        return


    def Get_Date(self):
        '''
        Returns the current date, as a string.
        '''
        return str(datetime.date.today())
    

    def Get_All_Virtual_Paths(self, pattern = None):
        '''
        Return a list of virtual_path names of all discovered files,
        optionally filtered by a wildcard pattern.

        * pattern
          - String, optional, wildcard pattern to use for matching names.
        '''
        # It is possible Init was never run if no transforms were provided.
        # Ensure it gets run here in such cases.
        self.Delayed_Init()

        # Pass the call to the source reader.
        return self.source_reader.Get_All_Virtual_Paths(pattern)
    

# Static copy of the file system object.
File_System = File_System_class()