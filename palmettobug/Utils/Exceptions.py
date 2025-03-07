'''
This module contains any special exceptions to be used in the PalmettoBUG program

Like the rest of PalmettoBUG, this code is licensed under the GPL-3 open source license.

'''

__all__ = []

class NoSharedFilesError(Exception):
    '''
    This Error occurs when searching through two parallel directories, which are expected to have matching filenames in each directory,
    but the two directories do not shared any common filenames
    '''