# PalmettoBUG -- Python3.10

## This Branch is for a version of PalmettoBUG that has extremely restrictive / strictly defined dependencies in Python 3.10

Goal: That this will be a an especially stable / easy to install version of the program, by minimizing the risk of dependency errors. HOWEVER -- this also
means that this version of the program will not receive updates, bugfixes, or security maintenance for its dependencies!

As the main branch of the program is updated / new features are added, I *might* update this branch and re-release with the added features, but such updates are not expected to be frequently (once this branch is setup, more effort will go into the main development branch which is intended to be kept more up-to-date with versions of python / dependencies, etc.)

As an additional consequence, the documentation, notebooks, environments, etc. associated with the main branch of PalmettoBUG are removed here.

## Installation

Once this branch is completed & released, run: 

    pip install palmettobug==0.1.2.dev310

Future version number for this branch will follow the convention 0.1.x.dev310, unless there is a truly major update to the program that I propagate to this branch.

Or copy this repository locally, navigate to the repository directory (the folder where pyproject.toml lives) then run:

    pip install .

## Licenses, acknowledgements, etc.
See the main branch for details like these, although for license information specifically you can also look at the LICENSE.txt file & Other_License_Details.txt file 
in this branch of the repository for more information. 
